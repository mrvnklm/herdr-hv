"""Group order follows the mouse, never the alphabet; the "+ New space" popup."""
import time

from harness import (Client, HOME, finish, herdr, hook_errors, hv, labels, link_plugin, members,
                     ok, prepare, wid)

prepare()
client = Client()
link_plugin()
herdr("workspace", "create", "--label", "+ Neuer Space", "--cwd", HOME, "--no-focus")  # lang-ok
hv("group-sync")
time.sleep(1)
ok("the button of hv < 0.3 is renamed, not doubled",
   labels().count("+ New space") == 1 and "+ Neuer Space" not in labels(), labels())  # lang-ok
for name in ("p-a", "p-b", "p-c", "p-d"):
    herdr("workspace", "create", "--label", name, "--cwd", f"{HOME}/{name}", "--no-focus")
time.sleep(1)
for group in ("#zz", "#mm", "#aa"):
    herdr("workspace", "create", "--label", group, "--cwd", HOME, "--no-focus")
    time.sleep(2)


def headers():
    return [label for label in labels() if label.startswith("▦")]


ok("new groups keep creation order, not alphabetical", headers() == ["▦ zz", "▦ mm", "▦ aa"], labels())
for name, group in (("p-a", "▦ zz"), ("p-b", "▦ mm"), ("p-c", "▦ aa"), ("p-d", "▦ aa")):
    x, y = client.find(name)
    _, target = client.find(group)
    client.drag((x, y), (x, target))
    time.sleep(2.5)
ok("members assigned, groups stay in place", headers() == ["▦ zz", "▦ mm", "▦ aa"], labels())

# drag header aa onto zz (moving up = in front of it)
x, y = client.find("▦ aa")
_, target = client.find("▦ zz")
client.drag((x, y), (x, target))
time.sleep(3)
ok("header dragged to the top stays there", headers() == ["▦ aa", "▦ zz", "▦ mm"], labels())
time.sleep(1)
client.click(*client.find("p-b"))
time.sleep(2)
ok("a click afterwards does not re-sort", headers() == ["▦ aa", "▦ zz", "▦ mm"], labels())

# reorder inside a group: p-c above p-d
x, y = client.find("p-c")
_, target = client.find("▦ aa")
client.drag((x, y), (x, target))
time.sleep(2.5)
order = labels()
ok("space reordered inside its group",
   order.index("p-c") < order.index("p-d") < order.index("▦ zz"), order)

# renaming a header carries members and position
herdr("workspace", "rename", wid("▦ zz"), "▦ yy")
time.sleep(3)
order = labels()
ok("renamed header keeps its place and members",
   headers() == ["▦ aa", "▦ yy", "▦ mm"] and order.index("p-a") == order.index("▦ yy") + 1
   and "zz" not in members().values(), (order, members()))

# popup: a typed name containing "+"
client.click(*client.find("+ New space"))
time.sleep(2.5)
client.send(b"x+y new")
time.sleep(0.8)
client.send(b"\r")
time.sleep(3)
ok("popup: typed name with + becomes a space", "x+y new" in labels(), labels())

# "pa" fuzzily matches the folder p-a; Enter must still create a space called "pa"
count = labels().count("p-a")
client.click(*client.find("+ New space"))
time.sleep(2.5)
client.send(b"pa")
time.sleep(0.8)
client.send(b"\r")
time.sleep(3)
ok("popup: a fuzzy folder match does not swallow the typed name",
   "pa" in labels() and labels().count("p-a") == count, labels())

# a folder by double-click, also after typing to filter
count = labels().count("p-c")
client.click(*client.find("+ New space"))
time.sleep(2.5)
client.send(b"p-c")
time.sleep(0.8)
hit = client.find("p-c", maxcol=150, mincol=46, skip="space>")
client.double_click(*hit)
time.sleep(3)
ok("popup: double-click on a folder creates a space for it", labels().count("p-c") == count + 1, labels())

ok("no hook errors", not hook_errors(), hook_errors())
finish(client)
