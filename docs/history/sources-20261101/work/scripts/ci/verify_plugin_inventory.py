#!/usr/bin/env python3
"""Refuse a plugin record that claims more traceability than it has.

Audit F07 exposed two failure modes in `config/plugin-inventory.json`:

1. A plugin could record `commit: null, hash: null` while the live install
   metadata DID declare a revision, so the record was less informative than the
   machine it described.
2. Worse, a revision STRING was treated as sufficient. It is not: the audit's own
   caveat is that a revision cannot prove the installed bytes match that commit.
   Verified live on chrome-profiles - the declared revision is correct
   (`git rev-parse HEAD` equals it) yet the working tree does NOT match, because
   `__init__.py` is locally modified (24,433 B installed vs 23,764 B committed).

This gate enforces the distinction the record must keep: a DECLARED lifecycle and
an OBSERVED installation are different facts, and a plugin with a floating
revision must not be presented as if it were pinned to verified bytes.

Rule set (fail-closed):
  - an entry whose lifecycle is `installed`/`enabled`/`active` must carry an
    `observed` block, because a claim of presence must be dated and evidenced;
  - an `observed` block must state whether the working tree matches the commit,
    and when it does not it must name the modified paths, so a local delta can
    never be silently dropped;
  - `pinned: false` (a floating revision) is only acceptable when the record says
    which revision was actually observed;
  - a declared-vs-observed disagreement must be recorded explicitly rather than
    being resolved by editing the declared value.

Read-only. Exit 0 = PASS, 1 = violation, 2 = usage/IO problem.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Lifecycle states that assert the plugin is PRESENT on the machine.
PRESENCE_STATES = ("installed", "enabled", "active")


class Violation(RuntimeError):
    """A plugin record that claims more than it can support."""


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - IO guard
        raise SystemExit(f"PLUGIN_INVENTORY_IO_FAIL {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"PLUGIN_INVENTORY_SHAPE_FAIL {path}: root must be an object")
    return data


def check_inventory(path: Path) -> list[str]:
    data = _load(path)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return [f"PLUGIN_INVENTORY_MALFORMED: {path.name} entries must be a list"]

    problems: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"PLUGIN_ENTRY_MALFORMED: {path.name}.entries[{index}]")
            continue
        pid = entry.get("id") or f"[{index}]"
        label = f"{path.name}.{pid}"
        lifecycle = entry.get("lifecycle")
        observed = entry.get("observed")

        # AG-06q: a BUNDLED component ships inside the application. Applying an
        # install-shaped observation to it produced a false "declared vs observed
        # disagreement" during this session (security-guidance, web-ddgs), because
        # absence from the USER install directory is its correct state. The rule
        # now makes that category error impossible to record.
        bundled = (
            entry.get("verification_kind") == "BUNDLED_COMPONENT"
            or entry.get("upstream") == "bundled"
        )
        if bundled:
            if entry.get("commit") is not None or entry.get("hash") is not None:
                problems.append(
                    f"PLUGIN_BUNDLED_CLAIMS_A_CHECKOUT: {label} is a bundled component "
                    "but records a commit or hash, as if it had an independent checkout"
                )
            if isinstance(observed, dict):
                if observed.get("working_tree_matches_commit") != "NOT_COMPARABLE":
                    problems.append(
                        f"PLUGIN_BUNDLED_COMPARED_AS_INSTALL: {label} is bundled yet its "
                        "observation compares a working tree to a commit; a bundled "
                        "component has no independent checkout to compare"
                    )
                if observed.get("bundled") is not True:
                    problems.append(
                        f"PLUGIN_BUNDLED_NOT_DECLARED: {label} is bundled but its "
                        "observation does not say so"
                    )
                if not observed.get("observed_path"):
                    problems.append(
                        f"PLUGIN_BUNDLED_WITHOUT_PATH: {label} does not record where the "
                        "bundled component was found"
                    )
            # The category error in its original form: flagging absence from the
            # user install directory as a disagreement.
            disagreement = entry.get("declared_vs_observed")
            if isinstance(disagreement, dict) and disagreement.get("agreement") is False:
                problems.append(
                    f"PLUGIN_BUNDLED_FALSE_DISAGREEMENT: {label} is bundled yet records a "
                    "declared/observed disagreement, which is the category error this "
                    "rule exists to prevent (its absence from the user install directory "
                    "is the correct state)"
                )

        if lifecycle in PRESENCE_STATES and not isinstance(observed, dict):
            problems.append(
                f"PLUGIN_PRESENCE_WITHOUT_OBSERVATION: {label} declares lifecycle "
                f"{lifecycle!r} but carries no observed block, so its presence is "
                "undated and unevidenced"
            )
            continue

        if isinstance(observed, dict):
            matches = observed.get("working_tree_matches_commit")
            # Three states, not two. When nothing is installed there are no bytes
            # to compare, so `NOT_COMPARABLE` is the honest answer; forcing it to
            # true/false would fabricate a comparison that never happened.
            if matches == "NOT_COMPARABLE":
                if not observed.get("comparison_not_possible_reason"):
                    problems.append(
                        f"PLUGIN_COMPARISON_UNEXPLAINED: {label} says the working tree "
                        "is NOT_COMPARABLE but gives no reason"
                    )
            elif matches is not True and matches is not False:
                problems.append(
                    f"PLUGIN_OBSERVATION_UNDECIDED: {label}.observed does not state "
                    "working_tree_matches_commit (true, false, or NOT_COMPARABLE with a "
                    "reason), so a local delta could be dropped"
                )
            if matches is False and not observed.get("locally_modified_paths"):
                problems.append(
                    f"PLUGIN_LOCAL_DELTA_UNNAMED: {label} states the working tree does "
                    "not match the commit but names no modified path"
                )
            if not observed.get("observed_at"):
                problems.append(
                    f"PLUGIN_OBSERVATION_UNDATED: {label}.observed has no observed_at"
                )

        # A floating revision must still record WHAT was observed.
        if entry.get("pinned") is False:
            revision = observed.get("observed_commit") if isinstance(observed, dict) else None
            if not revision:
                problems.append(
                    f"PLUGIN_FLOATING_WITHOUT_OBSERVED_REVISION: {label} is not pinned "
                    "but records no observed_commit"
                )

        # A declared-vs-observed disagreement must be recorded, not smoothed.
        disagreement = entry.get("declared_vs_observed")
        if isinstance(disagreement, dict):
            if disagreement.get("agreement") is False and not disagreement.get("interpretation"):
                problems.append(
                    f"PLUGIN_DISAGREEMENT_WITHOUT_INTERPRETATION: {label} records a "
                    "declared/observed disagreement without explaining it"
                )

        # The original F07 shape: a null commit while metadata declared one.
        if (
            entry.get("commit") is None
            and entry.get("declared_revision")
            and isinstance(observed, dict)
            and observed.get("installed_directory_present") is not False
        ):
            problems.append(
                f"PLUGIN_REVISION_KNOWN_BUT_UNRECORDED: {label} declares a revision "
                "yet records commit=null"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path, help="plugin inventory JSON files")
    args = parser.parse_args(argv)

    problems: list[str] = []
    for path in args.paths:
        if not path.is_file():
            print(f"PLUGIN_INVENTORY_IO_FAIL missing file: {path}", file=sys.stderr)
            return 2
        problems.extend(check_inventory(path))

    if problems:
        for problem in problems:
            print(f"PLUGIN_INVENTORY_FAIL {problem}", file=sys.stderr)
        return 1
    print(f"PLUGIN_INVENTORY_PASS inventories={len(args.paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
