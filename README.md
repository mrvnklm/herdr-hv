# hv — agents side by side, groups in the sidebar

A plugin for [herdr](https://herdr.dev). It does two things, both with the mouse:

- **Views:** pick agent panes from any workspace and put them side by side in one place.
  Send them back later; every agent returns to the workspace it came from.
- **Sidebar groups:** a `▦ name` row in the spaces sidebar is a group header. Drag spaces under
  it. Click the header and all agents of that group show up side by side. Click any other space
  and they go home again.

hv only moves panes. It never closes or restarts an agent.

## Install

```sh
herdr plugin install mrvnklm/herdr-hv
```

Requirements: herdr 0.9 or newer, Python 3.9 or newer, [fzf](https://github.com/junegunn/fzf)
0.45 or newer. macOS and Linux.

Optional, for the `hv` command in your shell:

```sh
ln -s "$(herdr plugin list --json | python3 -c 'import json,sys; print(next(p["plugin_root"] for p in json.load(sys.stdin)["result"]["plugins"] if p["plugin_id"]=="hv"))')/hv" ~/.local/bin/hv
```

Recommended sidebar rows in `~/.config/herdr/config.toml`: bold group headers and a blank line
between groups (hv sets the `$gap` token on the last space of each group).

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", { token = "workspace", rules = [{ contains = "▦", bold = true }] }, { token = "branch", dim = true }, "git_status"],
  [{ token = "$gap" }],
]
```

## Sidebar groups

| You do | hv does |
|---|---|
| Name a space `#clients` | It becomes the header `▦ clients` of a new group |
| Drag a space under a header | The space joins that group |
| Drag a space onto `+ New space` | The space leaves its group |
| Drag a header | The whole group moves; the order is what you see, never alphabetical |
| Click a header | The group's agents open side by side inside the header (up to 9, grid from 4) |
| Click any other space | Agents that came from that space go home; other open groups stay open (a second window may show them) |
| Rename a header | Members and position move along; a missing `▦ ` is put back |
| Close a header | The group dissolves; its spaces stay |
| Click `+ New space` | A popup: double-click a folder, or type a name and press Enter |

While a group is open, each emptied space keeps a placeholder shell (`hv stub`), so it stays in
the sidebar. The placeholder closes when its agent comes back, unless something runs in it.

Groups live in `$(herdr plugin config-dir hv)/groups.json`, one file per herdr server:

```json
{
  "order": ["clients", "ops"],
  "rules": [{ "tag": "ops", "labels": ["infra-*"], "cwds": ["~/work/ops*"] }],
  "members": { "w4R": { "tag": "clients", "cwd": "/Users/me/acme", "label": "acme" } }
}
```

`members` is written by dragging. An entry with an empty `tag` keeps the rules off that space.
`rules` are optional and edited by hand: glob on the space name (case-insensitive) or on its
working directory. A space that is closed and opened again finds its group by folder, then
by name.

## Views from the command line

| Command | |
|---|---|
| `hv` | Pick panes with fzf (click marks, double-click builds), build a view |
| `hv <pane-id>…` | Same without the picker |
| `hv add`, `hv eq` | Add panes to the focused view; make its columns equal again |
| `hv back [view] [pane-id…]` | Send panes home (all of the view without arguments) |
| `hv group [name]` | Open a group as a view |
| `hv group-sync` | Create missing headers and the button, sort the sidebar |
| `hv panel` | A pane that keeps offering the picker; mouse only |
| `-m <machine>` · `-n` · `-c` | Another herdr server · dry run · always columns |

Where each pane came from is stored by its terminal id, which survives every move.

## Coming from herdr-space-tags

```sh
hv import-space-tags          # copies order, rules and assignments; needs Python 3.11+
herdr plugin disable herdr-space-tags
hv group-sync
```

Both plugins sort the sidebar, so do not run them side by side.

## Limits

- One herdr server per call. Groups across machines do not exist.
- A pane can only be in one place: clicking a space whose agent is shown in an open group in
  another window brings it home there too.

## Development

```sh
python3 -m unittest discover -s tests -p 'test_unit.py'   # no herdr needed
python3 scripts/check_english.py                          # code and docs stay English
pip install pyte && tests/e2e/run_all.sh                  # private herdr server, real mouse events
```

The end-to-end tests start their own herdr server under `/tmp/hv-e2e` and never touch the one
you work in. `git config core.hooksPath .githooks` enables the pre-commit check.

## License

MIT
