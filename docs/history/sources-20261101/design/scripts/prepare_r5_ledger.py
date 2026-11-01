# SPDX-License-Identifier: MIT
"""Build a lossless R5 migration candidate in memory; never activate or write it."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.governance.reporting import Reader, _json, _validate
from verify_r5_intake import validate
from design_lab.governance.r5_contract import required_axes, validate_timestamp, SUCCESSORS

SOURCE_PATH = 'docs/history/taskpacks/r5-20260908/tasks.json'
SOURCE_HASH = '31dde89eb4ede81fe88c0a5c5144adfb86af8db4c4d8c263bde2199180369b69'
# Reviewed R3 -> R4.1 mapping, then the frozen one-to-one R4 -> R5 crosswalk.
# These are scope links, not evidence qualification or completion transfer.


def prepare(root, predecessor_raw, source_raw, *, updated_at):
    """Validate both sources and return an unaccepted, non-active candidate.

    The complete predecessor is embedded so no task or receipt is orphaned.
    Its digest binds original bytes, not a JSON reserialization. Activation must
    additionally preserve those bytes and validate the versioned report contract.
    """
    if hashlib.sha256(source_raw).hexdigest() != SOURCE_HASH:
        raise ValueError('frozen R5 task definition changed')
    validate_timestamp(updated_at)
    source = _json(source_raw)
    validate(source)
    predecessor = _json(predecessor_raw)
    if predecessor.get('schemaVersion') != 'design-lab/task-ledger/r3-v1':
        raise ValueError('only a validated R3 predecessor can be migrated')
    reader = Reader(root)
    _validate(reader, predecessor)
    reader.stable()
    tasks = []
    for definition in source['tasks']:
        identity = definition['id']
        number = int(identity.rsplit('-', 1)[1])
        tasks.append({
            'id': identity, 'title': definition['title'],
            'depends_on': list(definition['depends_on']),
            'definition': copy.deepcopy(definition),
            'predecessor_task_ids': [old for old, successors in SUCCESSORS.items() if number in successors],
            'reassessment': 'PENDING_EVIDENCE_REVIEW',
            'required_axes': required_axes(identity),
            'axes': {axis: {'state': 'PARTIAL', 'evidence': []}
                     for axis in ('implementation', 'unit', 'host_live', 'delivery')},
        })
    return {
        'schemaVersion': 'design-lab/task-ledger/r5-v1',
        'taskpack': source['id'],
        'plan_path': 'docs/history/taskpacks/r5-20260908/02-TASKS.md',
        'baseline_sha': source['developmentSha'],
        'updated_at': updated_at,
        'source': {'path': SOURCE_PATH, 'sha256': SOURCE_HASH},
        'predecessor': {'taskpack': predecessor['taskpack'],
                        'sha256': hashlib.sha256(predecessor_raw).hexdigest(),
                        'ledger': copy.deepcopy(predecessor)},
        'tasks': tasks, 'evidence': [],
    }


def main():
    previous = (ROOT / 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json').read_bytes()
    result = prepare(ROOT, previous, (ROOT / SOURCE_PATH).read_bytes(),
                     updated_at=_json(previous)['updated_at'])
    print(json.dumps({'status': 'CANDIDATE_PREPARED_NOT_ADOPTED',
                      'tasks': len(result['tasks']),
                      'preserved_tasks': len(result['predecessor']['ledger']['tasks']),
                      'preserved_receipts': len(result['predecessor']['ledger']['evidence']),
                      'predecessor_sha256': result['predecessor']['sha256']}))


if __name__ == '__main__':
    main()
