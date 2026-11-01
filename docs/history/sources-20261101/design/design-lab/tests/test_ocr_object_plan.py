# SPDX-License-Identifier: MIT
"""OCR observations become editable candidates, never verified host objects."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.analysis.decomposition import Plan, DecompositionError


class OcrObjectPlanTests(unittest.TestCase):
    def build(self, detections=None, **overrides):
        values = dict(decomposition_id='ocr-1', source_ref='reference.png',
                      source_sha256='sha256:' + 'a' * 64, canvas=(200, 100),
                      module='pp-ocrv6-medium-onnx', detections=detections if detections is not None else [
                          dict(text='设计标题', confidence=.93,
                               polygon=[[10, 20], [90, 20], [90, 40], [10, 40]])])
        values.update(overrides)
        return Plan.from_ocr(**values)

    def test_preserves_text_region_confidence_without_inventing_host_or_font(self):
        plan = self.build()
        obj = plan.to_contract()['objects'][0]
        self.assertEqual(obj['region'], dict(x=10, y=20, width=80, height=20))
        self.assertEqual(obj['text_content'], '设计标题')
        self.assertEqual(obj['confidence'], .93)
        self.assertEqual(obj['source_polygon'], [[10,20],[90,20],[90,40],[10,40]])
        self.assertEqual(obj['mapping_state'], 'unmapped')
        self.assertEqual(obj['font_status'], 'unknown')
        self.assertIsNone(obj['host_object_id'])
        import jsonschema
        schema = json.loads((ROOT/'design-lab/schemas/contracts/planar-decomposition.schema.json').read_text(encoding='utf-8'))
        jsonschema.validate(plan.to_contract(), schema)

    def test_ids_survive_backend_order_changes_and_input_is_not_mutated(self):
        a=dict(text='A', confidence=.8, polygon=[[1,1],[9,1],[9,8],[1,8]])
        b=dict(text='B', confidence=.7, polygon=[[20,1],[29,1],[29,8],[20,8]])
        original=copy.deepcopy([a,b])
        first=self.build([a,b]);second=self.build([b,a])
        self.assertEqual({o.text_content:o.object_id for o in first.objects},
                         {o.text_content:o.object_id for o in second.objects})
        self.assertEqual([a,b],original)
        self.assertNotEqual(first.objects[0].object_id,
                            self.build([a],source_sha256='sha256:'+'b'*64).objects[0].object_id)

    def test_rejects_invalid_or_authority_claiming_detections(self):
        base=dict(text='A', confidence=.8, polygon=[[1,1],[9,1],[9,8],[1,8]])
        cases=[dict(base,confidence=float('nan')),dict(base,confidence=True),dict(base,confidence=1.1),
               dict(base,text=''),dict(base,text='x'*4097),dict(base,host_object_id='AI:1'),
               dict(base,polygon=[[-1,1],[9,1],[9,8],[-1,8]]),
               dict(base,polygon=[[1,1],[9,1],[9,101],[1,101]]),
               dict(base,polygon=[[1,1],[1,1],[1,1],[1,1]]),
               dict(base,polygon=[[1,1],[9,8],[9,1],[1,8]])]
        for item in cases:
            with self.subTest(item=item),self.assertRaises(DecompositionError):self.build([item])
        for args in (dict(canvas=(0,100)),dict(canvas=(True,100)),dict(source_sha256='bad'),
                     dict(module=''),dict(detections=[base]*257),dict(detections=[base,base])):
            with self.subTest(args=args),self.assertRaises(DecompositionError):self.build(**args)

    def test_no_text_is_explicit_unknown_not_fabricated_background(self):
        plan=self.build([])
        self.assertEqual(len(plan.objects),1)
        self.assertEqual(plan.objects[0].kind,'unknown')
        self.assertEqual(plan.objects[0].mapping_state,'unrecovered')
        self.assertIsNone(plan.objects[0].text_content)

    def test_ids_ignore_polygon_start_winding_and_confidence(self):
        a=dict(text='A',confidence=.8,polygon=[[1,1],[9,1],[9,8],[1,8]])
        b=dict(a,confidence=.4,polygon=[[9,8],[9,1],[1,1],[1,8]])
        self.assertEqual(self.build([a]).objects[0].object_id,self.build([b]).objects[0].object_id)

    def test_rejects_aggregate_text_overflow(self):
        detections=[dict(text=str(i)+'x'*4095,confidence=.9,
                         polygon=[[1,1],[9,1],[9,8],[1,8]]) for i in range(5)]
        with self.assertRaises(DecompositionError):self.build(detections)

    def test_detected_text_does_not_claim_remaining_image_is_recovered(self):
        plan=self.build()
        self.assertEqual([o.kind for o in plan.objects],['text','unknown'])
        self.assertEqual(plan.objects[1].mapping_state,'unrecovered')


if __name__=='__main__':unittest.main()
