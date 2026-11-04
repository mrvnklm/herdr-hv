"""Moving from herdr-space-tags: rules, order and assignments carry over, old tokens go away.

Needs herdr-space-tags installed on the real herdr (its plugin root is linked into the test
server); the test is skipped otherwise.
"""
import json
import os
import subprocess
import sys
import time

from harness import (Client, HOME, REPO, finish, herdr, herdr_raw, hv, labels, ok, prepare, snap,
                     wait, wid)

real = json.loads(subprocess.run(["herdr", "plugin", "list", "--json"], capture_output=True,
                                 text=True).stdout or "{}").get("result", {}).get("plugins", [])
space_tags = next((p["plugin_root"] for p in real if p["plugin_id"] == "herdr-space-tags"), None)
if not space_tags:
    print("SKIP herdr-space-tags is not installed")
    sys.exit(0)


def tokens(label):
    return set(next(w for w in snap()["workspaces"] if w["label"] == label).get("tokens") or {})


prepare()
client = Client()
herdr_raw("plugin", "link", space_tags)
for name in ("p-a", "p-b", "p-c"):
    herdr("workspace", "create", "--label", name, "--cwd", f"{HOME}/{name}", "--no-focus")
time.sleep(1)
source = herdr_raw("plugin", "config-dir", "herdr-space-tags").stdout.strip()
os.makedirs(source, exist_ok=True)
with open(f"{source}/config.toml", "w") as fh:
    fh.write('order = ["X", "Y"]\nband = "first"\n\n[[rule]]\ntag = "Y"\ncwds = ["*/p-b"]\n')
with open(f"{source}/manual.tsv", "w") as fh:
    fh.write(f"# workspace_id\ttag\tcwd\tlabel\n{wid('p-a')}\tX\t{HOME}/p-a\tp-a\n"
             f"{wid('p-c')}\t\t{HOME}/p-c\tp-c\n")
herdr_raw("plugin", "action", "invoke", "herdr-space-tags.apply")
ok("setup: space-tags has set its tokens", wait(lambda: "tag" in tokens("p-a")), snap()["workspaces"])

result = hv("import-space-tags")
print(result.stdout.strip(), result.stderr.strip()[-300:])
target = herdr_raw("plugin", "config-dir", "hv").stdout.strip()
with open(f"{target}/groups.json") as fh:
    data = json.load(fh)
ok("import: order, rule and assignments",
   data["order"] == ["X", "Y"] and data["rules"] == [{"tag": "Y", "labels": [], "cwds": ["*/p-b"]}]
   and data["members"][wid("p-a")]["tag"] == "X" and data["members"][wid("p-c")]["tag"] == "", data)
ok("import: old tokens removed", not ({"tag", "pad", "air"} & (tokens("p-a") | tokens("p-b") | tokens("p-c"))))
again = hv("import-space-tags")
ok("import does not overwrite without --force", again.returncode != 0 and "exists" in again.stderr + again.stdout)

herdr_raw("plugin", "disable", "herdr-space-tags")
herdr_raw("plugin", "unlink", "herdr-space-tags")
herdr_raw("plugin", "link", REPO)
time.sleep(1)
hv("group-sync")
time.sleep(1.5)
order = labels()
ok("groups stand: X with p-a, Y with p-b (rule), p-c outside",
   order.index("▦ X") < order.index("p-a") < order.index("▦ Y") < order.index("p-b")
   and order.index("p-c") > order.index("p-b") and order[-1] == "+ New space", order)

# close p-a and open it again: it finds its group by its folder
herdr_raw("workspace", "close", wid("p-a"))
time.sleep(2)
herdr("workspace", "create", "--label", "p-a", "--cwd", f"{HOME}/p-a", "--no-focus")
time.sleep(3)
order = labels()
ok("a reopened space finds its group", order.index("▦ X") < order.index("p-a") < order.index("▦ Y"), order)
finish(client)
