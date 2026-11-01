# SPDX-License-Identifier: MIT
"""Source checkout uses the same public RIR import as the installed wheel."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]


class RirSourceImportTests(unittest.TestCase):
    def test_public_rir_import_without_repository_sys_path(self):
        env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',
            'import sys; from design_lab.reconstruction.adobe_job import canonical_rir_hash; print(canonical_rir_hash({"schemaVersion":"design-lab/reconstruction-ir/v1","canvas":{"width":8,"height":6,"colorSpace":"srgb"},"layers":[]},project_root=sys.argv[1]))',str(ROOT)],
            cwd=ROOT/'apps',env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertRegex(result.stdout.strip(),r'^[0-9a-f]{64}$')


if __name__ == '__main__':
    unittest.main()
