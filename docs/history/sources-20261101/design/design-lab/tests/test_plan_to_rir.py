# SPDX-License-Identifier: MIT
"""Plan -> reconstruction-ir/v1 bridge tests (E1 structural).

Guards the honesty rules of the bridge: ids are carried over unchanged so the
existing patch path can address them, nothing the analysis did not observe is
invented (fonts, geometry, colours), and every derived node stays `inferred`.
No OCR run, no host execution and no human judgement is claimed here.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

RASTER = "design-lab/evals/reconstruction/cases/poster-sunrise-001/reference.png"


def _plan(**overrides):
    from design_lab.analysis.decomposition import CanvasRegion, Plan, PlanObject

    objects = overrides.pop('objects', None) or [
        PlanObject('ocr-1', 'text', CanvasRegion(50, 50, 300, 80), module='ocr',
                   text_content='标题', font_status='matched', confidence=0.91),
        PlanObject('s-1', 'shape', CanvasRegion(10, 10, 20, 20), module='tracer',
                   source_polygon=((10, 10), (30, 10), (30, 30), (10, 30)),
                   confidence=0.6),
        PlanObject('i-1', 'image', CanvasRegion(50, 200, 500, 600), module='heuristic'),
        PlanObject('u-1', 'unknown', CanvasRegion(0, 0, 1000, 40), module='heuristic',
                   mapping_state='unrecovered'),
    ]
    plan = Plan(
        decomposition_id=overrides.get('decomposition_id', 'dec-1'),
        source_ref=overrides.get('source_ref', 'reference/poster.png'),
        source_sha256=overrides.get('source_sha256', 'sha256:' + 'a' * 64),
        canvas=CanvasRegion(0, 0, 1000, 1400),
        objects=objects,
    )
    plan.validate()
    return plan


class PlanToRirTests(unittest.TestCase):
    def _rir(self, plan=None):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        return plan_to_rir(plan or _plan(), raster_path=RASTER, project_root=REPO,
                           timestamp='2026-10-05T00:00:00Z')

    def test_output_validates_against_rir_contract(self):
        rir = self._rir()
        self.assertEqual(rir['schemaVersion'], 'design-lab/reconstruction-ir/v1')
        self.assertEqual(rir['canvas'], {'width': 1000, 'height': 1400, 'colorSpace': 'srgb'})
        self.assertEqual([n['id'] for n in rir['layers']], ['ocr-1', 's-1', 'i-1', 'u-1'])
        self.assertEqual(rir['provenance']['sourceId'], 'dec-1')

    def test_ids_are_carried_over_for_object_level_patch(self):
        """The patch path addresses nodes by id, so the bridge must not rename."""
        from design_lab.analysis.plan_to_rir import plan_to_rir
        plan = _plan()
        rir = plan_to_rir(plan, raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z')
        self.assertEqual({n['id'] for n in rir['layers']}, {o.object_id for o in plan.objects})

    def test_every_node_stays_inferred_and_unlocked(self):
        for node in self._rir()['layers']:
            self.assertTrue(node['inferred'])
            self.assertFalse(node['locked'])
            self.assertIn('confidence', node)
            self.assertIn('provenance', node)

    def test_matched_font_gets_no_invented_candidate(self):
        text = next(n for n in self._rir()['layers'] if n['type'] == 'text')
        self.assertEqual(text['text']['content'], '标题')
        self.assertEqual(text['text']['fontCandidates'], [])
        self.assertEqual(text['text']['outlineFallback'], {'available': False, 'pathData': None})
        self.assertNotIn('repairHistory', text)

    def test_unmatched_font_is_flagged_for_user_correction(self):
        from design_lab.analysis.decomposition import CanvasRegion, PlanObject
        plan = _plan(objects=[PlanObject('ocr-2', 'text', CanvasRegion(0, 0, 10, 10),
                                        module='ocr', text_content='Aa',
                                        font_status='missing')])
        text = self._rir(plan)['layers'][0]
        note = text['repairHistory'][0]
        self.assertEqual(note['operation'], 'USER_CORRECTION_REQUIRED')
        self.assertIn('font_status=missing', note['reason'])

    def test_traced_polygon_becomes_a_path_and_untraced_becomes_flagged_rect(self):
        layers = {n['id']: n for n in self._rir()['layers']}
        self.assertEqual(layers['s-1']['type'], 'path')
        self.assertEqual(layers['s-1']['geometry']['pathData'], 'M 10 10 30 10 30 30 10 30 Z')
        self.assertEqual(layers['s-1']['geometry']['closed'], True)
        self.assertEqual(layers['s-1']['style'], {})
        self.assertNotIn('repairHistory', layers['s-1'])

    def test_shape_without_polygon_is_a_box_substitution_not_traced_geometry(self):
        from design_lab.analysis.decomposition import CanvasRegion, PlanObject
        plan = _plan(objects=[PlanObject('s-2', 'shape', CanvasRegion(1, 2, 30, 40),
                                        module='tracer')])
        node = self._rir(plan)['layers'][0]
        self.assertEqual(node['type'], 'primitive')
        self.assertEqual(node['primitive']['kind'], 'rect')
        self.assertEqual(node['primitive']['parameters'], {'x1': 1, 'y1': 2, 'x2': 31, 'y2': 42})
        self.assertEqual(node['repairHistory'][0]['operation'], 'USER_CORRECTION_REQUIRED')
        self.assertIn('bounds substituted', node['repairHistory'][0]['reason'])

    def test_image_region_points_at_the_project_relative_raster(self):
        raster = next(n for n in self._rir()['layers'] if n['type'] == 'raster')
        self.assertEqual(raster['raster']['path'], RASTER)
        self.assertEqual(raster['raster']['crop'], {'x': 50, 'y': 200, 'width': 500, 'height': 600})
        self.assertEqual(raster['raster']['sourceMappings'][0]['targetBounds']['width'], 500)

    def test_unrecovered_content_stays_an_empty_group_with_a_reason(self):
        group = next(n for n in self._rir()['layers'] if n['type'] == 'group')
        self.assertEqual(group['children'], [])
        self.assertEqual(group['repairHistory'][0]['operation'], 'USER_CORRECTION_REQUIRED')
        self.assertIn('content not recovered', group['repairHistory'][0]['reason'])

    def test_absolute_raster_path_is_rejected_not_sanitised(self):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        from design_lab.reconstruction.contracts import ContractError
        with self.assertRaises(ContractError):
            plan_to_rir(_plan(), raster_path='D:/elsewhere/poster.png',
                        project_root=REPO, timestamp='2026-10-05T00:00:00Z')

    def test_absent_detector_score_is_labelled_not_silently_zero(self):
        from design_lab.analysis.decomposition import CanvasRegion, PlanObject
        plan = _plan(objects=[PlanObject('i-2', 'image', CanvasRegion(0, 0, 10, 10),
                                        module='heuristic')])
        confidence = self._rir(plan)['layers'][0]['confidence']
        self.assertEqual(confidence['score'], 0.0)
        self.assertIn('confidence unreported', confidence['method'])

    def test_unsupported_kind_fails_closed(self):
        from design_lab.analysis.decomposition import CanvasRegion, DecompositionError, PlanObject
        plan = _plan(objects=[PlanObject('x-1', 'video', CanvasRegion(0, 0, 5, 5))])
        with self.assertRaises(DecompositionError):
            self._rir(plan)

    def test_empty_plan_fails_closed(self):
        from design_lab.analysis.decomposition import DecompositionError
        plan = _plan(objects=[])
        plan.objects = []
        with self.assertRaises(DecompositionError):
            self._rir(plan)

    def test_ocr_detection_plan_lowers_end_to_end(self):
        """Plan.from_ocr output is consumable without hand-authored objects."""
        from design_lab.analysis.decomposition import Plan
        plan = Plan.from_ocr(
            decomposition_id='dec-ocr', source_ref='reference/poster.png',
            source_sha256='sha256:' + 'b' * 64, canvas=(1000, 1400), module='ocr-fixture',
            detections=[{'text': 'SUNRISE', 'confidence': 0.83,
                         'polygon': [[50, 60], [350, 60], [350, 120], [50, 120]]}])
        rir = self._rir(plan)
        self.assertEqual(rir['layers'][0]['text']['content'], 'SUNRISE')
        self.assertEqual(rir['layers'][0]['confidence']['score'], 0.83)
        # The non-text remainder must survive as an unrecovered group, never as
        # a fabricated background layer.
        self.assertEqual(rir['layers'][-1]['type'], 'group')


class PlanToAdobeLoweringTests(unittest.TestCase):
    """The bridge must feed the existing host-proven lowering, not a new one."""

    def _plan(self):
        from design_lab.analysis.decomposition import CanvasRegion, Plan, PlanObject
        return Plan('dec-low', 'reference/poster.png', 'sha256:' + 'c' * 64,
                    CanvasRegion(0, 0, 1000, 1400),
                    [PlanObject('ocr-1', 'text', CanvasRegion(50, 50, 300, 80),
                                module='ocr', text_content='SUNRISE',
                                font_status='matched', confidence=0.9),
                     PlanObject('s-1', 'shape', CanvasRegion(10, 10, 20, 20),
                                module='tracer', confidence=0.5,
                                source_polygon=((10, 10), (30, 10), (30, 30), (10, 30)))])

    TEXT_STYLE = {'font': 'Arial', 'size': 48, 'color': [17, 17, 17]}

    def setUp(self):
        # build_adobe_job refuses to create its run root, so the test owns a
        # fresh directory under the project runtime root.
        import tempfile
        base = REPO / '.project-local' / 'task-runtime' / 'plan-to-rir-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.run_dir = Path(tempfile.mkdtemp(dir=base))

    def test_uncorrected_style_is_refused_by_lowering_instead_of_guessed(self):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        from design_lab.reconstruction.adobe_job import AdobeJobError, build_adobe_job
        rir = plan_to_rir(self._plan(), raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z')
        with self.assertRaises(AdobeJobError) as caught:
            build_adobe_job(rir, self.run_dir,
                            text_styles={'ocr-1': dict(self.TEXT_STYLE)}, project_root=REPO)
        self.assertIn('solid RGB hex fill required', str(caught.exception))

    def test_missing_font_style_is_refused_too(self):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        from design_lab.reconstruction.adobe_job import AdobeJobError, build_adobe_job
        rir = plan_to_rir(self._plan(), raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z',
                          style_overrides={'s-1': {'fill': '#1a2b3c'}})
        with self.assertRaises(AdobeJobError):
            build_adobe_job(rir, self.run_dir, text_styles={}, project_root=REPO)

    def test_user_supplied_font_and_fill_reach_a_valid_illustrator_job(self):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        from design_lab.reconstruction.adobe_job import build_adobe_job
        rir = plan_to_rir(self._plan(), raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z',
                          style_overrides={'s-1': {'fill': '#1a2b3c'}})
        job = build_adobe_job(rir, self.run_dir,
                              text_styles={'ocr-1': dict(self.TEXT_STYLE)},
                              project_root=REPO)
        payload = job.to_dict()
        self.assertEqual(payload['artboard'], {'width': 1000, 'height': 1400})
        lowered = {item['id']: item['kind']
                   for layer in payload['layers'] for item in layer['items']}
        self.assertEqual(lowered, {'ocr-1': 'text', 's-1': 'path'})
        # The job id is derived from the canonical RIR hash, so the same plan
        # re-lowers to the same addressable object ids the patch path needs.
        self.assertTrue(payload['jobId'].startswith('adobe-'))


class MaterializeRasterRegionTests(unittest.TestCase):
    """A photo region only lowers once it is a real staged asset."""

    SOURCE = REPO / 'design-lab' / 'evals' / 'reconstruction' / 'cases' / \
        'poster-sunrise-001' / 'reference.png'

    def setUp(self):
        from design_lab.analysis.decomposition import CanvasRegion, Plan, PlanObject
        base = REPO / '.project-local' / 'task-runtime' / 'plan-to-rir-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.run_dir = Path(tempfile.mkdtemp(dir=base))
        self.plan = Plan('dec-raster', 'reference/poster.png', 'sha256:' + 'd' * 64,
                         CanvasRegion(0, 0, 192, 128),
                         [PlanObject('i-1', 'image', CanvasRegion(10, 10, 100, 50),
                                     module='heuristic', confidence=0.7)])

    def test_region_is_copied_not_resampled(self):
        from PIL import Image
        from design_lab.analysis.plan_to_rir import materialize_raster_regions
        regions = materialize_raster_regions(self.plan, self.SOURCE, self.run_dir,
                                             project_root=REPO)
        staged = self.run_dir / 'i-1.png'
        self.assertTrue(staged.is_file())
        with Image.open(staged) as crop:
            self.assertEqual(crop.size, (100, 50))
        self.assertEqual(regions['i-1']['width'], 100)
        self.assertEqual(regions['i-1']['height'], 50)
        self.assertTrue(regions['i-1']['path'].startswith('.project-local/'))
        self.assertNotIn('\\', regions['i-1']['path'])

    def test_staged_region_lowers_into_an_illustrator_raster_layer(self):
        from design_lab.analysis.plan_to_rir import (materialize_raster_regions,
                                                     plan_to_rir)
        from design_lab.reconstruction.adobe_job import build_adobe_job
        regions = materialize_raster_regions(self.plan, self.SOURCE, self.run_dir,
                                             project_root=REPO)
        rir = plan_to_rir(self.plan, raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z', regions=regions)
        raster = rir['layers'][0]['raster']
        self.assertEqual(raster['crop'], {'x': 0, 'y': 0, 'width': 100, 'height': 50})
        self.assertEqual(raster['sourceMappings'], [])
        payload = build_adobe_job(rir, self.run_dir, text_styles={},
                                  project_root=REPO).to_dict()
        lowered = [item for layer in payload['layers'] for item in layer['items']]
        self.assertEqual([item['kind'] for item in lowered], ['raster'])
        self.assertEqual(lowered[0]['id'], 'i-1')

    def test_unmaterialized_region_stays_visible_as_a_gate(self):
        from design_lab.analysis.plan_to_rir import plan_to_rir
        from design_lab.reconstruction.adobe_job import AdobeJobError, build_adobe_job
        rir = plan_to_rir(self.plan, raster_path=RASTER, project_root=REPO,
                          timestamp='2026-10-05T00:00:00Z')
        self.assertEqual(len(rir['layers'][0]['raster']['sourceMappings']), 1)
        with self.assertRaises(AdobeJobError) as caught:
            build_adobe_job(rir, self.run_dir, text_styles={}, project_root=REPO)
        self.assertIn('raster remapping/alpha requires explicit preprocessed asset',
                      str(caught.exception))

    def test_region_outside_the_reference_fails_closed(self):
        from design_lab.analysis.decomposition import CanvasRegion, DecompositionError, PlanObject
        from design_lab.analysis.plan_to_rir import materialize_raster_regions
        self.plan.objects = [PlanObject('i-2', 'image',
                                        CanvasRegion(150, 100, 100, 100),
                                        module='heuristic')]
        with self.assertRaises(DecompositionError):
            materialize_raster_regions(self.plan, self.SOURCE, self.run_dir,
                                       project_root=REPO)

    def test_object_id_that_is_not_a_safe_file_name_is_refused(self):
        from design_lab.analysis.decomposition import CanvasRegion, DecompositionError, PlanObject
        from design_lab.analysis.plan_to_rir import materialize_raster_regions
        self.plan.objects = [PlanObject('../escape', 'image',
                                        CanvasRegion(0, 0, 10, 10), module='heuristic')]
        with self.assertRaises(DecompositionError):
            materialize_raster_regions(self.plan, self.SOURCE, self.run_dir,
                                       project_root=REPO)


if __name__ == '__main__':
    unittest.main()
