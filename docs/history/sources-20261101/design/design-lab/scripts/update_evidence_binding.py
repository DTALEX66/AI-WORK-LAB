#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-EVD-003: evidence binding freshness (rewrite of DL-EVD-001 semantics).

States (only CURRENT_EXACT supports the current release):
- CURRENT_EXACT     lastVerifiedTree == HEAD tree (runtime attestation only;
                    a COMMITTED index must never self-claim the current tree —
                    DL-EVD-002 forbids "commit N proves commit N")
- HISTORICAL_VALID  lastVerifiedTree is the tree of an ancestor commit;
                    requiresRequalification=true (never supports current release)
- STALE             a valid tree object, but not on HEAD ancestry
- UNRESOLVABLE      missing / malformed binding

Usage:
  python update_evidence_binding.py --check   freshness of the committed binding
  python update_evidence_binding.py           rebind lastVerifiedTree to current
                                              HEAD tree (commit N+1 proves N)
  python update_evidence_binding.py --attestation
                                              emit a runtime Evidence Attestation
                                              (subjectCommitSha/subjectTreeSha) to
                                              .project-local/task-runtime/ (not committed);
                                              this is the CURRENT_EXACT artifact
                                              the release gate consumes
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.runtime.paths import resolve_paths
INDEX = ROOT / "design-lab" / "config" / "capability-evidence-index.json"
BINDING_KEY = "lastVerifiedTree"

SHA40 = "0123456789abcdef"


def git(args: list[str]) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def git_head() -> str:
    return git(["rev-parse", "HEAD"])


def git_tree(commit: str) -> str:
    return git(["rev-parse", commit + "^{tree}"])


def ancestor_trees(head: str) -> set[str]:
    """All commit tree SHAs on HEAD ancestry (one pass)."""
    out = git(["log", "--format=%T", head])
    return set(out.splitlines()) if out else set()


def compute_state(bound: str, head: str, head_tree: str) -> str:
    if not bound or len(bound) != 40 or any(c not in SHA40 for c in bound):
        return "UNRESOLVABLE"
    if bound == head_tree:
        return "CURRENT_EXACT"
    if bound in ancestor_trees(head):
        return "HISTORICAL_VALID"
    return "STALE"


def check() -> tuple[str, str]:
    head = git_head()
    if not head:
        return "UNRESOLVABLE", "git HEAD unresolvable"
    try:
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "UNRESOLVABLE", f"index unreadable: {exc}"
    bound = index.get(BINDING_KEY, "")
    head_tree = git_tree(head)
    state = compute_state(bound, head, head_tree)
    if state == "CURRENT_EXACT":
        msg = "committed index must not self-claim the current tree (DL-EVD-002); use a CI runtime attestation instead"
    elif state == "HISTORICAL_VALID":
        msg = f"ancestor binding {bound[:12]} -> requiresRequalification=true; supports HISTORICAL_VALID only"
    elif state == "STALE":
        msg = f"binding {bound[:12]} not on HEAD ancestry; re-run update_evidence_binding.py to rebind"
    else:
        msg = f"binding missing/malformed ({bound[:12]!r}); re-run update_evidence_binding.py to rebind"
    return state, msg


def main() -> int:
    if "--attestation" in sys.argv:
        attestation_root = resolve_paths(project_root=ROOT).category_dir('runtime', 'evidence')
        head = git_head()
        head_tree = git_tree(head) if head else ""
        if not head or not head_tree:
            print("EVIDENCE_ATTESTATION=FAIL (git HEAD/tree unresolvable)")
            return 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        attestation = {
            "attestationId": f"dl-evidence-{stamp}",
            "subjectCommitSha": head,
            "subjectTreeSha": head_tree,
            "producer": "dsh-local (update_evidence_binding.py --attestation)",
            "environment": "Windows local; host-neutral",
            "command": "python design-lab/scripts/update_evidence_binding.py --attestation",
            "exitCode": 0,
            "artifactDigests": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "reviewer": None,
            "evidenceLevel": "E1",
            "requiresRequalification": False,
            "notes": "runtime attestation generated outside Git; commit N+1 proves N only; not self-referential",
        }
        attestation_root.mkdir(parents=True, exist_ok=True)
        out = attestation_root / f"attestation-{stamp}.json"
        out.write_text(json.dumps(attestation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"EVIDENCE_ATTESTATION=OK subject={head[:12]} tree={head_tree[:12]} file={out}")
        print("EVIDENCE_ATTESTATION=CURRENT_EXACT (runtime; not committed)")
        return 0

    if "--check" in sys.argv:
        state, msg = check()
        print(f"UPDATE_EVIDENCE_BINDING={state} {msg}")
        # committed index: HISTORICAL_VALID is the honest steady state;
        # CURRENT_EXACT (self-claim) / STALE / UNRESOLVABLE are failures
        return 0 if state == "HISTORICAL_VALID" else 1

    # default: rebind to current HEAD tree (commit N+1 will then prove N)
    head = git_head()
    if not head:
        print("UPDATE_EVIDENCE_BINDING=FAIL (git HEAD unresolvable)")
        return 1
    head_tree = git_tree(head)
    try:
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"UPDATE_EVIDENCE_BINDING=FAIL ({exc})")
        return 1
    prev = index.get(BINDING_KEY, "")
    index[BINDING_KEY] = head_tree
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"UPDATE_EVIDENCE_BINDING=OK lastVerifiedTree {prev[:12] or '(none)'} -> {head_tree[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
