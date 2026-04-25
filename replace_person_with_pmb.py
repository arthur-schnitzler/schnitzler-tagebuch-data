#!/usr/bin/env python3
"""Replace person_NNNN identifiers with their pmb counterparts.

Reads the concordance from indices/person_pmb_concordance.json and rewrites all
files in editions/ as well as indices/index_*.xml. Use --apply to write changes;
without it the script runs as a dry run and only reports what would change.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent
CONCORDANCE = REPO / "indices" / "person_pmb_concordance.json"
PERSON_RE = re.compile(r"person_(\d+)")


def load_mapping() -> dict[str, str]:
    with CONCORDANCE.open(encoding="utf-8") as f:
        return json.load(f)


def target_files() -> list[Path]:
    files = sorted((REPO / "editions").glob("*.xml"))
    files += sorted((REPO / "indices").glob("index_*.xml"))
    return files


def process(text: str, mapping: dict[str, str], unmapped: Counter) -> tuple[str, int]:
    replacements = 0

    def sub(match: re.Match) -> str:
        nonlocal replacements
        key = f"person_{match.group(1)}"
        target = mapping.get(key)
        if target is None:
            unmapped[key] += 1
            return match.group(0)
        replacements += 1
        return target

    return PERSON_RE.sub(sub, text), replacements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    mapping = load_mapping()
    files = target_files()
    unmapped: Counter = Counter()
    total_files_changed = 0
    total_replacements = 0

    for path in files:
        original = path.read_text(encoding="utf-8")
        new_text, count = process(original, mapping, unmapped)
        if count:
            total_files_changed += 1
            total_replacements += count
            if args.apply:
                path.write_text(new_text, encoding="utf-8")

    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] files scanned:        {len(files)}")
    print(f"[{mode}] files with changes:   {total_files_changed}")
    print(f"[{mode}] total replacements:   {total_replacements}")
    print(f"[{mode}] unmapped person_ ids: {len(unmapped)} distinct, {sum(unmapped.values())} occurrences")
    if unmapped:
        print("  top unmapped:")
        for key, n in unmapped.most_common(20):
            print(f"    {key}: {n}")
    if not args.apply:
        print("\n(dry run — re-run with --apply to write changes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
