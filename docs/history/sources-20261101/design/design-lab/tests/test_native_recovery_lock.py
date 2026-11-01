# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess
import queue
import threading
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


class NativeRecoveryLockTests(unittest.TestCase):
    def test_other_process_cannot_take_live_lock_but_can_after_owner_exits(self):
        from design_lab.runtime.native_recovery_lock import recovery_lock, RecoveryBusy
        from design_lab.runtime.paths import resolve_paths
        parent = ROOT / '.project-local/task-runtime/recovery-lock-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temp:
            root = Path(temp)
            (root / 'AGENTS.md').write_text('# controlled fixture', encoding='utf-8')
            paths = resolve_paths(project_root=root, environ={})
            code = (
                'import sys; sys.path.insert(0,sys.argv[1]); '
                'from design_lab.runtime.paths import resolve_paths; '
                'from design_lab.runtime.native_recovery_lock import recovery_lock; '
                'p=resolve_paths(project_root=sys.argv[2],environ={}); '
                'c=recovery_lock(p,"attempt-test"); c.__enter__(); '
                'print("READY",flush=True); sys.stdin.readline()'
            )
            child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', code, str(ROOT/'src'), str(root)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            try:
                ready = queue.Queue()
                thread = threading.Thread(target=lambda: ready.put(child.stdout.readline()), daemon=True)
                thread.start()
                self.assertEqual(ready.get(timeout=10).strip(), 'READY')
                with self.assertRaises(RecoveryBusy):
                    with recovery_lock(paths, 'attempt-test'):
                        self.fail('live recovery lock stolen')
                # Only this test-owned helper is terminated; simulate worker crash.
                child.kill()
                child.communicate(timeout=10)
                with recovery_lock(paths, 'attempt-test'):
                    pass
                self.assertEqual(len(list((paths.runtime_root/'native-recovery-locks').glob('*.lock'))), 1)
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)


if __name__ == '__main__':
    unittest.main()
