# SPDX-License-Identifier: MIT
"""Evidence artefact presence gate tests.

Distinguishes the two kinds of artefact path: a tracked file that has gone is a
hard break, while a `.project-local/` runtime path is expected to be absent on a
clean checkout and may only ever warn. The gate has to keep that difference or it
is either useless (always green) or noise (always red).
"""
from __future__ import annotations

import collections
import copy
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / 'design-lab' / 'scripts' / 'verify_evidence_artifact_presence.py'
LEDGER = REPO / 'design-lab' / 'config' / 'task-ledger-r3.json'

spec = importlib.util.spec_from_file_location('evidence_artifact_presence', MODULE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding='utf-8'))


def _untracked_artefacts(ledger: dict, tracked: set) -> list:
    """Rows of `currentExecution` whose artefact exists here but is not in the index.

    `artifact_path` is read from disk by the ledger's consumers, so a file that is merely *present*
    passes locally and disappears in a clone. Git's index is the only authority on whether the next
    checkout will have it, and `.project-local/**` is exempt because those paths are gitignored by
    design -- the gate's whole point is that those two kinds are not the same finding.
    """
    offenders = []
    for row in ledger['currentExecution']['evidence']:
        path = str(row.get('artifact_path', '')).replace('\\', '/')
        if not path or path.startswith('.project-local/'):
            continue
        if path not in tracked and not (REPO / path).is_dir():
            offenders.append((row.get('id'), path))
    return offenders


class EvidenceArtifactPresenceTests(unittest.TestCase):
    def test_tracked_artefacts_of_the_real_ledger_all_read_back(self):
        result = gate.evaluate(REPO, _ledger())
        self.assertEqual(result['broken'], [],
                         'every tracked evidence artefact must still exist')
        # Known decay, asserted rather than hidden. Each entry is a record whose
        # artefact bytes legitimately moved after the observation, and the inventory is
        # exact so the NEXT unannounced move still goes red. Fifty-three records on twenty-two
        # distinct artefacts -- and the numbers here are re-measured, not inherited: see
        # the correction below, because this count was wrong in this file for an hour.
        #   * build/main.js -- a 2026-09-27 record used a mutable build output as
        #     its artefact, so the bundle has since moved on;
        #   * the two files the 2026-10-06 M1 runtime-slice record bound by hash --
        #     test_project_backup.py (commit 701ace9c replaced the raw file copy with a
        #     snapshot plus a writer barrier) and test_workbench_launch.py (the launch
        #     token path moved into the service);
        #   * test_service_http.py -- 0cb1397b added the delivery-receipt route cases.
        # In every case the older record is not rewritten: it stays as the historical
        # observation it was, and a newer record carries the current binding.
        #
        # 2026-10-08, a correction that has to stay in the file: an hour ago this inventory was
        # widened to 27 records across 5 artefacts, and the extra 23 were a measurement bug, not
        # decay. The gate hashed `Path.read_bytes()` and compared it to a record's blob hash, so on
        # this platform every CRLF working file drifted permanently -- `.gitattributes` says
        # text=auto and the audit document is CRLF in the checkout and LF in the object store. (One
        # more correction, same day: this sentence also named "this test module" as CRLF, and
        # counting the bytes says it is LF. The CRLF set among the artefacts these records name is
        # the audit document, src/design_lab/native_delivery.py,
        # design-lab/config/contract-bindings.json and the two rollback test modules; build/main.js,
        # http_service.py, shell.ts and this file are LF.)
        # `git hash-object <file>` equals the HEAD blob for all of them,
        # which is the proof that no content moved. The gate now hashes the committed form
        # (`git show HEAD:<path>`, index as fallback), and the count went back to the four this
        # assertion named before. Kept in Counter form with the total pinned because a count that
        # cannot be disturbed guards nothing: a fifth real move, or a 24th record on one of these
        # artefacts, is still red.
        counts = collections.Counter((record, why) for _, record, why in result['drifted'])
        expected = collections.Counter({
            ('apps/workbench/build/main.js', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_project_backup.py', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_workbench_launch.py', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_service_http.py', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-08, commit 02fa13cd: the row that recorded the per-module verification pass
            # binds its artefacts to the code it describes rather than to the audit prose -- one of
            # those files is this one, and the line-ending fix then edited it. So the record's
            # artefact is older than the bytes it names, which is exactly what this inventory
            # exists to say out loud. Nothing is rewritten: the row stays the observation it was and
            # the correcting row for the defect names the current bytes.
            # 2026-10-08, one more on this same artefact, and the cause is this very commit: the
            # change that widened the inventory below lives in this file, so HEAD's bytes for it are
            # newer than BOTH records that name it -- r5-003-per-module-verification-and-two-assertions-my-own-wave-moved-20261008
            # and r5-003-artefact-gate-hashed-working-bytes-so-crlf-always-drifted-20261008. A record
            # that names a source file ages whenever that file is edited; that is the property this
            # inventory exists to make visible, and the bound run caught it before I did -- the
            # module passed standalone (against the pre-commit HEAD) and failed once the commit
            # existed. The count is re-measured here, not inherited from the line above.
            ('design-lab/tests/test_evidence_artifact_presence.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            # 2026-10-08, the second time this exact number appeared in this file -- and the first
            # time it is true. Twenty-three records name
            # docs/audits/DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md as their artefact, and
            # section 22 of that document is now committed, so HEAD's bytes for that path are no
            # longer the bytes those records hashed. This is NOT the bug recorded below: that one
            # was 23 drifts caused by hashing working bytes against a blob hash on a CRLF checkout,
            # disproved by `git hash-object` equalling the HEAD blob. Here the committed blob
            # itself moved, which is what a continuously written document does to every record that
            # cites it. The practice this pays for is already in force: a new record binds the code
            # it describes (see the r5-010 rollback row), so it drifts when that code moves and not
            # when the prose is extended. The 23 ids are named by the gate's own output; none of
            # them is rewritten -- each stays the observation it was, and the newest records carry
            # the current binding.
            # 2026-10-08, commit ab45c818 added the missing `unittest.main()` entry guard to five
            # files that records from 2026-09-27/28 had hashed as artefacts:
            # test_comfy_http.py (2 records), test_illustrator_com_adapter.py, test_model_manifest.py,
            # test_photoshop_com_adapter.py and test_workbench_native_ui.py (4 records). Before that
            # commit, executing any of them ran zero tests and exited 0, so those records were
            # describing bytes belonging to files whose contents had never been read back per file --
            # the guard is what makes a per-module run mean anything. Nine more drifted pairs, and
            # test_workbench_launch.py was already in this list, so its own bootstrap adds none.
            ('design-lab/tests/test_comfy_http.py', 'HASH_MOVED_SINCE_OBSERVATION'): 2,
            ('design-lab/tests/test_illustrator_com_adapter.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_model_manifest.py', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_photoshop_com_adapter.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_workbench_native_ui.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 4,
            # 2026-10-19 T16/U09: candidate-knowledge became PRODUCT, so the pinned
            # UNREFERENCED row was deleted here -- and the 2026-10-08 records that bound
            # this gate now name older bytes. One more record on each of these two files,
            # re-measured at this HEAD rather than inherited: 59 pairs, broken=0.
            ('design-lab/scripts/verify_object_model_backing.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            # 2026-10-08, four more names on this inventory, all of them caused by the wave that
            # settled the delivery-manifest object row, and each one is a record whose artefact is
            # the code it described rather than the prose -- which is the binding practice this file
            # asked for. They drift because that code genuinely moved:
            #   * contract-bindings.json -- commit 717257ab re-pointed the artifact-preflight
            #     emitter from production_preflight.py:365 to :378, because the delivery-bom
            #     finding inserted thirteen lines above it. The pointer is checked by line number on
            #     purpose, so a real insertion must move it (verify_contract_bindings.py).
            #   * verify_design_lab.py -- 717257ab added verify_template_contracts.py to SCRIPTS
            #     (67 gates to 68) and corrected the object-model comment to the new 6/9/6 split.
            #   * verify_object_model_backing.py -- the same commit deleted the delivery-manifest
            #     row from UNREFERENCED, re-pinned the counts to product=6/unreferenced=6, and
            #     replaced the two stale "against HEAD 0a873fc1" citations with the commit the
            #     re-measurement actually ran at.
            #   * test_object_model_backing_gate.py -- REAL_COUNTS re-pinned to match, and the
            #     hardcoded "expected 7" in the weakened-copy test became derived from REAL_COUNTS
            #     so this class of staleness cannot come back.
            # Nothing above is rewritten: each stays the observation it was.
            ('design-lab/config/contract-bindings.json',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            ('design-lab/scripts/verify_design_lab.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('design-lab/tests/test_object_model_backing_gate.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 3,
            # 2026-10-08, the prose-classifier correction moved two more pairs and added one name.
            # Both are rows bound to code, which is why they drift when that code is corrected:
            #   * object-model.json -- a record hashes it as its artefact, and the quality-report row
            #     was re-pointed onto assurance-jury-record-v2.schema.json (the schema human_jury.py
            #     actually loads) once the classifier stopped reading docstrings as references;
            #   * test_object_model_backing_gate.py -- the second drifted record on this file is the
            #     same wave: REAL_COUNTS re-pinned 7/9/5 to 5/10/6 and the new
            #     ProseIsNotAReferenceTests added to it.
            # Neither older record is rewritten; each stays the observation it was.
            ('design-lab/config/object-model.json', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-08, commit 6fa40276 added two more, both records bound to the gate that
            # re-measures the INERT claims rather than to the audit prose:
            #   * verify_contract_bindings.py -- it now re-tests every "nothing implements this"
            #     assertion and requires a citation to be a path;
            #   * test_contract_bindings.py -- four injection cases went with those rules, including
            #     the one that caught this gate convicting one vanished file twice.
            # Re-measured 2026-10-13: 1 -> 2. A second record began binding this gate when the
            # EvidenceDirectory preflight wiring was added to its SCRIPTS list, so the same
            # legitimate move that drifted it the first time drifted it again. Still a moved
            # artefact, not a new artefact and not a silently absorbed record.
            ('design-lab/scripts/verify_contract_bindings.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            ('design-lab/tests/test_contract_bindings.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            # 2026-10-08, the evidence readback wave (3520c82f / 2aeaaaf4 / a0d001a8) added four
            # pairs. Every one is a record bound to code that this wave genuinely changed, which is
            # the binding practice this file asks for -- they drift because the shipped implementation
            # moved, not because prose was extended:
            #   * verify_route_payload_contracts.py -- a seventh live-socket binding for
            #     GET /api/evidence-projection, validated over 156 object locations;
            #   * contract-bindings.json -- the route row that makes that binding non-removable
            #     (routes 53 -> 54, bound 15 -> 16);
            #   * test_contract_bindings.py -- its pinned route count moved with the same row;
            #   * reporting.py -- the claim enumeration became the single owner the binding gate
            #     imports, and the object reads were batched per commit (10.0s -> 1.0s).
            # No older record is rewritten; each stays the observation it was.
            ('design-lab/scripts/verify_route_payload_contracts.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('docs/audits/DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md',
             'HASH_MOVED_SINCE_OBSERVATION'): 23,
            # 2026-10-08, commit 9e7db8a4 added one more. It is a record bound to code, not to prose:
            # reporting.py owns the byte-claim enumeration now, so the older record that hashed it as
            # its artefact is honestly describing bytes that have since moved. The older record is not
            # rewritten -- it stays the observation it was, and this line is what makes that visible
            # instead of silent.
            ('src/design_lab/governance/reporting.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 2,
            # 2026-10-08, the evidence readback wave's own boundary-text correction (78abda27) and
            # the brand-mark slice (11026229) both moved shell.ts. One record hashes shell.ts as its
            # artefact -- the row that bound the 证据 page's readback to the file it described -- so
            # it now describes bytes that have moved. It is not rewritten: the newer binding is the
            # brand row's own subject_files, and this line is what keeps the older observation
            # honest instead of silently absorbing the change.
            ('apps/workbench/shell.ts', 'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-08, commit a87b8eea: the object-model round-trip builder was taught to follow
            # a $ref, and one record binds that very file as its artefact -- the row that recorded
            # the round-trip gate's per-object coverage. Editing the gate ages the record that
            # quotes it, which is the property this inventory exists to expose rather than a defect
            # in either. The older record still reports what it observed; the newer bytes are bound
            # by the row this wave appends.
            ('design-lab/tests/test_oda4_0204b_object_model_roundtrip.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-08, commit af9a0985 added one pair, and it is a record bound to code:
            # r5-002-static-unit-20260928 hashes design-lab/tests/test_project_paths.py as its
            # artefact, and that commit put two new cases in the module (an inherited
            # PROJECT_LOCAL_ROOT that names an enclosing checkout must not relocate a project
            # the caller named explicitly; and the escaping/protected ambient values must still
            # fail closed). The runtime root policy genuinely moved, so the 2026-09-28
            # observation now describes older bytes than the file it names. The record is not
            # rewritten -- it stays the observation it was, and this line is what makes the age
            # visible instead of silently absorbing it. Re-measured at this HEAD, not inherited
            # from the lines above: observed 54 pairs against the 53 pinned before this line,
            # broken=0, and the only difference was this artefact.
            ('design-lab/tests/test_project_paths.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-13, one new pair: the taskpack-original exemption case stopped requiring a
            # machine-local directory to exist before TemporaryDirectory could use it, so a clean
            # clone could run it. The record binds this module, the module's bytes moved, and the
            # inventory is what makes that visible instead of silent. Re-measured at this HEAD:
            # observed 56 pairs against the 54 pinned before this line, broken=0.
            ('design-lab/tests/test_core_gates.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-19, one new pair: the route-table rewrite (72102fea) changed how
            # http_service.py dispatches, and the per-module verification record from
            # 2026-10-08 binds this test module as its artefact. Correcting the module to
            # read `ROUTES` moved its bytes, so the record now names older bytes. The
            # record is not rewritten; the newer binding is the correction's own commit.
            ('design-lab/tests/test_domain_pack_readback.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-19, the archive/removal wave aged the gate's own module. A record binds
            # design-lab/scripts/verify_evidence_artifact_presence.py as its artefact; the wave added
            # relocation and recovery resolution to that gate, so HEAD's bytes for it are now newer
            # than the record's digest. This is the property the inventory exists to make visible --
            # a record that names a source file ages when that file is edited -- and it is the same
            # self-inflicted entry this file already documents twice for itself. Re-measured, not
            # inherited: the delta between the pinned Counter and the run was exactly this one pair.
            ('design-lab/scripts/verify_evidence_artifact_presence.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-23, four new pairs, all of them records bound to the code they describe, and
            # all four files moved for the same reason: this batch pointed their contract/config
            # reads at `runtime/state_resources.repo_resource()` so an installed wheel can open them
            # (see the delivery report §5.25). `delivery_bom.py` and `evidence_readback.py` are the
            # two that only a live installed run caught -- a missing packaged file had been answering
            # `409 NATIVE_BUNDLE_UNVERIFIED` and `503 EVIDENCE_LEDGER_ABSENT`, i.e. wearing the mask
            # of a verdict; `design_layer.py` answered `500 INTERNAL`; `dtcg.py` ships the same
            # interop contract. Nothing older is rewritten: each stays the observation it was, and
            # the newer bytes are bound by this batch's own commits. Re-measured at HEAD `90d7d4ed`
            # with this file's own spy, not inherited: observed 64 pairs against the 60 pinned before
            # these four lines, broken=0, and the delta was exactly these four names.
            ('src/design_lab/assurance/delivery_bom.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('src/design_lab/design_layer.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('src/design_lab/governance/evidence_readback.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            ('src/design_lab/interop/dtcg.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-25, one new pair, and it is a record bound to a test module rather than to
            # product code: r5-workbench-http-native-ui-reobserved-20261006 hashes
            # design-lab/tests/test_design_layer_http.py as its artefact, and this round added
            # `test_unknown_project_id_answers_404_with_the_established_word` to that module after
            # proving the route previously answered a well-formed-but-absent project id with no
            # status line at all (http.client.RemoteDisconnected). The older 2026-10-06 observation
            # is not rewritten -- it stays what it saw -- and this line is what makes its age
            # visible instead of letting the newer bytes silently absorb it. Re-measured at this
            # HEAD against the 64 pinned before this line: observed 65 pairs, broken=0, and the
            # only difference was this artefact; no pair vanished and no existing count moved.
            ('design-lab/tests/test_design_layer_http.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
            # 2026-10-26, one new pair, and it is a record bound to a test module: the owner-audit
            # fix for `doctor --task` added the three format cases to test_doctor.py (refusal names
            # the expected '<TASKPACK>::<TASK_KEY>' shape and exits 2; success returns the preflight
            # contract envelope; --paths unchanged), and a record hashes that module as its
            # artefact. The product file it aged was `src/design_lab/runtime/doctor.py` -- no record
            # binds that one by hash, which is why only this pair moved. Re-measured against this
            # file's own spy rather than inherited: observed 66 pairs against the 65 pinned before
            # this line, broken=0, and the delta was exactly this one name; no pair shrank.
            ('design-lab/tests/test_doctor.py',
             'HASH_MOVED_SINCE_OBSERVATION'): 1,
        })
        self.assertEqual(counts, expected,
                         'the drifted-artefact inventory is exact in both directions: a new '
                         'move, a new artefact name, or one more record on a known artefact '
                         'are all findings, and a drifted pair that quietly disappeared is too')
        self.assertEqual(sum(counts.values()), 66,
                         'the total drifted-record count is pinned, not derived '
                         '(59 -> 60 on 2026-10-19: the gate module aged its own binding record; '
                         '60 -> 64 on 2026-10-23: four records aged when their bound code moved to '
                         'repo_resource so an installed wheel can open its own contracts; '
                         '64 -> 65 on 2026-10-25: one record aged when a 404 test was added to the '
                         'HTTP module it hashes; 65 -> 66 on 2026-10-26: one record aged when the '
                         'owner-audit fix for doctor --task added cases to the module it hashes)')

    def test_missing_tracked_artefact_is_a_hard_break_not_a_warning(self):
        ledger = copy.deepcopy(_ledger())
        target = next(e for e in ledger['evidence']
                      if any(not a['path'].startswith('.project-local')
                             for a in e['artifacts']))
        target['artifacts'] = [{'path': 'docs/this-evidence-file-does-not-exist.md',
                                'sha256': '0' * 64}]
        result = gate.evaluate(REPO, ledger)
        self.assertEqual([entry[2] for entry in result['broken']], ['NOT-IN-GIT-INDEX'])

    def test_changed_artefact_bytes_count_as_drift_not_destruction(self):
        """Decay vs destruction, asserted on a document the tree still holds.

        The 2026-10-19 removal wave deleted four handoff documents that ledger records name as
        artefacts. Those rows now resolve through REMOVALS.json into the `recovered` category: the
        gate can prove the bytes are still reachable (git cat-file on the recorded blob) but cannot
        compare content drift, because there is no tracked file left to hash. Tampering one of those
        rows would assert nothing, so the candidate is chosen among artefacts the tree still holds,
        and the recovered set is pinned by its own test below rather than quietly skipped.
        """
        ledger = copy.deepcopy(_ledger())
        relocated = set(gate._relocations(REPO)) | set(gate._removals(REPO))
        for receipt in ledger['evidence']:
            for artifact in receipt['artifacts']:
                path = artifact['path']
                if path.startswith('.project-local') or path in relocated:
                    continue
                artifact['sha256'] = 'f' * 64
                result = gate.evaluate(REPO, ledger)
                self.assertIn((receipt['id'], path,
                               'HASH_MOVED_SINCE_OBSERVATION'), result['drifted'])
                self.assertEqual(result['broken'], [])
                return
        self.fail('no live tracked artefact found to tamper with')

    def test_removed_artefacts_are_recovered_by_provable_objects_not_marked_present(self):
        """A removed artefact must be named, with a blob the object store still holds.

        This is the guard the removal wave replaced the drift check with. `recovered` is not a
        warning bucket: each entry is a ledger record whose artefact left the tree on owner order,
        and the gate only counts it as recovered after `git cat-file -e` accepts the blob the removal
        manifest recorded. Drop the manifest and these same four rows come back as BROKEN -- which is
        why the inventory is pinned in both directions here.
        """
        result = gate.evaluate(REPO, _ledger())
        self.assertEqual(sorted((receipt, path) for receipt, path, _ in result['recovered']),
                         [('r5-comfy-http-model-free-live-20260909',
                           'docs/handoffs/R5-COMFY-HTTP-LIVE-2026-09-09.md'),
                          ('r5-comfy-structural-rejection-20260909',
                           'docs/handoffs/R5-COMFY-STRUCTURAL-REJECTION-2026-09-09.md'),
                          ('r5-ps-handoff-review-20260909',
                           'docs/handoffs/R5-PHOTOSHOP-FULL-REGRESSION-2026-09-09.md'),
                          ('r5-ps-handoff-review-20260909',
                           'docs/handoffs/R5-PHOTOSHOP-PATCH-PRODUCT-2026-09-09.md')],
                         'the recovered set is exactly the four handoff artefacts the removal wave '
                         'deleted; a fifth one appearing here means an unannounced deletion')
        self.assertEqual(result['broken'], [])
        for _, path, restore in result['recovered']:
            self.assertTrue(restore and len(restore) == 40, f'{path} names no full restore commit')
            self.assertEqual(subprocess.run(['git', '-C', str(REPO), 'cat-file', '-e', restore],
                                            capture_output=True).returncode, 0,
                             f'{path} is not readable at its own restoreAt')

    def test_runtime_paths_only_warn(self):
        ledger = copy.deepcopy(_ledger())
        ledger['evidence'] = [{
            'id': 'synthetic', 'task_ids': ['DL-R5-001'], 'kind': 'local_test',
            'outcome': 'PASS', 'subject_sha': '0' * 40, 'binding': 'COMMIT',
            'observed_at': '2026-10-06T00:00:00Z', 'software': {}, 'subject_files': {},
            'artifacts': [{'path': '.project-local/never/existed.json',
                           'sha256': '0' * 64}],
            'note': 'synthetic',
        }]
        result = gate.evaluate(REPO, ledger)
        self.assertEqual(result['broken'], [])
        self.assertEqual(len(result['runtime_missing']), 1)


    def test_every_dispatched_artefact_the_ledger_names_is_in_git_index(self):
        """A row whose artefact exists only on my disk is a record that cannot be re-read.

        CI run 40338742258 at `4dc59349` is why this assertion exists: the script that closed the
        round staged whatever git marked ` M` and left the brand-new `??` receipt out of the commit,
        so `currentExecution` carried a row pointing at `dl-final-t04-exact-sha-ci-matrix-20261026
        .json`, which a clone did not have. Two gates read it there -- `CURRENT_EXECUTION` and the
        `evidence-projection` route, which re-hashes the ledger and answered
        `500 EVIDENCE_LEDGER_REJECTED` -- and neither could see it here, because the file was on my
        disk the whole time. Presence on disk is not presence in the delivery.
        """
        listing = subprocess.run(['git', 'ls-files', '-z'], cwd=str(REPO), capture_output=True,
                                 check=True).stdout.decode('utf-8').split('\0')
        offenders = _untracked_artefacts(_ledger(), set(listing))
        self.assertEqual([], offenders,
                         'these ledger rows name an artefact that a clean checkout will not '
                         'contain: %s' % (offenders,))

    def test_the_index_check_convicts_a_path_that_is_not_in_the_index(self):
        """Without the plant, the assertion above cannot be told apart from one that never fires.

        Deliberately no file is written: whether the artefact sits on my disk is exactly the
        distinction the index settles, and dropping a scratch file under `design-lab/evidence/` would
        let a concurrently running shard enumerate a row that only exists for the length of this
        test. An untracked path is untracked whether or not it is present.
        """
        listing = subprocess.run(['git', 'ls-files', '-z'], cwd=str(REPO), capture_output=True,
                                 check=True).stdout.decode('utf-8').split('\0')
        tracked = set(listing)
        stray = ('design-lab/evidence/current-execution/task-artifacts/kb-20261026/'
                 '_untracked-probe.json')
        self.assertNotIn(stray, tracked, 'the probe path is somehow tracked, so it proves nothing')
        ledger = copy.deepcopy(_ledger())
        row = {'id': 'probe-row', 'task_id': 'DL-KB-01', 'axis': 'unit', 'outcome': 'PASS',
               'observed_at': '2026-10-26T00:00:00Z', 'subject_sha': '0' * 40, 'exit_code': 0,
               'command': 'probe', 'artifact_path': stray, 'artifact_sha256': '0' * 64}
        ledger['currentExecution']['evidence'].append(row)
        offenders = _untracked_artefacts(ledger, tracked)
        self.assertIn('probe-row', [one[0] for one in offenders],
                      'an artefact outside the index slipped through the check')
        # And the exemption has to stay an exemption: a gitignored runtime path is a warning in the
        # gate's own vocabulary, never a missing record in the index.
        gitignored = copy.deepcopy(ledger)
        gitignored['currentExecution']['evidence'] = [dict(row,
                                                           artifact_path='.project-local/x.json')]
        self.assertEqual([], _untracked_artefacts(gitignored, tracked),
                         'the check now convicts gitignored runtime paths too, which would make '
                         'every clean checkout red')


if __name__ == '__main__':
    unittest.main()
