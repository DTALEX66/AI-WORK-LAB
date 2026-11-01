"""Build tests/node-census.json: how many test functions each test file actually declares.

Why this exists rather than being paranoia: during this round a rebuild of `test_v29_top_level_entry.py`
cut the file at the wrong index and dropped 9 of its 12 nodes to 3. The suite reported **green** --
the three survivors all passed. Nothing but `git diff --stat` noticed. A count that nobody pins is a
coverage number that can fall silently, and "the tests pass" then means less than it reads.

The census is deliberately static (`def test_` declarations) instead of collected: it must be cheap
enough to regenerate every round, and it must not need the venv, a workspace database or the two
read-only source repositories. Collected-node drift is a different, already-covered claim -- the
closure receipt records the suite's own counts and now names its failures.

Usage:
  build_test_census.py            write the census
  build_test_census.py --check    compare with the committed census, exit 1 on any change
  build_test_census.py --allow    rewrite even when a file lost nodes (the loss must be intended)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "node-census.json"
PATTERNS = (re.compile(r"^\s*def test_[A-Za-z0-9_]*\s*\(", re.MULTILINE),
            re.compile(r"^\s*def test_[A-Za-z0-9_]*\s*:", re.MULTILINE))
SKIP_DIRS = {".git", ".project-local", ".venv", "__pycache__", "node_modules"}


def census() -> dict:
    """Every declared test under ``tests/`` -- and deliberately nothing else.

    The archive and the packaged resource tree hold byte-verified copies of other repositories'
    test files. Counting them would couple this pin to blobs that must never change, so a history
    edit would light up the census for the wrong reason; the drift this guards is in *our* suite.
    """
    state = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if SKIP_DIRS & set(path.parts):
            continue
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        count = sum(len(pattern.findall(text)) for pattern in PATTERNS)
        state[relative] = {"tests": count,
                           "bytes": path.stat().st_size,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    unified = sum(row["tests"] for name, row in state.items() if name.startswith("tests/unified"))
    legacy = sum(row["tests"] for name, row in state.items() if name.startswith("tests/legacy"))
    return {"schema": "ai-work-lab/test-node-census/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "tests/ only: byte-verified history copies are not counted",
            "observed_from": "static scan of `def test_` declarations under this checkout",
            "files": len(state), "tests": sum(row["tests"] for row in state.values()),
            "unified_tests": unified, "legacy_tests": legacy, "nodes": state}


def _without_stamp(document: dict) -> dict:
    """The census minus its clock: the part that is a claim about the tree."""
    return {key: value for key, value in document.items() if key != "generated_at"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--allow", action="store_true",
                        help="accept a file that lost declared tests; without this the write refuses")
    args = parser.parse_args(argv)
    fresh = census()
    if args.check:
        if not OUT.is_file():
            print(json.dumps({"matches": False, "error": "CENSUS_MISSING", "path": str(OUT)},
                             ensure_ascii=False))
            return 1
        published = json.loads(OUT.read_text(encoding="utf-8"))
        grew, shrank, gone, added, changed = [], [], [], [], []
        before, after = published["nodes"], fresh["nodes"]
        for name, row in sorted(after.items()):
            old = before.get(name)
            if old is None:
                added.append([name, row["tests"]])
            elif row["tests"] < old["tests"]:
                shrank.append([name, old["tests"], row["tests"]])
            elif row["tests"] > old["tests"]:
                grew.append([name, old["tests"], row["tests"]])
            elif row["sha256"] != old["sha256"]:
                changed.append(name)
        for name in sorted(set(before) - set(after)):
            gone.append([name, before[name]["tests"]])
        # a byte change with the same declared count is not drift for this pin: the census guards
        # "did the suite lose coverage", and byte fidelity of every file is already pinned by the
        # closure receipt and the registers -- re-pinning it here would only make this census stale
        # the moment any file is edited for an unrelated reason
        drift = {"added_files": added, "files_that_lost_tests": shrank,
                 "files_that_gained_tests": grew, "deleted_files": gone,
                 "same_count_content_changed_not_a_loss": changed}
        matches = not (added or shrank or grew or gone)
        print(json.dumps({"matches": matches, "tests_published": published["tests"],
                          "tests_now": fresh["tests"], "files_published": published["files"],
                          "files_now": fresh["files"], "drift": drift},
                         ensure_ascii=False, indent=2))
        return 0 if matches else 1
    if OUT.is_file():
        before = json.loads(OUT.read_text(encoding="utf-8"))["nodes"]
        lost = [[name, before[name]["tests"], row["tests"]] for name, row in fresh["nodes"].items()
                if name in before and row["tests"] < before[name]["tests"]]
        if lost and not args.allow:
            print(json.dumps({"refused": "DECLARED_TESTS_DISAPPEARED", "files": lost,
                              "hint": "--allow 只在你确认这次减少是有意的时使用；"
                                      "删测试换绿是本项目明令禁止的动作"},
                             ensure_ascii=False, indent=2))
            return 3
        published = json.loads(OUT.read_text(encoding="utf-8"))
        if _without_stamp(published) == _without_stamp(fresh):
            # Re-running with identical readings must not move the file. `generated_at` alone would
            # change tracked bytes under tests/, and the receipt clause allows nothing there: a
            # refresh that restamps takes the measurement off the tree it is being read at.
            print(json.dumps({"written": str(OUT), "verdict": "UNCHANGED",
                              "generated_at_kept": published.get("generated_at"),
                              "files": fresh["files"], "tests": fresh["tests"]},
                             ensure_ascii=False))
            return 0
    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(OUT), "files": fresh["files"], "tests": fresh["tests"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
