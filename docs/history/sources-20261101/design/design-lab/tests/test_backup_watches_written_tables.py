# SPDX-License-Identifier: MIT
"""The backup's quiescence proof must be able to see every table production writes.

`PROVED_QUIESCENT` is a claim about the whole state database, but it is built from a
fixed list: lease/activity queries plus COUNTER_QUERIES. A store that commits without a
lease -- which is what every non-asset table here does -- is invisible unless it is in
that list. That is how a human verdict filed inside the backup window went unobserved
until 601a6422; this test is the reason it cannot happen again quietly.

Both directions are enforced, in the style of the gate-reachability rule: a written table
missing from the proof fails, and a watched name that is no longer a real written table
fails too, so an exemption cannot be carried after the thing it excused is gone.
"""
from __future__ import annotations

import re
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'src' / 'design_lab'
BACKUP = (SRC / 'runtime' / 'project_backup.py').read_text(encoding='utf-8')
STATE_DIR = ROOT / 'design-lab' / 'schemas' / 'state'

INSERT = re.compile(r'\bINSERT(?:\s+OR\s+(?:REPLACE|IGNORE|ROLLBACK|ABORT|FAIL))?\s+'
                    r'(?:INTO|TABLE)\s+(\w+)', re.I)

#: Tables the proof deliberately does not count, each with the reason it is safe.
#: Empty today: every written table here can move without holding a lease.
SANCTIONED_BLIND: dict[str, str] = {}


def state_tables() -> dict[str, str]:
    tables = {}
    for sql in sorted(STATE_DIR.glob('*.sql')):
        for match in re.finditer(r'CREATE TABLE IF NOT EXISTS\s+(\w+)',
                                 sql.read_text(encoding='utf-8')):
            tables[match.group(1).lower()] = sql.name
    return tables


def written_tables() -> dict[str, set]:
    writers = defaultdict(set)
    for path in sorted(SRC.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        for table in INSERT.findall(path.read_text(encoding='utf-8', errors='replace')):
            writers[table.lower()].add(path.relative_to(SRC).as_posix())
    return writers


def counted_names() -> set:
    """Every table name the proof names, BEFORE restricting to declared tables.

    Restricting first would make the "is this a real table" assertion vacuous: a typo in
    COUNTER_QUERIES would simply disappear from the watched set instead of being reported.
    """
    names = {name.lower() for name in re.findall(r"\('(\w+)',\s*'[\w_]+'\)", BACKUP)}
    names |= {name.lower() for name in re.findall(r'FROM (\w+)', BACKUP)}
    names |= {'asset_writer_lock'}
    return names


def watched_tables(tables: dict) -> set:
    return counted_names() & set(tables)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tables = state_tables()
        self.writers = written_tables()
        self.written = {table for table in self.tables if table in self.writers}

    def test_the_derivation_is_not_silently_empty(self):
        """A broken regex would make every other assertion here pass vacuously."""
        self.assertGreaterEqual(len(self.tables), 18, self.tables)
        self.assertGreaterEqual(len(self.written), 12,
                                f'only {sorted(self.written)} -- suspect the INSERT pattern')
        self.assertIn('jury_record', self.written)
        self.assertIn('project', self.written)

    def test_every_written_table_is_watched_by_the_proof(self):
        blind = sorted(self.written - watched_tables(self.tables) - set(SANCTIONED_BLIND))
        self.assertEqual(blind, [],
                         'these tables production writes without a lease and the quiescence '
                         f'proof cannot see them move: {blind}. Add them to COUNTER_QUERIES, '
                         'or add a reason to SANCTIONED_BLIND explaining why counting them '
                         'is unnecessary.')

    def test_no_sanity_is_claimed_for_a_table_that_is_now_covered(self):
        sanctioned = {name for name in SANCTIONED_BLIND if name in self.written
                      and name in watched_tables(self.tables)}
        self.assertEqual(sorted(sanctioned), [],
                         f'excused but already watched: {sorted(sanctioned)} -- drop the excuse')
        dead = sorted(name for name in SANCTIONED_BLIND if name not in self.written)
        self.assertEqual(dead, [], f'SANCTIONED_BLIND names tables nothing writes: {dead}')

    def test_no_counted_table_is_without_rowid(self):
        """The counters key on rowid; a WITHOUT ROWID table would need a named column.

        A typo in a counter name needs no separate check here: it makes the real table
        unwatched, and test_every_written_table_is_watched_by_the_proof goes red for it.
        (That is what a raw-name check would have to be able to say -- and could not,
        because part of the schema is declared inside native_tasks.py rather than a .sql
        file, so the set of real table names is not derivable from design-lab/schemas.)
        """
        for sql in STATE_DIR.glob('*.sql'):
            self.assertNotIn('WITHOUT ROWID', sql.read_text(encoding='utf-8').upper(),
                             f'{sql.name} declares a table without a rowid')

    def test_the_attribution_behind_the_coverage_is_real(self):
        """The coverage claim rests on who writes each table, so name two of them."""
        for table in sorted(self.written):
            self.assertTrue(self.writers[table], f'{table} has no attributed writer')
        self.assertIn('assurance/rights_ledger.py', self.writers['rights_decision'],
                      'rights_decision must be written by the gate that owns it, or the '
                      'counted table belongs to something else than the human rights store')
        self.assertIn('creative/approval.py', self.writers['approval'])


if __name__ == '__main__':
    unittest.main()
