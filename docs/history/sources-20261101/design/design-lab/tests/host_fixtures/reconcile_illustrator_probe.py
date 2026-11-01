# SPDX-License-Identifier: MIT
"""Quiesce only the identified failed text probe; preserve all its artifacts."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from design_lab.service import ProjectService
from design_lab.native_tasks import NativeTasks

service=ProjectService(ROOT)
run=service.paths.checked_path(ROOT/'.project-local/task-artifacts/text-position-probe-20260908/run-752fbabb7d704289966b0d2685b88b70')
aid='att-f1e6d74abb744c638f9f63c42def0695'
with closing(sqlite3.connect(service.database.as_uri()+'?mode=ro',uri=True)) as conn:
    row=conn.execute('SELECT request_json FROM native_execution_v1 WHERE attempt_id=?',(aid,)).fetchone()
if not row or Path(json.loads(row[0])['job']['runRoot'])!=run:raise ValueError('unexpected attempt owner')
output=run/'quiescence-readback.json'
if output.exists():raise ValueError('preserve prior receipt')
result=NativeTasks(service).quiesce_illustrator(aid,authorization=dict(actor='user',scope='project-native-test',
    receipt='active goal authorizes recovery of this new diagnostic document; preserve files and failed outcome'))
output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
