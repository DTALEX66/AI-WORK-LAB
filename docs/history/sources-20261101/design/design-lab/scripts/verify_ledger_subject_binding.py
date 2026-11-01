#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every evidence record claims it observed specific bytes at a specific commit.

`design-lab/config/task-ledger-r3.json` records, per evidence entry, a `subject_sha`, a `binding`, a
`subject_files` map {path: sha256} and an `artifacts` list of the same shape. That is the only
mechanism by which an entry can be checked by someone who was not there -- and until now nothing
checked `subject_files` at all: `verify_evidence_artifact_presence` looks at `artifacts` and asks
whether the file is still on disk, which is a different question from whether the bytes are the ones
the record hashed. So a record could name files that never existed at the commit it binds to, or
publish a digest that does not match those bytes, and stay green.

This gate recomputes each declared digest from `git show <subject_sha>:<path>` -- the object
database, never the working tree, so a later edit to the same path cannot move the answer -- over
BOTH lists, and fails on anything that does not match.

The basis is chosen by the record's own `binding`, which is not a courtesy: `WORKTREE_FILES` means
"the bytes came from a dirty tree and may never be presented as a commit"
(`design-lab/schemas/task-ledger-r5-v1.schema.json:316-317`), so judging such a record by the object
database asks it to reproduce something it disclaims. Those claims are counted and reported as
`worktree_claims=`, never judged by a basis they reject -- and they no longer sit inside KNOWN, which
is where four of them were until 2026-10-08: the list had been absorbing a basis error as if it were
a defect. Paths under `.project-local/task-artifacts/**` are outside the commit basis for the same
reason and are counted as `runtime=` rather than skipped.

The KNOWN list is two-way, the way this repo's other ledgers work: an unsanctioned defect fails, and
a sanctioned entry that has since become verifiable ALSO fails, so the list cannot rot into permanent
excuses for records nobody ever repairs. Rewriting an old record's digests to satisfy the gate would
be fabricating evidence; the honest move is to mark the defect, date it, and let it block anything new.
"""
from __future__ import annotations

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

# One owner for "which paths does this record claim bytes for" -- the current reports project the
# same claims, and the two of them keeping separate copies is what let them disagree on 2026-10-08.
from design_lab.governance.reporting import (  # noqa: E402
    COMMIT_BINDING, DIGEST_CONFLICT, RUNTIME_ARTIFACT_ROOT, WORKTREE_BINDING, basis, claims)

LEDGER = ROOT / 'design-lab/config/task-ledger-r3.json'

MATCH = 'MATCH'
MISMATCH = 'DIGEST_MISMATCH'
ABSENT = 'NOT_IN_BOUND_COMMIT'
NO_COMMIT = 'BOUND_COMMIT_NOT_IN_REPOSITORY'

# (record id, path) -> why this record cannot be made verifiable without fabricating it.
KNOWN = {
# 57 entries of this kind.
    ('r5-006-static-unit-20260928',
     'src/design_lab/readiness/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-006-static-unit-20260928',
     'src/design_lab/readiness/__pycache__/host_matrix.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-006-static-unit-20260928',
     'src/design_lab/readiness/__pycache__/model_radar.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-006-static-unit-20260928',
     'src/design_lab/readiness/__pycache__/reconstruction_bench.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-006-static-unit-20260928',
     'src/design_lab/readiness/__pycache__/vector_provider.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-008-static-unit-20260928',
     'src/design_lab/generators/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-008-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_http.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-008-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_task.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-009-static-unit-20260928',
     'src/design_lab/reconstruction/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-013-static-unit-20260928',
     'src/design_lab/reconstruction/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'packages/capabilities/quality/jury/__pycache__/check_anti_slop.cpython-311.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'packages/capabilities/quality/jury/__pycache__/check_anti_slop.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'src/design_lab/assurance/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'src/design_lab/assurance/__pycache__/human_jury.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'src/design_lab/assurance/__pycache__/knowledge_feedback.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'src/design_lab/assurance/__pycache__/qa_plane.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-014-static-unit-20260928',
     'src/design_lab/assurance/__pycache__/quality_record.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/delivery_receipt.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/dtcg.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/penpot.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/provenance.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-016-static-unit-20260928',
     'src/design_lab/interop/__pycache__/timeline.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/delivery_receipt.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/dtcg.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/penpot.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/provenance.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-017-static-unit-20260928',
     'src/design_lab/interop/__pycache__/timeline.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/delivery_receipt.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/dtcg.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/penpot.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/provenance.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-019-static-unit-20260928',
     'src/design_lab/interop/__pycache__/timeline.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/delivery_receipt.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/dtcg.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/penpot.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/provenance.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-020-static-unit-20260928',
     'src/design_lab/interop/__pycache__/timeline.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/delivery_receipt.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/dtcg.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/penpot.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/provenance.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-022-static-unit-20260928',
     'src/design_lab/interop/__pycache__/timeline.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-024-static-unit-20260928',
     'src/design_lab/adapters/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-024-static-unit-20260928',
     'src/design_lab/adapters/__pycache__/illustrator_com.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-024-static-unit-20260928',
     'src/design_lab/adapters/__pycache__/photoshop_com.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-024-static-unit-20260928',
     'src/design_lab/adapters/__pycache__/spi.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-025-static-unit-20260928',
     'src/design_lab/generators/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-025-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_http.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-025-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_task.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-026-static-unit-20260928',
     'src/design_lab/generators/__pycache__/__init__.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-026-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_http.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
    ('r5-026-static-unit-20260928',
     'src/design_lab/generators/__pycache__/comfy_task.cpython-313.pyc'): '2026-09-28 static-unit subject list includes an interpreter cache file. The digest matches those bytes, but a .pyc is not tracked, so no commit can ever reproduce it.',
# 6 entries of this kind.
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/anomaly.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/bgm-anomaly-pressure-loop.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/bgm-night-shift-loop.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/boot.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/click.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
    ('r5-027-static-unit-20260928',
     'fixtures/domains/game-visual/android-minigame/audio/lockdown.wav'): '2026-09-28 record binds 4c9f1849, before this generated audio fixture was committed; the digest came from disk.',
}





def default_reader(commit: str, path: str):
    """Bytes of `path` at `commit`, or None when that commit has no such blob."""
    result = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'],
                            capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout


def commit_exists(commit: str) -> bool:
    return subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', commit],
                          capture_output=True).returncode == 0


def tally(records) -> dict:
    """Counts the OK line must carry, so a narrowed basis is visible instead of silent."""
    commit_claims = worktree_claims = runtime_pairs = 0
    for record in records:
        state = claims(record)
        versioned = len(state.versioned())
        if basis(record) == WORKTREE_BINDING:
            worktree_claims += versioned
        else:
            commit_claims += versioned
        runtime_pairs += len(state.runtime)
    return {'commit_claims': commit_claims, 'runtime': runtime_pairs,
            'worktree_claims': worktree_claims,
            'subject_files': sum(len(record.get('subject_files') or {}) for record in records)}


def classify(records, reader, exists) -> list[tuple[str, str, str]]:
    """[(kind, record_id, path)] for every committed-bytes claim that cannot be reproduced.

    The basis follows the record's own `binding`. A WORKTREE_FILES entry disclaims commit status
    ("may never be presented as a commit"), so recomputing it from the object database measures
    something it never claimed; those are counted by `tally` instead. Four such claims sat in KNOWN
    until 2026-10-08 as excused defects, which is a basis error being paid for by the waiver list.
    """
    defects: list[tuple[str, str, str]] = []
    for record in records:
        identity = record.get('id', '(unidentified record)')
        commit = (record.get('subject_sha') or '').strip()
        state = claims(record)
        for path in state.conflicts:
            defects.append((DIGEST_CONFLICT, identity, path))
        claimed = state.versioned()
        if basis(record) != COMMIT_BINDING:
            continue
        if not claimed:
            continue
        if not commit or not exists(commit):
            for path in claimed:
                defects.append((NO_COMMIT, identity, path))
            continue
        for path, declared in claimed.items():
            blob = reader(commit, path)
            if blob is None:
                defects.append((ABSENT, identity, path))
            elif sha256(blob).hexdigest() != declared:
                defects.append((MISMATCH, identity, path))
    return defects


def partition(defects):
    unsanctioned, stale = [], []
    hit = set()
    for kind, record_id, path in defects:
        key = (record_id, path)
        if key in KNOWN:
            hit.add(key)
        else:
            unsanctioned.append((kind, record_id, path))
    for key in KNOWN:
        if key not in hit:
            stale.append(key)
    return sorted(unsanctioned), sorted(stale)


def main() -> int:
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    records = ledger.get('evidence', [])
    defects = classify(records, default_reader, commit_exists)
    unsanctioned, stale = partition(defects)
    if unsanctioned:
        print(f'LEDGER_SUBJECT_BINDING=FAIL unsanctioned={len(unsanctioned)}')
        for kind, record_id, path in unsanctioned:
            print(f'  {kind} {record_id} :: {path}')
        return 1
    if stale:
        print(f'LEDGER_SUBJECT_BINDING=FAIL stale_known={len(stale)}')
        for record_id, path in stale:
            print(f'  now verifiable but still listed as a known defect: {record_id} :: {path}')
        return 1
    counts = tally(records)
    print(f'LEDGER_SUBJECT_BINDING=OK checked={counts["commit_claims"]} '
          f'subject_files={counts["subject_files"]} runtime={counts["runtime"]} '
          f'worktree_claims={counts["worktree_claims"]} '
          f'known_unverifiable={len(defects)} records={len(records)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
