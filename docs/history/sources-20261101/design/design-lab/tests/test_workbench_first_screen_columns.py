# SPDX-License-Identifier: MIT
"""首屏双列（最近方案进右列）：结构、说法与"一份声明"的静态看守。

owner 2026-10-28 那一刀的原文是"首屏双列（最近方案进右列）"。设计辅助那屏早就有了这一列
（`2d9372fb`，2026-10-24），真正没有的是应用打开时那面——默认路由 `''`（遗留工作台）：它的一行
两列里右边那块是一个从未导入过东西的预览占位。这一组检查量的是改完之后仍然可能安静坏掉的四件事：

* 结构：`.grid` 的两个直接子元素必须是两个 `.col`，方案面板必须在**第二个**里，01→02 的顺序与
  03/04/05 仍在 `.grid` 之外（那三面是全宽的，被搬进列里会静默变窄）；
* 一份声明：方案列表信封的 TypeScript 形状只能在 contracts.ts 声明一次。它在 shell.ts 里原本
  有一份，这一刀让第二个读者（首屏）出现，第二份就成了会漂移的台账；
* 说法：未选项目 / 读被拒 / 形状缺字段 三句必须各自说"没读到"，只有真读到 0 条的那句能说"共 0 条"，
  而 index.html 里脚本运行前的初始文字必须与 resetProject() 写回的那句逐字相同（两份各写一次就
  会在下一次改文案时只改到一份）；
* 目的地：`#open-assistant` 写的 hash 必须等于 ROUTE_VIEWS 里 view='assistant' 那条，否则这一列
  的按钮指向一个不存在的路由，而页面不会为此报任何错。

浏览器那侧的几何（两列是否真排在两侧、面板是否真在第二列里、那句话是否真被画出来）由
design-lab/tests/e2e/audit_workbench_overflow.mjs 的 `firstScreen` 读数与
test_workbench_overflow_gate.py 的 `_assert_first_screen_columns` 负责；这里只守静态字节，
每条都配了植入缺陷的证伪，免得断言因为无条件而恒真。
"""
from __future__ import annotations

import html.parser
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INDEX = REPO / 'apps' / 'workbench' / 'index.html'
STYLES = REPO / 'apps' / 'workbench' / 'style.css'
WORKBENCH_TS = REPO / 'apps' / 'workbench' / 'workbench.ts'
SHELL_TS = REPO / 'apps' / 'workbench' / 'shell.ts'
CONTRACTS_TS = REPO / 'apps' / 'workbench' / 'contracts.ts'
PLAN_STORE_PY = REPO / 'src' / 'design_lab' / 'assistance_plan.py'

VOID = {'input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'area', 'col', 'wbr'}


class _GridChildren(html.parser.HTMLParser):
    """The direct children of the landing's `.grid`, with the ids painted inside each of them.

    An HTML parser rather than a regex because the fact being counted is nesting: a panel that
    moved *inside* the second column and a panel that merely sits near it in the text are the same
    match to a pattern and different boxes to a browser. `closed_at` is where `.grid` ended, which
    is what lets the caller say that panels 03-05 are still after the two columns.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.done = False
        self.depth = 0                      # 1 == inside .grid itself
        self.children: list[dict] = []
        self.current: dict | None = None
        self.closed_at: tuple[int, int] | None = None

    def _note(self, attrs: dict) -> None:
        if self.current is not None and attrs.get('id'):
            self.current['ids'].append(attrs['id'])

    def handle_starttag(self, tag, raw_attrs):
        if self.done:
            return
        attrs = dict(raw_attrs)
        classes = (attrs.get('class') or '').split()
        if not self.inside:
            if tag == 'div' and 'grid' in classes:
                self.inside = True
                self.depth = 1
            return
        if self.depth == 1:
            self.current = {'tag': tag, 'class': attrs.get('class') or '',
                            'ids': [], 'text': ''}
            self.children.append(self.current)
        else:
            self._note(attrs)
        if tag not in VOID:
            self.depth += 1

    def handle_endtag(self, tag):
        if self.done or not self.inside or tag in VOID:
            return
        self.depth -= 1
        if self.depth == 1:
            self.current = None
        elif self.depth == 0:
            # `.grid` is closed; the full-width panels after it are graded by position instead,
            # and keeping the walk alive here would report them as third children.
            self.closed_at = self.getpos()
            self.current = None
            self.done = True

    def handle_data(self, data):
        if not self.done and self.current is not None:
            self.current['text'] += data


def _offset_of(markup: str, position: tuple[int, int]) -> int:
    line, column = position
    return sum(len(kept) for kept in markup.splitlines(True)[:line - 1]) + column


def assert_landing_structure(markup: str) -> list[str]:
    """Findings about the first screen's two columns. Empty list == the cut is in place."""
    parser = _GridChildren()
    parser.feed(markup)
    if not parser.inside:
        return ['no `<div class="grid">` was found: the landing markup moved out from under '
                'this check']
    problems: list[str] = []
    children = parser.children
    cols = [c for c in children if 'col' in c['class'].split()]
    if len(children) != 2 or len(cols) != 2:
        problems.append('.grid has %d direct child(ren) (%s) and %d of them are .col, expected '
                        'the two .col wrappers this cut introduced'
                        % (len(children), [c['class'] or c['tag'] for c in children], len(cols)))
        return problems
    left, right = cols[0], cols[1]
    if '01 / REFERENCE' not in left['text'] or '02 / VERIFIED READBACK' not in left['text']:
        problems.append('the left column does not carry both import panels')
    if left['text'].find('01 / REFERENCE') > left['text'].find('02 / VERIFIED READBACK'):
        problems.append('the left column puts the readback preview before the import form')
    if '01 / REFERENCE' in right['text']:
        problems.append('the import panel moved into the plan column')
    if '最近方案' not in right['text']:
        problems.append('the right column renders no 最近方案 heading')
    for needle in ('recent-plans', 'recent-plans-info', 'open-assistant'):
        if needle not in right['ids']:
            problems.append(f'the right column does not contain id="{needle}": {right["ids"]}')
    # Panels 03-05 are full width by being OUTSIDE .grid; pulling one in would narrow it silently.
    if parser.closed_at is None:
        return problems + ['the `.grid` element never closed, so its extent is not knowable']
    end = _offset_of(markup, parser.closed_at)
    for eyebrow in ('03 / EXECUTION HISTORY', '04 / NATIVE ASSETS', '05 / DESIGN LAYER'):
        if eyebrow in left['text'] + right['text']:
            problems.append(f'{eyebrow} was moved inside a column, so it is no longer a '
                            'full-width panel')
        elif markup.find(eyebrow) < end:
            problems.append(f'{eyebrow} is now before the end of .grid, which is the same move '
                            'worn differently')
    return problems


def top_level_rule(block: str, selector: str) -> str | None:
    """The declarations of `selector{...}` at top level, or None if it is not defined once.

    Counted, not assumed: the second definition of the same selector is the defect
    test_workbench_css_single_definition.py exists to convict, and this rule is new.
    """
    found = re.findall(r'(?m)^' + re.escape(selector) + r'\{([^}]*)\}', block)
    return found[0] if len(found) == 1 else None


#: The two rules this cut introduced, and what each must still carry. `.plan-line` is here because
#: the row layout is the fix for a date breaking mid-token at 1100px, seen in the rendered screen.
COLUMN_RULES = (('.grid>.col', ('display:grid', 'gap:inherit', 'min-width:0')),
                ('.plan-line', ('display:flex', 'flex-direction:column', 'min-width:0')))


def assert_column_rule(css: str) -> list[str]:
    problems: list[str] = []
    for selector, required in COLUMN_RULES:
        declarations = top_level_rule(css, selector)
        if declarations is None:
            seen = len(re.findall(re.escape(selector) + r'\s*\{', css))
            problems.append(f'{selector} is not defined exactly once at top level (the loose scan '
                            f'saw {seen}): the layout has either gone or grown a second definition, '
                            'and a second one wins by source order in silence')
            continue
        compact = declarations.replace(' ', '')
        for wanted in required:
            if wanted not in compact:
                problems.append(f'{selector} lost {wanted}: {declarations.strip()!r}')
        if selector == '.grid>.col' \
                and re.search(r'\b(?:[2-9]|[1-9]\d{1,3})px\b', declarations):
            problems.append('.grid>.col hard-codes a length instead of inheriting the row gap, '
                            f'which is the duplicate the debt ledger counts: '
                            f'{declarations.strip()!r}')
    return problems


#: The three sentences that must NOT imply the project has no plans, and the phrase each one is
#: built around. These are the same three phrases the geometry gate reads
#: (test_workbench_overflow_gate.UNREAD_MARKERS): the painted text and the source that writes it
#: are checked against one list, not two that can drift.
UNREAD_SENTENCES = ('没有读过', '没读到', '未读回')
ZERO_CLAIM = '没有方案记录'


def _string_literals(source: str) -> list[str]:
    """The single-quoted and template literals of a TypeScript file, comments excluded.

    Comments are excluded on purpose: this file's own comment says "没读到 = the read was refused",
    and a check that grades prose would convict the sentence that documents the rule.
    """
    return [(match.group(1) if match.group(1) is not None else match.group(2))
            for match in re.finditer(r"'([^'\n]*)'|`([^`]*)`", source)]


def assert_honest_sentences(markup: str, source: str) -> list[str]:
    problems = []
    initial = re.search(r'<p id="recent-plans-info"[^>]*>([^<]*)</p>', markup)
    if not initial:
        return ['#recent-plans-info is not in index.html: the column has no readback line']
    reset = re.search(r"byId<HTMLParagraphElement>\('recent-plans-info'\)\.textContent = "
                      r"'([^']*)'", source)
    if not reset:
        return ['resetProject() no longer resets #recent-plans-info, so a disconnected session '
                'keeps the previous project\'s sentence on screen']
    if initial.group(1).strip() != reset.group(1).strip():
        problems.append('the two writers of the initial sentence disagree: index.html says %r, '
                        'resetProject writes %r' % (initial.group(1).strip(), reset.group(1).strip()))
    literals = _string_literals(source)
    unread = [text for text in literals if any(m in text for m in UNREAD_SENTENCES)]
    missing = [marker for marker in UNREAD_SENTENCES
               if not any(marker in text for text in unread)]
    if missing:
        problems.append('these not-read states no longer have their own sentence: %s (seen: %s)'
                        % (missing, [text.strip() for text in unread]))
    for text in unread:
        if ZERO_CLAIM in text or '共 0' in text:
            problems.append('a state that never got an answer claims the project has no plans: %s'
                            % text.strip())
    return problems


def assert_destination_agrees(workbench_ts: str, shell_ts: str) -> list[str]:
    problems = []
    written = re.findall(r"window\.location\.hash = '([^']+)'", workbench_ts)
    if len(written) != 1:
        return [f'the landing writes {len(written)} route hash(es) from its own handlers, '
                f'expected the one plan-column action: {written}']
    row = re.search(r"\{ hash: '([^']+)', view: 'assistant'", shell_ts)
    if not row:
        return ['ROUTE_VIEWS no longer carries a view named "assistant" in the shape this check '
                'reads, so the destination cannot be verified']
    if written[0] != row.group(1):
        problems.append('the plan column opens %r but ROUTE_VIEWS names %r for 设计辅助'
                        % (written[0], row.group(1)))
    return problems


def assert_bounded_read(workbench_ts: str, max_limit: int) -> list[str]:
    problems = []
    declared = re.search(r'export const RECENT_PLANS_LIMIT = ([0-9]+);', workbench_ts)
    if not declared:
        return ['RECENT_PLANS_LIMIT is no longer a literal number: the column would read the '
                'route without a bound, which is what this repository calls an unbounded route']
    limit = int(declared.group(1))
    if not 1 <= limit <= max_limit:
        problems.append(f'the column asks limit={limit}, outside the store\'s 1..{max_limit}')
    if 'assistance-plans?limit=${RECENT_PLANS_LIMIT}' not in workbench_ts:
        problems.append('the landing read no longer passes the bound into the query, so the '
                        'column would pull a whole list into the first screen')
    return problems


def contracts_import_names(source: str) -> set[str]:
    """The names one module takes from './contracts.js'. Matched on the import block, not on a
    substring: `AssistancePlanListView,` also occurs in ordinary code, and a check that cannot
    tell the two apart passes for the wrong reason."""
    block = re.search(r"import type \{([^}]*)\}\s*from\s*'\./contracts\.js'", source)
    if not block:
        return set()
    return {part.strip() for part in block.group(1).split(',') if part.strip()}


def assert_single_declaration(contracts_ts: str, shell_ts: str) -> list[str]:
    problems = []
    imported = contracts_import_names(shell_ts)
    for name in ('AssistancePlanRow', 'AssistancePlanListView'):
        in_contracts = len(re.findall(r'export interface ' + name + r'\b', contracts_ts))
        in_shell = len(re.findall(r'\binterface ' + name + r'\b', shell_ts))
        if in_contracts != 1 or in_shell != 0:
            problems.append(f'{name}: declared {in_contracts} time(s) in contracts.ts and '
                            f'{in_shell} in shell.ts; two readers need one declaration')
        if name not in imported:
            problems.append(f'shell.ts no longer imports {name} from contracts.js, so the shared '
                            'declaration is not the one the assistant screen compiles against')
    return problems


def assert_guard_precedes_dereference(source: str) -> list[str]:
    """The array guard must come before anything reads `.plans` — CI caught the reverse order.

    `api()` does not normalise a short answer, so a 200 without `plans` reaches the view as an
    object whose `plans` is undefined. The seam-aware `shapeFieldMissing` cannot see that (it only
    reports what `apiOrEmpty` invented), and `data.plans.length` on the strength of the type
    annotation is what made `test_workbench_native_ui` fail at the first cloud run of this cut.
    """
    guard = source.find('Array.isArray(data?.plans)')
    read = source.find('const rows = data.plans;')
    if read < 0:
        return ['the plan column no longer reads data.plans through a named local; this check '
                'cannot tell guard order from absence']
    if guard < 0:
        return ['the column dereferences data.plans without an array guard, so a 200 answer that '
                'omits plans throws instead of saying 未读回']
    if guard > read:
        return [f'the array guard sits at {guard}, after the dereference at {read}: the crash it '
                'exists to prevent happens first']
    return []


class LandingStructureTests(unittest.TestCase):
    def test_the_shipped_landing_passes_its_own_check(self):
        self.assertEqual(assert_landing_structure(INDEX.read_text(encoding='utf-8')), [])

    def test_the_column_rule_is_defined_once_and_adds_no_literal(self):
        self.assertEqual(assert_column_rule(STYLES.read_text(encoding='utf-8')), [])

    def test_the_sentences_stay_distinguishable_and_the_two_writers_agree(self):
        markup = INDEX.read_text(encoding='utf-8')
        source = WORKBENCH_TS.read_text(encoding='utf-8')
        self.assertEqual(assert_honest_sentences(markup, source), [])

    def test_the_plan_column_opens_the_route_the_table_declares(self):
        self.assertEqual(assert_destination_agrees(
            WORKBENCH_TS.read_text(encoding='utf-8'),
            SHELL_TS.read_text(encoding='utf-8')), [])

    def test_the_read_is_bounded_by_a_number_the_store_accepts(self):
        store = PLAN_STORE_PY.read_text(encoding='utf-8')
        maximum = re.search(r'MAX_LIMIT = ([0-9]+)', store)
        self.assertIsNotNone(maximum, 'assistance_plan.py no longer declares MAX_LIMIT')
        self.assertEqual(assert_bounded_read(
            WORKBENCH_TS.read_text(encoding='utf-8'), int(maximum.group(1))), [])

    def test_the_list_envelope_is_declared_in_one_file(self):
        self.assertEqual(assert_single_declaration(
            CONTRACTS_TS.read_text(encoding='utf-8'),
            SHELL_TS.read_text(encoding='utf-8')), [])

    def test_the_plans_array_is_guarded_before_anything_reads_it(self):
        self.assertEqual(assert_guard_precedes_dereference(
            WORKBENCH_TS.read_text(encoding='utf-8')), [])


class PlantedFaultsAreConvicted(unittest.TestCase):
    """Each finding above is shown to move: an assertion nobody has seen red guards nothing."""

    def setUp(self):
        self.markup = INDEX.read_text(encoding='utf-8')
        self.source = WORKBENCH_TS.read_text(encoding='utf-8')
        self.css = STYLES.read_text(encoding='utf-8')
        self.shell = SHELL_TS.read_text(encoding='utf-8')

    def test_a_panel_moved_out_of_the_column_is_convicted(self):
        # The exact accident this cut invites: a fourth panel added straight to `.grid`, which
        # auto-places it as a third column instead of joining the left stack.
        planted = self.markup.replace('<section class="panel preview-panel">',
                                      '</div><section class="panel preview-panel">')
        findings = assert_landing_structure(planted)
        self.assertTrue(findings, 'a third direct child of .grid passed as two columns')
        self.assertIn('two .col wrappers', findings[0])

    def test_a_plan_column_without_the_readback_line_is_convicted(self):
        findings = assert_landing_structure(self.markup.replace('id="recent-plans-info"',
                                                                'id="other-line"'))
        self.assertTrue([f for f in findings if 'recent-plans-info' in f], findings)

    def test_a_second_definition_of_the_column_rule_is_convicted(self):
        findings = assert_column_rule(self.css + '\n.grid>.col{display:block}\n')
        self.assertTrue(findings, 'a duplicate .grid>.col definition slipped through')
        findings = assert_column_rule(self.css.replace('gap:inherit', 'gap:20px'))
        self.assertTrue([f for f in findings if 'hard-codes a length' in f], findings)
        findings = assert_column_rule(self.css.replace('.plan-line{', '.plan-row{'))
        self.assertTrue([f for f in findings if '.plan-line is not defined' in f], findings)
        findings = assert_column_rule(self.css.replace('flex-direction:column;', ''))
        self.assertTrue([f for f in findings if 'lost flex-direction:column' in f], findings)

    def test_the_zero_claim_in_an_unread_state_is_convicted(self):
        planted = self.source.replace(
            '最近方案没读到：${errMsg(error)}。这不代表这个项目没有方案。',
            '最近方案没读到：${errMsg(error)}。所以这个项目还没有方案记录。')
        self.assertNotEqual(planted, self.source, 'the planted sentence no longer matches')
        findings = assert_honest_sentences(self.markup, planted)
        self.assertTrue([f for f in findings if 'claims the project has no plans' in f], findings)

    def test_a_drifted_initial_sentence_is_convicted(self):
        planted = self.source.replace(
            "byId<HTMLParagraphElement>('recent-plans-info').textContent = "
            "'未选项目，因此这一列没有读过任何方案。'",
            "byId<HTMLParagraphElement>('recent-plans-info').textContent = '还没选项目。'")
        findings = assert_honest_sentences(self.markup, planted)
        self.assertTrue([f for f in findings if 'two writers' in f], findings)

    def test_a_destination_that_is_not_in_the_route_table_is_convicted(self):
        findings = assert_destination_agrees(
            self.source.replace("window.location.hash = '#/assistant'",
                                "window.location.hash = '#/plans'"), self.shell)
        self.assertTrue(findings, 'a hash that ROUTE_VIEWS does not declare passed')

    def test_an_unbounded_or_out_of_range_read_is_convicted(self):
        findings = assert_bounded_read(self.source.replace(
            '/assistance-plans?limit=${RECENT_PLANS_LIMIT}', '/assistance-plans'), 50)
        self.assertTrue([f for f in findings if 'without the bound' in f
                         or 'passes the bound' in f], findings)
        findings = assert_bounded_read(self.source.replace(
            'export const RECENT_PLANS_LIMIT = 5;', 'export const RECENT_PLANS_LIMIT = 500;'), 50)
        self.assertTrue([f for f in findings if 'outside' in f], findings)

    def test_reading_the_plans_array_before_the_guard_is_convicted(self):
        """The exact defect the first cloud run of this cut caught, planted both ways."""
        guard = '  if (!Array.isArray(data?.plans)) {\n    return;\n  }\n'
        read = '  const rows = data.plans;\n'
        self.assertEqual(assert_guard_precedes_dereference(guard + read), [])
        self.assertTrue([f for f in assert_guard_precedes_dereference(read)
                         if 'without an array guard' in f])
        self.assertTrue([f for f in assert_guard_precedes_dereference(read + guard)
                         if 'happens first' in f])
        self.assertTrue(assert_guard_precedes_dereference('export async function f() {}\n'),
                        'a column that stopped reading the envelope at all must not pass')
        self.assertEqual(assert_guard_precedes_dereference(self.source), [])

    def test_a_second_copy_of_the_envelope_is_convicted(self):
        contracts = CONTRACTS_TS.read_text(encoding='utf-8')
        findings = assert_single_declaration(
            contracts, self.shell + '\ninterface AssistancePlanRow {\n  plan_id: string;\n}\n')
        self.assertTrue([f for f in findings if 'AssistancePlanRow' in f], findings)
        findings = assert_single_declaration(
            contracts.replace('export interface AssistancePlanRow {', 'interface AssistancePlanRow {'),
            self.shell)
        self.assertTrue([f for f in findings if 'AssistancePlanRow' in f], findings)
        findings = assert_single_declaration(
            contracts, self.shell.replace('  AssistancePlanListView,\n', ''))
        self.assertTrue([f for f in findings if 'imports AssistancePlanListView' in f], findings)


if __name__ == '__main__':
    unittest.main()
