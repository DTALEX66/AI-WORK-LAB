# SPDX-License-Identifier: MIT
"""Versioned R5 reporting contract; predecessor links never qualify new work."""
import copy
from datetime import datetime
import hashlib
import re
from jsonschema import Draft202012Validator, FormatChecker

SOURCE_PATH = 'docs/history/taskpacks/r5-20260908/tasks.json'
SOURCE_HASH = '31dde89eb4ede81fe88c0a5c5144adfb86af8db4c4d8c263bde2199180369b69'
PREDECESSOR_PATH = 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json'
PREDECESSOR_HASH = '2df7e722b96443dbfa451060f6747cfff135fa48847eb6eb212fae5fe46d65fb'
SUCCESSORS = {
    'R3-01': (1,), 'R3-02': (2,), 'R3-03': (1, 23), 'R3-04': (3,),
    'R3-05': (4,), 'R3-06': (5,), 'R3-07': (6,), 'R3-08': (7,),
    'R3-09': (9,), 'R3-10': (10,), 'R3-11': (11, 24), 'R3-12': (12, 24),
    'R3-13': (13,), 'R3-14': (14,), 'R3-15': (15,), 'R3-16': (8, 25, 26),
    'R3-17': (16,), 'R3-18': (17,), 'R3-19': (18,), 'R3-20': (19, 25),
    'R3-21': (21,), 'R3-22': (20,), 'R3-23': (22, 27), 'R3-24': (23,),
}
# Required actual-host and delivery evidence follows task acceptance, not priority.
HOST = {2, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27}
DELIVERY = {3, 9, 15, 23, 28}


def validate_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('expected an RFC3339 date-time')
    datetime.fromisoformat(value)


def required_axes(identity):
    number = int(identity.rsplit('-', 1)[1])
    return ['implementation', 'unit'] + (['host_live'] if number in HOST else []) + (['delivery'] if number in DELIVERY else [])


def validate(reader, ledger, validate_r3):
    source_raw = reader.read(SOURCE_PATH)
    previous_raw = reader.read(PREDECESSOR_PATH)
    if hashlib.sha256(source_raw).hexdigest() != SOURCE_HASH or hashlib.sha256(previous_raw).hexdigest() != PREDECESSOR_HASH:
        raise ValueError('frozen R5 source or R3 predecessor changed')
    source = reader.json(SOURCE_PATH)
    previous = reader.json(PREDECESSOR_PATH)
    validate_r3(reader, previous)
    schema = copy.deepcopy(reader.json('design-lab/schemas/task-ledger-r3.schema.json'))
    props = schema['properties']
    props['schemaVersion'] = {'const': 'design-lab/task-ledger/r5-v1'}
    props['taskpack'] = {'const': source['id']}
    props['baseline_sha'] = {'const': source['developmentSha']}
    props['plan_path'] = {'const': 'docs/history/taskpacks/r5-20260908/02-TASKS.md'}
    props['source'] = {'const': {'path': SOURCE_PATH, 'sha256': SOURCE_HASH}}
    props['predecessor'] = {'const': {'taskpack': previous['taskpack'], 'sha256': PREDECESSOR_HASH, 'ledger': previous}}
    if 'currentExecution' in ledger:
        from .current_execution import schema as current_schema, validate as validate_current
        props['currentExecution'] = current_schema()
        validate_current(reader, ledger)
    schema['required'].append('predecessor')
    props['tasks']['minItems'] = props['tasks']['maxItems'] = 28
    task_schema = props['tasks']['items']
    task_schema['additionalProperties'] = False
    task_schema['required'] = ['id', 'title', 'depends_on', 'definition', 'predecessor_task_ids', 'reassessment', 'required_axes', 'axes']
    task_schema['properties']['id']['pattern'] = '^DL-R5-(00[1-9]|01[0-9]|02[0-8])$'
    task_schema['properties'].update({
        'definition': {'type': 'object'},
        'predecessor_task_ids': {'type': 'array', 'uniqueItems': True, 'items': {'type': 'string'}},
        'reassessment': {'enum': ['PENDING_EVIDENCE_REVIEW', 'REVIEWED']},
        'condition_decisions': {'type': 'object', 'additionalProperties': {
            'type': 'object', 'additionalProperties': False, 'required': ['required', 'reason'],
            'properties': {'required': {'type': 'boolean'}, 'reason': {'type': 'string', 'pattern': '\\S'}}}},
    })
    props['evidence']['items']['properties']['task_ids']['items']['pattern'] = '^DL-R5-(00[1-9]|01[0-9]|02[0-8])$'
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(ledger))
    if errors:
        raise ValueError('invalid R5 ledger contract at ' + '/'.join(map(str, errors[0].path)))
    validate_timestamp(ledger['updated_at'])
    for receipt in ledger['evidence']:
        validate_timestamp(receipt['observed_at'])
    tasks = {t['id']: t for t in ledger['tasks']}
    originals = {t['id']: t for t in source['tasks']}
    if len(tasks) != 28 or set(tasks) != set(originals):
        raise ValueError('R5 task inventory mismatch')
    receipts = {e['id']: e for e in ledger['evidence']}
    if len(receipts) != len(ledger['evidence']):
        raise ValueError('duplicate R5 evidence ID')
    for identity, task in tasks.items():
        number = int(identity.rsplit('-', 1)[1])
        old_ids = [old for old, successors in SUCCESSORS.items() if number in successors]
        conditions = task['definition'].get('conditional_dependencies', {})
        if not set(task.get('condition_decisions', {})) <= set(conditions):
            raise ValueError('unknown R5 case condition')
        if (task['definition'] != originals[identity] or task['title'] != originals[identity]['title']
                or task['depends_on'] != originals[identity]['depends_on']
                or task['predecessor_task_ids'] != old_ids
                or task['required_axes'] != required_axes(identity)):
            raise ValueError('R5 definition, mapping or required axes changed: ' + identity)
        for name, axis in task['axes'].items():
            if name != 'implementation' and axis['state'] == 'IMPLEMENTED_LOCAL':
                raise ValueError('implementation cannot qualify another axis')
            if name in task['required_axes'] and axis['state'] == 'NOT_REQUIRED':
                raise ValueError('required R5 axis cannot be waived')
            if any(eid not in receipts for eid in axis['evidence']):
                raise ValueError('unknown R5 evidence reference')
            if task['reassessment'] != 'REVIEWED' and axis['state'] in {'PASS', 'IMPLEMENTED_LOCAL'}:
                raise ValueError('R5 completion requires explicit evidence reassessment')
    order = []
    visiting = set()
    def visit(identity):
        if identity in visiting:
            raise ValueError('cyclic R5 dependencies')
        if identity in order:
            return
        visiting.add(identity)
        for dependency in tasks[identity]['depends_on']:
            visit(dependency)
        for condition, dependency in tasks[identity]['definition'].get('conditional_dependencies', {}).items():
            if tasks[identity].get('condition_decisions', {}).get(condition, {}).get('required'):
                visit(dependency)
        visiting.remove(identity)
        order.append(identity)
    for identity in tasks:
        visit(identity)
    reader.read(ledger['plan_path'])
    return tasks, receipts, order
