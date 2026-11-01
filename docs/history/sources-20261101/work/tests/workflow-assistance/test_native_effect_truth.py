"""Regression checks for observed effects, not just returned status strings."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class NativeEffectTruthTests(unittest.TestCase):
    def test_unwired_operations_cannot_succeed(self):
        m = load('truth_openhands', 'services/execution-federation/openhands_adapter.py')
        adapter = m.OpenHandsAdapter(reachable=True)
        # The contract this test defends is "no unwired operation claims
        # success" — observed effect, not one specific string. Two honest
        # degraded reasons are valid:
        #   NOT_IMPLEMENTED  the adapter advertises the capability but the
        #                    operation is still the base no-op;
        #   NOT_SUPPORTED    the adapter does not advertise the capability at
        #                    all (it never was wired).
        # AG-06 (2026-10-01) removed the false `resume` capability declaration
        # from openhands/codex/dsh, which legitimately moved resume from the
        # first reason to the second. Pinning to one string would have forced
        # the adapter to keep advertising a capability it cannot deliver.
        honest_degraded = {'NOT_IMPLEMENTED', 'NOT_SUPPORTED', 'NOT_LAUNCHABLE'}
        for result in (adapter.new(), adapter.resume('absent'),
                       adapter.prompt('absent', 'synthetic'),
                       adapter.cancel('absent'), adapter.fork('absent')):
            with self.subTest(op=result.op):
                self.assertFalse(result.ok)
                self.assertIn(result.status, honest_degraded)
                self.assertNotIn(result.status, {'OK', 'SUCCESS', 'COMPLETED'})

    def plane(self):
        m = load('truth_config', 'services/policy/config_control_plane.py')
        plane = m.ConfigControlPlane()
        plane.set_layer('official_baseline', {'x': 1})
        return plane

    def test_plan_is_not_apply(self):
        plane = self.plane()
        self.assertEqual(plane.apply_plan(plane.diff({'x': 1}, {'x': 2}),
                                         approved=True)['status'], 'UNSUPPORTED_APPLY')

    def test_missing_rollback_does_not_claim_restoration(self):
        plane = self.plane()
        state = {'x': 1}
        def apply(before):
            state['x'] = 2
            return {'x': 2}
        result = plane.transaction('fixture', plane.diff({'x': 1}, {'x': 2}),
                                   approved=True, apply_fn=apply,
                                   readback_fn=lambda: {'x': 999})
        self.assertEqual(result['status'], 'ROLLBACK_REQUIRED')
        self.assertEqual(state['x'], 2)

    def test_rollback_restores_a_real_file_and_reads_it_back(self):
        plane = self.plane()
        runtime = ROOT / '.project-local/runs/native-effect-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as td:
            path = Path(td) / 'synthetic-config.json'
            before = plane.effective('fixture')
            path.write_text(json.dumps(before))
            def apply(old):
                path.write_text(json.dumps({'x': 999}))
                return {'x': 2}
            result = plane.transaction('fixture', plane.diff({'x': 1}, {'x': 2}),
                                       approved=True, apply_fn=apply,
                                       readback_fn=lambda: json.loads(path.read_text()),
                                       rollback_fn=lambda old: path.write_text(json.dumps(old)))
            self.assertEqual(result['status'], 'ROLLED_BACK')
            self.assertEqual(json.loads(path.read_text()), before)

    def test_failed_rollback_is_not_success(self):
        plane = self.plane()
        result = plane.transaction('fixture', plane.diff({'x': 1}, {'x': 2}),
                                   approved=True, apply_fn=lambda old: {'x': 2},
                                   readback_fn=lambda: {'x': 999}, rollback_fn=lambda old: None)
        self.assertEqual(result['status'], 'ROLLBACK_FAILED')


if __name__ == '__main__':
    unittest.main()
