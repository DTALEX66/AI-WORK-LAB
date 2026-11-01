# SPDX-License-Identifier: MIT
"""Workbench stylesheet: no class may be defined twice by accident.

Cascade makes the *later* declaration win, so a repeated selector is not merely
untidy -- the earlier block becomes dead or silently partly dead. `DL-DIR` audit
D-2 found three such cases in the Workbench (`.items`, `.mono`, `.error`) where
the winning layout / family / size came from a different block than the reader
would assume. The owner ruled on 2026-10-07 that the fix is to split the
overloaded names into distinct ones.

Layer overrides that ARE intended (the B10 replica block, the F-3 font-scale
correction block) stay legal by being listed in SANCTIONED with a reason. The
gate is two-way, so a sanctioned entry that gets fixed away also fails: the
ledger cannot rot into a list of excuses for bugs that no longer exist.
"""
import re
import unittest
from pathlib import Path

WORKBENCH_DIR = Path(__file__).resolve().parents[2] / "apps" / "workbench"
STYLE_SHEET = WORKBENCH_DIR / "style.css"

# selector -> why two definitions of it are intentional.
SANCTIONED = {
    "*": "B10 replica block re-declares the identical box-sizing reset; "
         "byte-identical, so cascade order is irrelevant.",
    "body": "legacy body{margin:0} vs the B10 block's html,body{margin:0}; "
            "same value from both.",
    ".panel": "B10 replica block is the visual authority for .panel and "
              "redefines the legacy card (see the authority-order comment).",
    ".toolbar": "B10 replica block is the visual authority for .toolbar.",
    ".kpi-grid": "B10 replica block is the visual authority for .kpi-grid.",
    ".eyebrow": "F-3 block raises the label scale to the project's own declared "
                "token sizes; the override is the point of that block.",
    ".badge": "F-3 block, same reason as .eyebrow.",
    ".brand small": "F-3 block, same reason as .eyebrow.",
    "body > header p": "F-3 block pins body copy to 14px for the legacy page "
                       "chrome only.",
    "body > main p": "F-3 block, same reason as body > header p.",
    "body > footer p": "F-3 block, same reason as body > header p.",
    # The 20261023 pack states 圆角输入/按钮 as 6-10px, and its colours ship as an additive
    # theme (standing owner ruling: a new pack's values become a selectable theme, never an
    # override of what is already shipped). So the radius is re-declared ONLY inside
    # :root[data-palette="stitch"][data-scheme="light"]; the default theme keeps 12/14px.
    # Measured before the block, one width: 474 of 501 graded form controls over 10px.
    ".primary-btn": "20261023 pack theme sets the control radius band for the pack palette "
                    "only; the override is the point of that block.",
    ".soft-btn": "20261023 pack theme, same reason as .primary-btn.",
    "select": "20261023 pack theme, same reason as .primary-btn.",
}

# The D-2 split: these names must exist exactly once each, and the overloaded
# name they were split out of must be gone.
SINGLE_DEFINITION_CLASSES = (".items-stack", ".items-chips")
RETIRED_CLASS = ".items"


def strip_comments(text):
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def split_top_level_rules(css_text):
    """Return [(selector, declarations_text)] for top-level rule blocks.

    At-rule blocks (@media/@supports/@keyframes/@layer/@font-face) are consumed
    whole and not descended into: a responsive or state override is intended
    cascade, not a duplicate definition.
    """
    body = strip_comments(css_text)
    rules = []
    i = 0
    n = len(body)
    while i < n:
        while i < n and body[i] in " \t\r\n;":
            i += 1
        if i >= n:
            break
        brace = body.find("{", i)
        if brace < 0:
            break
        semicolon = body.find(";", i)
        if 0 <= semicolon < brace:
            i = semicolon + 1
            continue
        selector = body[i:brace].strip()
        depth = 1
        j = brace + 1
        while j < n and depth:
            if body[j] == "{":
                depth += 1
            elif body[j] == "}":
                depth -= 1
            j += 1
        if not selector.startswith("@"):
            rules.append((selector, body[brace + 1:j - 1]))
        i = j
    return rules


def rule_properties(declarations_text):
    props = []
    for part in declarations_text.split(";"):
        part = part.strip()
        if part and ":" in part:
            props.append(part.split(":", 1)[0].strip().lower())
    return props


def duplicate_definitions(css_text):
    """{selector: [(block_index, [clashing property, ...]), ...]} for real clashes."""
    blocks = []
    for selector, declarations_text in parse(css_text):
        blocks.append((selector, rule_properties(declarations_text)))
    seen = {}
    for index, (selector, props) in enumerate(blocks):
        for part in [p.strip() for p in selector.split(",") if p.strip()]:
            if part.startswith("@") or part.startswith(":root"):
                continue
            seen.setdefault(part, []).append((index, props))
    duplicates = {}
    for selector, occurrences in seen.items():
        if len(occurrences) < 2:
            continue
        first_owner = {}
        clashes = []
        for index, props in occurrences:
            for prop in props:
                if prop in first_owner:
                    clashes.append(prop)
                else:
                    first_owner[prop] = index
        if clashes:
            duplicates[selector] = [(i, p) for i, p in occurrences]
    return duplicates


def parse(css_text):
    return split_top_level_rules(css_text)


class StylesheetParsing(unittest.TestCase):
    def setUp(self):
        self.css = STYLE_SHEET.read_text(encoding="utf-8")

    def test_parser_reads_the_real_stylesheet(self):
        """A parser that silently returns nothing would pass every assertion below."""
        rules = parse(self.css)
        self.assertGreater(len(rules), 200,
                           "the Workbench stylesheet should have far more than 200 "
                           "top-level rules; the parser is broken, not the CSS")
        selectors = {s for s, _ in rules}
        for must_exist in (".tag", ".list-item", ".panel", ".mono"):
            self.assertTrue(any(must_exist in s for s in selectors),
                            f"parser lost {must_exist}")


class ViolationShapeIsDetected(unittest.TestCase):
    """Falsification: the gate must fire on the exact defect it claims to catch."""

    def test_second_definition_of_the_same_class_is_reported(self):
        css = """
        .items{padding:0;display:grid;gap:9px}
        .other{color:red}
        .items{display:flex;flex-wrap:wrap;gap:8px}
        """
        duplicates = duplicate_definitions(css)
        self.assertIn(".items", duplicates,
                      "a class defined twice with a clashing property must be found")
        self.assertEqual(sorted(set(duplicates[".items"][-1][1])),
                         ["display", "flex-wrap", "gap"])
        self.assertNotIn(".other", duplicates)

    def test_no_overlap_means_no_clash(self):
        """Two blocks of the same selector that set different properties are fine."""
        css = ".box{color:red}\n.box{padding:4px}\n"
        self.assertNotIn(".box", duplicate_definitions(css))

    def test_media_query_override_is_not_a_duplicate(self):
        css = ".box{color:red}\n@media(max-width:600px){.box{color:blue}}\n"
        self.assertEqual(duplicate_definitions(css), {})

    def test_clean_stylesheet_reports_nothing(self):
        self.assertEqual(duplicate_definitions(".a{color:red}\n.b{color:blue}\n"), {})


class SingleDefinitionLedger(unittest.TestCase):
    def setUp(self):
        self.duplicates = duplicate_definitions(STYLE_SHEET.read_text(encoding="utf-8"))

    def test_duplicate_definitions_are_all_sanctioned(self):
        unsanctioned = sorted(set(self.duplicates) - set(SANCTIONED))
        self.assertEqual(
            unsanctioned, [],
            "these class selectors are defined more than once with a clashing "
            f"property, so the later block silently wins: {unsanctioned}. Split "
            "them into distinct names (the D-2 ruling) or add an entry to "
            "SANCTIONED with a reason if the override is intended.")

    def test_sanctioned_entries_are_still_real_duplicates(self):
        stale = sorted(set(SANCTIONED) - set(self.duplicates))
        self.assertEqual(
            stale, [],
            f"these SANCTIONED entries are no longer duplicates: {stale}. Remove "
            "them so the ledger keeps describing the stylesheet as it is.")


class DTwoSplitLanded(unittest.TestCase):
    """The D-2 fix itself, not just the guard around it."""

    def setUp(self):
        self.css = STYLE_SHEET.read_text(encoding="utf-8")
        self.rules = parse(self.css)

    def _blocks_for(self, exact_selector):
        hits = []
        for selector, declarations_text in self.rules:
            parts = [p.strip() for p in selector.split(",")]
            if exact_selector in parts:
                hits.append(rule_properties(declarations_text))
        return hits

    def test_retired_overloaded_name_is_gone(self):
        hits = self._blocks_for(RETIRED_CLASS)
        self.assertEqual(hits, [],
                         f"{RETIRED_CLASS} must no longer be defined: it carried two "
                         "conflicting layouts, which is what D-2 was about. Its "
                         "replacement names are "
                         f"{', '.join(SINGLE_DEFINITION_CLASSES)}.")
        bare = re.findall(r"(?<![-_a-zA-Z0-9])\.items(?![-_a-zA-Z0-9])",
                          strip_comments(self.css))
        self.assertEqual(bare, [], "no rule or descendant selector may still target "
                                   "the retired .items class")

    def test_split_classes_each_have_one_layout_definition(self):
        """Exactly one block per name may decide how it lays out.

        The shrink-guard near the bottom re-lists both names to set min-width;
        that is not a second layout, so the assertion is on `display`.
        """
        for name in SINGLE_DEFINITION_CLASSES:
            owners = [blocks for blocks in self._blocks_for(name) if "display" in blocks]
            self.assertEqual(len(owners), 1,
                             f"{name} should have exactly one block declaring display")

    def test_stack_and_chips_carry_the_layout_their_name_promises(self):
        """A renamed class must keep the layout it was split out for."""
        stack = self._blocks_for(".items-stack")
        chips = self._blocks_for(".items-chips")
        self.assertIn("display", stack[0])
        self.assertIn("display", chips[0])
        stack_css = strip_comments(self.css)
        self.assertRegex(stack_css, r"\.items-stack\{[^}]*display:grid")
        self.assertRegex(stack_css, r"\.items-chips\{[^}]*display:flex")

    def test_mono_and_error_were_merged_into_one_authoritative_block(self):
        for name in (".mono", ".error"):
            owners = [i for i, (selector, _) in enumerate(self.rules)
                      if name in [p.strip() for p in selector.split(",")]]
            self.assertEqual(len(owners), 1,
                             f"{name} must be defined exactly once, found at blocks "
                             f"{owners}")
        css = strip_comments(self.css)
        mono = re.search(r"\.mono\{([^}]*)\}", css)
        self.assertIsNotNone(mono)
        self.assertIn("font-family", mono.group(1))
        self.assertIn("font-size", mono.group(1))
        self.assertIn("overflow-wrap", mono.group(1),
                      "the merged .mono block must keep every property the three "
                      "separate blocks used to contribute")

    def test_markup_targets_only_the_new_names(self):
        """A renamed class with no call site is dead CSS, and a call site with no
        rule renders unstyled -- both are the failure mode of a rename."""
        markup = (WORKBENCH_DIR / "index.html").read_text(encoding="utf-8")
        shell = (WORKBENCH_DIR / "shell.ts").read_text(encoding="utf-8")
        self.assertNotIn('class="items"', markup)
        self.assertNotIn("'items'", shell)
        self.assertGreaterEqual(markup.count("items-stack"), 8,
                                "the legacy workspace lists should all target "
                                "items-stack")
        self.assertIn("items-chips", shell)


class RowCardSplitLanded(unittest.TestCase):
    """`.list-item` also meant "free-standing card"; that overload is now gone.

    The card half was identifiable exactly because it overrides the row layout
    with its own inline `display`, which a list member never does.
    """

    def setUp(self):
        self.css = STYLE_SHEET.read_text(encoding="utf-8")
        self.shell = (WORKBENCH_DIR / "shell.ts").read_text(encoding="utf-8")

    def test_no_card_still_wears_the_list_member_name(self):
        shape = re.findall(r"class: 'list-item', style: 'display:", self.shell)
        self.assertEqual(shape, [],
                         "an element that sets its own display is a card, not a list "
                         "member; it must use .row-card or the ul/li conversion will "
                         "produce an <li> outside a <ul>")

    def test_row_card_is_defined_with_the_card_surface(self):
        block = re.search(r"\.row-card,\s*\.list-item\{([^}]*)\}", strip_comments(self.css))
        self.assertIsNotNone(block, ".row-card must share the card surface block")
        for prop in ("padding", "border-radius", "background", "border", "transition"):
            self.assertIn(prop, block.group(1),
                          f".row-card/.list-item lost {prop}")


class ListItemIsReallyAListMember(unittest.TestCase):
    """`.list` renders as <ul> with <li> members; cards stay <div>.

    The pattern here is deliberately a regex over the whole attribute object rather
    than a class-name substring. My first pass at this conversion counted
    `class: 'list-item'` occurrences and reported a complete match, while
    `class: 'list-item value-row'` -- a different string -- sat untouched in the same
    helper. A real browser walk found it; this assertion makes the static check see
    it too.
    """

    def setUp(self):
        self.shell = (WORKBENCH_DIR / "shell.ts").read_text(encoding="utf-8")

    def test_no_div_still_claims_to_be_a_list_member(self):
        stray = re.findall(r"el\('div',\s*\{[^}]*class:\s*'[^']*\blist-item\b", self.shell)
        self.assertEqual(stray, [],
                         "a <div> carrying .list-item renders as a list member without "
                         "being one, so screen readers will not announce it in the list")

    def test_no_div_still_claims_to_be_a_list_container(self):
        stray = re.findall(r"el\('div',\s*\{[^}]*class:\s*'[^']*\blist\b[^']*'", self.shell)
        filtered = [s for s in stray if re.search(r"class:\s*'list(\s|')", s)
                    and 'list-item' not in s and 'inspector' not in s]
        self.assertEqual(filtered, [],
                         "a <div> still used as a .list container would leave its <li> "
                         "children outside a list")

    def test_members_and_containers_are_both_present(self):
        """Guard against the assertion above passing because everything was deleted."""
        # Rows are counted as *rendered*, not as literal strings in the file: an empty
        # state now comes from emptyLi(), which holds the one `el('li', ...)` literal for
        # all of its call sites. Counting literals alone fell to 47 while every list row
        # was still an <li> -- the floor is about the DOM, so the measure has to follow
        # the helper. The two subtractions drop the helper's own definition from each
        # tally so a call site is counted exactly once.
        rendered_rows = (self.shell.count("el('li', { class: 'list-item'") - 1
                         + self.shell.count("emptyLi(") - 1)
        self.assertGreaterEqual(rendered_rows, 50,
                                "the source builds list rows through el('li') or emptyLi(); "
                                "a drop below 50 means rows were deleted, not converted")
        # An exact inventory, not a floor: the equality is what makes a half-done
        # migration impossible to miss. 2026-10-08: 30 -> 31 because the Human Jury
        # readback column joined it as a real <ul> (its first version was a <div>,
        # which the two assertions above caught). 2026-10-08 later: 31 -> 32 for the
        # design-system Token column (renderTokenDocumentPanel) -- its live rows and
        # its empty state are both real list members. 2026-10-08 again: 32 -> 33 for
        # the Domain Pack column (renderDomains), whose rows come from domainPackRow()
        # and whose empty state comes from emptyLi(). 2026-10-08 again: 33 -> 34 for the
        # Human Jury column on 证据系统 (evidenceJuryColumn) -- its verdict rows are real
        # <li> members and its empty state comes from emptyLi(), so a read that did not
        # arrive cannot be shown as an empty list. The delivery-receipt column rendered
        # beside it is tables inside .table-wrap, so it adds no container to this count.
        # 2026-10-08 again: 34 -> 35 for the Human RIGHTS column -- rightsScopeRows() is
        # the one list container the rights slice adds, shared by the 预检 / QA readback
        # panel and the read-only 证据系统 column so the two surfaces cannot disagree about
        # what stands; its rows are real <li> members and its empty state is emptyLi(). The
        # rights submission form is a <details>/label/input form (like the jury form) and
        # the does_not_prove lines are paragraphs, so neither adds a container.
        # The number moves because the inventory grew by one verified column, not because
        # a check was relaxed.
        # 2026-10-08 again: 35 -> 38 for the 研究洞察 read-back. Three containers, all three
        # named: researchFacts() lists the façade's own does_not_prove lines so the numbers on the
        # page travel with the sentence about what they do not cover; researchFindingRows() lists
        # the project's persisted findings as real <li> members; and its empty branch is the
        # repository's own three-way empty (emptyLi behind emptyWording), so an absent service can
        # never be drawn as "this project has no findings". Measured with
        # `s.count("el('ul', { class: 'list'")`, because the needle matches the exact class -- a
        # `class: 'list research-findings'` hook would sit outside this inventory while still
        # taking .list styling, so all three use the bare class.
        # 2026-10-08 again: 38 -> 39 for the receipt envelope's does_not_prove list
        # (rollbackLimits()). The proof table itself is a .table inside .table-wrap like the
        # receipt's other tables, so it adds no container; the caveat sentences are the emitter's
        # own and are listed as members so a future single-string collapse cannot drop one.
        # 2026-10-08 again: 39 -> 41 for the evidence projection card (commit a0d001a8). Two
        # containers, both named: projectionReasonList() lists the emitter's own per-token counts
        # so the numbers travel with the state word beside them, and projectionReceiptRows() lists
        # the receipts the projection returned, capped, with the remainder stated in words.
        # This move is recorded four commits late and the gate has been red since a0d001a8: it was
        # found while measuring a different stylesheet gate, and the bound run quoted as clean at
        # 3c43d0af selected modules that did not include this file -- a `--modules` run is not the
        # suite, and calling it one is how an inventory pin survives being broken.
        # 2026-10-09 (DL-UI-U02): 41 -> 42 for the 组件规范 screen's list sample
        # (renderUiComponents). One container, named: it is the screen that states the ul.list +
        # li.list-item convention, so the convention is demonstrated by a real list rather than by
        # a <div> wearing the class. The screen's other blocks are <section>/<p>/<table> and add no
        # container. This is the inventory growing by one verified column, not a threshold moving.
        # li 成员，其空态是 emptyLi()，所以读回没到也不会被画成空列表。
        # 2026-10-09 (DL-UI-U03) again: 42 -> 43 for the capability detail list
        # (capabilityDetail()) on 能力目录. One container, named: it lists the seven
        # classification axes with their values, the qualification basis, the licence and
        # rights line, the evidence level and the "no recorded counter-example" row, so the
        # detail is a real list of record fields rather than a paragraph a reader has to
        # parse. Rows are real <li> members; the block's only button is the disabled
        # 使用此能力 entry, which adds no container.
        # 2026-10-09 (DL-UI-U04) again: 43 -> 45 for the 输入与目标 screen. Two containers,
        # both named: referencePickerForProject() lists the project's real imported assets as
        # checkable <li> members (with media type, size, rights and version carried on the row),
        # and intakeForm()'s readback column lists the briefs the service returned after a
        # submit. Neither adds a <div> wearing the list class, and the intake form itself is a
        # label/input grid, which contributes no container.
        # 2026-10-09 (DL-UI-U05) again: 45 -> 46 for the 目标生成包 composition list
        # (planComposer()). One container, named: it lists the nodes the page actually composed
        # (the user-chosen raster with its recorded rights/version, the canvas taken from that
        # asset's real size, and the row that states which node families are NOT composed and
        # why). The RIR preview is a <pre>, so it adds no container.
        # 2026-10-09 (DL-UI-U04 屏04) again: 46 -> 47 for the 分析与方案 judgement-basis list
        # (analysisPanel()). One container, named: current direction, method/preference fields,
        # source/knowledge references, and the design-system binding are each a real <li> member
        # read back from the design layer. The gap blocks beside it are stateBlock() articles and
        # the correction form is labels/inputs, so neither adds a container.
        # 2026-10-09 (DL-UI-U04 屏07 制作记录) 47 -> 49: two containers, both named.
        # recordsBody() adds the job list itself (one <li> per real TaskRecord read back from
        # GET /projects/{id}/tasks) and the "what this page may and may not claim" panel, whose
        # three <li> members state the state-word source, the missing domain field and the
        # unwired continue action. The per-task event list is `.record-event-list`, not a
        # `.list` container, so it does not count here.
        # 2026-10-10 (DL-UI-U06) 49 -> 50: one container, named. runtimeObservation() lists the
        # five native runtime tables plus the budget row and the emitter's own does_not_say
        # sentences as real <li> members, because the whole point of that panel is that
        # ABSENT / PRESENT-empty / NOT-READ are three different rows a reader can tell apart --
        # which a paragraph cannot carry. The panel's heading and hint are <h3>/<p>, so they add
        # no container. This is the inventory growing by one verified column, not a threshold.
        # 2026-10-13 (DL-UI-U07) again: 50 -> 52 for the 成果版本 panel (renderVersionsPanel) on
        # 项目详情. Two containers, both named: the outer one lists the bundle kinds, and each
        # kind's own version chain is a nested ul.list whose rows are real <li> members -- so
        # "current" and "superseded" sit beside each other inside a list rather than in
        # paragraphs that happen to line up. The panel's empty state is a <p class="view-hint">
        # and its unread state is a <p class="error">, deliberately neither emptyLi() nor a list:
        # "this project has no versions" and "the route did not return the collection" are
        # different claims, and the second must not be drawn as an empty list. The number moves
        # because the inventory grew by two verified columns, not because a check was relaxed.
        # 2026-10-18 (DL-UI-U09) again: 52 -> 53 for the knowledge readback panel
        # (knowledgePanel) on 制作记录. One container, named: each persisted candidate is a real
        # <li> member carrying its review/revocation/freshness/export state, every storage
        # conflict the service reports is a row beside them, and the service's own
        # does_not_say sentences close the list. The three write forms are labels/inputs and
        # paragraphs, and the unread state is a <p class="error"> rather than emptyLi(), so
        # neither adds a container -- "did not ask" must not be drawn as an empty list.
        # 2026-10-23 (DL-KB-03/06, batch K) again: 53 -> 59. Six new containers, all named:
        # two in the settings view rebuilt by the three-entry shell (模型服务 value rows,
        # 备份与诊断 diagnostics rows), and four on the knowledge screen -- the entry's own
        # field block (kbEntryBlocks), the 来源与许可 block, the 修订历史 chain, and the
        # service's does_not_say sentences (the last only when the service sent any). The
        # search results container is not one of the six: it replaced the pre-existing list
        # in the same position, so only a first-screen form and empty-state paragraph vary
        # around it. Empty states on this screen stay <p>/emptyLi(), as above.
        # 2026-10-24 (DL-KB-08) again: 59 -> 66. The assistant screen's seven containers, all
        # named: the project's plan records (as-list), the 目标与方向 value rows, the external
        # steps that the service explicitly does not dispatch, the 参考与依据 status rows, the
        # 已知缺口 rows, the 修订历史 chain, and the does_not_say sentences. Its attached-
        # reference container is `class: 'list as-refs'` and is therefore NOT one of these --
        # the exact-substring count is deliberate, so a container that shares the tag but not
        # the class does not silently inflate it. Empty states here stay <p>/emptyLi() too:
        # "no plan yet" must not be drawn as a list with zero members.
        # 2026-10-24 (DL-KB-10) again: 66 -> 70. The 目标组合选择面板's four containers, all named:
        # the 官方支持 column (tp-official-list), the 本项目未测试 column (tp-untested-list), the
        # validate answer's verdict rows (tp-verdict-list), and the 更多设置 block's 13-field
        # readback of one profile. The screen's route cards are <article class="row-card">, the
        # dimension rows and the histogram are <div class="grid-stack">, and every empty state is
        # <p> or emptyLi() — so none of those add a container. Again the inventory grew by four
        # verified columns, the threshold did not move.
        # 2026-10-24 (DL-KB-16) again: 70 -> 71. One new container, named: the plan detail's
        # voluntary-feedback history (`as-fb-history`). Its empty and unreadable states stay on the
        # <p class="view-hint"> status line above it -- a list of zero rows would read as "checked
        # and empty", which is a different claim from "the service refused" or "nothing recorded".
        # 2026-10-24 (DL-KB-12) again: 71 -> 72. One new container, named: the revision comparison's
        # field rows (`as-compare-body`). The 镜头表 read back in the plan body is
        # `'list as-shot-list'`, which the exact substring deliberately does not count, and the
        # comparison's "cannot read, so nothing is compared" case stays on the status <p>.
        # 2026-10-24 (DL-KB-05 D5) again: 72 -> 73. One new container, named: the entry detail's
        # judgement trail (`kb-judgements`). It is emitted only when the readback carries rows --
        # "nobody has recorded a judgement yet" is a sentence (`<p class="muted">`), not an empty
        # list that would read as "asked and answered with nothing".
        # 2026-10-28 (owner automation unfreeze) again: 73 -> 74. One new container, named: the
        # automation connector roster (`#/automation`, one row per registered connector read from
        # GET /api/automation-connectors). Its sibling panels are `<p class="view-hint">` and the
        # `items-stack` list of owner-closed capabilities, which this exact substring does not
        # count; an empty connector table would have read as "nothing is registered" rather than
        # "the record could not be read", so the unread case stays on the status line.
        self.assertEqual(self.shell.count("el('ul', { class: 'list'"), 74)


if __name__ == "__main__":
    unittest.main(verbosity=2)
