#!/usr/bin/env python3
"""Three-project boundary verifier (WORK-LAB V2, fail-closed).

Machine check for the control-plane / knowledge / design ownership split:
    .project/governance/three-project-boundary.json  (SSOT)
    .project/governance/boundary-migration-manifest.json  (what moves, where)

The verifier fails closed when ANY of the following is missing:
  1. the boundary SSOT contract,
  2. a BOUNDARY.md marker in every split dir that is marked,
  3. a seam (integrations/archeaxis/contracts/*) for every split that declares one,
  4. a migration manifest entry covering every split.

No file moves, no code deletion — this only PROVES the boundary is marked and
gated. Running it is the audit trail that the three-project split is real,
not a doc promise.

Exit 0 = boundary marked+gated; exit 1 = fail-closed (boundary gap).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# split dir (repo-relative) -> required marker file
SPLIT_DIRS = {
    "services/memory": "BOUNDARY.md",
    "services/knowledge": "BOUNDARY.md",
    "services/evolution": "BOUNDARY.md",
    "knowledge-staging": "BOUNDARY.md",
    "90-archive": "BOUNDARY.md",
}

# required seams (repo-relative), by split id
REQUIRED_SEAMS = {
    "MEMORY_BACKEND": "integrations/archeaxis/contracts/memory-query-contract.py",
    "KNOWLEDGE_TRUTH": "integrations/archeaxis/contracts/promotion_contract.py",
    "DESIGN_LAB": "integrations/archeaxis/contracts/open_design_client_seam.py",
}

SSOT = ".project/governance/three-project-boundary.json"
MANIFEST = ".project/governance/boundary-migration-manifest.json"

failures: list[str] = []

# Where the recorded seam-caller baseline lives, and which module-name marker
# identifies a caller of each seam contract.
SEAM_CALLER_BASELINE = ".project/governance/seam-caller-baseline.json"

SEAM_CALLER_MARKERS = {
    "MEMORY_BACKEND": "memory-query-contract",
    "KNOWLEDGE_TRUTH": "promotion_contract",
    "DESIGN_LAB": "open_design_client_seam",
}

# Text-like sources that could import or shell out to a seam contract. Binary and
# vendored trees are excluded; this is a caller scan, not a lint pass.
CALLER_SCAN_SUFFIXES = (".py", ".sh", ".ps1", ".cmd", ".bat", ".js", ".ts", ".tsx")
CALLER_SCAN_ROOTS = (
    "services",
    "packages",
    "apps",
    "scripts",
    "integrations",
    "tests",
)
CALLER_SCAN_SKIP = ("node_modules", ".project-local", "dist", "build", "__pycache__")


def _seam_callers(seam_id: str) -> set[str]:
    """Return repo-relative files that name a seam contract's module marker.

    A reference in this file itself is not a caller: the verifier holds each
    contract path as a constant purely to assert the file exists. Counting that
    would make the baseline describe the checker instead of the codebase.
    """
    marker = SEAM_CALLER_MARKERS.get(seam_id)
    if not marker:
        return set()
    try:
        self_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        # ROOT was patched (fixtures); there is no meaningful "this file" then.
        self_rel = ""
    found: set[str] = set()
    for root_rel in CALLER_SCAN_ROOTS:
        root = ROOT / root_rel
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in CALLER_SCAN_SUFFIXES:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel == self_rel or any(part in rel for part in CALLER_SCAN_SKIP):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if marker in text:
                found.add(rel)
    return found


def check(cond: bool, label: str, detail: str = "") -> None:
    if not cond:
        failures.append(f"{label}: {detail}".strip())


def main() -> int:
    # 1) SSOT contract
    ssot_path = ROOT / SSOT
    check(ssot_path.is_file(), "SSOT", f"{SSOT} missing")
    split_ids: set[str] = set()
    if ssot_path.is_file():
        try:
            ssot = json.loads(ssot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            check(False, "SSOT", f"invalid JSON: {e}")
            ssot = {}
        split_ids = {s.get("id") for s in ssot.get("boundary_splits", []) if s.get("id")}
        check(len(split_ids) >= 5, "SSOT.splits", f"expected >=5 splits, got {len(split_ids)}")
        check(
            "worklab_owned" in ssot and ssot.get("worklab_owned"),
            "SSOT.worklab_owned", "worklab_owned must be a non-empty allowlist",
        )

    # 2) markers present in every marked split dir
    for d, marker in SPLIT_DIRS.items():
        mp = ROOT / d / marker
        check(mp.is_file(), f"marker {d}/{marker}", "missing boundary marker")

    # 3) seams present for every split that declares one
    declared_seams = set()
    if ssot_path.is_file():
        try:
            for s in json.loads(ssot_path.read_text(encoding="utf-8")).get("boundary_splits", []):
                if s.get("seam"):
                    declared_seams.add(s.get("id"))
        except json.JSONDecodeError:
            pass
    for split_id, seam_rel in REQUIRED_SEAMS.items():
        if split_id not in split_ids:
            continue
        sp = ROOT / seam_rel
        check(sp.is_file(), f"seam {seam_rel}", f"split {split_id} seam missing")
    # every required-seam split must be a declared split
    for sid in REQUIRED_SEAMS:
        check(sid in split_ids, f"split {sid}", "declared in SSOT but absent from splits")

    # 4) migration manifest covers every split
    manifest_path = ROOT / MANIFEST
    check(manifest_path.is_file(), "manifest", f"{MANIFEST} missing")
    if manifest_path.is_file():
        try:
            moves = json.loads(manifest_path.read_text(encoding="utf-8")).get("moves", [])
        except json.JSONDecodeError as e:
            check(False, "manifest.json", f"invalid JSON: {e}")
            moves = []
        covered_dirs = {m.get("dir") for m in moves if m.get("dir")}
        manifest_split_ids = {m.get("splitId") for m in moves if m.get("splitId")}
        for d in SPLIT_DIRS:
            # manifest must record at least one move touching each marked dir
            check(any(d in (cd or "") for cd in covered_dirs), f"manifest covers {d}", "no move records this dir")
        # every split has a manifest entry (via splitId)
        for sid in split_ids:
            check(sid in manifest_split_ids, f"manifest entry {sid}", "split not covered by manifest")

    # 5) caller graph against the declared seam rule (AG-06k, audit F19).
    #
    # Audit F19's point: this verifier checked markers, seams and manifests, so a
    # PASS could not show that a business boundary violation was absent - a marker
    # test is not a boundary-acceptance test. The SSOT's MEMORY_BACKEND seam
    # literally declares "no new callers allowed", and that rule had no machine
    # check at all. Scanning today finds ZERO code callers of any of the three
    # seamless contracts: the only references are this file's own path constants.
    # So the rule was unenforced AND trivially satisfiable, which is exactly when
    # a silent regression is cheapest to introduce.
    #
    # This records the baseline as data and fails if the caller set GROWS. It is
    # deliberately one-directional: removing a caller is progress, adding one is
    # the thing the seam forbids.
    baseline_path = ROOT / SEAM_CALLER_BASELINE
    if baseline_path.is_file():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            check(False, "seam-caller-baseline", f"invalid JSON: {e}")
            baseline = {}
        for seam_id, recorded in (baseline.get("seams") or {}).items():
            observed = _seam_callers(seam_id)
            recorded_set = set(recorded.get("callers") or [])
            # Files that mention a contract only to ASSERT it is unreferenced (the
            # seam's own negative control) are declared separately and are not
            # code callers. Keeping them out of `callers` preserves what the
            # baseline means instead of letting the guard quietly widen itself,
            # and an undeclared exemption is itself a failure.
            declared_refs = set(
                (baseline.get("verification_references") or {}).get(seam_id) or []
            )
            added = sorted(observed - recorded_set - declared_refs)
            check(
                not added,
                f"seam callers {seam_id}",
                "new caller(s) added despite the declared 'no new callers allowed' "
                f"seam: {added}; a boundary violation must be reviewed, not assumed absent",
            )
            # A declared exemption that no longer references the contract is stale
            # and must not linger: otherwise the baseline would carry an allowance
            # for a file that could later start calling the seam unnoticed.
            stale = sorted(declared_refs - observed)
            check(
                not stale,
                f"seam verification_references {seam_id}",
                "declared as a verification-only reference but no longer references "
                f"the contract: {stale}",
            )
    else:
        check(False, "seam-caller-baseline", f"{SEAM_CALLER_BASELINE} missing")

    if failures:
        print(f"THREE_PROJECT_BOUNDARY_FAIL ({len(failures)} failures)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"THREE_PROJECT_BOUNDARY_PASS splits={len(split_ids)} markers={len(SPLIT_DIRS)} seams={len(REQUIRED_SEAMS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
