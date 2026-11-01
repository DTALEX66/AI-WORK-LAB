from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'packages/client-neutral-core/scripts'))
sys.path.insert(0,str(ROOT/'services/receipts'))
from observer_projection_adapter import WorkflowProjectionAdapter
from telemetry_ledger import TelemetryLedger
class ObserverProjectionAdapterTests(unittest.TestCase):
 def test_observer_rebuilds_from_workflow_ledger_and_cannot_append(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/'telemetry.jsonl'; TelemetryLedger(path).append({'event_id':'e1','source':'workflow','outcome':'completed'})
   adapter=WorkflowProjectionAdapter(path)
   self.assertEqual(adapter.snapshot()['event_count'],1)
   self.assertEqual(adapter.events_after('e1'),[])
   self.assertEqual(adapter.events_after('missing')[0]['event_id'],'e1')
   with self.assertRaises(PermissionError): adapter.append({'event_id':'e2'})
if __name__=='__main__': unittest.main()
