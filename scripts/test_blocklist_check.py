"""Tests for blocklist_check.py. Run: python3 -m unittest discover -s scripts"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import blocklist_check as bc  # noqa: E402

TODAY = datetime.date(2026, 10, 11)
HASH_A = "a" * 64
HASH_B = "0123456789abcdef" * 4


def blocklist(**fields):
    data = {
        "version": 3,
        "updated": "2026-10-10",
        "blocked_stages": [],
        "blocked_hashes": [],
        "blocked_creators": [],
    }
    data.update(fields)
    return data


def text(data):
    return json.dumps(data, indent=2) + "\n"


class Case(unittest.TestCase):
    def errors(self, data, base=None):
        base_text = None if base is None else (base if isinstance(base, str) else text(base))
        new_text = data if isinstance(data, str) else text(data)
        return bc.check(new_text, base_text, TODAY)


class Shape(Case):
    def test_the_real_shape_passes(self):
        self.assertEqual(self.errors(blocklist()), [])

    def test_invalid_json_fails(self):
        self.assertEqual(len(self.errors('{"version": 3,')), 1)
        self.assertIn("not valid JSON", self.errors('{"version": 3,')[0])

    def test_nan_is_not_json(self):
        self.assertIn("not valid JSON", self.errors(text(blocklist()).replace("3", "NaN", 1))[0])

    def test_a_duplicate_key_fails(self):
        doubled = '{"version": 3, "version": 4, "updated": "2026-10-10", "blocked_stages": [],' \
                  ' "blocked_hashes": [], "blocked_creators": []}'
        self.assertEqual(self.errors(doubled), ["duplicate key `version`"])

    def test_not_an_object_fails(self):
        self.assertEqual(self.errors("[]"), ["the top level is not a JSON object"])

    def test_a_missing_key_fails(self):
        data = blocklist()
        del data["blocked_creators"]
        self.assertEqual(self.errors(data), ["missing key `blocked_creators`"])

    def test_an_unknown_key_fails(self):
        self.assertEqual(self.errors(blocklist(note="x")), ["unknown key `note`"])


class Version(Case):
    def test_a_string_version_fails(self):
        self.assertEqual(self.errors(blocklist(version="3")),
                         ["`version` is not a whole number of at least 1"])

    def test_a_bool_version_fails(self):
        self.assertEqual(self.errors(blocklist(version=True)),
                         ["`version` is not a whole number of at least 1"])

    def test_zero_fails(self):
        self.assertEqual(self.errors(blocklist(version=0)),
                         ["`version` is not a whole number of at least 1"])


class Updated(Case):
    def test_today_passes(self):
        self.assertEqual(self.errors(blocklist(updated="2026-10-11")), [])

    def test_tomorrow_fails(self):
        self.assertEqual(self.errors(blocklist(updated="2026-10-12")),
                         ["`updated` 2026-10-12 is after today (2026-10-11, UTC)"])

    def test_not_a_date_fails(self):
        for bad in ["2026-10-32", "2026-1-01", "20261011", "", 20261011]:
            with self.subTest(bad=bad):
                self.assertEqual(self.errors(blocklist(updated=bad)),
                                 ["`updated` is not a date YYYY-MM-DD"])


class Lists(Case):
    def test_not_a_list_fails(self):
        self.assertEqual(self.errors(blocklist(blocked_creators="spammer")),
                         ["`blocked_creators` is not a list"])

    def test_a_non_string_entry_fails(self):
        self.assertEqual(self.errors(blocklist(blocked_creators=[7])),
                         ["`blocked_creators[0]` is not a string"])

    def test_unsorted_fails(self):
        self.assertEqual(self.errors(blocklist(blocked_creators=["bob", "alice"])),
                         ["`blocked_creators` is not sorted: `alice` comes after `bob`"])

    def test_a_duplicate_fails(self):
        self.assertEqual(self.errors(blocklist(blocked_hashes=[HASH_A, HASH_A])),
                         [f"`blocked_hashes` lists `{HASH_A}` twice"])

    def test_sorted_and_unique_passes(self):
        data = blocklist(
            blocked_stages=["alice/my-stages@bad-stage@v1", "alice/my-stages@bad-stage@v2"],
            blocked_hashes=[HASH_B, HASH_A],
            blocked_creators=["Zed", "alice", "spammer123"],
        )
        self.assertEqual(self.errors(data), [])


class Entries(Case):
    def test_hashes_are_64_lowercase_hex(self):
        for bad in ["A" * 64, "a" * 63, "a" * 65, "g" * 64, " " + "a" * 63]:
            with self.subTest(bad=bad):
                self.assertEqual(self.errors(blocklist(blocked_hashes=[bad])),
                                 [f"`blocked_hashes[0]` `{bad}` is not 64 lowercase hex digits"])

    def test_good_stage_codes_pass(self):
        for good in ["alice/my-stages@bad-stage@v1", "A-1/repo.name_x@a@v10",
                     "a/b@" + "x" * 40 + "@v999"]:
            with self.subTest(good=good):
                self.assertEqual(self.errors(blocklist(blocked_stages=[good])), [])

    def test_bad_stage_codes_fail(self):
        for bad in [
            "alice/my-stages@bad-stage",          # no version
            "alice/my-stages@bad-stage@v0",       # versions start at 1
            "alice/my-stages@bad-stage@v01",      # leading zero
            "alice/my-stages@Bad-Stage@v1",       # stage IDs are lowercase slugs
            "alice/my-stages@" + "x" * 41 + "@v1",  # stage IDs are at most 40 characters
            "alice@bad-stage@v1",                 # no repository
            "-alice/my-stages@bad-stage@v1",      # owner starts with a hyphen
            "al--ice/my-stages@bad-stage@v1",     # owner has a double hyphen
            "a" * 40 + "/r@s@v1",                 # owner longer than 39
            "alice/..@bad-stage@v1",              # repository `..`
            "alice/my stages@bad-stage@v1",       # space
        ]:
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.errors(blocklist(blocked_stages=[bad])),
                    [f"`blocked_stages[0]` `{bad}` is not a stage code owner/repo@stage-id@vN"])

    def test_creators_are_github_logins(self):
        for bad in ["-spammer", "spammer-", "spam--mer", "spam_mer", "a" * 40, "", "x/y"]:
            with self.subTest(bad=bad):
                self.assertEqual(self.errors(blocklist(blocked_creators=[bad])),
                                 [f"`blocked_creators[0]` `{bad}` is not a GitHub login"])


class AgainstBase(Case):
    def test_unchanged_needs_no_bump(self):
        self.assertEqual(self.errors(blocklist(), base=blocklist()), [])

    def test_formatting_only_needs_no_bump(self):
        self.assertEqual(self.errors(text(blocklist()), base=json.dumps(blocklist())), [])

    def test_a_change_with_a_bump_passes(self):
        new = blocklist(version=4, updated="2026-10-11", blocked_creators=["spammer123"])
        self.assertEqual(self.errors(new, base=blocklist()), [])

    def test_a_change_without_a_bump_fails(self):
        new = blocklist(blocked_creators=["spammer123"])
        self.assertEqual(self.errors(new, base=blocklist()),
                         ["`version` is 3; blocklist.json changed, so it must be 4"])

    def test_a_bump_by_two_fails(self):
        new = blocklist(version=5, blocked_creators=["spammer123"])
        self.assertEqual(self.errors(new, base=blocklist()),
                         ["`version` is 5; blocklist.json changed, so it must be 4"])

    def test_a_bump_alone_is_a_change(self):
        self.assertEqual(self.errors(blocklist(version=4), base=blocklist()), [])

    def test_updated_may_not_go_back(self):
        new = blocklist(version=4, updated="2026-10-09")
        self.assertEqual(self.errors(new, base=blocklist()),
                         ["`updated` 2026-10-09 is before the base's 2026-10-10"])

    def test_an_unreadable_base_skips_the_comparison(self):
        self.assertEqual(self.errors(blocklist(blocked_creators=["x"]), base="{"), [])
        self.assertEqual(self.errors(blocklist(blocked_creators=["x"]), base="[]"), [])

    def test_a_base_without_a_usable_version_skips_the_comparison(self):
        base = blocklist(version="2")
        self.assertEqual(self.errors(blocklist(blocked_creators=["x"]), base=base), [])


class CommandLine(unittest.TestCase):
    SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocklist_check.py")

    def run_script(self, new, base=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "blocklist.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text(new))
            args = [sys.executable, self.SCRIPT, path, "--today", "2026-10-11"]
            if base is not None:
                base_path = os.path.join(tmp, "base.json")
                with open(base_path, "w", encoding="utf-8") as f:
                    f.write(text(base))
                args += ["--base", base_path]
            return subprocess.run(args, capture_output=True, text=True)

    def test_a_valid_file_exits_0(self):
        result = self.run_script(blocklist())
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "blocklist.json is valid\n")

    def test_problems_exit_1_one_per_line(self):
        result = self.run_script(blocklist(version=0, blocked_creators=["b", "a"]))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines(), [
            "`version` is not a whole number of at least 1",
            "`blocked_creators` is not sorted: `a` comes after `b`",
        ])

    def test_the_base_is_compared(self):
        result = self.run_script(blocklist(blocked_creators=["x"]), base=blocklist())
        self.assertEqual(result.returncode, 1)

    def test_a_missing_base_file_is_no_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "blocklist.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text(blocklist()))
            result = subprocess.run(
                [sys.executable, self.SCRIPT, path, "--base", os.path.join(tmp, "none.json")],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
