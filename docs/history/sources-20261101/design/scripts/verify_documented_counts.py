#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prose numbers must equal measured numbers.

Two stale figures reached a live surface this session: a source comment that still narrated the
workbench route table as 15 entries (it is 19), and DESIGN.md's "11 nav items need 587px, the list
only overflows below 720" (19 items, and it overflows at every desktop height measured). Both were
believed, and nothing failed. The repo already solves this once -- `scripts/design_debt_baseline.py
--check` compares the debt prose against the measurement -- so this is the same mechanism for the
counts no gate owned yet.

A claim is (file, a template holding exactly one `{n}`, a callable). The measurement reads code,
never the sentence; the sentence is never an input to the measurement -- that separation is the only
thing keeping this from being a tautology. Every extractor fails loudly when it matches nothing,
because a dead pattern that reports 0 would otherwise green-light a wrong document.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))


def _require(count: int, what: str) -> int:
    if count == 0:
        raise SystemExit(f'DOCUMENTED_COUNTS=FAIL the {what} extractor matched nothing; '
                         'a dead pattern must not be allowed to report a count')
    return count


def route_views() -> int:
    """Entries in the workbench route table -- the authority for how many nav items exist."""
    src = (REPO / 'apps/workbench/shell.ts').read_text(encoding='utf-8')
    start = src.index('export const ROUTE_VIEWS')
    body = src[start:src.index('] as const', start)]
    return _require(len(re.findall(r'^\s{2}\{ hash:', body, re.M)), 'ROUTE_VIEWS')


def cli_subcommands() -> int:
    src = (REPO / 'src/design_lab/cli.py').read_text(encoding='utf-8')
    return _require(src.count('add_parser('), 'cli add_parser')


def registry_adapters() -> int:
    data = json.loads((REPO / 'integrations/adapter-registry.json').read_text(encoding='utf-8'))
    rows = data.get('adapters', data if isinstance(data, list) else [])
    return _require(len(rows), 'adapter-registry')


def current_execution_states() -> tuple[int, int]:
    """`(still-frozen, dispatched)` for `currentExecution`, read from the one ledger.

    Until 2026-10-23 this measurement refused to report a number at all while any task had left the
    frozen state, because every prose sentence said "all 34 are frozen" and the gate would not help
    hide a silent unfreeze. The owner then recorded the decision to dispatch a new segment
    (docs/taskpacks/20261023-ui-kb/OWNER-DECISION-2026-10-23.md), so the honest shape is two
    separately measured numbers: the 34 that stay frozen keep their sentences, and the new dispatch
    gets its own. A silent move of any old row out of `FROZEN_DEFERRED` now changes the frozen count
    and reddens all four of those sentences at once -- the protection is the measurement, not a
    refusal to measure.
    """
    ledger = json.loads((REPO / 'design-lab/config/task-ledger-r3.json').read_text(encoding='utf-8'))

    def walk(node):
        for task in node.get('tasks') or []:
            yield task
            yield from walk(task)

    tasks = list(walk(ledger.get('currentExecution') or {}))
    _require(len(tasks), 'currentExecution task walk')
    frozen = len([t for t in tasks if t.get('state') == 'FROZEN_DEFERRED'])
    return frozen, len(tasks) - frozen


def frozen_current_tasks() -> int:
    return current_execution_states()[0]


def dispatched_current_tasks() -> int:
    return current_execution_states()[1]


def http_routes() -> int:
    from design_lab import http_service
    return _require(len(http_service.ROUTES), 'http_service.ROUTES')


CHAIN_TEST = 'design-lab/tests/test_standalone_chain_http.py'


def _chain_labels(*methods: str) -> int:
    """How many hop labels that walk prints, counted from the bodies it actually runs.

    A label comes from either `self.hop(...)` or a manual `self.hops.append(...)` (the native read
    back is appended, not called), so both forms count. This is the number quoted as
    "N 跳验收链" / "N 跳交付链" in the prompt -- if a hop is added and the prose is not, this moves
    and the sentence fails to match.

    Several methods may be named because the delivery walk shares its seed with the GET sweep: the
    hops live in `_deliver_to_preflight`, and a single-method pattern went red the moment that
    helper was extracted. Counting the delegation target keeps the claim measured instead of
    pinning the file's shape in place.
    """
    src = (REPO / CHAIN_TEST).read_text(encoding='utf-8')
    total = 0
    for method in methods:
        start = src.index('def ' + method)
        nxt = src.find('\n    def ', start + 10)
        body = src[start:nxt if nxt > 0 else len(src)]
        total += len(re.findall(r'self\.hop\(', body))
        total += len(re.findall(r'self\.hops\.append\(', body))
    _require(total, '+'.join(methods) + ' hop labels')
    return total


def acceptance_hops() -> int:
    return _chain_labels('test_the_chain_walks_from_project_to_a_reviewed_candidate')


def delivery_hops() -> int:
    return _chain_labels('test_the_delivery_leg_reaches_a_preflight_verdict_on_one_project',
                         '_deliver_to_preflight')


WRITE_TEST = 'design-lab/tests/test_installed_write_surface.py'
LEDGER = 'design-lab/config/contract-bindings.json'


def ledger_post_rows() -> int:
    """POST-containing ledger rows -- the denominator the write sweep is checked against."""
    document = json.loads((REPO / LEDGER).read_text(encoding='utf-8'))
    rows = [row['route'] for row in document['routes'] if 'POST' in row['method']]
    _require(len(rows), 'ledger POST rows')
    return len(rows)


def write_sweep_walked() -> int:
    """How many rows the write table performs, counted from the table itself.

    The prose distinguishes "walked" from "excluded", so the number has to come from the table's own
    entries rather than from the ledger: those two differ by exactly the rows the sweep refuses to
    POST, and a sentence that conflated them must not be able to agree with itself.
    """
    src = (REPO / WRITE_TEST).read_text(encoding='utf-8')
    start = src.index('WRITES = (')
    region = src[start:src.index('# -- the walk', start)]
    count = len(re.findall(r"^\s+\{'route':", region, re.M))
    _require(count, 'write-sweep WRITES entries')
    return count



def ledger_get_rows() -> int:
    """Ledger rows whose method is GET only -- the read sweep's denominator."""
    document = json.loads((REPO / LEDGER).read_text(encoding='utf-8'))
    rows = [row['route'] for row in document['routes'] if row['method'] == 'GET']
    _require(len(rows), 'ledger GET rows')
    return len(rows)


def get_sweep_unmeasured() -> int:
    """How many ledger GET rows the read sweep still does not call, counted from its own table.

    The sweep prints this number; the prose quotes it. Counting the marker-prefixed entries
    (`UNCONSTRUCTED:` / `COVERED-ELSEWHERE:` / `NOT-A-PATH:`) rather than trusting the sentence keeps
    "we stopped measuring this" from being reported as "there was nothing to measure".
    """
    src = (REPO / CHAIN_TEST).read_text(encoding='utf-8')
    region = src[src.index('GET_READS = {'):src.index('#: 5xx the sweep may see')]
    count = len(re.findall(r"\['(UNCONSTRUCTED:|COVERED-ELSEWHERE:|NOT-A-PATH:)", region))
    _require(count, 'read-sweep unmeasured entries')
    return count


PAYLOAD_GATE = 'design-lab/scripts/verify_route_payload_contracts.py'

WEIGHT_TEST = 'design-lab/tests/test_workbench_weight.py'


def unbounded_routes() -> int:
    """How many list GET routes the weight gate still registers as answering without a bound.

    Read from `UNBOUNDED_REGISTER` in the test that owns it, by text: the register's own
    `test_the_unbounded_set_is_exactly_the_register` already proves the table agrees with the live
    instrument, so counting the table is counting the population without importing anything (this
    gate runs on a bare interpreter in the node job's step, where Pillow is not installed).
    Added 2026-10-26 because the prose said "其余 7 条" while the register held eight: bounding
    `_list_prompt_results` moved the set from nine to eight, and the sentence was doing arithmetic
    on neither.
    """
    src = (REPO / WEIGHT_TEST).read_text(encoding='utf-8')
    start = src.index('UNBOUNDED_REGISTER = {')
    body = src[start:src.index('\n}\n', start)]
    return _require(len(re.findall(r"^\s+'(_list_[a-z0-9_]+)':", body, re.M)), 'UNBOUNDED_REGISTER')

#: The four envelope versions the design-layer family got on 2026-10-23. Named here because the
#: sentence this measures claims a row COUNT, and a count of "the rows that carry these versions"
#: can only be re-checked against the ledger that records them.
DESIGN_LAYER_FAMILY_VERSIONS = ('design-lab/design-record/v1',
                                'design-lab/design-collection/v1',
                                'design-lab/design-lineage/v1',
                                'design-lab/design-layer-rollup/v1')


def ledger_kind(kind: str) -> int:
    """How many route rows the ledger classifies as `kind` right now."""
    document = json.loads((REPO / LEDGER).read_text(encoding='utf-8'))
    count = len([row for row in document['routes'] if row.get('kind') == kind])
    _require(count, f'ledger {kind} rows')
    return count


def design_layer_family_rows() -> int:
    """Route rows bound by one of the four design-layer envelope versions."""
    document = json.loads((REPO / LEDGER).read_text(encoding='utf-8'))
    count = len([row for row in document['routes']
                 if row.get('version') in DESIGN_LAYER_FAMILY_VERSIONS])
    _require(count, 'design-layer family rows')
    return count


def payload_gate_bindings() -> int:
    """Bindings the live-payload gate declares, counted from its own table.

    The gate prints `bindings=N` from `len(build_bindings())`; the prose quotes that number, so it
    is re-derived from the same list literal rather than copied from a run.
    """
    src = (REPO / PAYLOAD_GATE).read_text(encoding='utf-8')
    region = src[src.index('def build_bindings('):src.index('\ndef registry(',
                           src.index('def build_bindings('))]
    count = len(re.findall(r"^\s+'name': ", region, re.M))
    _require(count, 'payload-gate bindings')
    return count


# (file, template, measurement). Templates carry enough words to be unambiguous and to fail loudly
# when the sentence is rewritten rather than updated.
#
# The two ledger-count sentences are separate denominators on purpose. The frozen one appears on four
# authority surfaces that all restate the same fact about the 2026-10-09 dispatch; the dispatched one
# appears on the two surfaces that describe the 2026-10-23 segment. Neither may be quoted from the
# other: a session that read "34" and wrote it as the size of the current dispatch would match a real
# sentence and still be wrong.
CLAIMS = [
    ('DESIGN.md', '导航 {n} 项', route_views),
    ('docs/current/NEXT-AGENT-PROMPT.md', '{n} 个子命令（`src/design_lab/cli.py`', cli_subcommands),
    ('docs/current/NEXT-AGENT-PROMPT.md', 'adapter-registry.json` {n} 条', registry_adapters),
    ('docs/current/NEXT-AGENT-PROMPT.md', 'ROUTES` 为准，共 {n} 条', http_routes),
    # The write sweep's two denominators: the ledger's POST rows, and how many of them the table
    # actually performs. Both are quoted in the current face, and they differ by the excluded rows.
    ('docs/current/NEXT-AGENT-PROMPT.md', '账本 **{n} 条 POST 行**', ledger_post_rows),
    ('docs/current/NEXT-AGENT-PROMPT.md', '其中 **{n} 行**逐行真写', write_sweep_walked),
    ('docs/current/NEXT-AGENT-PROMPT.md', '账本是 **{n} 条** GET 行', ledger_get_rows),
    ('docs/current/NEXT-AGENT-PROMPT.md', '仍有 **{n} 条**没被这条扫描读到', get_sweep_unmeasured),
    # The capacity half of owner finding 7: how many list routes still answer without a bound.
    ('docs/current/NEXT-AGENT-PROMPT.md', '**{n} 条无界路由**', unbounded_routes),
    # The design-layer family's three denominators (batch I, 2026-10-23): how many rows that family
    # was paid, how many route rows still have no contract at all, and how many live bindings the
    # payload gate now runs. All three are counted from the ledger and the gate table itself.
    ('docs/current/NEXT-AGENT-PROMPT.md', '这一族付掉 **{n} 行**', design_layer_family_rows),
    ('docs/current/NEXT-AGENT-PROMPT.md', '账本仍有 **{n} 行**没有合同',
     lambda: ledger_kind('SCHEMA_LESS')),
    ('docs/current/NEXT-AGENT-PROMPT.md', 'live 载荷比对现在 **{n} 条绑定**',
     payload_gate_bindings),
    ('docs/current/NEXT-AGENT-PROMPT.md', '**{n} 跳验收链**', acceptance_hops),
    ('docs/current/NEXT-AGENT-PROMPT.md', '**{n} 跳交付链**', delivery_hops),
    ('docs/current/NEXT-AGENT-PROMPT.md', '` 的 **{n} 项父/子任务全部', frozen_current_tasks),
    ('AUTHORITY.md', '其余 {n} 项仍 `FROZEN_DEFERRED`', frozen_current_tasks),
    ('AGENTS.md', '其余 {n} 项仍 `FROZEN_DEFERRED`', frozen_current_tasks),
    ('docs/current/PRODUCT_DEFINITION.md', '其余 {n} 项仍 `FROZEN_DEFERRED`', frozen_current_tasks),
    ('docs/taskpacks/20261020-unfreeze/OWNER-DECISION-2026-10-20.md',
     '其余 {n} 项仍 `FROZEN_DEFERRED`', frozen_current_tasks),
    # The 2026-10-23 dispatch segment, on the two surfaces that describe it. Counted from the ledger
    # itself, so a task added there without a sentence here -- or a sentence without a task -- is red.
    ('docs/current/NEXT-AGENT-PROMPT.md', '当前可派工 **{n} 项**', dispatched_current_tasks),
    ('docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md',
     '新派工 **{n} 项**', dispatched_current_tasks),
]



def check(verbose: bool = False) -> int:
    problems = []
    for rel, template, measure in CLAIMS:
        truth = measure()
        text = (REPO / rel).read_text(encoding='utf-8')
        want = template.format(n=truth)
        if want in text:
            if verbose:
                print(f'PASS {rel}: {want}')
            continue
        # The template is prose, not a pattern: '**{n} 跳验收链**' starts with `**`, which is an
        # illegal regex on its own. Escaping first and substituting the escaped placeholder keeps the
        # report path from raising PatternError exactly when a document is stale -- the one moment the
        # gate has to answer with a finding instead of a traceback.
        pattern = re.escape(template).replace(re.escape('{n}'), r'(\d+)')
        said = re.findall(pattern, text)
        problems.append(f'{rel}: prose says {said or "nothing"}, measurement says {truth} '
                        f'(expected the sentence "{want}")')
    for line in problems:
        print('FAIL ' + line)
    if problems:
        print(f'DOCUMENTED_COUNTS=FAIL claims={len(CLAIMS)} failed={len(problems)}')
        return 1
    print(f'DOCUMENTED_COUNTS=PASS claims={len(CLAIMS)} route_views={route_views()} '
          f'cli={cli_subcommands()} adapters={registry_adapters()} routes={http_routes()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(check('--verbose' in sys.argv))
