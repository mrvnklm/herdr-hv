"""End-to-end harness: a private herdr server, a real terminal client and real mouse events.

Each test starts its own herdr server under a throwaway HOME, links this repository as the
hv plugin, and drives the UI through a pyte-rendered pty with SGR mouse sequences. Nothing
touches the herdr server you are working in: every HERDR_* variable is stripped first.

Needs: herdr on PATH (or HERDR_BIN), fzf, python3 with `pyte` (pip install pyte).
"""
import json
import os
import platform
import pty
import fcntl
import select
import shutil
import struct
import subprocess
import termios
import threading
import time

import pyte

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOME = os.environ.get("HV_E2E_HOME", "/tmp/hv-e2e")
HERDR = os.environ.get("HERDR_BIN") or shutil.which("herdr")
HV = os.environ.get("HV_BIN", os.path.join(REPO, "hv"))
RESULTS = {"pass": 0, "fail": 0}

SIDEBAR_CONFIG = """onboarding = false
[ui]
sidebar_width = 40
[ui.sidebar.spaces]
row_gap = 0
rows = [
  ["state_icon", { token = "workspace", rules = [{ contains = "▦", bold = true }] }, { token = "branch", dim = true }, "git_status"],
  [{ token = "$gap" }],
]
"""


def env():
    base = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "CLAUDE", "TMUX"))}
    base.update(HOME=HOME, TERM="xterm-256color", ZDOTDIR=HOME, SHELL="/bin/zsh",
                PATH=f"{HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    return base


def herdr(*args):
    """Run the herdr CLI against the test server; JSON result or {"raw": ...}."""
    p = subprocess.run([f"{HOME}/.local/bin/herdr", *args], capture_output=True, text=True,
                       env=env(), timeout=20)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return {"raw": p.stdout, "err": p.stderr}


def herdr_raw(*args):
    return subprocess.run([f"{HOME}/.local/bin/herdr", *args], capture_output=True, text=True,
                          env=env(), timeout=20)


def hv(*args):
    """Run hv by hand inside the test server, the way a user would from a shell."""
    return subprocess.run([f"{HOME}/.local/bin/hv", *args], capture_output=True, text=True,
                          env={**env(), "HERDR_SOCKET_PATH": f"{HOME}/.config/herdr/herdr.sock"})


def prepare(link=True):
    """Fresh HOME with herdr, hv, a fake `claude` agent and a sidebar config."""
    assert HERDR, "herdr not found: put it on PATH or set HERDR_BIN"
    subprocess.run(["rm", "-rf", HOME])
    os.makedirs(f"{HOME}/.local/bin")
    os.makedirs(f"{HOME}/.config/herdr")
    open(f"{HOME}/.zshrc", "w").close()
    for name in ("p-a", "p-b", "p-c", "p-d"):
        os.makedirs(f"{HOME}/{name}")
    os.symlink(HERDR, f"{HOME}/.local/bin/herdr")
    os.symlink(HV, f"{HOME}/.local/bin/hv")
    # herdr detects agents by process name: a copy of `sleep` called `claude` is enough
    agent = f"{HOME}/.local/bin/claude"
    shutil.copy(shutil.which("sleep"), agent)
    if platform.system() == "Darwin":  # a copied system binary needs a fresh ad-hoc signature
        subprocess.run(["codesign", "-f", "-s", "-", agent], capture_output=True)
    with open(f"{HOME}/.config/herdr/config.toml", "w") as fh:
        fh.write(SIDEBAR_CONFIG)


def link_plugin():
    herdr_raw("plugin", "link", REPO)


def stop():
    subprocess.run([f"{HOME}/.local/bin/herdr", "server", "stop"], capture_output=True,
                   env=env(), timeout=15)


def cleanup():
    subprocess.run(["rm", "-rf", HOME])


class _Screen(pyte.Screen):
    def report_device_status(self, *a, **k):
        pass

    def report_device_attributes(self, *a, **k):
        pass


class Client:
    """herdr's terminal UI in a pty, rendered by pyte; clicks and drags as SGR mouse events."""

    def __init__(self, cols=150, rows=48):
        self.screen = _Screen(cols, rows)
        self.stream = pyte.ByteStream(self.screen)
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(HOME)
            os.execve(f"{HOME}/.local/bin/herdr", ["herdr"], env())
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.alive = True
        threading.Thread(target=self._pump, daemon=True).start()
        time.sleep(2.5)

    def _pump(self):
        while self.alive:
            ready, _, _ = select.select([self.fd], [], [], 0.2)
            if ready:
                try:
                    data = os.read(self.fd, 65536)
                except OSError:
                    return
                if not data:
                    return
                self.stream.feed(data)

    def text(self):
        return list(self.screen.display)

    def show(self, title="", width=46, n=None):
        print(f"--- {title}")
        for i, line in enumerate(self.text()[:n or len(self.text())]):
            if line[:width].strip():
                print(f"{i + 1:2} {line[:width].rstrip()}")

    def find(self, text, maxcol=44, mincol=0, skip=None):
        """(x, y) of `text` on screen, 1-based; the sidebar is the first ~44 columns."""
        for y, line in enumerate(self.text()):
            x = line[:maxcol].find(text, mincol)
            if x >= 0 and not (skip and skip in line):
                return x + 1, y + 1
        raise AssertionError(f"not on screen: {text!r}\n" + "\n".join(l[:60] for l in self.text()))

    def send(self, data):
        os.write(self.fd, data)

    def click(self, x, y, gap=0.05):
        self.send(f"\x1b[<0;{x};{y}M".encode())
        time.sleep(gap)
        self.send(f"\x1b[<0;{x};{y}m".encode())

    def double_click(self, x, y):
        self.click(x, y)
        time.sleep(0.08)
        self.click(x, y)

    def drag(self, a, b):
        self.send(f"\x1b[<0;{a[0]};{a[1]}M".encode())
        time.sleep(0.15)
        step = 1 if b[1] > a[1] else -1
        for y in range(a[1], b[1] + step, step):
            self.send(f"\x1b[<32;{a[0]};{y}M".encode())
            time.sleep(0.04)
        time.sleep(0.1)
        self.send(f"\x1b[<0;{a[0]};{b[1]}m".encode())

    def close(self):
        self.alive = False
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.kill(self.pid, 15)
            os.waitpid(self.pid, 0)
        except OSError:
            pass


# -- state helpers ---------------------------------------------------------------------

def snap():
    return herdr("api", "snapshot")["result"]["snapshot"]


def labels():
    return [w["label"] for w in snap()["workspaces"]]


def wid(label):
    return next(w["workspace_id"] for w in snap()["workspaces"] if w["label"] == label)


def panes_of(label):
    return [p for p in snap()["panes"] if p["pane_id"].startswith(wid(label) + ":")]


def agents():
    return {p["terminal_id"] for p in snap()["panes"] if p.get("agent")}


def run_in(pane_id, command):
    herdr_raw("pane", "run", pane_id, command)


def rows():
    s = snap()
    out = []
    for w in s["workspaces"]:
        ps = [p for p in s["panes"] if p["pane_id"].startswith(w["workspace_id"] + ":")]
        out.append((w["label"], len(ps), sum(1 for p in ps if p.get("agent")), "F" if w["focused"] else ""))
    return out


def members():
    """{workspace_id: group} from hv's groups.json in the test server."""
    directory = herdr_raw("plugin", "config-dir", "hv").stdout.strip()
    try:
        with open(os.path.join(directory, "groups.json")) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    return {k: v.get("tag", "") for k, v in data.get("members", {}).items()}


def wait(fn, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def ok(name, condition, detail=""):
    RESULTS["pass" if condition else "fail"] += 1
    print(("PASS " if condition else "FAIL ") + name, "" if condition else detail)


def hook_errors():
    logs = herdr("plugin", "log", "list").get("result", {}).get("logs", [])
    return [(e.get("event"), e.get("stderr", "")[-300:]) for e in logs
            if e.get("plugin_id") == "hv" and e.get("status") != "running"  # still busy is fine
            and (e.get("status") != "succeeded" or e.get("stderr", "").strip())]


def finish(client):
    for event, err in hook_errors():
        print("HOOK ERROR", event, err)
    stop()
    client.close()
    cleanup()
    print(f"{RESULTS['pass']} passed, {RESULTS['fail']} failed")
    raise SystemExit(1 if RESULTS["fail"] else 0)
