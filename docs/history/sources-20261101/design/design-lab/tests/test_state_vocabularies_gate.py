# SPDX-License-Identifier: MIT
"""The vocabulary contract must stay fatal to the claim it was written for.

`verify_state_vocabularies.py` runs in CI (canonical-verify.yml) but had no test module, so
nothing proved it still caught the thing it exists to catch -- and on 2026-10-08 the file-wide
ban on the literal 'PASS' was legitimately loosened, because a second emitter
(`assurance/production_preflight.py`) really does verdict PASS. A loosening with no test is
just a regression waiting to be forgotten.

Every fixture here is the REAL file with exactly one substitution, so these cases cannot pass
because a synthetic fixture was written too kindly.
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = ROOT / 'design-lab/scripts/verify_state_vocabularies.py'
REAL = {
    'CONTRACT': ROOT / 'design-lab/config/state-vocabularies.json',
    'JOB_STORE': ROOT / 'src/design_lab/runtime/job_store.py',
    'TASK_RESOURCES': ROOT / 'src/design_lab/runtime/task_resources.py',
    'PRODUCTION_PREFLIGHT': ROOT / 'src/design_lab/assurance/production_preflight.py',
    'SHELL_TS': ROOT / 'apps/workbench/shell.ts',
    'BUNDLE': ROOT / 'apps/workbench/build/main.js',
}


class VocabularyGateTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/vocabulary-gate-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        spec = importlib.util.spec_from_file_location('vocab_gate', GATE_SCRIPT)
        self.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gate)
        for key, source in REAL.items():
            copy = self.root / source.name
            shutil.copyfile(source, copy)
            setattr(self.gate, key, copy)

    def write(self, key, text):
        path = self.root / REAL[key].name
        path.write_text(text, encoding='utf-8')
        return path

    def run_gate(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.gate.main()
        return code, buffer.getvalue()

    # ---------------------------------------------------------------- the teeth
    def test_the_historical_lie_is_still_fatal(self):
        """'PASS / BLOCKED' pasted onto the task-resource verdict is the claim this file
        exists for. Loosening the bare word must not have lost it."""
        shell = REAL['SHELL_TS'].read_text(encoding='utf-8')
        self.write('SHELL_TS', shell + "\nconst lie = 'PASS / BLOCKED';\n")
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('task-resource preflight emits READY or BLOCKED only', output)

    def test_a_status_no_emitter_produces_is_fatal(self):
        shell = REAL['SHELL_TS'].read_text(encoding='utf-8')
        self.write('SHELL_TS', shell + "\nconst invented = 'APPROVED';\n")
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn("'APPROVED'", output)

    def test_an_invented_pair_is_fatal_even_though_pairs_are_now_vocabulary_checked(self):
        shell = REAL['SHELL_TS'].read_text(encoding='utf-8')
        self.write('SHELL_TS', shell + "\nconst pair = 'PASS / SUPERB';\n")
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('no declared emitter produces', output)

    def test_contract_drift_against_the_artifact_emitter_is_fatal(self):
        """The artifact vocabulary was ADDED to the contract today; if the emitter's words
        change and the contract does not, the UI could advertise a verdict nobody emits."""
        preflight = REAL['PRODUCTION_PREFLIGHT'].read_text(encoding='utf-8')
        drifted = re.sub(r"^VERDICTS = \((.*?)\)$",
                         r"VERDICTS = ('PASS', 'WARN', 'BLOCKED')", preflight, flags=re.M)
        assert drifted != preflight, 'the VERDICTS anchor moved; re-read the emitter'
        self.write('PRODUCTION_PREFLIGHT', drifted)
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('production_preflight VERDICTS', output)

    def test_contract_drift_against_job_store_is_still_fatal(self):
        store = REAL['JOB_STORE'].read_text(encoding='utf-8')
        anchor = '    "RUNNING": {'
        assert anchor in store, 'the ALLOWED block moved; re-read the store'
        drifted = store.replace(
            anchor, '    "AWAITING_FATE": {"RECEIPTED"},\n' + anchor, 1)
        self.write('JOB_STORE', drifted)
        # a mutation that does not change what the gate parses would pass for the wrong
        # reason, so assert the parser actually sees the new state
        parsed, _terminal = self.gate.py_attempt_states()
        self.assertIn('AWAITING_FATE', parsed)
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('job_store ALLOWED/TERMINAL', output)

    def test_ui_triage_sets_must_match_the_contract(self):
        shell = REAL['SHELL_TS'].read_text(encoding='utf-8')
        drifted = shell.replace("const HUMAN_STATES = new Set([",
                                "const HUMAN_STATES = new Set(['RECEIPTED',", 1)
        assert drifted != shell, 'HUMAN_STATES moved; re-read the UI'
        self.write('SHELL_TS', drifted)
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('HUMAN_STATES', output)

    def test_missing_ui_set_is_reported_not_ignored(self):
        """A gate that silently finds nothing is a gate that passes forever."""
        shell = re.sub(r"const IN_FLIGHT_STATES = new Set\(\[.*?\]\)", '',
                       REAL['SHELL_TS'].read_text(encoding='utf-8'), flags=re.S, count=1)
        self.write('SHELL_TS', shell)
        code, output = self.run_gate()
        self.assertEqual(code, 1, output)
        self.assertIn('IN_FLIGHT_STATES not found', output)

    # ---------------------------------------------------------------- the tolerance
    def test_the_real_tree_passes_including_the_artifact_preflight_pass(self):
        """The other half: the artifact column's 'PASS' is legitimate, and the gate must not
        be so tight that honesty reads as a violation."""
        for key in REAL:
            setattr(self.gate, key, REAL[key])
        code, output = self.run_gate()
        self.assertEqual(code, 0, output)

    def test_the_artifact_vocabulary_is_declared_not_assumed(self):
        contract = json.loads(REAL['CONTRACT'].read_text(encoding='utf-8'))
        self.assertIn('artifactPreflight', contract)
        self.assertIn('artifactPreflight', contract['sources'],
                      'a vocabulary with no named source is a hand copy in disguise')
        verdicts, outcomes = self.gate.py_artifact_preflight()
        self.assertEqual(set(contract['artifactPreflight']['verdicts']), verdicts)
        self.assertLessEqual(set(contract['artifactPreflight']['outcomes']), outcomes)


if __name__ == '__main__':
    unittest.main()
