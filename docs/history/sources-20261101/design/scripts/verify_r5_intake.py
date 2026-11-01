# SPDX-License-Identifier: MIT
"""Read-only frozen R5 intake gate; never adopts or promotes task states."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/history/taskpacks/r5-20260908'
EXPECTED_IDS={f'DL-R5-{i:03d}' for i in range(1,29)}
AXES=dict(implementation='REASSESS_FROM_R3',unit='REASSESS_FROM_R3',
          host_live='NOT_VERIFIED_BY_THIS_AUDIT',delivery='NOT_ACCEPTED')


def validate(document):
    def require(condition,message):
        if not condition:raise ValueError(message)
    require(isinstance(document,dict),'taskpack must be an object')
    require(document.get('schemaVersion')=='design-lab/taskpack-r5/v1'
        and document.get('id')=='DL-TP-20260908-R5'
        and document.get('status')=='PLAN_DELIVERED_NOT_IMPLEMENTED','wrong intake identity/state')
    items=document.get('tasks')
    require(isinstance(items,list) and len(items)==28,'expected 28 tasks')
    tasks={}
    required={'id','title','depends_on','priority','execution_state','baseline_observation',
              'implementation','acceptance','rollback','evidence_required','axes','execution_owner'}
    for task in items:
        require(isinstance(task,dict),'task must be an object')
        identity=task.get('id')
        require(isinstance(identity,str) and identity in EXPECTED_IDS and identity not in tasks,'invalid/duplicate ID')
        extra={'conditional_dependencies'} if identity=='DL-R5-019' else ({'conditional_gate'} if identity in {'DL-R5-008','DL-R5-024'} else set())
        require(set(task)==required|extra,'missing/unknown task fields')
        if 'conditional_dependencies' in extra:
            require(task['conditional_dependencies']==dict(TTS_required='DL-R5-016',generated_music_required='DL-R5-017'),'invalid conditional media dependencies')
        if 'conditional_gate' in extra:
            require(isinstance(task['conditional_gate'],str) and bool(task['conditional_gate'].strip()),'missing optional gate policy')
        require(task['execution_state']=='PLANNED_DELTA' and task['axes']==AXES,'intake cannot promote evidence')
        for field in ('title','priority','baseline_observation','implementation','rollback','execution_owner'):
            require(isinstance(task[field],str) and bool(task[field].strip()),'empty task text: '+field)
        for field in ('acceptance','evidence_required','depends_on'):
            values=task[field]
            require(isinstance(values,list) and all(isinstance(v,str) and v.strip() for v in values),'invalid list: '+field)
            require(len(set(values))==len(values),'duplicate list entries: '+field)
            if field!='depends_on':require(bool(values),'empty list: '+field)
        require(set(task['depends_on'])<=EXPECTED_IDS,'unknown dependency')
        tasks[identity]=task
    require(set(tasks)==EXPECTED_IDS,'task inventory mismatch')
    visiting=set();done=set();order=[]
    def visit(identity):
        require(identity not in visiting,'cyclic dependency')
        if identity in done:return
        visiting.add(identity)
        for dependency in tasks[identity]['depends_on']:visit(dependency)
        visiting.remove(identity);done.add(identity);order.append(identity)
    for identity in tasks:visit(identity)
    ancestors=set()
    def collect(identity):
        for dependency in tasks[identity]['depends_on']:
            if dependency not in ancestors:
                ancestors.add(dependency);collect(dependency)
    collect('DL-R5-015')
    require(not ancestors & {'DL-R5-008','DL-R5-018','DL-R5-024'},'optional runtime blocks Adobe M1')
    return order


def main():
    # Pinned source definition, not merely a mutable adjacent checksum list.
    raw=(SOURCE/'tasks.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='31dde89eb4ede81fe88c0a5c5144adfb86af8db4c4d8c263bde2199180369b69':
        raise ValueError('frozen R5 task definition changed')
    order=validate(json.loads(raw))
    print(json.dumps(dict(status='R5_INTAKE_VERIFIED_NOT_ADOPTED',tasks=len(order),order=order)))


if __name__=='__main__':main()
