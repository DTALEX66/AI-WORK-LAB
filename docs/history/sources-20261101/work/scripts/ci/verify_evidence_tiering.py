#!/usr/bin/env python3
"""Fail closed when an evidence bundle makes behavioural claims without a tier.

Audit F15/F16 exposed a class of defect rather than a single typo: an evidence
package can be *internally consistent* (every digest matches, every count adds
up) while still inviting a reader to conclude something the package cannot
support. The motivating examples were `external_roots_touched: []` and a secret
scan whose scanner source was not retained -- neither can establish that a root
was never accessed, only that the bundle says so.

The rule enforced here: if a bundle states a behavioural claim, it must carry an
explicit evidence tier, and a tier below VERIFIED must name what it cannot
establish. Tier meanings:

  DECLARED  the generating procedure asserted it; not independently reproduced
  OBSERVED  a named observation was recorded in the bundle
  VERIFIED  a third party can re-derive it from the bundle alone

This is a structural gate, not a text check: it inspects the structured fields a
bundle uses for behavioural claims, so silence can no longer pass as proof.

Read-only. Exit 0 = PASS, 1 = violation, 2 = usage/IO problem.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TIERS = ("DECLARED", "OBSERVED", "VERIFIED")

# Field names that assert something HAPPENED (or did not happen). A bundle that
# carries any of these must carry behavioural tiering alongside them.
BEHAVIOURAL_KEYS = (
    "external_roots_touched",
    "secrets_included",
    "executed",
)
# The tiering block a bundle must provide once it makes such claims.
TIER_BLOCK_KEYS = ("behavior_declarations", "behaviour_declarations")


class Violation(RuntimeError):
    """A bundle claim that cannot be supported as stated."""


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - IO guard
        raise SystemExit(f"EVIDENCE_TIER_IO_FAIL {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"EVIDENCE_TIER_SHAPE_FAIL {path}: root must be an object")
    return data


def _find_behavioural(data: dict) -> list[str]:
    """Return behavioural claim keys present anywhere in the document."""
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in BEHAVIOURAL_KEYS and not isinstance(value, (dict, list)):
                    found.append(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def _tier_block(data: dict) -> dict | None:
    for key in TIER_BLOCK_KEYS:
        block = data.get(key)
        if isinstance(block, dict):
            return block
    return None


def check_bundle(path: Path) -> list[str]:
    """Return a list of violations for one bundle (empty means it passed)."""
    data = _load(path)
    problems: list[str] = []
    claims = _find_behavioural(data)
    block = _tier_block(data)

    if claims and block is None:
        problems.append(
            f"BEHAVIOURAL_CLAIM_WITHOUT_TIER: {path.name} states {sorted(set(claims))} "
            "but carries no behavior_declarations block, so a reader cannot tell a "
            "declared claim from a verified one"
        )
        return problems

    if block is None:
        return problems

    tier = block.get("evidence_tier")
    if tier not in TIERS:
        problems.append(
            f"BEHAVIOURAL_TIER_UNKNOWN: {path.name} evidence_tier={tier!r} "
            f"not in {list(TIERS)}"
        )

    entries = block.get("claims")
    if entries is None:
        # A top-level tier without per-claim detail is only acceptable when the
        # bundle's claims are covered by the block itself.
        if not block.get("tier_definition"):
            problems.append(
                f"BEHAVIOURAL_TIER_WITHOUT_DEFINITION: {path.name} declares tier "
                f"{tier!r} with no tier_definition and no per-claim entries"
            )
        return problems

    if not isinstance(entries, list) or not entries:
        problems.append(
            f"BEHAVIOURAL_CLAIMS_MALFORMED: {path.name} claims must be a non-empty list"
        )
        return problems

    for index, entry in enumerate(entries):
        label = f"{path.name}.behavior_declarations.claims[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"BEHAVIOURAL_CLAIM_MALFORMED: {label} must be an object")
            continue
        entry_tier = entry.get("tier")
        if entry_tier not in TIERS:
            problems.append(
                f"BEHAVIOURAL_CLAIM_TIER_UNKNOWN: {label} tier={entry_tier!r}"
            )
            continue
        # The whole point: a claim below VERIFIED must say what it CANNOT do.
        if entry_tier != "VERIFIED":
            cannot = entry.get("cannot_establish")
            if not isinstance(cannot, list) or not cannot:
                problems.append(
                    f"BEHAVIOURAL_CLAIM_OVERREACH: {label} is tier {entry_tier} but "
                    "names nothing it cannot establish, so it reads as proof"
                )
        if not entry.get("field") and not entry.get("claim"):
            problems.append(
                f"BEHAVIOURAL_CLAIM_UNLABELLED: {label} names neither field nor claim"
            )

    # A bundle that admits the generating procedure was not retained may not also
    # present its findings as verified.
    if block.get("generating_procedure_retained") is False:
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("tier") == "VERIFIED":
                problems.append(
                    f"BEHAVIOURAL_UNREPRODUCIBLE_VERIFIED: {path.name} "
                    f"claims[{index}] is VERIFIED while the generating procedure was "
                    "not retained, so a third party cannot re-derive it"
                )
    return problems


def check_cleanup_candidates(path: Path) -> list[str]:
    """Refuse a cleanup-candidate list that could be read as a delete queue.

    Audit F14 is a blocker: user state (session/history or state databases) must
    never be mixed into a cleanup list without an explicit, machine-readable
    rejection, because a reinstall-time reader may act on the list as written.
    Audit F13 adds that overlapping globs need an explicit precedence so the same
    path cannot be owned by two candidates.
    """
    data = _load(path)
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        return []
    problems: list[str] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            problems.append(
                f"CLEANUP_CANDIDATE_MALFORMED: {path.name}.candidates[{index}]"
            )
            continue
        cid = candidate.get("id") or f"[{index}]"
        label = f"{path.name}.{cid}"
        disposition = candidate.get("disposition")
        if disposition is None:
            problems.append(
                f"CLEANUP_CANDIDATE_UNDISPOSITIONED: {label} has no disposition, so a "
                "reader cannot tell a rejected item from an authorised one"
            )
            continue
        # A rejected item must be impossible to execute and must say why.
        if disposition == "REJECT_USER_DATA":
            if candidate.get("executed") is not False:
                problems.append(
                    f"CLEANUP_REJECTED_BUT_EXECUTED: {label} is REJECT_USER_DATA yet "
                    "executed is not false"
                )
            if candidate.get("deletion_rejected") is not True:
                problems.append(
                    f"CLEANUP_REJECTED_WITHOUT_FLAG: {label} is REJECT_USER_DATA but "
                    "deletion_rejected is not true"
                )
            if candidate.get("authorization_required") is not True:
                problems.append(
                    f"CLEANUP_REJECTED_WITHOUT_AUTH_GATE: {label} is REJECT_USER_DATA but "
                    "authorization_required is not true"
                )
            if not candidate.get("forbidden_actions"):
                problems.append(
                    f"CLEANUP_REJECTED_WITHOUT_FORBIDDEN_ACTIONS: {label} is "
                    "REJECT_USER_DATA but names no forbidden actions"
                )
        elif not isinstance(disposition, str):
            problems.append(f"CLEANUP_DISPOSITION_MALFORMED: {label}")

    # Overlap must be declared in both directions, with a precedence.
    by_id = {
        c.get("id"): c for c in candidates if isinstance(c, dict) and c.get("id")
    }
    for cid, candidate in by_id.items():
        for other in candidate.get("overlaps_with") or []:
            counterpart = by_id.get(other)
            if counterpart is None:
                problems.append(
                    f"CLEANUP_OVERLAP_DANGLING: {cid} overlaps {other}, which is not a candidate"
                )
                continue
            if cid not in (counterpart.get("overlaps_with") or []):
                problems.append(
                    f"CLEANUP_OVERLAP_NOT_RECIPROCAL: {cid} names {other} but not the reverse"
                )
        if candidate.get("overlaps_with") and not (
            candidate.get("precedence_over") or candidate.get("subordinate_to")
        ):
            problems.append(
                f"CLEANUP_OVERLAP_WITHOUT_PRECEDENCE: {cid} overlaps another candidate "
                "without declaring which one owns the shared path"
            )
    return problems


def check_archive_index_coverage(path: Path) -> list[str]:
    """Refuse an archive index whose skill enumeration skipped a layout level.

    Audit F05: the archive claimed "all SKILL.md main files were copied in full",
    but its enumeration only covered categorised skills
    (`hermes/skills/<category>/<name>/SKILL.md`). Root-level skills
    (`hermes/skills/<name>/SKILL.md`) were never captured at all - 5 of them,
    including `model-switch`, one of the 13 MANAGED skills. So the completeness
    claim was false, and the failure was silent because the index reported a
    healthy-looking total.

    The shape that gives it away is structural, not textual: a directory layout
    where one nesting level is richly populated and a sibling level is empty. If
    an index records many `SKILL.md` at one depth under a client and ZERO at the
    documented shallower layout, the enumeration almost certainly skipped it, and
    that must be declared rather than left to look like an absence of content.
    """
    data = _load(path)
    files = data.get("files")
    if not isinstance(files, list):
        return []

    # client prefix -> set of depths at which SKILL.md files are indexed
    skills_by_client: dict[str, dict[int, int]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            continue
        rel = entry.get("archive_path") or ""
        if not rel.endswith("SKILL.md"):
            continue
        head = rel.split("/", 1)[0]
        depth = rel.count("/")
        skills_by_client.setdefault(head, {}).setdefault(depth, 0)
        skills_by_client[head][depth] += 1

    declared = data.get("skills_depth_reconciliation")
    # Separator count of the ROOT-LEVEL layout, `<client>/skills/<name>/SKILL.md`,
    # which is the placement audit F05 found missing. Derived, not hardcoded, so
    # the check keeps meaning if the archive prefix changes.
    root_layout_depth = f"x/skills/n/SKILL.md".count("/")
    problems: list[str] = []
    for client, depths in sorted(skills_by_client.items()):
        if not depths:
            continue
        populated = sorted(d for d, n in depths.items() if n > 0)
        if not populated:
            continue
        deepest_populated = populated[-1]
        if isinstance(declared, dict) and client in declared:
            continue  # explicitly reconciled, so the gap is recorded not silent
        # Only ONE level populated, and it is DEEPER than the root-level layout:
        # that is the signature of an enumeration that descended into categories
        # and never looked at the flat layout.
        if len(populated) == 1 and deepest_populated > root_layout_depth:
            problems.append(
                f"ARCHIVE_SKILL_DEPTH_UNAUDITED: {path.name} indexes {client} SKILL.md "
                f"only at depth {deepest_populated} ({depths[deepest_populated]} entries) "
                "and at no shallower depth, so the root-level layout "
                "(<client>/skills/<name>/SKILL.md) could have been skipped silently; "
                "declare skills_depth_reconciliation for this client or account for the "
                "missing depths"
            )
    return problems


ARCHIVE_DISARM_MARKER = "ARCHIVED EVIDENCE — NOT LIVE INSTRUCTIONS"

# Filenames that agent tooling auto-loads as governance. Copying one into a
# repository is not inert: whichever file an agent reads, it obeys.
INSTRUCTION_FILENAMES = ("AGENTS.md", "CLAUDE.md", ".cursorrules")


def find_undisarmed_instruction_files(root: Path) -> list[str]:
    """Return archived instruction-shaped files that lack a disarm banner.

    Audit F18 found an ArcheAxis `AGENTS.md` archived inside WORK-LAB whose text
    still pointed at WORK-LAB's removed `00-governance/` path. Reconciling it
    surfaced something the audit had not stated: because the file is named
    AGENTS.md, agent tooling loads it as guidance and injects it into a WORK-LAB
    session - observed live during the reconciliation itself, before the banner
    existed. A read-only archive copy is therefore not passive.

    Structural, not textual, in the sense that matters: it keys off the filename
    class that tooling auto-loads, so a future archived AGENTS.md cannot inherit
    the same silent authority.
    """
    problems: list[str] = []
    if not root.is_dir():
        return problems
    for name in INSTRUCTION_FILENAMES:
        for path in sorted(root.rglob(name)):
            if not path.is_file():
                continue
            try:
                head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
            except OSError:
                continue
            if ARCHIVE_DISARM_MARKER not in head:
                rel = path.relative_to(root).as_posix()
                problems.append(
                    f"ARCHIVED_INSTRUCTION_FILE_UNDISARMED: {rel} is an auto-loaded "
                    "governance filename sitting in an archive, so agent tooling will "
                    "inject it as live guidance; prefix it with the disarm banner"
                )
    return problems


def check_cross_project_provenance(path: Path) -> list[str]:
    """Refuse a cross-project archive that hides which revision it copied.

    Audit F01 asks that history gaps be registered with fixed ids and that anything
    not recovered stay UNKNOWN. The archive copies files from two OTHER projects
    (ArcheAxis-Knowledge-OS, DESIGN-LAB) while anchoring only its own freeze commit,
    so a reader cannot tell which revision of those projects was copied - or that
    nobody knows. The honest states are a real commit/tree, or an explicit UNKNOWN
    with a reason; a silent null is the one that must not pass, because it looks
    like there was nothing to record.
    """
    data = _load(path)
    projects = data.get("project_provenance")
    if not isinstance(projects, dict):
        # Only required when the index actually references another project's files.
        if any(
            isinstance(entry, dict)
            and str(entry.get("archive_path", "")).startswith("projects/")
            for entry in (data.get("files") or [])
        ):
            return [
                f"ARCHIVE_CROSS_PROJECT_UNBOUND: {path.name} contains files copied from "
                "other projects but declares no project_provenance, so no revision "
                "binding and no explicit UNKNOWN is recorded"
            ]
        return []

    problems: list[str] = []
    per_project = projects.get("per_project")
    if not isinstance(per_project, dict) or not per_project:
        problems.append(
            f"ARCHIVE_PROJECT_PROVENANCE_EMPTY: {path.name} declares project_provenance "
            "with no per_project entries"
        )
        return problems

    for name, entry in sorted(per_project.items()):
        label = f"{path.name}.project_provenance.{name}"
        if not isinstance(entry, dict):
            problems.append(f"ARCHIVE_PROJECT_ENTRY_MALFORMED: {label}")
            continue
        if not entry.get("files_in_archive"):
            problems.append(
                f"ARCHIVE_PROJECT_NO_FILE_COUNT: {label} does not say how many files it "
                "contributed"
            )
        bound = bool(entry.get("commit")) or bool(entry.get("tree"))
        status = entry.get("provenance_status")
        if bound:
            continue
        # Unbound: acceptable ONLY when declared UNKNOWN with a reason.
        if status != "UNKNOWN":
            problems.append(
                f"ARCHIVE_PROJECT_UNBOUND_NOT_DECLARED: {label} has no commit or tree and "
                f"provenance_status={status!r}; accept only an explicit UNKNOWN so the gap "
                "is visible instead of looking like nothing to record"
            )
        if not entry.get("reason"):
            problems.append(
                f"ARCHIVE_PROJECT_UNBOUND_WITHOUT_REASON: {label} is UNKNOWN but gives no "
                "reason"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path, help="evidence bundle JSON files to check")
    args = parser.parse_args(argv)

    problems: list[str] = []
    checked = 0
    claimed = 0
    for path in args.paths:
        if path.is_dir():
            # A directory argument means "check this archive", not "check a bundle".
            problems.extend(find_undisarmed_instruction_files(path))
            checked += 1
            continue
        if not path.is_file():
            print(f"EVIDENCE_TIER_IO_FAIL missing file: {path}", file=sys.stderr)
            return 2
        # Both checks run: a bundle can be correctly tiered AND still present user
        # state as a deletion target, so neither may short-circuit the other.
        findings = (
            check_bundle(path)
            + check_cleanup_candidates(path)
            + check_archive_index_coverage(path)
            + check_cross_project_provenance(path)
        )
        if _find_behavioural(_load(path)):
            claimed += 1
        problems.extend(findings)
        checked += 1

    if problems:
        for problem in problems:
            print(f"EVIDENCE_TIER_FAIL {problem}", file=sys.stderr)
        return 1
    print(
        f"EVIDENCE_TIER_PASS bundles={checked} with_behavioural_claims={claimed} "
        f"tiered={claimed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
