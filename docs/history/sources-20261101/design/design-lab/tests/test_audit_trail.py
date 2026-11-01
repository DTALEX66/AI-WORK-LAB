# SPDX-License-Identifier: MIT
"""The writer journal must be readable, or it is not an audit trail.

`audit_event` rows were written by the asset store and read by nothing in the product. These
cases pin the read path -- including the row-value cursor, which exists because ordering by a
timestamp alone cannot page without repeating or dropping a row -- and one of them is a
standing guard that the journal can never go back to being write-only.
"""
from __future__ import annotations

import ast
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.runtime import asset_store  # noqa: E402
from design_lab.runtime import audit_trail  # noqa: E402


class FakePaths:
    def __init__(self, database):
        self._database = database

    def database_path(self, _name):
        return self._database


class FakeService:
    """The module only needs a path policy and a database name, so nothing is faked about
    either: the connection is the product's own read-only open."""

    def __init__(self, database):
        self.paths = FakePaths(database)
        self.database = database


class JournalReadTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/audit-trail-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        # The store's own path policy refuses a database whose owning project marker is
        # absent, so the fixture is a real project root and not just a directory.
        (self.root / 'AGENTS.md').write_text('# synthetic owner project', encoding='utf-8')
        self.database = self.root / '.project-local/task-runtime/service/state.db'
        self.service = FakeService(self.database)
        self.conn = asset_store.connect(self.database, project_root=self.root)
        self.addCleanup(self.conn.close)

    def take_over(self, holder):
        asset_store.takeover_writer(self.conn, 'psd:one.psd', holder, lease_seconds=60)

    def test_a_lease_takeover_can_be_read_back(self):
        self.take_over('att-' + 'a' * 32)
        self.conn.commit()
        read = audit_trail.recent(self.service)
        self.assertEqual(read['status'], 'PRESENT', read)
        self.assertEqual(read['counts'], {'writer_takeover': 1})
        event = read['events'][0]
        self.assertEqual(event['actor'], 'att-' + 'a' * 32,
                         'the actor is the attempt that took the lease over, verbatim')
        self.assertEqual(event['kind'], 'writer_takeover')
        self.assertIn('psd:one.psd', read['events'][0]['action'],
                        'the action names the resource that was taken over')

    def test_a_project_with_no_database_says_so_instead_of_claiming_zero_events(self):
        missing = FakeService(self.root / 'nowhere' / 'state.db')
        read = audit_trail.recent(missing)
        self.assertEqual(read['status'], 'NO_STATE_DATABASE', read)
        self.assertEqual(read['events'], [])

    def test_an_empty_journal_is_empty_and_not_an_error(self):
        with closing(asset_store.connect(self.database, project_root=self.root)):
            pass
        self.assertEqual(audit_trail.recent(self.service)['status'], 'EMPTY')

    def test_paging_neither_repeats_nor_drops_a_row(self):
        for index in range(3):
            self.take_over('att-' + hex(index)[2:].lower().zfill(32))
        self.conn.commit()
        first = audit_trail.recent(self.service, limit=2)
        self.assertEqual(len(first['events']), 2, first)
        self.assertIsNotNone(first['next_cursor'], 'three rows read as two must yield a cursor')
        second = audit_trail.recent(self.service, limit=2, **first['next_cursor'])
        seen = [e['audit_id'] for e in first['events'] + second['events']]
        self.assertEqual(len(seen), 3, seen)
        self.assertEqual(len(set(seen)), 3, 'the (at, audit_id) cursor must not repeat a row')
        self.assertIsNone(second['next_cursor'])

    def test_a_written_through_the_store_version_is_in_the_journal(self):
        import hashlib
        payload = self.root / 'layer.psd'
        payload.write_bytes(b'8BPS journal fixture')
        digest = hashlib.sha256(payload.read_bytes()).hexdigest()
        # through the store's own API, not hand-written INSERTs: if the journal is only
        # reachable when somebody bypasses the helper, that is a different (worse) answer.
        asset_store.create_project(self.conn, 'p-journal', 'journal fixture')
        asset_store.register_asset(self.conn, 'p-journal', 'asset-' + 'b' * 32, 'psd')
        version = asset_store.record_version(
            self.conn, 'asset-' + 'b' * 32, 'sha256:' + digest,
            artifacts=[(str(payload), 'sha256:' + digest, payload.stat().st_size, 'primary')],
            attempt_id='att-' + 'd' * 32)
        self.conn.commit()
        read = audit_trail.recent(self.service)
        self.assertEqual(read['counts'].get('asset_version_created'), 1, read)
        self.assertIn(version, read['events'][0]['action'])

    def test_the_read_path_cannot_write(self):
        self.take_over('att-' + 'e' * 32)
        self.conn.commit()
        conn = audit_trail.connect(self.service)
        self.addCleanup(conn.close)
        with self.assertRaises(sqlite3.OperationalError):
            conn.execute("INSERT INTO audit_event VALUES ('forged','x','y','z')")

    def test_shape_of_the_request_is_refused_before_the_store_is_touched(self):
        for bad in (0, 201, '20', True, None):
            with self.subTest(limit=bad):
                with self.assertRaises(ValueError):
                    audit_trail.recent(self.service, limit=bad)
        with self.assertRaises(ValueError):
            audit_trail.recent(self.service, action='writer_abandoned')


class JournalIsNotWriteOnlyTests(unittest.TestCase):
    """The defect this file exists to prevent: rows written, nobody reading them.

    A product scan for a SELECT over audit_event is a weak proof in general, so it is made
    precise here: the reader must be in src/design_lab (not a test), and the module that reads
    it must also be reachable from a production entry point.
    """

    def _selectors(self):
        hits = []
        for path in (ROOT / 'src/design_lab').rglob('*.py'):
            text = path.read_text(encoding='utf-8', errors='replace')
            if 'audit_event' not in text or 'SELECT' not in text.upper():
                continue
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and 'audit_event' in node.value \
                        and 'SELECT' in node.value.upper():
                    hits.append((path.relative_to(ROOT).as_posix(), node.value[:48]))
        return hits

    def test_something_in_the_product_reads_the_journal(self):
        self.assertGreaterEqual(len(self._selectors()), 1,
                                'audit_event is written by asset_store and read by nothing -- '
                                'a write-only journal is not an audit trail')

    def test_the_reader_is_reachable_from_the_cli(self):
        cli = (ROOT / 'src/design_lab/cli.py').read_text(encoding='utf-8')
        self.assertIn('audit-trail', cli, 'no verb can reach the journal')
        self.assertIn('from .runtime.audit_trail import recent', cli,
                      'the verb is declared but never calls the reader')

    def test_a_journal_row_can_still_be_written_by_the_product(self):
        """Guard the other direction: deleting the writes would also silence my first test."""
        store = (ROOT / 'src/design_lab/runtime/asset_store.py').read_text(encoding='utf-8')
        self.assertGreaterEqual(store.count('INSERT INTO audit_event'), 2,
                                'the takeover journal write is gone, so the readback has '
                                'nothing to prove')


if __name__ == '__main__':
    unittest.main()
