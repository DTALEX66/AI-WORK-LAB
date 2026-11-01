#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GA-1: fail-closed gate for authority path-reference drift + machine policy.

Closes CROSSWALK 2026-09-24 items G-A (path-reference drift, RAW P0-T2) and
G-C (machine install-policy, RAW P0-T3 residual). Deterministic, stdlib-only,
read-only against the working tree.

Checks (all fail-closed; any FAIL makes the exit code 1):

1.  the authority surface files exist: ``AUTHORITY.md``, ``AGENTS.md``;
2.  every repo-relative path reference inside ``AUTHORITY.md`` and
    ``AGENTS.md`` (outside fenced code blocks) resolves to a file on disk,
    or is explicitly allowlisted in the machine policy with a reason. The
    documented alias form ``project/x`` also resolves through
    ``.project/x``. Unallowlisted missing references FAIL (no silent drift);
3.  the machine policy ``.project/governance/path-ref-policy.json`` parses,
    carries the ``design-lab/path-ref-policy/v1`` schema, and is consistent:
    - ``allowAutoInstall`` is ``false`` (no agent-initiated installation);
    - ``officialReleaseOnly`` is ``true`` (updates follow official releases);
    - ``eDriveProtected`` is ``true`` and no external root points at ``E:``;
    - every external root string starts with the declared
      ``externalRootDrive`` (local-first D: drive contract);
    - ``sharedInputs`` equals ``.project/paths.json`` ``shared_inputs``;
    - ``externalAssetsRoots`` equals
      ``design-lab/config/external-assets-index.json`` ``shared_roots``;
4.  ``design-lab/scripts/verify_project_drift.py`` (DL-GOV-130 language /
    product drift guard) exists and is wired into
    ``.github/workflows/canonical-verify.yml`` — removing the wiring makes
    THIS gate fail (G-B self-enforcing);
5.  the machine policy file itself is tracked-consistent: its ``policyId``
    is declared and its ``allowlist_missing`` entries each carry a
    non-empty ``reason`` (allowlist entries are reviewed, not silent).

The gate writes nothing.

Usage:
    python scripts/verify_path_refs.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

AUTHORITY_MD = "AUTHORITY.md"
AGENTS_MD = "AGENTS.md"
PATHS_JSON = ".project/paths.json"
POLICY_JSON = ".project/governance/path-ref-policy.json"
EXTERNAL_INDEX = "design-lab/config/external-assets-index.json"
DRIFT_GUARD = "design-lab/scripts/verify_project_drift.py"
CI_WORKFLOW = ".github/workflows/canonical-verify.yml"

POLICY_SCHEMA = "design-lab/path-ref-policy/v1"

# Repo-relative path reference: one or more path segments with a dot-suffixed
# final segment. Slash-form only (root files are asserted explicitly in
# check 1); absolute, URL, drive-letter and home-relative refs are excluded.
#
# The character classes are ASCII on purpose. Python's \w is Unicode-aware, so a
# Chinese sentence written without spaces -- "唯一可变状态仍在design-lab/config/..." --
# was absorbed into one giant token that began in the prose, and the gate then reported a
# perfectly good reference as missing. Restricting the classes makes the CJK text a boundary,
# which is what the check needs: it extracts `design-lab/config/task-ledger-r3.json`.
REF_RE = re.compile(
    r"(?<![A-Za-z0-9_.:~/\\-])(\.?[A-Za-z0-9_.+-]+/)+[A-Za-z0-9_.+-]+"
    r"\.(?:md|json|py|yml|yaml|sql|txt|html|css|js|ts|toml|lock)"
)
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _out_fenced(text: str) -> str:
    """Drop fenced code blocks from markdown (documented extraction scope)."""
    kept: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            kept.append(line)
    return "\n".join(kept)


def _extract_refs(md_text: str) -> list[str]:
    refs: list[str] = []
    for match in REF_RE.finditer(_out_fenced(md_text)):
        token = match.group(0)
        if "://" in token:
            continue
        if token.startswith(("~", "/", "http", "https")):
            continue
        # drive-letter / absolute-external refs are machine roots, not repo refs
        if re.match(r"^[A-Za-z]:", token):
            continue
        refs.append(token)
    return sorted(set(refs))


def _ref_exists(repo: Path, ref: str) -> bool:
    candidates = [repo / ref]
    if ref.startswith("project/"):
        candidates.append(repo / ref.replace("project/", ".project/", 1))
    return any(c.is_file() for c in candidates)


def check_surface(repo: Path, checks: list[dict]) -> None:
    for rel in (AUTHORITY_MD, AGENTS_MD):
        if not (repo / rel).is_file():
            checks.append({"check": "authority-surface", "result": "FAIL", "detail": f"{rel} missing"})
            return
    checks.append({"check": "authority-surface", "result": "PASS", "detail": "AUTHORITY.md + AGENTS.md present"})


def check_path_refs(repo: Path, policy: dict, checks: list[dict]) -> None:
    allowlist = {str(e.get("ref", "")) for e in policy.get("allowlist_missing", [])}
    all_refs: list[str] = []
    for rel in (AUTHORITY_MD, AGENTS_MD):
        text = (repo / rel).read_text(encoding="utf-8")
        all_refs.extend(_extract_refs(text))
    all_refs = sorted(set(all_refs))
    missing = [r for r in all_refs if not _ref_exists(repo, r)]
    unapproved = [r for r in missing if r not in allowlist]
    if unapproved:
        checks.append({
            "check": "path-refs-resolve",
            "result": "FAIL",
            "detail": f"unallowlisted missing references: {unapproved}",
        })
        return
    checks.append({
        "check": "path-refs-resolve",
        "result": "PASS",
        "detail": f"refs={len(all_refs)} allowlisted_missing={len([r for r in missing if r in allowlist])}",
    })


def load_policy(repo: Path, checks: list[dict]) -> dict:
    path = repo / POLICY_JSON
    if not path.is_file():
        checks.append({"check": "policy-exists", "result": "FAIL", "detail": f"{POLICY_JSON} missing (fail-closed)"})
        return {}
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        checks.append({"check": "policy-parses", "result": "FAIL", "detail": f"policy does not parse: {exc}"})
        return {}
    if not isinstance(policy, dict) or policy.get("schemaVersion") != POLICY_SCHEMA:
        checks.append({
            "check": "policy-schema",
            "result": "FAIL",
            "detail": f"schemaVersion must be {POLICY_SCHEMA!r}, got {policy.get('schemaVersion') if isinstance(policy, dict) else policy!r}",
        })
        return policy
    if not str(policy.get("policyId", "")):
        checks.append({"check": "policy-schema", "result": "FAIL", "detail": "policyId missing"})
        return policy
    checks.append({"check": "policy-schema", "result": "PASS", "detail": policy.get("policyId")})
    return policy


def check_machine_policy(policy: dict, repo: Path, checks: list[dict]) -> None:
    if policy.get("allowAutoInstall") is not False:
        checks.append({"check": "auto-install-deny", "result": "FAIL",
                      "detail": f"allowAutoInstall must be false, got {policy.get('allowAutoInstall')!r}"})
        return
    checks.append({"check": "auto-install-deny", "result": "PASS", "detail": "allowAutoInstall=false"})

    if policy.get("officialReleaseOnly") is not True:
        checks.append({"check": "official-release-only", "result": "FAIL",
                      "detail": f"officialReleaseOnly must be true, got {policy.get('officialReleaseOnly')!r}"})
        return
    checks.append({"check": "official-release-only", "result": "PASS", "detail": "officialReleaseOnly=true"})

    paths = json.loads((repo / PATHS_JSON).read_text(encoding="utf-8"))
    shared_inputs = paths.get("shared_inputs", {})
    if policy.get("sharedInputs") != shared_inputs:
        checks.append({"check": "shared-inputs-consistent", "result": "FAIL",
                       "detail": f"policy sharedInputs={policy.get('sharedInputs')!r} != paths.json shared_inputs={shared_inputs!r}"})
        return
    checks.append({"check": "shared-inputs-consistent", "result": "PASS", "detail": f"sharedInputs==paths.json shared_inputs ({len(shared_inputs)} roots)"})

    external = json.loads((repo / EXTERNAL_INDEX).read_text(encoding="utf-8"))
    ext_roots = external.get("shared_roots", {})
    if policy.get("externalAssetsRoots") != ext_roots:
        checks.append({"check": "external-assets-roots-consistent", "result": "FAIL",
                       "detail": f"policy externalAssetsRoots={policy.get('externalAssetsRoots')!r} != external-assets-index shared_roots={ext_roots!r}"})
        return
    checks.append({"check": "external-assets-roots-consistent", "result": "PASS", "detail": f"externalAssetsRoots==external-assets-index shared_roots ({len(ext_roots)} roots)"})

    if policy.get("eDriveProtected") is not True:
        checks.append({"check": "e-drive-protected", "result": "FAIL",
                       "detail": "eDriveProtected must be true"})
        return
    drive = str(policy.get("externalRootDrive", "D:"))
    all_root_values = (*shared_inputs.values(), *ext_roots.values())
    bad = [v for v in all_root_values
           if not str(v).lower().startswith(drive.lower())
           or str(v).upper().startswith("E:")]
    if bad:
        checks.append({"check": "e-drive-protected", "result": "FAIL",
                       "detail": f"external roots must start with {drive!r} and never E: — offenders: {bad}"})
        return
    checks.append({"check": "e-drive-protected", "result": "PASS", "detail": f"all external roots on {drive}"})


def check_allowlist_reviewed(policy: dict, checks: list[dict]) -> None:
    bad = [e for e in policy.get("allowlist_missing", [])
           if not str(e.get("reason", "")).strip() or not str(e.get("approvedIn", "")).strip()]
    if bad:
        checks.append({"check": "allowlist-reviewed", "result": "FAIL",
                       "detail": f"allowlist_missing entries missing reason/approvedIn: {bad}"})
        return
    checks.append({"check": "allowlist-reviewed", "result": "PASS", "detail": f"allowlisted={len(policy.get('allowlist_missing', []))} entries reviewed"})


def check_drift_guard_wired(repo: Path, checks: list[dict]) -> None:
    if not (repo / DRIFT_GUARD).is_file():
        checks.append({"check": "dl-gov-130-guard-present", "result": "FAIL", "detail": f"{DRIFT_GUARD} missing"})
        return
    workflow = (repo / CI_WORKFLOW).read_text(encoding="utf-8")
    if DRIFT_GUARD not in workflow:
        checks.append({"check": "dl-gov-130-ci-wired", "result": "FAIL",
                       "detail": f"{DRIFT_GUARD} not wired into {CI_WORKFLOW}"})
        return
    checks.append({"check": "dl-gov-130-ci-wired", "result": "PASS", "detail": "verify_project_drift.py wired into canonical-verify.yml"})


def checks_all(repo: Path) -> list[dict]:
    out: list[dict] = []
    check_surface(repo, out)
    policy = load_policy(repo, out)
    if policy:
        check_path_refs(repo, policy, out)
        check_machine_policy(policy, repo, out)
        check_allowlist_reviewed(policy, out)
    check_drift_guard_wired(repo, out)
    return out


def main(repo: Path = REPO) -> int:
    results = checks_all(repo)
    failed = [r for r in results if r["result"] != "PASS"]
    for r in results:
        print(f"{r['result']}\t{r['check']}\t{r['detail']}")
    print(f"PATH_REF_GATE={'PASS' if not failed else 'FAIL'} checks={len(results)} failed={[r['check'] for r in failed]}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
