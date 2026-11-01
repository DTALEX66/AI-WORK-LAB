#!/usr/bin/env python3
"""Hold the three WUI-17 surfaces to the policy each one earned, instead of switching them on naively.

WUI-17 registered `REFS-RATCHET-HISTORY-SURFACES-20261009` after measuring 4,153 references across
`reports/`, `knowledge-staging/` and the repository root: 3,262 did not resolve against the tracked tree.
Switching that population into a "every reference must resolve" gate would have dumped 3,262 findings on
the next writer, so the decision was to split it by what each surface is FOR:

  1. external skill copies -- these sentences describe their own upstream repositories, not this tree,
     so the subtree is declared, per surface, as a non-repository navigation surface;
  2. date-stamped archives -- rewriting a dated record makes it describe a tree it never saw, so they
     are ratcheted: the count may not grow, and every baseline row must still be broken;
  3. "still being written" -- re-measured 2026-10-18 and reclassified on evidence: all of the 143 broken
     references in that bucket live in date-stamped reports (44), five NON-NORMATIVE-HISTORICAL root
     records (93) whose bodies are byte-frozen by `verify_root_document_dispositions.py`, or AGENTS.md's
     six `skills/`/`bin/` citations -- the sentence whose point is that those repository-root directories
     do not exist. None of them is a navigation claim about the current tree, so they are ratcheted with
     the same growth/shrinkage rule rather than edited.

The resolution rule is imported, not re-implemented: `scripts/ci/verify_authority_index_paths.py:check()`.
A gate that invented its own reader would drift from the live-surface gate and the two numbers would stop
being comparable.

Ratchet semantics, deliberately two-sided: a new broken reference fails (growth), and a baseline row that
resolves today fails too (drift) -- repairing a pointer is a real change and must reissue the baseline in
the same commit. A one-sided ceiling would let a repair silently shrink what the baseline records.

Usage:
    python scripts/ci/verify_refs_surface_policies.py              # report
    python scripts/ci/verify_refs_surface_policies.py --write-baseline   # reissue after a measured change

Exit: 0 clean, 1 policy violation, 2 the scan itself could not run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import verify_authority_index_paths as checker  # noqa: E402

POLICY = ".project/governance/refs-surface-policies.json"


def load_policy(root: Path, policy: str) -> dict:
    path = root / policy
    if not path.is_file():
        raise SystemExit(f"REFS_SURFACE_POLICIES_FAIL policy file is missing: {policy}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"REFS_SURFACE_POLICIES_FAIL policy is not JSON: {error}") from error


def population(tracked: list[str], policy: dict) -> list[str]:
    """Every tracked markdown file the policies govern, from git rather than from a hand-written list."""
    roots = policy["population"]["roots"]
    return sorted(
        path for path in tracked
        if path.endswith(".md") and any(path.startswith(root) or ("/" not in path and root == "<root>")
                                        for root in roots)
    )


def is_external_skill_copy(target: str, policy: dict) -> bool:
    rules = policy["externalSkillCopies"]
    if any(target.startswith(prefix) for prefix in rules["prefixes"]):
        return True
    if Path(target).name in rules["basenames"]:
        return True
    return any(segment in target for segment in rules["pathSegments"])


def scan(root: Path, tracked: list[str], targets: list[str], policy: dict) -> dict:
    """Run the shared resolver over the governed surfaces; split declared copies from the ratchet."""
    surfaces = []
    external = hard = 0
    refs = external_refs = 0
    external_broken = 0
    current: list[dict] = []
    problems: list[dict] = []
    for target in targets:
        rows, broken, target_problems = checker.check(root, tracked, target)
        refs += len(rows)
        if is_external_skill_copy(target, policy):
            external += 1
            external_refs += len(rows)
            external_broken += len(broken)
            surfaces.append({"target": target, "declared": "external-skill-copy",
                             "refs": len(rows), "broken": len(broken)})
            continue
        hard += 1
        surfaces.append({"target": target, "declared": "ratcheted",
                         "refs": len(rows), "broken": len(broken)})
        current.extend({"target": target, "line": line, "ref": ref, "kind": kind}
                       for line, ref, kind in broken)
        problems.extend({"target": target, "line": line, "message": message}
                        for line, message in target_problems)
    current.sort(key=lambda row: (row["target"], row["line"], row["ref"], row["kind"]))
    return {"targets": len(targets), "refs": refs, "externalSurfaces": external,
            "externalRefs": external_refs, "externalBroken": external_broken,
            "ratchetSurfaces": hard, "current": current, "problems": problems,
            "surfaces": surfaces}


def row_key(row: dict) -> tuple:
    return (row["target"], row["line"], row["ref"], row["kind"])


def compare(baseline: list[dict], current: list[dict]) -> tuple[list[dict], list[dict]]:
    """(new, fixed) as multiset differences, so a duplicated reference is still two references."""
    before = Counter(row_key(row) for row in baseline)
    after = Counter(row_key(row) for row in current)
    new = after - before
    fixed = before - after
    return ([dict(zip(("target", "line", "ref", "kind"), key)) for key in new.elements()],
            [dict(zip(("target", "line", "ref", "kind"), key)) for key in fixed.elements()])


def population_violations(result: dict, policy: dict) -> list[str]:
    """Floors that make a broken scan loud instead of quietly reporting a clean tree."""
    floors = policy["population"]["floor"]
    findings = []
    if result["targets"] < floors["surfaces"]:
        findings.append(f"surface floor: scanned {result['targets']} < {floors['surfaces']}")
    if result["refs"] < floors["references"]:
        findings.append(f"reference floor: extracted {result['refs']} < {floors['references']}")
    external_floor = policy["externalSkillCopies"]["floor"]["surfaces"]
    if result["externalSurfaces"] < external_floor:
        findings.append(f"external declaration floor: matched {result['externalSurfaces']} surfaces "
                        f"< {external_floor}; the declaration no longer covers what it claims")
    return findings


def write_baseline(root: Path, policy_path: str, policy: dict, current: list[dict]) -> None:
    policy["ratchet"]["baseline"] = current
    policy["ratchet"]["baselineMeasuredAt"] = policy["measuredAt"]
    (root / policy_path).write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default=POLICY, help="repo-relative policy JSON (tests point at a copy)")
    ap.add_argument("--write-baseline", action="store_true",
                    help="reissue the ratchet baseline from today's measurement")
    args = ap.parse_args(argv)

    root = ROOT
    policy = load_policy(root, args.policy)
    tracked = checker.tracked_paths(root)
    if not tracked:
        print("REFS_SURFACE_POLICIES_FAIL git ls-files returned nothing -- an empty tracked set "
              "resolves every reference and proves nothing")
        return 2
    targets = population(tracked, policy)
    if not targets:
        print("REFS_SURFACE_POLICIES_FAIL the policy's population matched no tracked markdown")
        return 2
    result = scan(root, tracked, targets, policy)
    floors = population_violations(result, policy)
    if floors:
        for finding in floors:
            print(f"REFS_SURFACE_POLICIES_FAIL {finding}")
        return 2

    if args.write_baseline:
        if result["problems"]:
            print("REFS_SURFACE_POLICIES_FAIL refusing to reissue a baseline while declaration problems "
                  "are open; fix those first")
            return 1
        write_baseline(root, args.policy, policy, result["current"])
        print(f"REFS_SURFACE_POLICIES_BASELINE_WRITTEN policy={args.policy} rows={len(result['current'])}")
        return 0

    baseline = policy["ratchet"].get("baseline")
    if baseline is None:
        print(f"REFS_SURFACE_POLICIES_FAIL policy has no ratchet baseline; run --write-baseline once")
        return 2
    new, fixed = compare(baseline, result["current"])
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()
    for row in new:
        print(f"REFS_SURFACE_POLICIES_FAIL NEW_BROKEN {row['target']}:{row['line']} "
              f"`{row['ref']}` ({row['kind']}) -- a new unresolvable reference on a ratcheted surface; "
              "either fix it or reissue the baseline with a stated reason")
    for row in fixed:
        print(f"REFS_SURFACE_POLICIES_FAIL FIXED_BUT_BASELINE_STALE {row['target']}:{row['line']} "
              f"`{row['ref']}` resolves today but is still recorded as broken; reissue the baseline in "
              "the same change so a repair is a decision, not silent drift")
    for problem in result["problems"]:
        print(f"REFS_SURFACE_POLICIES_FAIL DECLARATION {problem['target']}:{problem['line']} "
              f"{problem['message']}")

    print(f"REFS_SURFACE_POLICIES_{'PASS' if not (new or fixed or result['problems']) else 'FAIL'} "
          f"head={head[:12]} surfaces={result['targets']} refs={result['refs']} "
          f"external_surfaces={result['externalSurfaces']} external_refs={result['externalRefs']} "
          f"external_broken_declared={result['externalBroken']} "
          f"ratchet_surfaces={result['ratchetSurfaces']} ratchet_baseline={len(baseline)} "
          f"ratchet_broken_today={len(result['current'])} new={len(new)} fixed={len(fixed)} "
          f"declaration_problems={len(result['problems'])}")
    return 0 if not (new or fixed or result["problems"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
