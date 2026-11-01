# SPDX-License-Identifier: MIT
"""The current-version gate must refuse a lie, and must not be vacuous.

Fixtures are synthetic modules written into a temp tree, so each branch is provoked by
name rather than hoped for on the live tree (the live tree is clean by construction -- a
gate that only runs against clean bytes proves nothing).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / 'design-lab' / 'scripts' / 'verify_current_version_rule.py'

GOOD_MAX = '''
def list_current(conn, project_id):
    return conn.execute(
        "SELECT v.version_id FROM asset_version v JOIN asset a ON a.asset_id = v.asset_id"
        " WHERE a.project_id = ? AND v.state = 'ACTIVE'"
        " AND v.version_no = (SELECT MAX(b.version_no) FROM asset_version b"
        "                     WHERE b.asset_id = v.asset_id AND b.state = 'ACTIVE')",
        (project_id,)).fetchall()
'''
GOOD_ORDER = '''
def current(conn, asset_id):
    return conn.execute(
        "SELECT version_id FROM asset_version WHERE asset_id=? AND state='ACTIVE'"
        " ORDER BY version_no DESC LIMIT 1", (asset_id,)).fetchone()
'''
PINNED_VERSION = '''
def receipt(conn, version_id):
    return conn.execute("SELECT receipt_json FROM delivery_receipt r"
                        " JOIN asset_version v ON v.version_id = r.version_id"
                        " WHERE v.version_id = ? AND v.state='ACTIVE'",
                        (version_id,)).fetchone()
'''
PINNED_SHA = '''
def republish(conn, asset_id, digest):
    return conn.execute("SELECT p.version_id FROM asset_publication p"
                        " JOIN asset_version v ON p.version_id = v.version_id"
                        " WHERE p.asset_id = ? AND p.sha256 = ? AND v.state = 'ACTIVE'",
                        (asset_id, digest)).fetchone()
'''
BAD = '''
def everything(conn, project_id):
    return conn.execute("SELECT v.version_id FROM asset_version v JOIN asset a"
                        " ON a.asset_id = v.asset_id"
                        " WHERE a.project_id = ? AND v.state = 'ACTIVE'",
                        (project_id,)).fetchall()
'''


def load_gate():
    spec = importlib.util.spec_from_file_location('verify_current_version_rule', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_gate(root: Path) -> tuple:
    proc = subprocess.run([sys.executable, '-B', str(GATE), '--root', str(root)],
                          capture_output=True, text=True, encoding='utf-8', errors='replace')
    return proc.returncode, (proc.stdout or '') + (proc.stderr or '')


class FixtureTree(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local' / 'task-runtime' / 'current-version-gate'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def write(self, **modules):
        for name, text in modules.items():
            (self.base / f'{name}.py').write_text(text, encoding='utf-8')

    def test_compliant_reads_pass_and_are_counted_as_seen(self):
        self.write(good_max=GOOD_MAX, good_order=GOOD_ORDER,
                   pinned_version=PINNED_VERSION, pinned_sha=PINNED_SHA)
        code, out = run_gate(self.base)
        self.assertEqual(code, 0, out)
        self.assertIn('CURRENT_VERSION_RULE=OK statements=4', out)

    def test_an_active_only_read_is_refused_and_named(self):
        self.write(good_max=GOOD_MAX, offender=BAD)
        code, out = run_gate(self.base)
        self.assertEqual(code, 1, f'the gate let a bare ACTIVE read through:\n{out}')
        self.assertIn('CURRENT_VERSION_RULE=FAIL', out)
        self.assertIn('UNRULED: offender.py', out)
        # The failure must say what to do, not just that something is wrong.
        self.assertIn('MAX(<alias>.version_no)', out)

    def test_an_empty_scan_is_a_failure_not_a_pass(self):
        code, out = run_gate(self.base)
        self.assertEqual(code, 1, out)
        self.assertIn('no statement', out)

    def test_a_scan_root_that_is_not_a_directory_is_a_failure(self):
        code, out = run_gate(self.base / 'nowhere')
        self.assertEqual(code, 1, out)
        self.assertIn('not a directory', out)


class ScannerUnit(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local' / 'task-runtime' / 'current-version-scanner'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def test_the_scanner_sees_literals_split_across_adjacent_strings(self):
        gate = load_gate()
        (self.base / 'm.py').write_text(BAD, encoding='utf-8')
        rows, stale = gate.scan(self.base)
        self.assertEqual([(row['state'], row['file']) for row in rows], [('UNRULED', 'm.py')])
        self.assertEqual(stale, [])

    def test_a_stale_exemption_is_reported(self):
        gate = load_gate()
        (self.base / 'm.py').write_text(GOOD_MAX, encoding='utf-8')
        gate.EXEMPT[('ghost.py', 'SELECT nothing FROM asset_version')] = 'an exemption '
        try:
            rows, stale = gate.scan(self.base)
            self.assertEqual([row['state'] for row in rows], ['RULED'])
            self.assertEqual(len(stale), 1, 'an exemption for a statement that no longer '
                                           'exists must be visible, not silently carried')
        finally:
            gate.EXEMPT.clear()


class LiveTree(unittest.TestCase):
    """The gate's real job: the shipped product complies today, and says how many."""

    def test_the_product_tree_has_no_unruled_active_read(self):
        code, out = run_gate(ROOT / 'src' / 'design_lab')
        self.assertEqual(code, 0, out)
        self.assertIn('CURRENT_VERSION_RULE=OK', out)
        # A number, asserted as a floor: the product has more than one ACTIVE reader, and
        # a scan that quietly matched nothing must never look like this line.
        statements = int(out.split('statements=')[1].split()[0])
        self.assertGreaterEqual(statements, 11,
                                f'the scan found only {statements} statements; suspect the matcher')

    def test_the_gate_is_registered_in_the_aggregate(self):
        scripts = (ROOT / 'design-lab' / 'scripts' / 'verify_design_lab.py').read_text(encoding='utf-8')
        self.assertIn('verify_current_version_rule.py', scripts,
                      'a gate nobody invokes is documentation')


if __name__ == '__main__':
    unittest.main()
