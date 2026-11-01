# SPDX-License-Identifier: MIT
"""DL-TP-R2-013: LocalStateStore init tests."""
from __future__ import annotations
import tempfile, unittest
from pathlib import Path
import sys
SRC = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(SRC))


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.parent = SRC.parent / '.project-local/task-runtime/state-store-tests'
        self.parent.mkdir(parents=True, exist_ok=True)

    def test_init_creates_tables(self):
        from design_lab.runtime.state_store import init_db, schema_version
        with tempfile.TemporaryDirectory(dir=self.parent) as td:
            conn = init_db(Path(td) / 'test.db')
            self.assertEqual(schema_version(conn), 'v1')
            conn.close()

    def test_unique_idempotency(self):
        from design_lab.runtime.state_store import init_db
        with tempfile.TemporaryDirectory(dir=self.parent) as td:
            conn = init_db(Path(td) / 'test.db')
            conn.execute('INSERT INTO operation_intent VALUES (?,?,?,?,?)', ('op1', 'scope', 'key', 'hash1', '2026-09-04'))
            with self.assertRaises(Exception):
                conn.execute('INSERT INTO operation_intent VALUES (?,?,?,?,?)', ('op2', 'scope', 'key', 'hash2', '2026-09-04'))
            conn.close()


if __name__ == '__main__':
    unittest.main()
