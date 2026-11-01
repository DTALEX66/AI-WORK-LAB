# SPDX-License-Identifier: MIT
"""The RIGHTS surface may only say what the rights façade and its contract can say.

apps/workbench/tests/appshell.mjs block ⑧ proves the behaviour: one click files one
decision to the real POST route, a refusal replaces the previous verdict, an unread field
is drawn as 未读回, and the column reports the façade's own limits. Behaviour cannot see a
vocabulary, and text cannot see a click. This module checks the other half -- the claims the
page makes about the SERVICE -- against Python and against the contract file the store loads:

  * the clearance chip only colours words `rights_review.py` can emit, both ways;
  * the decision chip only colours the contract's own enum, and never the approving word,
    because the page decides "does this scope clear?" from the façade's `unapproved_scopes`;
  * the submitted document is exactly the contract's closed property set, so no field is
    dropped and none is smuggled in (`supersedes` is a query parameter, not a document
    field -- the store refuses it inside the document);
  * every field the page reads back is a key the façade actually publishes, and every row
    attribute is a contract property. An HTTP readback cannot carry `actor_kind` or
    `supersedes` at all, so a page that rendered them would be showing a claim this route
    never sent;
  * the route exists, is dispatched before the fall-through 404, and keeps
    `RightsReviewError` ahead of the generic ValueError clause so the refusal code and its
    detail reach the operator instead of collapsing into INVALID_REQUEST.

Every extraction asserts on the way. A pattern that matches nothing fails the gate rather
than passing on an empty set.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
SHELL = REPO / 'apps' / 'workbench' / 'shell.ts'
BUNDLE = REPO / 'apps' / 'workbench' / 'build' / 'main.js'
REVIEW = REPO / 'src' / 'design_lab' / 'rights_review.py'
LEDGER = REPO / 'src' / 'design_lab' / 'assurance' / 'rights_ledger.py'
CONTRACT = REPO / 'design-lab' / 'schemas' / 'contracts' / 'rights-decision.schema.json'
HTTP = REPO / 'src' / 'design_lab' / 'http_service.py'

SHELL_TEXT = SHELL.read_text(encoding='utf-8')

# The declarations that make up the rights surface. Everything below is checked against
# these blocks only, because `NOT_REVIEWED` also appears in the pre-existing bundle-manifest
# column, which belongs to a different emitter (native_bundles) and a different gate.
RIGHTS_DECLARATIONS = (
    'interface RightsDecisionRecord',
    'interface RightsReadback',
    'const RIGHTS_UNREADABLE',
    'const RIGHTS_CLEARANCE_TAGS',
    'const RIGHTS_DECISION_TAGS',
    'const RIGHTS_DECISION_SCHEMA_VERSION',
    'function rightsCount(',
    'function clearanceFraction(',
    'function unapprovedScopeSet(',
    'function rightsDecisionTagClass(',
    'function clearanceExplanation(',
    'function rightsScopeRows(',
    'function rightsFacts(',
    'function evidenceRightsColumn(',
    'function rightsReadbackPanel(',
    'function rightsDecisionForm(',
    'export async function renderRightsReview(',
)


def block_in(text: str, start_marker: str) -> str:
    """One top-level declaration, taken from its signature to the next one."""
    assert start_marker in text, f'{start_marker!r} is not in the source -- the gate lost ' \
                                'its subject rather than passing on it'
    start = text.index(start_marker)
    rest = text[start + len(start_marker):]
    stop = re.search(r"\n(?:export )?(?:async )?(?:function|const|type|interface|class|def) ",
                     rest)
    return text[start:start + len(start_marker) + (stop.start() if stop else len(rest))]


def block(start_marker: str) -> str:
    return block_in(SHELL_TEXT, start_marker)


def without_comments(text: str) -> str:
    """Source with its comments gone: a comment can mention a shape without drawing it.

    Used only for the `0/0` check. The quoted-vocabulary checks deliberately keep comments
    in, because design-lab/scripts/verify_state_vocabularies.py scans shell.ts and the
    committed bundle without stripping them either -- a copied word in prose is a word the
    next reader may paste into code.
    """
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def rights_slice_text() -> str:
    """The whole rights surface, concatenated. Never empty: a lost declaration is a failure."""
    parts = [block(marker) for marker in RIGHTS_DECLARATIONS]
    joined = '\n'.join(parts)
    assert 'rights_clearance' in joined and 'unapproved_scopes' in joined, \
        'the rights slice no longer reads the façade readback at all, so these checks ' \
        'would be measuring nothing'
    return joined


def map_keys(declaration: str, where: str) -> set[str]:
    body = re.search(rf"const {declaration}: Record<string, string> = \{{([^}}]*)\}}",
                     SHELL_TEXT)
    assert body, f'{declaration} is gone from shell.ts -- {where}'
    keys = set(re.findall(r'([A-Z][A-Z_]+):', body.group(1)))
    assert keys, f'{declaration} declares no entries -- the gate would prove nothing'
    return keys


def emitted_clearance() -> set[str]:
    """CLEARANCE_STATES resolved through rights_review.py's own NAME = 'WORD' assignments.

    The same reading design-lab/scripts/verify_state_vocabularies.py uses: a word quoted in
    a docstring is prose, not an emission.
    """
    text = REVIEW.read_text(encoding='utf-8')
    assigned = dict(re.findall(r"^([A-Z][A-Z0-9_]*) = '([A-Z][A-Z0-9_]*)'$", text, re.M))
    anchor = re.search(r'^CLEARANCE_STATES = \((.*?)\)$', text, re.M)
    assert anchor, 'rights_review.py declares no CLEARANCE_STATES tuple, so the clearance ' \
                   'words the page colours cannot be read from their emitter'
    names = re.findall(r'[A-Z][A-Z0-9_]*', anchor.group(1))
    assert names, 'CLEARANCE_STATES is empty; a gate with no words to compare proves nothing'
    unresolved = [name for name in names if name not in assigned]
    assert not unresolved, f'CLEARANCE_STATES names {unresolved}, which nothing assigns'
    return {assigned[name] for name in names}


def approving_word() -> str:
    """The one contract word that clears a scope, read from the façade that compares it."""
    text = REVIEW.read_text(encoding='utf-8')
    match = re.search(r"^APPROVED = '([A-Z_]+)'$", text, re.M)
    assert match, 'rights_review.py no longer names the approving word as a constant, so ' \
                  '"what clears a scope" is not something either side can be held to'
    return match.group(1)


def contract_fields() -> dict:
    doc = json.loads(CONTRACT.read_text(encoding='utf-8'))
    props = doc.get('properties') or {}
    assert props, 'rights-decision.schema.json declares no properties; a closed schema with ' \
                  'no fields would let this gate pass on an empty set'
    required = set(doc.get('required') or [])
    assert required, 'the contract declares no required fields'
    enum = ((props.get('decision') or {}).get('enum') or [])
    assert enum, 'the contract declares no decision enum'
    assert doc.get('additionalProperties') is False, \
        'the contract no longer closes its properties, so the field set is not a boundary'
    return {'properties': set(props), 'required': required, 'decisions': set(enum)}


def readback_keys() -> set[str]:
    """The keys rights_review.readback() actually returns."""
    text = REVIEW.read_text(encoding='utf-8')
    start = text.index('def readback(')
    body = text[start:]
    stop = re.search(r"^class ", body, re.M)
    body = body[:stop.start()] if stop else body
    anchor = body.index('return {')
    inner = body[anchor + len('return {'):]
    end = re.search(r"^\    \}", inner, re.M)
    assert end, 'cannot find the end of readback()\'s return dict'
    keys = set(re.findall(r"^\s+'([a-z_]+)':", inner[:end.start()], re.M))
    assert keys, 'readback() returns no keys -- the gate would be comparing against nothing'
    return keys


class ClearanceVocabulary(unittest.TestCase):
    def test_the_page_colours_only_the_clearance_words_the_facade_emits(self):
        emitted = emitted_clearance()
        painted = map_keys('RIGHTS_CLEARANCE_TAGS',
                           'the rights column lost its clearance chips')
        self.assertEqual(painted - emitted, set(),
                          f'the page colours {sorted(painted - emitted)}, which '
                          'rights_review.py never emits')
        self.assertEqual(emitted - painted, set(),
                          f'the façade emits {sorted(emitted - painted)} and the page has no '
                          'wording for it, so a real clearance would fall through to neutral')

    def test_no_clearance_word_claims_a_review_is_pending(self):
        """An untouched gate was never asked anything. PENDING is not a clearance state.

        The façade can only say CLEARED or NOT_REVIEWED (rights_review.py states the rule),
        so a page that mapped a pending-looking clearance to a colour would advertise a
        status the service refuses to infer.
        """
        painted = map_keys('RIGHTS_CLEARANCE_TAGS', 'the clearance chip map moved')
        self.assertEqual({word for word in painted if 'PENDING' in word}, set(),
                         f'the clearance chips include {sorted(painted)}, and a PENDING word '
                         'in the clearance plane would read as somebody owing an answer')

    def test_the_pending_word_is_offered_only_as_a_human_choice(self):
        """PENDING_REVIEW may appear because a human filed it -- never because the page said so."""
        form = block('function rightsDecisionForm(')
        self.assertIn('Array.isArray(data.decision_vocabulary)', form,
                      'the form no longer takes its decision words from the readback, so the '
                      'offer is a hand copy of the contract')
        self.assertIn('if (!vocabulary.length) submit.disabled = true;', form,
                      'the form can submit with no vocabulary read back, which means it '
                      'would be filing a word nobody emitted')
        explanation = block('function clearanceExplanation(')
        self.assertIn('没有被问过', explanation,
                      'a gate with nothing filed must be described as never asked, not as '
                      'waiting for an answer')
        self.assertIn('PENDING_REVIEW 只能由人提交产生', explanation,
                      'the screen must say where the pending word can come from')


class DecisionVocabulary(unittest.TestCase):
    def test_the_decision_chips_are_the_contract_enum_minus_the_word_that_clears(self):
        fields = contract_fields()
        painted = map_keys('RIGHTS_DECISION_TAGS', 'the rights column lost its decision chips')
        self.assertEqual(painted - fields['decisions'], set(),
                         f'the page colours {sorted(painted - fields["decisions"])}, which '
                         'rights-decision.schema.json does not allow a decision to be')
        self.assertEqual(painted, fields['decisions'] - {approving_word()},
                         'the non-approving decision words must each carry a chip, and the '
                         'approving word must NOT: the page clears a scope from the '
                         "façade's own unapproved_scopes list, never from a copy of the word")

    def test_the_approving_word_is_never_hand_copied_into_the_ui(self):
        """verify_state_vocabularies.py convicts this literal; the rights slice must agree.

        The clearing rule lives in the façade. Copying its word into the page would create a
        second authority able to disagree with the contract the store loads from disk.
        """
        word = approving_word()
        for path, label in ((SHELL, 'shell.ts'), (BUNDLE, 'build/main.js')):
            body = path.read_text(encoding='utf-8')
            for quote in ("'", '"'):
                self.assertNotIn(f'{quote}{word}{quote}', body,
                                 f'{label} compares against a copied {word} literal')

    def test_the_slice_quotes_no_vocabulary_word_at_all(self):
        """Every rights word on screen is data the readback sent, or a key, never a literal."""
        slice_text = rights_slice_text()
        words = emitted_clearance() | contract_fields()['decisions']
        for word in sorted(words):
            for quote in ("'", '"'):
                self.assertNotIn(f'{quote}{word}{quote}', slice_text,
                                 f'the rights slice carries a copied {word} literal; a word '
                                 'the contract drops would then stay on screen')

    def test_the_clearing_rule_comes_from_the_faades_own_list(self):
        slice_text = rights_slice_text()
        self.assertIn('data.unapproved_scopes', slice_text,
                      'the page no longer classifies scopes from unapproved_scopes, so it is '
                      'deciding "approved" by itself')
        self.assertIn(': null;', block('function unapprovedScopeSet('),
                      'an unread unapproved_scopes list must classify nothing; without the '
                      'null path every scope would keep its colour from a fabricated empty')
        tagger = block('function rightsDecisionTagClass(')
        self.assertIn("if (unapproved === null) return 'neutral';", tagger,
                      'with no classification source the page must not paint any verdict')


class FieldSurfaceMatchesTheReadback(unittest.TestCase):
    def test_the_page_reads_only_fields_the_readback_publishes(self):
        emitted = readback_keys()
        slice_text = rights_slice_text()
        read = set(re.findall(r'\bdata\.([a-z_]+)', slice_text))
        assert read, 'the rights slice reads no field off the readback at all'
        self.assertEqual(read - emitted - {'error'}, set(),
                         f'the page reads {sorted(read - emitted)}, which '
                         'rights_review.readback() does not return')
        for must in ('rights_clearance', 'approved_scope_count', 'filed_scope_count',
                     'unapproved_scopes', 'scope_conflicts', 'name_checked_only',
                     'does_not_prove', 'ever_filed_scopes', 'decision_states',
                     'current_decisions', 'decision_count', 'decision_vocabulary'):
            self.assertIn(must, emitted, f'the façade no longer publishes {must}, which the '
                                         'UI contract says is on screen')
            self.assertIn(f'data.{must}', slice_text,
                          f'{must} is published but the rights slice never reads it')

    def test_the_rows_expose_only_the_contract_document_fields(self):
        """No actor_kind, no supersedes: an HTTP row cannot carry either."""
        fields = contract_fields()
        slice_text = rights_slice_text()
        read = set(re.findall(r'record\??\.([a-z_]+)', slice_text))
        assert read, 'the rights rows read no document field at all'
        allowed = fields['properties'] | {'decision_ids', 'use_scope'}
        self.assertEqual(read - allowed, set(),
                         f'the rows read {sorted(read - allowed)}, which the closed contract '
                         'never carries across the HTTP boundary')
        self.assertEqual(read & {'actor_kind', 'supersedes'}, set(),
                         'the page renders a store column the route cannot send')

    def test_the_submission_is_exactly_the_closed_contract_field_set(self):
        fields = contract_fields()
        form = block('function rightsDecisionForm(')
        body = re.search(r'const body: Record<string, unknown> = \{(.*?)\n\s*\};', form, re.S)
        assert body, 'the rights form no longer builds one contract document object'
        sent = set(re.findall(r'^\s*([a-z][A-Za-z0-9_]*):', body.group(1), re.M))
        sent |= set(re.findall(r'const payload = \{ ([a-z_]+):', form))
        assert sent, 'no field is sent -- the gate would pass on an empty body'
        self.assertEqual(sent - fields['properties'], set(),
                         f'the page sends {sorted(sent - fields["properties"])}, which the '
                         'contract closes out; the store refuses the whole document for it')
        self.assertEqual(fields['required'] - sent, set(),
                         f'the page omits required field(s) {sorted(fields["required"] - sent)}')
        self.assertEqual(sent, fields['properties'],
                         'the submission should cover the contract exactly: a dropped '
                         'optional field is a limit nobody stated')
        for foreign in ('juror', 'attestation', 'actor_kind', 'proposal_id'):
            self.assertNotIn(f'{foreign}:', form,
                             f'a jury field ({foreign}) does not belong in a rights document')


class AbsentFieldsAreUnread(unittest.TestCase):
    def test_an_unread_denominator_is_never_drawn_as_zero(self):
        fraction = block('function clearanceFraction(')
        self.assertIn("!== 'number'", fraction,
                      'the approved/filed fraction no longer checks both halves are numbers')
        self.assertIn('未读回', fraction, 'a missing denominator must be said as 未读回')
        self.assertNotIn('0/0', without_comments(fraction),
                         'the fraction function draws a literal 0/0; the only way that pair '
                         'should reach the screen is from two real zeros the façade sent')
        counter = block('function rightsCount(')
        self.assertIn('未读回', counter, 'an unread count must be said as 未读回')
        # The one sentence the page must never let stand: a clearance word without its
        # denominator. Both halves are named in the same line as the chip.
        facts = block('function rightsFacts(')
        self.assertIn('当前批准 ${clearanceFraction(data)}', facts,
                      'the clearance chip must travel with its approved/filed denominator')

    def test_an_absent_clearance_word_is_not_replaced_by_one(self):
        facts = block('function rightsFacts(')
        self.assertIn("typeof data.rights_clearance === 'string'", facts,
                      'the clearance word is no longer read defensively')
        self.assertIn('权利清算状态未读回', facts,
                      'a readback without the word must say so in its own line')

    def test_the_limits_are_transponded_not_restated(self):
        """does_not_prove travels from the ledger; a copy here would outlive it."""
        facts = block('function rightsFacts(')
        self.assertIn('data.does_not_prove', facts,
                      'the column no longer shows the service\'s own does_not_prove list')
        ledger = LEDGER.read_text(encoding='utf-8')
        sentences = set(re.findall(r"'([a-z][^']{40,})'", ledger[ledger.index('DOES_NOT_PROVE'):]))
        copied = [text for text in sentences if text in SHELL_TEXT]
        self.assertEqual(copied, [], 'the page restates the ledger\'s own sentences; when the '
                                    'emitter edits one, the screen would keep the old claim')


class RouteContract(unittest.TestCase):
    def test_both_routes_exist_and_precede_the_fall_through_not_found(self):
        # Routes are data now (`http_service.ROUTES`), not `re.fullmatch(...)` literals
        # inside dispatch(). Read the inventory: grepping dispatch() for the old textual
        # shape would fail against a file that still dispatches both methods correctly.
        from design_lab.http_service import ROUTES

        # The POST pattern also admits the optional `?supersedes=` query group, so match
        # the path prefix rather than the whole pattern.
        scoped = [route for route in ROUTES
                  if not route.exact
                  and route.pattern.startswith(r'/api/projects/([0-9a-f]{32})/rights')]
        self.assertEqual(sorted(route.method for route in scoped), ['GET', 'POST'],
                         'http_service.py no longer dispatches both rights methods')
        self.assertEqual({route.action for route in scoped},
                         {'_list_rights', '_record_rights'},
                         'a rights route no longer answers through the rights façade')
        text = HTTP.read_text(encoding='utf-8')
        dispatch = text[text.index('def dispatch(self):'):text.index('do_GET = dispatch')]
        self.assertLess(dispatch.index('for route in ROUTES'),
                        dispatch.index("raise RequestError(404, 'NOT_FOUND')"),
                        'the rights read must be dispatched before the fall-through 404')

    def test_a_refusal_keeps_its_code_and_its_reason(self):
        text = HTTP.read_text(encoding='utf-8')
        self.assertLess(text.index('except RightsReviewError'),
                        text.index('except (ValueError, PathPolicyError)'),
                        'RightsReviewError must keep its own code and status; after the '
                        'generic ValueError clause every rights refusal would collapse to '
                        'INVALID_REQUEST and the operator could not tell why the gate said no')

    def test_the_ui_calls_the_route_the_service_dispatches(self):
        form = block('function rightsDecisionForm(')
        self.assertIn('`/projects/${projectId}/rights`', form,
                      'the form no longer posts to the project-scoped rights route')
        self.assertIn('?supersedes=${encodeURIComponent(previousId)}', form,
                      'supersession must travel as the query parameter the route parses, '
                      'not as a field the closed contract refuses')
        self.assertIn("el('select', { class: 'input', id: 'rights-supersedes' }", form,
                      'the supersession target must be chosen from the read-back, never typed')
        self.assertEqual(form.count('await api('), 1,
                         'one click must file exactly one decision; a second call in the '
                         'handler would put two rows on the append-only ledger')

    def test_the_read_back_is_a_seam_read(self):
        loader = block('export async function renderRightsReview(')
        self.assertIn('apiOrEmpty<RightsReadback>(`/projects/${id}/rights`, RIGHTS_UNREADABLE)',
                      loader, 'the rights read does not go through the seam that reports a '
                              'collection the service left out')
        self.assertIn('shapeNotice(data)', loader,
                      'the read-back is rendered without naming the fields that were missing')
        evidence = block('export async function renderEvidence(')
        self.assertIn('apiOrEmpty<RightsReadback>(`/projects/${id}/rights`, RIGHTS_UNREADABLE)',
                      evidence, '证据系统 does not read the rights ledger')
        self.assertIn('rightsResp', re.search(r'shapeNoticeRows\(([^)]*)\)', evidence).group(1),
                      'the rights read-back is rendered but its missing fields are never named')


class EnglishIsMarked(unittest.TestCase):
    def test_the_service_words_are_marked_and_not_translated(self):
        facts = block('function rightsFacts(')
        rows = block('function rightsScopeRows(')
        form = block('function rightsDecisionForm(')
        self.assertIn('en(clearance)', facts,
                      'the clearance word must carry lang="en" (WCAG 3.1.2, service vocabulary)')
        self.assertIn('en(String(record.decision))', rows,
                      'the decision word must carry lang="en"')
        self.assertIn('en(word)', form,
                      'the offered decision words must carry lang="en"')


if __name__ == '__main__':
    unittest.main(verbosity=2)
