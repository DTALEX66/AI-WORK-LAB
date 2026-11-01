# SPDX-License-Identifier: MIT
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'packages/capabilities')]
from reconstruction.adobe_lowering import path_points,lower_layers,validate_objects
from reconstruction.adobe_job import AdobeJobError


class CompoundPathsTests(unittest.TestCase):
    def test_relative_curve_keeps_control_points_and_close_handle(self):
        points,closed=path_points('m 10 20 c 2 -3 8 -3 10 0 l 0 10 -10 0 z',100)
        self.assertTrue(closed)
        self.assertEqual(points[0],dict(anchor=[10,80],left=[10,80],right=[12,83]))
        self.assertEqual(points[1],dict(anchor=[20,80],left=[18,83],right=[20,80]))
        self.assertEqual(points[3]['anchor'],[10,70])

    def scene(self):
        return dict(canvas=dict(width=100,height=100),layers=[dict(id='ring',type='path',
            name='ring',bounds=dict(x=10,y=10,width=40,height=40),opacity=1,visible=True,
            locked=False,blendMode='normal',zOrder=0,style=dict(fill='#112233'),
            geometry=dict(pathData='M10 10 l40 0 0 40 -40 0z m10 10 l0 20 20 0 0 -20z',closed=True))])

    def test_compound_preserves_two_oppositely_wound_contours(self):
        layers,assets=lower_layers(self.scene(),ROOT,{})
        item=layers[0]['items'][0]
        self.assertEqual(item['kind'],'compound')
        self.assertEqual(len(item['contours']),2)
        self.assertEqual([p['anchor'] for p in item['contours'][1]['points']],
                         [[20,80],[20,60],[40,60],[40,80]])
        validate_objects(dict(layers=layers,assets=assets),ROOT)
        for mutate in (lambda x:x['contours'][0].update(closed=False),
                       lambda x:x['contours'][0].update(color=[255,0,0]),
                       lambda x:x.update(contours=[])):
            bad=copy.deepcopy(item);mutate(bad)
            with self.assertRaises(AdobeJobError):validate_objects(dict(layers=[dict(id='l',items=[bad])],assets=[]),ROOT)

    def test_invalid_segments_and_single_path_compound_fail_closed(self):
        for data in ('M1 1 C2 3','M1 1 A2 2 0 0 0 5 5','M1 1 L2 2 Z 3 3',
                     'M1 1 L2 2 z M5 5 L6 6z','M1 1 L2 2 C','M1 1 L1e999 2',
                     'M1 1 L2 2 Z Z'):
            with self.subTest(data=data),self.assertRaises(AdobeJobError):path_points(data,100)

    def test_open_or_degenerate_compound_not_silently_filled(self):
        for data in ('M1 1 L9 1 L9 9 M3 3 L5 3 L5 5 Z',
                     'M1 1 L9 9Z M3 3 L5 5Z'):
            rir=self.scene();rir['layers'][0]['geometry']['pathData']=data
            with self.assertRaises(AdobeJobError):lower_layers(rir,ROOT,{})


if __name__=='__main__':unittest.main()
