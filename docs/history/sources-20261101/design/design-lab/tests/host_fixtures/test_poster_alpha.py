# SPDX-License-Identifier: MIT
import unittest
import numpy as np
from PIL import Image
from prepare_real_poster_ps import white_to_alpha


class AlphaTests(unittest.TestCase):
    def test_white_transparent_black_opaque_and_color_preserved(self):
        source=Image.new('RGB',(4,1))
        source.putdata([(255,255,255),(0,0,0),(13,15,16),(128,180,250)])
        output=white_to_alpha(source)
        self.assertEqual(output.getpixel((0,0))[3],0)
        self.assertEqual(output.getpixel((1,0)),(0,0,0,255))
        composite=Image.alpha_composite(Image.new('RGBA',source.size,'white'),output).convert('RGB')
        self.assertLessEqual(np.abs(np.asarray(composite).astype(int)-np.asarray(source)).max(),1)
        self.assertNotEqual(output.getpixel((2,0))[0],output.getpixel((2,0))[2])


if __name__=='__main__':unittest.main()
