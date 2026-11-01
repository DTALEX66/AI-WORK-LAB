# SPDX-License-Identifier: MIT
"""Run with the installed interpreter -I; qualify a freshly prepared native job.

Arguments: project root, illustrator|photoshop, project-local job JSON.
Creates only a new qualification project; never claims complex-reference E3.
"""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from design_lab.service import ProjectService
from design_lab.native_tasks import NativeTasks
import design_lab.native_tasks as native_module


def main():
    root=Path(sys.argv[1]);host=sys.argv[2]
    if host not in ('illustrator','photoshop'):raise ValueError('unsupported host')
    service=ProjectService(root);paths=service.paths
    job_path=paths.checked_path(sys.argv[3]);job=json.loads(job_path.read_text(encoding='utf-8'))
    run=paths.checked_path(job['runRoot']);result_path=run/'native-task-readback.json'
    if result_path.exists():raise ValueError('qualification result already exists')
    project=service.create_project('Native '+host+' durable qualification')
    authorization=dict(actor='user',scope='project-native-test',
        receipt='active goal authorizes software tests in new project-local documents')
    def invoke(current):
        return NativeTasks(current).execute(project['id'],host,job,idempotency_key='native-installed-qualification',
            approved_root=run,authorization=authorization)
    first=invoke(service);second=invoke(ProjectService(root))
    assert first['asset']==second['asset'] and first['attempt']==second['attempt'] and second['attempt']['state']=='RECEIPTED'
    with closing(sqlite3.connect(service.database)) as conn:
        aid=first['attempt']['attempt_id']
        count=conn.execute("SELECT COUNT(*) FROM attempt_event WHERE attempt_id=? AND to_state='RUNNING'",(aid,)).fetchone()[0]
        guard=conn.execute('SELECT COUNT(*) FROM native_host_guard_v1 WHERE attempt_id=?',(aid,)).fetchone()[0]
    assert count==1 and guard==0
    proof=dict(status='NATIVE_TASK_REPLAY_VERIFIED',observed_at=datetime.now(timezone.utc).isoformat(),
        module=native_module.__file__,module_sha256=hashlib.sha256(Path(native_module.__file__).read_bytes()).hexdigest(),
        repo_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        project_id=project['id'],dispatch_events=count,remaining_host_guards=guard,result=second)
    result_path.write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(dict(run=str(run),proof=proof)))


if __name__=='__main__':main()
