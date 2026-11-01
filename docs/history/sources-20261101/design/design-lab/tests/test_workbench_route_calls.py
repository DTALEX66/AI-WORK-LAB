# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_workbench_route_calls.py.

The gate asserts a two-way agreement: every API call in the Workbench reaches a Route in the
service's ROUTES table, and every Route is either reached or exempted with a measured reason.
A gate like that fails in two quiet ways, so both are pinned here:

* the scanner could stop seeing call sites (a helper renamed, a declaration counted as a call,
  a trailing comma read as a body) and then a dead frontend path would simply vanish from the
  inventory -- the green would mean "nothing found", not "everything served";
* the verdict could be unconditional -- every direction below is driven through `evaluate`
  with a planted fault, so each error code is shown to convict its own defect.

The shipped tree is asserted green first. Every falsifier then changes exactly the fact its
error names, and the error is required to carry that fact.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_workbench_route_calls.py'

sys.path.insert(0, str(REPO / 'src'))

from design_lab.http_service import Route  # noqa: E402


def load_gate():
    spec = importlib.util.spec_from_file_location(
        'verify_workbench_route_calls_under_test', GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def shipped(gate):
    calls = []
    for path in sorted(gate.WORKBENCH.glob('*.ts')):
        calls.extend(gate.scan(path.read_text(encoding='utf-8'), path.name))
    errors, stats = gate.evaluate(
        gate.ROUTES, calls, gate.BACKEND_ONLY, gate.SPECIAL_ROUTES, gate.DYNAMIC_FETCH)
    return errors, stats, calls


def codes(errors):
    """The verdict token of each error line (`FRONTEND_ROUTE_UNSERVED`, ...)."""
    return [match.group(1) for error in errors
            for match in [re.search(r'\b([A-Z][A-Z_]*_[A-Z][A-Z_]*)\b', error)] if match]


class ShippedTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = load_gate()
        cls.errors, cls.stats, cls.calls = shipped(cls.gate)

    def test_the_shipped_tree_agrees_in_both_directions(self):
        self.assertEqual(self.errors, [])

    def test_the_scan_sees_the_product_not_one_file(self):
        self.assertGreaterEqual(self.stats['calls'], 80)
        self.assertGreaterEqual(self.stats['routes'], 50)
        files = {call.file for call in self.calls}
        self.assertTrue({'shell.ts', 'design.ts', 'workbench.ts'} <= files, files)

    def test_every_route_is_accounted_for_exactly_once(self):
        self.assertEqual(self.stats['matched'] + self.stats['backend_only'],
                         self.stats['routes'])

    def test_each_exemption_states_a_measured_reason(self):
        for key, reason in self.gate.BACKEND_ONLY.items():
            self.assertGreater(len(reason), 40, f'{key} has a placeholder exemption')

    def test_dropping_one_exemption_convicts_that_route(self):
        key = next(iter(self.gate.BACKEND_ONLY))
        reduced = dict(self.gate.BACKEND_ONLY)
        del reduced[key]
        errors, _ = self.gate.evaluate(
            self.gate.ROUTES, self.calls, reduced,
            self.gate.SPECIAL_ROUTES, self.gate.DYNAMIC_FETCH)
        self.assertTrue(
            any(error.startswith('BACKEND_ROUTE_UNREACHED') and repr(key[1]) in error
                for error in errors),
            f'{key} stayed green without its exemption: {errors[:3]}')

    def test_a_renamed_frontend_path_is_red_against_the_shipped_routes(self):
        poisoned = list(self.calls) + [self.gate.CallSite(
            'shell.ts', 1, 'GET', '/api/telemetry', "'/telemetry'")]
        errors, _ = self.gate.evaluate(
            self.gate.ROUTES, poisoned, self.gate.BACKEND_ONLY,
            self.gate.SPECIAL_ROUTES, self.gate.DYNAMIC_FETCH)
        self.assertIn('FRONTEND_ROUTE_UNSERVED', codes(errors), errors)


class ScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = load_gate()

    def scan(self, source):
        return self.gate.scan(source, 'fixture.ts')

    def test_a_function_declaration_is_not_a_call(self):
        calls = self.scan(
            'function api<T>(path: string): Promise<T> { return null as T; }\n'
            'export async function apiOrEmpty<T extends object>(path: string, empty: T) '
            '{ return empty; }\n')
        self.assertEqual(calls, [])

    def test_a_comment_or_string_naming_a_call_is_not_a_call(self):
        calls = self.scan(
            "// api('/api/ghost') is prose about the gate\n"
            "const help = 'call apiOrEmpty(/api/ghost) to read it';\n")
        self.assertEqual(calls, [])

    def test_a_trailing_comma_is_a_read_not_a_write(self):
        calls = self.scan(
            'api<TaskList>(\n  `/projects/${id}/tasks`,\n);\n')
        self.assertEqual([call.method for call in calls], ['GET'])
        self.assertEqual(calls[0].template, '/api/projects/${id}/tasks')

    def test_a_second_argument_is_a_write_and_undefined_is_not(self):
        calls = self.scan(
            "api('/projects', { name: 'x' });\n"
            "api('/projects', undefined);\n")
        self.assertEqual([call.method for call in calls], ['POST', 'GET'])

    def test_a_path_field_expands_to_the_literals_the_table_carries(self):
        source = (
            "const GROUPS = [{ label: 'a', path: '/capabilities', limit: 8 }, "
            "{ label: 'b', path: '/projects', limit: 8 }];\n"
            "async function go() { await apiOrEmpty(group.path, {}); }\n")
        templates = {call.template for call in self.scan(source)}
        self.assertEqual(templates, {'/api/capabilities', '/api/projects'})

    def test_a_prefixed_constant_resolves_to_its_value(self):
        calls = self.scan("const base = '/health';\napi('/api' + base);\n")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].template, '/api/health')

    def test_a_fetch_outside_api_is_unresolved_rather_than_guessed(self):
        calls = self.scan(
            "fetch('/api/local-session');\n"
            "fetch(data.download_path);\n")
        self.assertEqual([call.template for call in calls], ['/api/local-session', None])
        self.assertEqual(calls[1].expression, 'data.download_path')


class EvaluateDirectionTests(unittest.TestCase):
    """Each direction is convicted by a planted fault and carries the fact it names."""

    @classmethod
    def setUpClass(cls):
        cls.gate = load_gate()
        cls.routes = (
            Route('GET', '/api/health', '_health', exact=True),
            Route('GET', '/api/quiet', '_quiet', exact=True),
        )
        cls.call = cls.gate.CallSite('shell.ts', 1, 'GET', '/api/health', "'/health'")

    def evaluate(self, calls=None, backend_only=None, special=None, dynamic=None,
                 routes=None):
        return self.gate.evaluate(
            routes if routes is not None else self.routes,
            calls if calls is not None else [self.call],
            backend_only or {}, special or {}, dynamic or {})

    def test_an_unserved_frontend_call_is_red(self):
        calls = [self.call, self.gate.CallSite(
            'design.ts', 2, 'GET', '/api/retired', "'/retired'")]
        errors, _ = self.evaluate(calls=calls)
        self.assertIn('FRONTEND_ROUTE_UNSERVED', codes(errors), errors)

    def test_a_method_disagreement_says_so(self):
        calls = [self.gate.CallSite(
            'design.ts', 2, 'POST', '/api/health', "'/health'")]
        errors, _ = self.evaluate(calls=calls)
        self.assertIn('FRONTEND_ROUTE_UNSERVED', codes(errors), errors)
        self.assertIn('the method disagrees', ' '.join(errors))

    def test_an_unreached_route_is_red_until_it_is_exempted(self):
        errors, _ = self.evaluate()
        self.assertIn('BACKEND_ROUTE_UNREACHED', codes(errors), errors)
        errors, _ = self.evaluate(backend_only={('GET', '/api/quiet'): 'reason' * 8})
        self.assertEqual(errors, [])

    def test_an_exemption_for_a_vanished_route_is_stale(self):
        errors, _ = self.evaluate(backend_only={('GET', '/api/deleted'): 'reason' * 8})
        self.assertIn('STALE_BACKEND_ONLY', codes(errors), errors)

    def test_an_exemption_the_frontend_now_calls_is_stale(self):
        calls = [self.call, self.gate.CallSite(
            'design.ts', 2, 'GET', '/api/quiet', "'/quiet'")]
        errors, _ = self.evaluate(
            calls=calls, backend_only={('GET', '/api/quiet'): 'reason' * 8})
        self.assertIn('STALE_BACKEND_ONLY', codes(errors), errors)

    def test_a_stale_special_route_is_red(self):
        errors, _ = self.evaluate(
            special={('GET', '/api/local-session'): 'served before auth' * 4})
        self.assertIn('STALE_SPECIAL_ROUTE', codes(errors), errors)

    def test_a_special_route_that_is_called_is_not_stale(self):
        calls = [self.call, self.gate.CallSite(
            'shell.ts', 2, 'GET', '/api/local-session', "'/local-session'")]
        errors, _ = self.evaluate(
            calls=calls,
            special={('GET', '/api/local-session'): 'served before auth' * 4})
        self.assertNotIn('STALE_SPECIAL_ROUTE', codes(errors), errors)

    def test_a_stale_dynamic_fetch_allowance_is_red(self):
        errors, _ = self.evaluate(dynamic={'data.download_path': 'payload readback' * 4})
        self.assertIn('STALE_DYNAMIC_FETCH', codes(errors), errors)

    def test_a_duplicated_route_is_red(self):
        routes = self.routes + (Route('GET', '/api/health', '_health_again', exact=True),)
        errors, _ = self.evaluate(routes=routes)
        self.assertIn('DUPLICATE_ROUTE', codes(errors), errors)

    def test_nothing_to_compare_is_a_failure(self):
        errors, _ = self.evaluate(calls=[], routes=())
        self.assertEqual(codes(errors).count('NOTHING_TO_COMPARE'), 2, errors)


if __name__ == '__main__':
    unittest.main(verbosity=2)
