# SPDX-License-Identifier: MIT
"""Explicitly reconcile a failed owned run; never clear a guard with raw SQL."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.native_tasks import NativeTasks

service=ProjectService(ROOT);run=service.paths.checked_path(sys.argv[1])
output=run/'quiescence-readback.json'
if not run.is_dir() or output.exists():raise ValueError('new recovery receipt required')
with closing(sqlite3.connect(service.database.as_uri()+'?mode=ro',uri=True)) as conn:
    rows=conn.execute('SELECT g.attempt_id,e.request_json FROM native_host_guard_v1 g JOIN native_execution_v1 e ON g.attempt_id=e.attempt_id WHERE g.host=?',('illustrator',)).fetchall()
matches=[aid for aid,request in rows if Path(json.loads(request)['job']['runRoot'])==run]
if len(matches)!=1:raise ValueError('run does not uniquely own current guard')
result=NativeTasks(service).quiesce_illustrator(matches[0],authorization=dict(actor='user',scope='project-native-test',
    receipt='active goal authorizes recovery of this identified new test run; preserve outputs and unknown outcome'))
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
