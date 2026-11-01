# SPDX-License-Identifier: MIT
"""Execute the actual JSX validator with a Windows fsName boundary double.

This is a JavaScript regression, not evidence of Illustrator execution.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class IllustratorBridgePathTests(unittest.TestCase):
    def test_windows_child_and_escape_decisions(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node is required for the actual JSX JavaScript regression')
        code = r'''
const fs = require('fs');
const vm = require('vm');
const path = require('path').win32;
const context = {
  File: p => ({fsName: path.resolve(p)}),
  Folder: p => ({fsName: path.resolve(p)})
};
vm.createContext(context);
const source = fs.readFileSync(process.argv[1], 'utf8').replace(/^#target.*$/m, '');
vm.runInContext(source, context);
const cases = [
 ['valid-backslash', 'D:\\run\\output.ai', 'D:\\run', true],
 ['valid-forwardslash', 'D:/run/output.ai', 'D:/run', true],
 ['valid-root-trailing-slash', 'D:/run/sub/output.ai', 'D:/run/', true],
 ['valid-case-insensitive', 'd:/RUN/output.ai', 'D:/run', true],
 ['sibling-prefix', 'D:/run-other/output.ai', 'D:/run', false],
 ['parent-traversal', 'D:/run/../output.ai', 'D:/run', false],
 ['root-is-not-child', 'D:/run', 'D:/run', false],
 ['other-drive', 'C:/run/output.ai', 'D:/run', false],
 ['unc-child', '//server/share/run/output.ai', '//server/share/run', true],
 ['unc-sibling', '//server/share/run-other/output.ai', '//server/share/run', false]
];
console.log(JSON.stringify(cases.map(([name, child, root, expected]) => {
 let actual = true;
 try { context.assertInside(child, root); } catch (error) { actual = false; }
 return {name, expected, actual};
})));
'''
        result = subprocess.run(
            [node, '-e', code, str(ROOT / 'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx')],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        cases = json.loads(result.stdout)
        self.assertEqual(len(cases), 10)
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertEqual(case['actual'], case['expected'])


if __name__ == '__main__':
    unittest.main()
