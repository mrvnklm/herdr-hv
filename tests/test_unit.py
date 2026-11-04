"""Unit tests for the parts of hv that need no herdr server: group store, ordering, manifest."""
import importlib.machinery
import importlib.util
import json
import os
import re
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("hv", os.path.join(REPO, "hv"))
_spec = importlib.util.spec_from_loader("hv", _loader)
hv = importlib.util.module_from_spec(_spec)
_loader.exec_module(hv)


def space(wid, label="", **extra):
    return {"workspace_id": wid, "label": label or wid, **extra}


class GroupStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = hv.Groups(self.dir.name)
        self.store.regroup = lambda: False  # sorting needs a server; the data logic does not

    def tearDown(self):
        self.dir.cleanup()

    def write(self, data):
        with open(self.store.path, "w") as fh:
            json.dump(data, fh)

    def test_missing_file_means_no_groups(self):
        self.assertEqual(self.store.load_mapping(), [])
        self.assertEqual(self.store.load_config(), hv.GroupConfig([], []))

    def test_manual_entry_wins_and_empty_tag_turns_rules_off(self):
        self.write({"rules": [{"tag": "web", "cwds": ["*/site*"]}],
                    "members": {"w2": {"tag": "ops"}, "w3": {"tag": ""}}})
        spaces = [space("w1"), space("w2"), space("w3")]
        cwds = {"w1": "/x/site-a", "w2": "/x/site-b", "w3": "/x/site-c"}
        self.assertEqual(self.store.resolved_tags(spaces, cwds), {"w1": "web", "w2": "ops", "w3": ""})

    def test_label_rules_ignore_case(self):
        rules = [hv.Rule("crm", ["CRM-*"], [])]
        self.assertEqual(self.store.match_rules("crm-proto", "", rules), "crm")
        self.assertIsNone(self.store.match_rules("billing", "", rules))

    def test_group_order_is_never_alphabetical(self):
        self.assertEqual(self.store.tag_order(["b"], ["z", "a", "b", "", "z"]), ["b", "z", "a"])

    def test_apply_clear_reset(self):
        self.store.apply_tag("w1", "  ops   team ", "/x", "one")
        self.assertEqual(self.store.load_mapping(), [hv.Record("w1", "ops team", "/x", "one")])
        self.store.clear_tag("w1")
        self.assertEqual(self.store.load_mapping()[0].tag, "")
        self.store.reset_tag("w1")
        self.assertEqual(self.store.load_mapping(), [])

    def test_group_name_is_validated(self):
        with self.assertRaises(SystemExit):
            self.store.validate_tag("   ")
        with self.assertRaises(SystemExit):
            self.store.validate_tag("x" * (hv.MAX_TAG + 1))

    def test_retag_moves_every_member(self):
        self.write({"members": {"w1": {"tag": "a"}, "w2": {"tag": "a"}, "w3": {"tag": "b"}}})
        self.store.retag("a", "c")
        self.assertEqual({r.workspace_id: r.tag for r in self.store.load_mapping()},
                         {"w1": "c", "w2": "c", "w3": "b"})

    def test_adopt_by_cwd_then_label(self):
        self.write({"members": {"old1": {"tag": "a", "cwd": "/p/one", "label": "x"},
                                "old2": {"tag": "b", "cwd": "", "label": "two"}}})
        spaces = [space("n1", "renamed"), space("n2", "two")]
        self.assertTrue(self.store.adopt(spaces, {"n1": "/p/one", "n2": "/elsewhere"}))
        self.assertEqual({r.workspace_id: r.tag for r in self.store.load_mapping()}, {"n1": "a", "n2": "b"})

    def test_adopt_matches_headers_by_label_only(self):
        # a header lives in ~ like many spaces: it must not take over a space's entry by cwd
        self.write({"members": {"old": {"tag": "a", "cwd": "/home/u", "label": "proj"}}})
        header = space("h1", hv.HEADER + "b")
        self.assertFalse(self.store.adopt([header], {"h1": "/home/u"}))

    def test_adopt_skips_the_button(self):
        self.write({"members": {"old": {"tag": "a", "cwd": "/home/u", "label": hv.NEW_BUTTON}}})
        self.assertFalse(self.store.adopt([space("b1", hv.NEW_BUTTON)], {"b1": "/home/u"}))

    def test_writes_are_atomic_files(self):
        self.store.apply_tag("w1", "a")
        leftovers = [n for n in os.listdir(self.dir.name) if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])


class LegacyState(unittest.TestCase):
    def test_origins_move_once_from_the_old_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved = hv._STATE_DIR, hv.LEGACY_ORIGINS
            try:
                hv._STATE_DIR = os.path.join(tmp, "config")
                os.makedirs(hv._STATE_DIR)
                hv.LEGACY_ORIGINS = os.path.join(tmp, "hv-origins")
                with open(hv.LEGACY_ORIGINS + ".json", "w") as fh:
                    json.dump({"term_1": {"label": "a"}}, fh)
                self.assertEqual(hv.load_origins(), {"term_1": {"label": "a"}})
                self.assertFalse(os.path.exists(hv.LEGACY_ORIGINS + ".json"))
                self.assertEqual(hv.origins_path(), os.path.join(hv._STATE_DIR, "origins.json"))
            finally:
                hv._STATE_DIR, hv.LEGACY_ORIGINS = saved


class Ordering(unittest.TestCase):
    def test_worktrees_travel_with_their_repo(self):
        spaces = [space("a", worktree={"repo_key": "r", "is_linked_worktree": True}), space("b"),
                  space("c", worktree={"repo_key": "r", "is_linked_worktree": False})]
        units = [[w["workspace_id"] for w in unit] for unit in hv.unit_groups(spaces)]
        self.assertEqual(units, [["c", "a"], ["b"]])

    def test_header_label(self):
        self.assertEqual(hv.header_tag(hv.HEADER + "ops"), "ops")
        self.assertIsNone(hv.header_tag("ops"))


class Manifest(unittest.TestCase):
    def test_every_hook_calls_an_existing_subcommand(self):
        text = open(os.path.join(REPO, "herdr-plugin.toml")).read()
        source = open(os.path.join(REPO, "hv")).read()
        table = re.search(r"table = \{(.*?)\}", source, re.S).group(1)
        known = set(re.findall(r'"([a-z-]+)":', table))
        for sub in re.findall(r'"python3", "hv", "([a-z-]+)"', text):
            self.assertIn(sub, known, sub)


if __name__ == "__main__":
    unittest.main()
