# SPDX-License-Identifier: MIT
"""Task tests for DL-FINAL-T07: distilled sources, and the gate that keeps them honest.

Every test drives `verify_selected_source_adaptation` against the REAL repository bytes
(the taxonomy row, the adapter registry, the published vocabularies, the vendored blob),
then plants one specific lie and requires that exact finding by name. The plants are the
point: a guard that cannot be made to fail guards nothing, and the three clauses this
task is judged on -- popularity is only a filter, registering a source is not integrating
it, no execution qualification without evidence -- are each convicted here on a mutated
copy of the shipped record.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'design-lab' / 'scripts' / 'verify_selected_source_adaptation.py'
DOC_REL = 'packages/capabilities/selected-sources.json'

sys.path.insert(0, str(SCRIPT.parent))
import verify_selected_source_adaptation as gate  # noqa: E402

LIE = 'LIE'  # marker so a missing assertion cannot pass silently


def record(doc, source_id):
    for rec in doc['selected']:
        if rec['sourceId'] == source_id:
            return rec
    raise AssertionError(f'{source_id} is not in the selection')


def only(findings, needle):
    hits = [f for f in findings if needle in f]
    assert hits, f'expected a finding containing {needle!r}; got {findings}'
    return hits


class SelectedSourceAdaptation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.load = gate.Load(REPO)
        cls.doc = json.loads((REPO / DOC_REL).read_text(encoding='utf-8'))

    def mutated(self, mutate):
        doc = copy.deepcopy(self.doc)
        mutate(doc)
        return gate.check(doc, self.load)[0]

    # ---------------------------------------------------------------------- baseline
    def test_shipped_record_passes_the_shipped_gate(self):
        bad = [f for f in gate.check(copy.deepcopy(self.doc), self.load)[0] if LIE not in f]
        self.assertEqual([], bad, 'the shipped record must pass on its own bytes')

    def test_gate_cli_is_green_on_the_shipped_bytes(self):
        res = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                             encoding='utf-8', errors='replace',
                             env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(0, res.returncode, res.stdout + res.stderr)
        out = res.stdout
        self.assertIn('SELECTED_SOURCES=OK', out)
        for token in ('records=6', 'mapped=1', 'consumed=1', 'motion_deviations=0'):
            # 2026-10-22 (B5): the first CONSUMED landing was earned by a browser measurement, so the
            # register moved from mapped=2/consumed=0 to mapped=1/consumed=1. These are counts of the
            # shipped record, not a floor: a landing that quietly reverts to MAPPED goes red here.
            self.assertIn(token, out)
        # The citations are re-read from the vendored blob when that blob is on disk, and
        # the blob lives in the gitignored vendor cache -- so a clean clone legitimately
        # verifies zero of them. The original assertion here demanded VERIFIED != 0, which
        # is true only on a workstation that has fetched the cache and is therefore a test
        # that could only ever pass in one environment. What must hold everywhere is the
        # relation: if nothing was re-read, the run has to SAY so. A green line reading
        # VERIFIED(0) with no note is the silent-pass this test exists to prevent.
        verified = re.search(r'citations=VERIFIED\((\d+)\)/SKIPPED\((\d+)\)', out)
        self.assertIsNotNone(verified, out)
        crosschecked, skipped = int(verified.group(1)), int(verified.group(2))
        if crosschecked == 0:
            self.assertGreater(skipped, 0, 'nothing was re-read and nothing was skipped: '
                                           'the gate silently checked nothing')
            self.assertIn('SKIPPED citations are inside the gitignored vendor cache', out,
                          'a run that re-read no citation must state why')

    def test_empty_selection_is_not_a_pass(self):
        findings = self.mutated(lambda d: d.__setitem__('selected', []))
        only(findings, 'selects nothing')

    # ------------------------------------------------- popularity is only a filter
    def test_popularity_cannot_be_a_selection_basis(self):
        def mutate(d):
            record(d, 'visual-quality__taste-skill')['selectionBasis'].append(
                f'{LIE} 它有很多 stars，所以品质最高')
        hits = only(self.mutated(mutate), 'uses')
        self.assertIn('as a reason', ' '.join(hits))
        self.assertIn('star', ' '.join(hits).lower())

    def test_a_refuted_popularity_mention_is_not_a_lie(self):
        def mutate(d):
            record(d, 'visual-quality__taste-skill')['selectionBasis'].append(
                f'{LIE} 热度与选中理由无关，规则可静态判定才入选')
        findings = [f for f in self.mutated(mutate) if LIE in f]
        self.assertEqual([], findings, 'a refuted mention was convicted as a reason')

    def test_adoption_numbers_are_copied_not_restated(self):
        def mutate(d):
            record(d, 'visual-quality__dataviz-critique')['adoptionFilter']['stargazerCount'] = 999999
        only(self.mutated(mutate), 'adoptionFilter.stargazerCount')

    def test_quality_claim_requires_measurement(self):
        def mutate(d):
            record(d, 'visual-quality__dataviz-critique')['qualityClaim'] = 'MEASURED_S'
        findings = self.mutated(mutate)
        only(findings, 'still unmeasured')
        self.assertTrue(any('MEASURED_S' in f for f in findings), findings)

    def test_a_measured_claim_still_needs_the_human_approval_ref(self):
        # The other branch: a taxonomy row that HAS been graded still cannot support a
        # claim unless the human approval reference exists.
        doc = copy.deepcopy(self.doc)
        rec = record(doc, 'visual-quality__dataviz-critique')
        rec['qualityClaim'] = 'MEASURED_S'
        entry = self.load.entries['visual-quality__dataviz-critique']
        self.assertTrue(gate.unmeasured(entry.get('designQuality')), 'fixture drifted')
        # simulate a graded row without touching the taxonomy file
        self.load.entries['visual-quality__dataviz-critique'] = dict(
            entry, designQuality={'overall': 4})
        try:
            findings = gate.check(doc, self.load)[0]
            only(findings, 'needs humanApprovalRef')
        finally:
            self.load.entries['visual-quality__dataviz-critique'] = entry

    # ------------------------------------------ registering a source is not integrating
    def test_registered_landing_is_not_integration(self):
        def mutate(d):
            land = record(d, 'visual-quality__ux-audit-skill')['landing'][0]
            land['mode'] = 'MAPPED'
            land['ruleId'] = 'SRC-T07-UX-EVIDENCE-RULES'
            land['derivedFromMethod'] = 'SRC-T07-UX-EVIDENCE-RULES'
        findings = self.mutated(mutate)
        only(findings, 'does not contain')
        only(findings, 'promotionLevel says')

    def test_mapped_landing_requires_the_rule_id_in_the_target(self):
        def mutate(d):
            land = record(d, 'visual-quality__motion-design-skill')['landing'][0]
            land['ruleId'] = 'SRC-T07-MOTION-NOT-WRITTEN-ANYWHERE'
            land['derivedFromMethod'] = 'SRC-T07-MOTION-NOT-WRITTEN-ANYWHERE'
        only(self.mutated(mutate), 'does not contain')

    def test_registered_only_landing_must_say_what_is_missing(self):
        def mutate(d):
            record(d, 'visual-quality__ux-audit-skill')['landing'][0]['notYetReason'] = ''
        only(self.mutated(mutate), 'needs notYetReason')

    def test_landing_paths_must_exist(self):
        def mutate(d):
            record(d, 'visual-quality__taste-skill')['landing'][0]['path'] = \
                'packages/capabilities/standards/NEVER_SHIPPED.md'
        only(self.mutated(mutate), 'does not exist -- a landing must name a')

    def test_domain_pack_landing_stays_in_the_real_taxonomy(self):
        def mutate(d):
            record(d, 'visual-quality__motion-design-skill')['landing'][1]['path'] = \
                'packages/capabilities/quality/jury/JURY_MODEL.md'
        only(self.mutated(mutate), 'outside design-lab/domain-packs')

    def test_adapter_landing_needs_a_registry_row(self):
        def mutate(d):
            record(d, 'tool-control')['landing'][0]['adapterId'] = 'adapter-adobe-illustrator'
        self.assertIn('has no row in adapter-registry.json',
                      ' '.join(self.mutated(mutate)))

    def test_declared_adapter_cannot_be_claimed_mapped(self):
        def mutate(d):
            land = record(d, 'visual-quality__extract-design-system')['landing'][1]
            land['kind'] = 'Adapter'
            land['adapterId'] = 'adapter-dtcg'
            land['mode'] = 'MAPPED'
            land['ruleId'] = 'SRC-T07-EXTRACT-SCOPE'
            land['derivedFromMethod'] = 'SRC-T07-EXTRACT-SCOPE'
            land['path'] = 'packages/capabilities/standards/DESIGN_TOKEN_INTEROP.md'
        only(self.mutated(mutate), 'cannot support a MAPPED landing')

    def test_consumed_landing_needs_a_test_and_e2(self):
        def mutate(d):
            land = record(d, 'visual-quality__motion-design-skill')['landing'][0]
            land['mode'] = 'CONSUMED'
            # Chosen because it names neither the rule nor the standard: this test file now quotes
            # both (the positive check below needed them), so pointing the plant back at itself used
            # to satisfy the very requirement it was meant to refuse.
            land['proof'] = {'testPath': 'design-lab/config/contract-bindings.json'}
            # The shipped landing is a real CONSUMED at E2 since 2026-10-22, so this plant has to
            # lower the level itself; relying on the record still saying E1 was the whole claim.
            record(d, 'visual-quality__motion-design-skill')['executionQualification'] \
                ['evidenceLevel'] = 'E1'
        findings = self.mutated(mutate)
        only(findings, 'CONSUMED requires evidence level E2')
        self.assertTrue(any('names both' in f for f in findings), findings)

    def test_the_one_shipped_consumed_landing_is_a_browser_measurement(self):
        """The positive claim behind `consumed=1`, written as a test rather than as prose.

        A CONSUMED landing is the strongest mode this ladder has. It is here because the motion
        rule is read in a real Chromium over the built bundle, the same scanner has to convict a
        planted layout transition before the zero is trusted, and the evidence level says E2 --
        controlled runtime, not a host run and not a human jury.
        """
        consumed = [(rec, land) for rec in self.doc['selected'] for land in rec['landing']
                    if land.get('mode') == 'CONSUMED']
        self.assertEqual([rec['sourceId'] for rec, _ in consumed],
                         ['visual-quality__motion-design-skill'],
                         'a second CONSUMED landing has to be earned the same way, not added')
        rec, land = consumed[0]
        self.assertEqual(land['ruleId'], 'SRC-T07-MOTION-COMPOSITED')
        test_path = REPO / land['proof']['testPath']
        self.assertTrue(test_path.is_file(), f'{test_path} is not a file')
        text = test_path.read_text(encoding='utf-8', errors='replace')
        self.assertIn('SRC-T07-MOTION-COMPOSITED', text)
        self.assertIn('MOTION_ACCESSIBILITY.md', text)
        self.assertEqual(rec['executionQualification']['evidenceLevel'], 'E2',
                         'the record claims consumption at a level the gate would refuse')
        self.assertEqual(rec['executionQualification']['capabilityState'], 'structural-pass',
                         'E2 measurement is not an isolated run; the state must not have drifted')
        for ref in ('design-lab/tests/e2e/audit_workbench_motion.mjs',
                    'design-lab/tests/test_workbench_motion_gate.py'):
            self.assertTrue((REPO / ref).is_file(), f'{ref} is cited but absent')
        harness = (REPO / 'design-lab/tests/e2e/audit_workbench_motion.mjs') \
            .read_text(encoding='utf-8', errors='replace')
        self.assertIn('dlMotionPlant', harness,
                      'the browser half no longer contains its own falsifier')

    # ------------------------------------------------------------------ revision/licence
    def test_revision_and_license_are_copied_by_reference(self):
        def mutate(d):
            rec = record(d, 'tool-control')
            rec['revision']['pinnedCommitSHA'] = 'f' * 40
            rec['license']['id'] = 'CC0-1.0'
        findings = self.mutated(mutate)
        only(findings, 'but the taxonomy row says')
        only(findings, 'may not upgrade a licence')

    def test_revision_status_is_derived_from_the_taxonomy_not_the_record(self):
        # A record cannot declare itself PINNED while the taxonomy row has no commit.
        findings = self.mutated(lambda d: record(d, 'tool-control')['revision'].__setitem__(
            'status', 'PINNED'))
        only(findings, 'revision.status must be UNPINNED')
        # ...and the reverse: a pinned row may not hedge itself as UNPINNED.
        findings = self.mutated(lambda d: record(d, 'visual-quality__ux-audit-skill')[
            'revision'].__setitem__('status', 'UNPINNED'))
        only(findings, 'revision.status must be PINNED')

    def test_quarantine_and_unpinned_revision(self):
        # tool-control has no pinned commit, so no level other than quarantined is available
        # to it -- not even the ladder's entry rung.
        findings = self.mutated(lambda d: record(d, 'tool-control').__setitem__(
            'promotionLevel', 'candidate'))
        only(findings, 'unpinned revision quarantines the record')
        findings = self.mutated(lambda d: record(d, 'tool-control').__setitem__(
            'promotionLevel', 'task_proven'))
        only(findings, 'unpinned revision quarantines the record')

    def test_a_quarantined_record_cannot_claim_a_mapped_landing(self):
        findings = self.mutated(self._map_tool_control_landing)
        only(findings, 'does not contain')
        only(findings, 'cannot support a MAPPED landing')

    @staticmethod
    def _map_tool_control_landing(d):
        land = record(d, 'tool-control')['landing'][0]
        land['mode'] = 'MAPPED'
        land['ruleId'] = 'SRC-T07-TOOLCONTROL-REFONLY'
        land['derivedFromMethod'] = 'SRC-T07-TOOLCONTROL-REFONLY'

    def test_withdrawal_path_matches_the_taxonomy_and_restore_exists(self):
        def mutate(d):
            rec = record(d, 'visual-quality__ux-audit-skill')
            rec['withdrawal']['removalPath'] = 'delete it'
            rec['withdrawal']['restore'] = ''
            rec['withdrawal']['restoreCommandPaths'] = ['design-lab/scripts/verify_never_written.py']
        findings = self.mutated(mutate)
        only(findings, 'withdrawal.removalPath says')
        only(findings, 'no restore path')
        only(findings, 'restoreCommandPaths entry')

    # ------------------------------------------------------------- execution qualification
    def test_execution_qualification_uses_the_published_vocabulary(self):
        def mutate(d):
            record(d, 'visual-quality__ux-audit-skill')['executionQualification']['capabilityState'] = 'READY'
        only(self.mutated(mutate), 'is not in the published vocabulary')

    def test_qualification_cannot_outrun_the_promotion_level(self):
        def mutate(d):
            record(d, 'visual-quality__taste-skill')['executionQualification']['capabilityState'] = 'runtime-pass'
        findings = self.mutated(mutate)
        only(findings, 'exceeds what promotion level')

    def test_evidence_state_without_refs_is_a_finding(self):
        def mutate(d):
            record(d, 'visual-quality__extract-design-system')['executionQualification']['evidenceRefs'] = []
        only(self.mutated(mutate), 'without evidenceRefs')

    def test_evidence_refs_resolve_through_the_reader_roots(self):
        def mutate(d):
            refs = record(d, 'visual-quality__extract-design-system')['executionQualification']['evidenceRefs']
            refs[0] = '.project-local/cache/vendor/visual-quality__extract-design-system/LICENSE'
            refs.append('design-lab/tests/test_never_written.py')
        findings = self.mutated(mutate)
        only(findings, 'rejected by the ledger reader roots')
        self.assertIn('does not exist on disk', ' '.join(findings))

    # ------------------------------------------------------------------------- citations
    def test_cited_excerpt_shape_matches_the_record(self):
        def mutate(d):
            cite = record(d, 'visual-quality__ux-audit-skill')['method'][0]['citation']
            cite['quote'] = cite['quote'].split('\n')[0]
        only(self.mutated(mutate), 'quote has 1 lines but cites')

    def test_cited_excerpt_must_match_the_blob_when_present(self):
        def mutate(d):
            record(d, 'visual-quality__motion-design-skill')['method'][0]['citation']['quote'] = \
                LIE + ' invented excerpt'
        doc = copy.deepcopy(self.doc)
        mutate(doc)
        findings, stats = gate.check(doc, self.load)
        if stats['crosschecked']:
            only(findings, 'on disk -- the excerpt')
        else:
            # No local blob means CI could not re-read the bytes; the shape check still ran,
            # so a mutated quote must still be convicted by line count, never in silence.
            self.assertGreater(stats['crosscheck_skipped'], 0, 'no citations were checked at all')
            only(findings, 'quote has')

    def test_derived_check_must_exist_in_the_gate(self):
        def mutate(d):
            record(d, 'visual-quality__motion-design-skill')['method'][0]['derivedCheck'] = 'not_a_function'
        only(self.mutated(mutate), 'but this gate does not define it')

    def test_a_method_needs_a_counter_example(self):
        def mutate(d):
            record(d, 'visual-quality__dataviz-critique')['counterExamples'] = []
            record(d, 'visual-quality__extract-design-system')['method'] = []
        findings = self.mutated(mutate)
        only(findings, 'no counter-example')
        only(findings, 'still only a bookmark')

    # -------------------------------------------------------------------------- task test
    def test_task_tests_must_be_defined(self):
        findings = self.mutated(lambda d: record(d, 'visual-quality__ux-audit-skill')[
            'taskTest'].__setitem__('file', 'design-lab/tests/test_nonexistent_file.py'))
        only(findings, 'is not a file')
        findings = self.mutated(lambda d: record(d, 'visual-quality__ux-audit-skill')[
            'taskTest'].__setitem__('tests', ['test_never_written']))
        only(findings, 'that test is not defined')
        findings = self.mutated(lambda d: record(d, 'visual-quality__ux-audit-skill')[
            'taskTest'].__setitem__('tests', []))
        only(findings, 'no taskTest')

    # ----------------------------------------------------------------------- selection bounds
    def test_selection_is_bounded_and_poc_only(self):
        entry = self.load.entries['baoyu-design']
        self.assertEqual('CONDITIONAL_POC', entry['disposition'], 'fixture drifted')

        def mutate(d):
            record(d, 'visual-quality__ux-audit-skill')['sourceId'] = 'never-triaged-row'
        findings = self.mutated(mutate)
        only(findings, 'not a row in CANDIDATE-TAXONOMY.json')

        def demote(d):
            rec = record(d, 'visual-quality__ux-audit-skill')
            rec['sourceId'] = 'tool-control'
        findings = self.mutated(demote)
        self.assertTrue(any('listed twice' in f for f in findings), findings)

    def test_selection_larger_than_the_task_asks_for_is_a_finding(self):
        def mutate(d):
            extra = copy.deepcopy(d['selected'][0])
            d['selected'] = d['selected'] + [extra] * 8
        findings = self.mutated(mutate)
        only(findings, 'exceed the')
        only(findings, 'not all 980 candidates have to be absorbed')

    # ---------------------------------------------------- the derived motion validator
    def test_composited_motion_counts_the_real_stylesheet(self):
        land = record(self.doc, 'visual-quality__motion-design-skill')['landing'][0]
        scope = land['appliesTo']
        self.assertIn('apps/workbench/build/main.js', scope,
                      'the built bundle the applet actually loads is outside the rule scope')
        self.assertEqual(7, len(scope), scope)
        violations = gate.composited_motion_violations(REPO, scope)
        self.assertEqual([], violations, 'a layout-triggering animation came back into the CSS')
        self.assertEqual([], land['knownDeviations'])
        # An empty ledger must still say it was measured, or the next reader deletes it
        # as decoration. The two declarations this rule found on 2026-10-11 are named here.
        note = land.get('deviationLedgerNote') or ''
        self.assertIn('NOT', note, 'the empty deviation ledger carries no provenance note')
        for needle in ('1061', '1065', 'translateX(540px)'):
            self.assertIn(needle, note, note[:120])

    def test_composited_motion_convicts_a_planted_layout_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'workbench.css').write_text(
                '.a{transition:width .2s ease}\n.b{transition:transform .2s ease}\n'
                '.c{animation:slide 1s}\n', encoding='utf-8')
            found = gate.composited_motion_violations(root, ['workbench.css'])
            self.assertEqual(1, len(found), found)
            self.assertEqual('width', found[0]['property'])
            self.assertEqual(1, found[0]['line'])
            missing = gate.composited_motion_violations(root, ['not/here.css'])
            self.assertEqual('FILE_MISSING', missing[0]['property'], missing)

    def test_stale_deviation_ledger_is_a_finding(self):
        def mutate(d):
            land = record(d, 'visual-quality__motion-design-skill')['landing'][0]
            land['knownDeviations'] = [{'file': 'apps/workbench/style.css', 'line': 1,
                                        'property': 'left', 'declaration': LIE + ' transition: left .9s'}]
        only(self.mutated(mutate), 'no longer exists -- drop it from knownDeviations')

    # ------------------------------------------------------------------------ vocabularies
    def test_the_ladder_is_read_from_the_policy_file(self):
        self.assertEqual('candidate', self.load.ladder[0])
        self.assertEqual('commercially_proven', self.load.ladder[-1])
        self.assertIn('statically_verified', self.load.ladder)

    def test_adapter_status_model_is_read_from_the_registry(self):
        self.assertTrue(self.load.adapters, 'no adapter rows loaded')
        self.assertIn('adapter-adobe-photoshop', self.load.adapters)
        self.assertEqual('BLOCKED_BY_LICENSE', self.load.adapters['adapter-minimax-h3']['status'])

    def test_verdict_shaped_fields_are_graded(self):
        def mutate(d):
            record(d, 'visual-quality__taste-skill')['integrationStatus'] = 'ABSORBED'
        only(self.mutated(mutate), 'no published vocabulary')


if __name__ == '__main__':
    unittest.main()
