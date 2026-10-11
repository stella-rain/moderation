"""Checks blocklist.json before it reaches every player (CLAUDE.md, ADR-025).

- Strict JSON (no duplicate keys, no NaN) with exactly the keys `version`, `updated`,
  `blocked_stages`, `blocked_hashes` and `blocked_creators`.
- `version` is a whole number of at least 1; `updated` is a date YYYY-MM-DD, not after today (UTC).
- Every list holds strings, sorted and without duplicates.
- Hashes are 64 lowercase hex digits; stage codes are `owner/repo@stage-id@vN` (ADR-010);
  creators are GitHub logins.
- With `--base` (the file on the base commit): if the content changed, `version` is the base's
  plus 1 and `updated` is not before the base's. A missing or unreadable base is not compared.

Usage: python3 blocklist_check.py [FILE] [--base FILE] [--today YYYY-MM-DD]
Exit status 1 lists every problem, one per line.
"""

import argparse
import datetime
import json
import re
import sys

KEYS = ["version", "updated", "blocked_stages", "blocked_hashes", "blocked_creators"]
LISTS = KEYS[2:]

LOGIN = r"[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}"
REPO = r"(?!\.\.?@)[A-Za-z0-9._-]{1,100}"
STAGE_CODE = re.compile(rf"{LOGIN}/{REPO}@[a-z0-9-]{{1,40}}@v[1-9][0-9]*")
HASH = re.compile(r"[0-9a-f]{64}")
CREATOR = re.compile(LOGIN)
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

ENTRY_RULES = {
    "blocked_stages": (STAGE_CODE, "is not a stage code owner/repo@stage-id@vN"),
    "blocked_hashes": (HASH, "is not 64 lowercase hex digits"),
    "blocked_creators": (CREATOR, "is not a GitHub login"),
}


class DuplicateKey(ValueError):
    pass


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKey(key)
        seen[key] = value
    return seen


def _no_constants(name):
    raise ValueError(name)


def parse(text):
    """The parsed JSON, strictly: duplicate keys and NaN or Infinity raise ValueError."""
    return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)


def parse_date(value):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def is_version(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def check_list(name, items):
    if not isinstance(items, list):
        return [f"`{name}` is not a list"]
    errors = []
    pattern, problem = ENTRY_RULES[name]
    strings = []
    for i, item in enumerate(items):
        if not isinstance(item, str):
            errors.append(f"`{name}[{i}]` is not a string")
            continue
        strings.append(item)
        if not pattern.fullmatch(item):
            errors.append(f"`{name}[{i}]` `{item}` {problem}")
    for prev, item in zip(strings, strings[1:]):
        if item == prev:
            errors.append(f"`{name}` lists `{item}` twice")
        elif item < prev:
            errors.append(f"`{name}` is not sorted: `{item}` comes after `{prev}`")
    return errors


def check_base(data, base_text):
    """Problems with `data` against the base file's text; none if the base is unreadable."""
    try:
        base = parse(base_text)
    except ValueError:
        return []
    if not isinstance(base, dict) or not is_version(base.get("version")) or base == data:
        return []
    errors = []
    expected = base["version"] + 1
    if is_version(data["version"]) and data["version"] != expected:
        errors.append(f"`version` is {data['version']}; blocklist.json changed, "
                      f"so it must be {expected}")
    new_date, base_date = parse_date(data["updated"]), parse_date(base.get("updated"))
    if new_date and base_date and new_date < base_date:
        errors.append(f"`updated` {new_date} is before the base's {base_date}")
    return errors


def check(text, base_text, today):
    """Every problem with blocklist.json's text, given the base's text (or None) and today."""
    try:
        data = parse(text)
    except DuplicateKey as e:
        return [f"duplicate key `{e}`"]
    except ValueError as e:
        return [f"not valid JSON: {e}"]
    if not isinstance(data, dict):
        return ["the top level is not a JSON object"]

    errors = [f"missing key `{k}`" for k in KEYS if k not in data]
    errors += [f"unknown key `{k}`" for k in data if k not in KEYS]
    if errors:
        return errors

    if not is_version(data["version"]):
        errors.append("`version` is not a whole number of at least 1")
    updated = parse_date(data["updated"])
    if updated is None:
        errors.append("`updated` is not a date YYYY-MM-DD")
    elif updated > today:
        errors.append(f"`updated` {updated} is after today ({today}, UTC)")
    for name in LISTS:
        errors += check_list(name, data[name])
    if base_text is not None:
        errors += check_base(data, base_text)
    return errors


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", nargs="?", default="blocklist.json")
    parser.add_argument("--base", help="blocklist.json on the base commit, if it exists")
    parser.add_argument("--today", type=datetime.date.fromisoformat,
                        default=datetime.datetime.now(datetime.timezone.utc).date())
    args = parser.parse_args(argv)
    base_text = None
    if args.base:
        try:
            base_text = read(args.base)
        except FileNotFoundError:
            print(f"no base file {args.base}; version not compared")
    errors = check(read(args.file), base_text, args.today)
    for e in errors:
        print(e)
    if not errors:
        print("blocklist.json is valid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
