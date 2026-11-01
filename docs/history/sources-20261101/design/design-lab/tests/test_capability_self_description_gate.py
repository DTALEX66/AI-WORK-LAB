# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_capability_self_description.py.

The gate exists because the Workbench's own capability table went stale: the store, the façade
and both routes for persisted research findings landed on 2026-10-08 and the slot kept telling the
operator that no route persisted conclusions. Two obligations are tested:

1. the shipped gate is true of the shipped repository, and it says so with numbers rather than
   silence (routes, resources and registry rows all non-zero, and research no longer declared
   unbacked);
2. each refusal goes RED FOR ITS OWN REASON against a mutated COPY of the two files it compares.
   The control copy is asserted green first, because a mutation that goes red because the scratch
   tree was assembled badly proves nothing, and a mutation that stays green means the gate cannot
   see that defect.

Both directions of the linkage are exercised: a claim that a route is missing when it exists, and
a claim that a route exists when it does not. Only checking the first would let the table be
"repaired" by typing IMPLEMENTED.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_capability_self_description.py'
SCRATCH_BASE = REPO / '.project-local' / 'task-runtime' / 'capability-self-description-scratch'


def load_gate(path: Path = None):
    target = Path(path or GATE_PATH)
    spec = importlib.util.spec_from_file_location('verify_capability_sd_under_test', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_scratch(dest: Path, mutate_shell=None, mutate_http=None, drop_bindings=False) -> Path:
    """A tree with just the two files the gate compares, plus the route reader it borrows."""
    gate = load_gate()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shell = (REPO / gate.SHELL_REL).read_text(encoding='utf-8')
    http = (REPO / gate.HTTP_REL).read_text(encoding='utf-8')
    if mutate_shell:
        shell = mutate_shell(shell)
    if mutate_http:
        http = mutate_http(http)
    for rel, text in ((gate.SHELL_REL, shell), (gate.HTTP_REL, http)):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    if not drop_bindings:
        reader = dest / gate.BINDINGS_GATE_REL
        reader.parent.mkdir(parents=True, exist_ok=True)
        reader.write_text((REPO / gate.BINDINGS_GATE_REL).read_text(encoding='utf-8'),
                          encoding='utf-8')
    return dest


def outcome(dest: Path, repo_override: Path = None):
    gate = load_gate()
    if repo_override is not None:
        gate.REPO = repo_override
    try:
        findings, summary = gate.scan(dest)
    except gate.SelfDescriptionError as exc:
        return [exc.code], {}
    return sorted({line.split(' ', 1)[0] for line in findings}), summary


def readd_research_notice(shell: str) -> str:
    anchor = "export const VIEW_NOT_OPEN: Partial<Record<RouteView, string>> = {\n"
    assert anchor in shell, 'the VIEW_NOT_OPEN declaration moved'
    return shell.replace(
        anchor, anchor + "  'research': '研究洞察页未开放：当前服务没有研究结论的持久化路由。',\n", 1)


def demote_research_row(shell: str) -> str:
    old = "implementationState: 'IMPLEMENTED',\n    permission: 'brief/reference"
    assert old in shell, 'the research row is no longer the IMPLEMENTED row before a permission line'
    return shell.replace(old, "implementationState: 'PLANNED',\n    permission: 'brief/reference", 1)


def research_row_hides_its_route(shell: str) -> str:
    """PLANNED, and a placeholder route the matcher cannot resolve -- only the slot links it.

    This is the case that pays for `slot`: a row may describe its future route in prose or with an
    ellipsis, and then the route comparison sees nothing. The view linkage is what still catches
    the claim that the slot has no backend.
    """
    shell = demote_research_row(shell)
    old = "route: 'GET /api/projects/{id}/research', slot: 'research',"
    assert old in shell, 'the research row no longer names its route and slot on one line'
    return shell.replace(old, "route: 'GET /api/research/…', slot: 'research',", 1)


def point_domain_row_at_nothing(shell: str) -> str:
    old = "route: 'GET /api/domains'"
    assert old in shell, 'the design-domain row no longer names /api/domains'
    return shell.replace(old, "route: 'GET /api/domains-that-do-not-exist'", 1)


def vague_notice(shell: str) -> str:
    old = "'collaboration': '团队协作页未开放：本地单机服务尚无协作路由（本地单用户模型）。',"
    assert old in shell, 'the collaboration notice moved'
    return shell.replace(old, "'collaboration': '团队协作页敬请期待',", 1)


def strip_registry(shell: str) -> str:
    start = shell.index('const CAPABILITY_REGISTRY')
    end = shell.index('\n];', start) + len('\n];')
    return shell[:start] + 'const CAPABILITY_REGISTRY: readonly CapabilityContract[] = [];' + \
        shell[end:]


def strip_view_table(shell: str) -> str:
    start = shell.index('export const VIEW_NOT_OPEN')
    end = shell.index('\n};', start) + len('\n};')
    return shell[:start] + shell[end:]


def no_dispatcher(http: str) -> str:
    """A service file that dispatches nothing at all, to test the vacuity floor itself.

    Mutating only the /api prefix was not enough: the AST reader also takes routes from
    `== self.path` comparisons and constants, so some paths survived and the gate correctly
    found a route rather than nothing.
    """
    return ('# SPDX-License-Identifier: MIT\n'
            '"""A stub with no request handling."""\n\n\nclass Service:\n'
            '    def handle(self):\n        return None\n')


class ShippedRepositoryTests(unittest.TestCase):
    def test_the_shipped_pair_passes_the_shipped_gate(self):
        gate = load_gate()
        findings, summary = gate.scan(REPO)
        self.assertEqual(findings, [], '\n'.join(findings[:6]))
        self.assertGreater(summary['routes'], 40)
        self.assertGreater(len(summary['terminal_resources']), 20)
        self.assertEqual(summary['rows'], 5)
        self.assertEqual(summary['views_declared_unopen'], ['collaboration'])

    def test_the_gate_reads_routes_from_the_shared_ast_reader(self):
        """One route reader, not two that can disagree about what the service dispatches."""
        gate = load_gate()
        reader = gate.route_reader()
        self.assertTrue(callable(reader.route_tokens))
        own = set(gate.terminal_segments(gate.dispatched_routes(REPO)))
        borrowed = set(gate.terminal_segments(
            [key for key, _ in reader.route_tokens(REPO / gate.HTTP_REL)
             if key.startswith('/')]))
        self.assertEqual(own, borrowed)


class MutatedCopyTests(unittest.TestCase):
    def setUp(self):
        control = build_scratch(SCRATCH_BASE / 'control')
        codes, summary = outcome(control)
        self.assertEqual(codes, [], f'the control copy must be green first: {codes}')
        self.assertTrue(summary['rows'])

    def assert_red(self, code, expect, mutate_shell=None, mutate_http=None,
                   drop_bindings=False):
        dest = build_scratch(SCRATCH_BASE / 'case', mutate_shell, mutate_http, drop_bindings)
        codes, _ = outcome(dest)
        self.assertIn(code, codes, f'expected {code}, got {codes}')
        gate = load_gate()
        findings, _ = gate.scan(dest)
        line = next((f for f in findings if f.startswith(code)), '')
        self.assertIn(expect, line, f'{code} fired but did not say {expect!r}: {line}')

    def test_a_slot_that_claims_no_route_while_one_is_dispatched_is_refused(self):
        self.assert_red('CAPABILITY_CLAIM_STALE', 'while the service dispatches',
                        mutate_shell=readd_research_notice)

    def test_a_row_demoted_while_its_route_exists_is_refused(self):
        self.assert_red('CAPABILITY_CLAIM_STALE', 'which the service dispatches',
                        mutate_shell=demote_research_row)

    def test_a_slot_claim_is_refused_even_when_the_row_hides_its_route(self):
        """The reason `slot` exists: prose routes are not matchable, the view linkage is."""
        self.assert_red('CAPABILITY_CLAIM_STALE', 'for slot',
                        mutate_shell=research_row_hides_its_route)

    def test_an_implemented_row_naming_a_route_that_does_not_exist_is_refused(self):
        self.assert_red('CAPABILITY_ROUTE_ABSENT', 'no route it names',
                        mutate_shell=point_domain_row_at_nothing)

    def test_a_not_open_notice_that_names_no_route_is_refused(self):
        self.assert_red('NOT_OPEN_COPY_VAGUE', 'without naming a missing route',
                        mutate_shell=vague_notice)

    def test_an_empty_registry_is_refused_not_passed(self):
        dest = build_scratch(SCRATCH_BASE / 'empty-registry', mutate_shell=strip_registry)
        codes, _ = outcome(dest)
        self.assertEqual(codes, ['NOTHING_TO_COMPARE'])

    def test_a_missing_view_table_is_refused_as_unreadable(self):
        dest = build_scratch(SCRATCH_BASE / 'no-table', mutate_shell=strip_view_table)
        codes, _ = outcome(dest)
        self.assertEqual(codes, ['SELF_DESCRIPTION_UNREADABLE'])

    def test_a_dispatcher_that_matches_nothing_is_refused(self):
        dest = build_scratch(SCRATCH_BASE / 'no-routes', mutate_http=no_dispatcher)
        codes, _ = outcome(dest)
        self.assertEqual(codes, ['NOTHING_TO_COMPARE'])

    def test_a_missing_route_reader_is_refused(self):
        dest = build_scratch(SCRATCH_BASE / 'no-reader', drop_bindings=True)
        codes, _ = outcome(dest, repo_override=dest)
        self.assertEqual(codes, ['ROUTE_READER_BROKEN'])

    def test_the_weakened_gate_lets_the_same_lie_through(self):
        """The check is what convicts: remove the comparison and the identical defect passes."""
        dest = build_scratch(SCRATCH_BASE / 'weakened', mutate_shell=readd_research_notice)
        source = GATE_PATH.read_text(encoding='utf-8')
        self.assertIn("if hits:", source)
        weakened = SCRATCH_BASE / 'verify_capability_sd_weakened.py'
        weakened.write_text(source.replace('        hits = segments.get(view)',
                                           '        hits = None', 1), encoding='utf-8')
        self.assertNotEqual(weakened.read_text(encoding='utf-8'), source,
                            'the weakened copy changed no bytes')
        try:
            weak = load_gate(weakened)
            # REPO is derived from __file__, so a copy parked in the scratch tree would otherwise
            # resolve its repository root to .project-local. Re-anchor it: the only difference
            # under test is the removed comparison, not where the files live.
            weak.REPO = REPO
            findings, _ = weak.scan(dest)
        finally:
            weakened.unlink()
        self.assertEqual([f for f in findings if f.startswith('CAPABILITY_CLAIM_STALE')
                          and 'while the service dispatches' in f], [],
                         'a gate with the view comparison removed still reported the lie')
        strict, _ = load_gate().scan(dest)
        self.assertTrue([f for f in strict if f.startswith('CAPABILITY_CLAIM_STALE')])


class SegmentMatchingTests(unittest.TestCase):
    def test_a_placeholder_segment_matches_one_real_segment(self):
        gate = load_gate()
        routes = gate.dispatched_routes(REPO)
        self.assertTrue(gate.route_is_dispatched('GET /api/projects/{id}/research', routes))
        self.assertTrue(gate.route_is_dispatched('GET /api/domains', routes))

    def test_a_placeholder_route_never_counts_as_dispatched(self):
        gate = load_gate()
        routes = gate.dispatched_routes(REPO)
        self.assertFalse(gate.route_is_dispatched('GET /api/research/…', routes))
        self.assertFalse(gate.route_is_dispatched('', routes))

    def test_a_non_literal_terminal_segment_produces_no_resource(self):
        """An optional query tail is not a resource name, and is skipped rather than guessed."""
        gate = load_gate()
        segments = gate.terminal_segments(['/api/projects/([0-9a-f]{32})/native-assets'
                                           '(?:\\?after=(native-[0-9a-f]{64}))?'])
        self.assertEqual(segments, {})


if __name__ == '__main__':
    unittest.main()
