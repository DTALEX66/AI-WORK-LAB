from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/orchestration'))
from sidecar_lock import SingleInstanceLock
class SidecarLockTests(unittest.TestCase):
 def test_second_instance_is_rejected_and_release_recovers(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/'sidecar.lock'
   first=SingleInstanceLock(path); first.acquire()
   with self.assertRaises(RuntimeError): SingleInstanceLock(path).acquire()
   first.release()
   second=SingleInstanceLock(path); second.acquire(); second.release()

 def test_status_reports_owner_and_acquired_at_without_touching_lock(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/'sidecar.lock'
   self.assertIsNone(SingleInstanceLock(path).status())
   lock=SingleInstanceLock(path); lock.acquire()
   status=SingleInstanceLock(path).status()
   self.assertIsNotNone(status)
   assert status is not None
   self.assertEqual(status['pid'], __import__('os').getpid())
   self.assertIs(status['alive'], True)
   self.assertIn('acquired_at', status)
   self.assertIn('token', status)
   lock.release()
   self.assertIsNone(SingleInstanceLock(path).status())

 def test_stale_pid_is_recovered_but_malformed_owner_fails_closed(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/'sidecar.lock'
   path.write_text(json.dumps({'pid': 2147483647, 'token': 'stale'}), encoding='utf-8')
   lock=SingleInstanceLock(path); lock.acquire(); lock.release()
   self.assertFalse(path.exists())
   path.write_text('not-json', encoding='utf-8')
   with self.assertRaisesRegex(RuntimeError, 'sidecar_lock_unreadable'):
    SingleInstanceLock(path).acquire()
   self.assertEqual(path.read_text(encoding='utf-8'), 'not-json')

 def test_live_subprocess_owner_rejects_competing_process(self):
  with tempfile.TemporaryDirectory() as raw:
   path=Path(raw)/'sidecar.lock'
   script=(
   "import sys; from pathlib import Path; "
    f"sys.path.insert(0, {str(ROOT / 'services/orchestration')!r}); "
    "from sidecar_lock import SingleInstanceLock; "
    "lock=SingleInstanceLock(Path(sys.argv[1])); lock.acquire(); "
    "print('READY', flush=True); sys.stdin.readline(); lock.release()"
   )
   process=subprocess.Popen(
    [sys.executable, '-c', script, str(path)],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
   )
   try:
    self.assertEqual(process.stdout.readline().strip(), 'READY')
    with self.assertRaisesRegex(RuntimeError, 'sidecar_already_running'):
     SingleInstanceLock(path).acquire()
   finally:
    if process.stdin:
     process.stdin.write('\n'); process.stdin.flush()
    return_code=process.wait(timeout=10)
    error=process.stderr.read() if process.stderr else ''
    try:
     self.assertEqual(return_code, 0, error)
    finally:
     for stream in (process.stdin, process.stdout, process.stderr):
      if stream:
       stream.close()
if __name__=='__main__': unittest.main()
