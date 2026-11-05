"""Build the README screenshot from a private demo server: made-up projects, fake agents.

Nothing comes from the herdr server you work in: the harness strips every HERDR_* variable
and runs its own server under a throwaway HOME. The result is a JSON dump of the terminal
cells; scripts/render_screen.py turns it into an image.

    HV_E2E_HOME=/tmp/hv-demo python3 scripts/demo_screen.py /tmp/screen.json
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "e2e"))
from harness import (Client, HOME, agents, herdr, herdr_raw, hv, link_plugin,  # noqa: E402
                     panes_of, prepare, run_in, stop, cleanup, wait, wid)

PROJECTS = {  # name: (branch, group, what the fake agent shows)
    "checkout-ui": ("feat/apple-pay", "web", [
        "> add Apple Pay to the checkout form",
        "",
        "  * Reading src/checkout/PaymentForm.tsx",
        "  * Editing PaymentForm.tsx  (+42 -6)",
        "  * Running pnpm test checkout",
        "    31 passed",
        "",
        "  Apple Pay button added behind the",
        "  `applePay` feature flag.",
    ]),
    "marketing-site": ("main", "web", [
        "> pricing table overflows on mobile",
        "",
        "  * Reading app/pricing/Table.vue",
        "  * Editing app/pricing/Table.vue  (+9 -3)",
        "",
        "  Columns now stack below 640px.",
    ]),
    "orders-api": ("fix/retry-webhooks", "backend", [
        "> webhooks fail when the queue is slow",
        "",
        "  * Reading webhooks/handler.go",
        "  * Editing handler.go  (+18 -4)",
        "  * Running go test ./webhooks/...",
        "    ok  0.41s",
        "",
        "  Retries now back off up to 5 times.",
    ]),
    "billing-worker": ("main", "backend", [
        "> why do EU invoices lack VAT?",
        "",
        "  * Searching for vat_rate",
        "  * Reading src/invoice/tax.ts",
        "",
        "  The rate comes from the billing",
        "  country; EU accounts without one",
        "  fall back to 0.",
    ]),
    "search-index": ("feat/synonyms", "backend", [
        "> add synonyms to the product search",
        "",
        "  * Editing synonyms.yaml  (+120)",
        "  * Running make reindex",
        "    indexed 48,210 documents",
    ]),
    "dotfiles": ("main", "", [
        "> tidy up my zsh aliases",
    ]),
}

CONFIG = """onboarding = false
[ui]
sidebar_width = 30
[ui.sidebar.spaces]
row_gap = 0
rows = [
  ["state_icon", { token = "workspace", rules = [{ contains = "▦", bold = true }] }, { token = "branch", dim = true }],
  [{ token = "$gap" }],
]
"""


def git(path, *args):
    subprocess.run(["git", "-C", path, *args], capture_output=True, check=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "HOME": HOME})


def setup():
    prepare()
    for name in ("p-a", "p-b", "p-c", "p-d"):
        os.rmdir(f"{HOME}/{name}")
    with open(f"{HOME}/.config/herdr/config.toml", "w") as fh:
        fh.write(CONFIG)
    with open(f"{HOME}/.zshrc", "w") as fh:  # a neutral prompt: no host or user name
        fh.write("PROMPT='%1~ $ '\nunsetopt PROMPT_SP\n")
    os.makedirs(f"{HOME}/.demo")
    for name, (branch, _, lines) in PROJECTS.items():
        path = f"{HOME}/code/{name}"
        os.makedirs(path)
        git(path, "init", "-q", "-b", branch)
        git(path, "-c", "user.name=demo", "-c", "user.email=demo@example.com",
            "commit", "-q", "--allow-empty", "-m", "init")
        with open(f"{HOME}/.demo/{name}.txt", "w") as fh:
            fh.write("\n".join(lines) + "\n")


def main(out):
    setup()
    client = Client(cols=156, rows=30)
    try:
        link_plugin()
        herdr("workspace", "rename", wid(os.path.basename(HOME)), "scratch")
        directory = herdr_raw("plugin", "config-dir", "hv").stdout.strip()
        os.makedirs(directory, exist_ok=True)
        rules = {}
        for name, (_, group, _) in PROJECTS.items():
            if group:
                rules.setdefault(group, []).append(f"*/code/{name}")
        with open(os.path.join(directory, "groups.json"), "w") as fh:
            json.dump({"order": ["web", "backend"],
                       "rules": [{"tag": t, "cwds": c} for t, c in rules.items()]}, fh)
        for name in PROJECTS:
            herdr("workspace", "create", "--label", name, "--cwd", f"{HOME}/code/{name}", "--no-focus")
            time.sleep(0.6)
            run_in(panes_of(name)[0]["pane_id"], f"clear; cat ~/.demo/{name}.txt; exec claude 100000")
        wait(lambda: len(agents()) == len(PROJECTS), 20)
        hv("group-sync")
        time.sleep(2)
        client.click(*client.find("▦ backend", maxcol=30))
        wait(lambda: sum(1 for p in panes_of("▦ backend") if p.get("agent")) == 3, 15)
        time.sleep(3)
        cells = [[{"c": ch.data, "fg": ch.fg, "bg": ch.bg, "b": ch.bold, "r": ch.reverse}
                  for ch in (client.screen.buffer[y][x] for x in range(client.screen.columns))]
                 for y in range(client.screen.lines)]
        with open(out, "w") as fh:
            json.dump(cells, fh)
        print("\n".join(client.text()))
    finally:
        stop()
        client.close()
        cleanup()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "screen.json")
