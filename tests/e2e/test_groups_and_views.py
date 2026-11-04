"""Groups with real (fake) agents: drag into groups, open a group in its header, send home.

The hard rule under test: hv moves panes and never closes anything that runs.
"""
import os
import time

from harness import (Client, HOME, agents, finish, herdr, herdr_raw, hook_errors, hv, labels,
                     link_plugin, members, ok, panes_of, prepare, rows, run_in, snap, wait, wid)

prepare()
client = Client()
link_plugin()
hv("group-sync")  # creates the "+ New space" button
for name in ("p-a", "p-b", "p-c", "p-d"):
    herdr("workspace", "create", "--label", name, "--cwd", f"{HOME}/{name}", "--no-focus")
    run_in(panes_of(name)[0]["pane_id"], "claude 100000")
second = herdr("pane", "split", panes_of("p-d")[0]["pane_id"], "--direction", "right",
               "--no-focus")["result"]["pane"]["pane_id"]
run_in(second, "claude 100000")
ok("5 fake agents detected", wait(lambda: len(agents()) == 5, 15), rows())

herdr("workspace", "create", "--label", "#G1", "--cwd", HOME, "--no-focus")
time.sleep(1.5)
for name in ("p-a", "p-b", "p-c", "p-d"):
    x, y = client.find(name)
    _, target = client.find("▦ G1")
    client.drag((x, y), (x, target))
    time.sleep(2.5)

# an empty group directly below a full one: dropping onto its name lands inside it
herdr("workspace", "create", "--label", "p-e", "--cwd", f"{HOME}/p-d", "--no-focus")
time.sleep(0.5)
herdr("workspace", "create", "--label", "#Z0", "--cwd", HOME, "--no-focus")
time.sleep(1.5)
ok("empty group Z0 below G1", labels().index("▦ Z0") > labels().index("▦ G1"), labels())
x, y = client.find("p-e")
_, target = client.find("▦ Z0")
client.drag((x, y), (x, target))
time.sleep(2.5)
order = labels()
ok("drop onto empty Z0 lands in Z0",
   order.index("p-e") == order.index("▦ Z0") + 1 and members().get(wid("p-e")) == "Z0", (order, members()))
x, y = client.find("p-e")
_, target = client.find("+ New space")
client.drag((x, y), (x, target))
time.sleep(2.5)
ok("dragging onto the button takes a space out of its group",
   not members().get(wid("p-e")) and labels()[-1] == "+ New space", (labels(), members()))
ok("dragging onto the button opens no popup", "new-space" not in str(herdr("pane", "list")))
herdr("workspace", "close", wid("p-e"))
herdr("workspace", "close", wid("▦ Z0"))
time.sleep(1.5)

order = labels()
ok("4 spaces in G1", order[0] == "▦ G1" and set(order[1:5]) == {"p-a", "p-b", "p-c", "p-d"}, order)
base = agents()
ids = {name: wid(name) for name in ("p-a", "p-b", "p-c", "p-d")}
head = wid("▦ G1")


def in_header(label="▦ G1"):
    return sum(1 for p in panes_of(label) if p.get("agent"))


x, y = client.find("▦ G1")
client.click(x, y)
ok("click on header: 5 agents side by side in it", wait(lambda: in_header() == 5, 12), rows())
time.sleep(1)
ok("every space stays in the sidebar, also the one with two agents", all(n in labels() for n in ids), labels())
ok("no view: row", "view:G1" not in labels())
ok("agents unchanged", agents() == base)
client.click(x, y)
time.sleep(2)
ok("second click on the header changes nothing", in_header() == 5)
client.click(*client.find(os.path.basename(HOME)))  # the server's first space, not in any group
time.sleep(2.5)
ok("a click on an unrelated space leaves the open group open (second window)", in_header() == 5, rows())

# a renamed origin gets its agent back, not a new space of the same name
herdr("workspace", "rename", ids["p-a"], "p-a2")
herdr("workspace", "create", "--label", "p-a", "--cwd", f"{HOME}/p-a", "--no-focus")
time.sleep(1)
client.click(*client.find("p-d"))
ok("renamed space gets its own agent back, not the new one of the same name",
   wait(lambda: any(p.get("agent") for p in snap()["panes"] if p["pane_id"].startswith(ids["p-a"] + ":"))
        and not any(p.get("agent") for p in panes_of("p-a")), 12), rows())
herdr("workspace", "close", wid("p-a"))
herdr("workspace", "rename", ids["p-a"], "p-a")
time.sleep(1.5)
ok("click on p-d: both its agents are back", wait(lambda: sum(1 for p in panes_of("p-d") if p.get("agent")) == 2, 12), rows())
time.sleep(1.5)
ok("header empty again, one pane", len(panes_of("▦ G1")) == 1 and not panes_of("▦ G1")[0].get("agent"))
ok("placeholders gone", not any(p.get("label") == "hv stub" for p in snap()["panes"]))
ok("space ids unchanged", ids == {n: wid(n) for n in ids} and head == wid("▦ G1"), ids)
ok("agents unchanged", agents() == base)

# quick double switch: a click while a run is still busy
client.click(*client.find("▦ G1"))
time.sleep(0.3)
client.click(*client.find("p-a"))
ok("a fast switch ends cleanly on p-a",
   wait(lambda: len(panes_of("▦ G1")) == 1 and any(p.get("agent") for p in panes_of("p-a")), 20), rows())
time.sleep(1.5)
ok("nothing left behind", not any(p.get("label") == "hv stub" for p in snap()["panes"]) and agents() == base, rows())

# an open header renamed without its marker stays a header, and its agents still go home
client.click(*client.find("▦ G1"))
wait(lambda: in_header() == 5, 12)
herdr("workspace", "rename", head, "G9")
ok("header renamed without the marker stays a header", wait(lambda: "▦ G9" in labels(), 8) and "G9" not in labels(), labels())
ok("members move to the renamed group", wait(lambda: list(members().values()).count("G9") == 5, 5), members())
client.click(*client.find("p-a"))
ok("a click brings the agents home from the renamed header",
   wait(lambda: sum(1 for p in panes_of("p-d") if p.get("agent")) == 2 and in_header("▦ G9") == 0, 15), rows())
herdr("workspace", "rename", head, "▦ G1")
wait(lambda: "▦ G1" in labels(), 8)
time.sleep(1.5)

# a placeholder that runs something (an editor, a dev server) must survive the way home
client.click(*client.find("▦ G1"))
wait(lambda: in_header() == 5, 12)
time.sleep(1)
stub = next((p for p in snap()["panes"] if p.get("label") == "hv stub"), None)
if stub:
    run_in(stub["pane_id"], "sleep 100000")
    time.sleep(1.5)
client.click(*client.find("p-b"))
wait(lambda: in_header() == 0, 15)
time.sleep(2)
ok("placeholder with a running process stays open",
   bool(stub) and any(p["terminal_id"] == stub["terminal_id"] for p in snap()["panes"]), rows())
ok("all agents still made it home", agents() == base and in_header() == 0, rows())
if stub:
    pane = next(p for p in snap()["panes"] if p["terminal_id"] == stub["terminal_id"])
    herdr_raw("pane", "close", pane["pane_id"])
    time.sleep(1)

# an agent started inside the header stays there and no shells pile up
run_in(panes_of("▦ G1")[0]["pane_id"], "claude 100000")
wait(lambda: panes_of("▦ G1")[0].get("agent"), 10)
client.click(*client.find("p-b"))
time.sleep(2)
client.click(*client.find("p-c"))
time.sleep(2)
ok("an agent started in the header stays, no new shells", len(panes_of("▦ G1")) == 1, rows())

ok("no hook errors", not hook_errors(), hook_errors())
finish(client)
