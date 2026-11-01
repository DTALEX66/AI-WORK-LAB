# SPDX-License-Identifier: MIT
"""A read path that resolves a repository file at runtime must also be packaged.

CI's clean-wheel job found this class of defect the hard way on 2026-10-22: the project roll-up read
its own contract through ``PROJECT_ROOT``, which is ``Path(__file__).parents[3]`` -- the checkout in
a source tree, but the interpreter's ``Lib`` once installed. The route answered 500 and nothing but
an installed run could see it. ``repo_resource`` fixes the read; this module is what stops the next
call site from silently shipping a wheel that cannot serve it.

Two independent questions, because a declaration can rot in either direction:
  * does every ``repo_resource('…')`` literal in ``src/design_lab`` appear in pyproject's
    ``force-include`` block, mapped to the packaged path that helper actually looks under?
  * does the repository still carry the bytes that declaration points at?

The literals are enumerated from disk, not from a hand-kept list here: a gate that only proves its
own inventory would pass while an undeclared new call site shipped broken.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src' / 'design_lab'
SOURCE_ROOT = 'design-lab'
PACKAGED_PREFIX = 'design_lab/resources/repo/'
CALL = re.compile(r"""repo_resource\(\s*['"]([^'"]+)['"]\s*\)""")


def call_sites(tree=SRC) -> set[str]:
    return {match.group(1)
            for path in sorted(tree.rglob('*.py'))
            for match in CALL.finditer(path.read_text(encoding='utf-8'))}


def is_declared(relative: str, pyproject: str) -> bool:
    """Whether a force-include line ships this read -- by its own key or by a directory key.

    `design-lab/schemas/state` and `design-lab/readiness` are declared as directories, so a child
    of one needs no line of its own. Matching is on whole quoted keys, never on a bare substring,
    or `readiness` would appear to declare `readiness-archive.json`.
    """
    parts = Path(relative).parts
    for depth in range(len(parts), 0, -1):
        source = f'{SOURCE_ROOT}/' + '/'.join(parts[:depth])
        target = f'{PACKAGED_PREFIX}{source}'
        if any(f'"{source}"' in line and f'"{target}"' in line
               for line in pyproject.splitlines()):
            return True
    return False


class PackagedContractResourceTests(unittest.TestCase):
    def setUp(self):
        self.pyproject = (REPO / 'pyproject.toml').read_text(encoding='utf-8')
        self.sites = call_sites()

    def test_the_scanner_finds_the_reads_it_claims_to_cover(self):
        # Without this, an inert regex would report "nothing to check" and every other test here
        # would pass over an empty population.
        self.assertTrue(self.sites, 'no repo_resource call site was found in src/design_lab')
        for expected in ('schemas/project-list-v1.schema.json', 'schemas/task-readback-v1.schema.json',
                         'config/state-vocabularies.json', 'schemas/bom.schema.json',
                         'schemas/evidence-projection.schema.json', 'production/profiles',
                         'config/provider-capabilities.json', 'readiness/model-radar.json',
                         'schemas/prompt-result-v1.schema.json'):
            self.assertIn(expected, self.sites)

    def test_every_repo_resource_read_is_declared_in_the_wheel(self):
        undeclared = sorted(site for site in self.sites if not is_declared(site, self.pyproject))
        self.assertEqual(undeclared, [],
                         'these runtime reads resolve a repository file that no force-include line '
                         f'ships, so an installed wheel refuses instead of answering: {undeclared}')

    def test_the_declared_bytes_still_exist_in_the_checkout(self):
        absent = sorted(f'{SOURCE_ROOT}/{site}' for site in self.sites
                        if not (REPO / SOURCE_ROOT / site).exists())
        self.assertEqual(absent, [],
                         f'these packaged resources are declared but not in the repository: {absent}')

    def test_a_dropped_declaration_is_convicted(self):
        relative = 'schemas/project-list-v1.schema.json'
        self.assertTrue(is_declared(relative, self.pyproject))
        mutated = '\n'.join(line for line in self.pyproject.splitlines()
                            if f'"{SOURCE_ROOT}/{relative}"' not in line)
        self.assertNotEqual(mutated, self.pyproject, 'the sample line was never found')
        self.assertFalse(is_declared(relative, mutated),
                         'removing a force-include line changed nothing, so the check guards '
                         'nothing')


class RouteReachableRootReadTests(unittest.TestCase):
    """No new checkout-only root read may enter the service's import closure.

    Runs design-lab/scripts/audit_repo_root_reads.py, which walks the import closure of
    `http_service.py` and reports every expression that builds a repository path from the root.
    Its positive control is asserted here too: a detector that silently saw nothing would report
    the same clean line as a tree that has no such reads, and that is exactly how the wheel defect
    survived three batches.
    """

    SCRIPT = REPO / 'design-lab' / 'scripts' / 'audit_repo_root_reads.py'
    # The Adobe bridges resolve packaged-first under a deliberately different prefix
    # (design_lab/resources/adobe/), and they are opened only on a real host dispatch, which is
    # frozen. They are not shipped under `resources/repo/`, which is the only prefix
    # `repo_resource()` looks in, so the audit reports them as undeclared by design.
    # Both rows are listed because the parked-variable form is followed now: the Illustrator bridge
    # was in the same category all along and the old detector never walked into it (measured
    # 2026-10-28: the live report went paths=1 -> paths=2 when the walk got stronger, and the new
    # row is `adapters/illustrator_com.py`, whose bytes ARE force-included at
    # design_lab/resources/adobe/reconstruction-assemble.jsx). Anything else joining this set is a
    # finding, and the two behavioural gates below are what an installed wheel is actually judged by.
    KNOWN = {'integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx',
             'integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx'}

    def run_audit(self, *args):
        result = subprocess.run([sys.executable, str(self.SCRIPT), *args], cwd=str(REPO),
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_the_detector_still_sees_the_disease(self):
        self.assertIn('CONTROL=OK', self.run_audit('--control'))

    def test_no_undeclared_root_read_reachable_from_the_service(self):
        report = self.run_audit()
        lines = [line for line in report.splitlines() if line.startswith('REPO_ROOT_READS=REPORT')]
        self.assertEqual(len(lines), 1, report)
        listed = lines[0].split('NOT_SHIPPED=[', 1)[1].split(']', 1)[0]
        found = {name for name in listed.split(',') if name}
        self.assertEqual(sorted(found - self.KNOWN), [],
                         'a route-reachable read opens repository bytes through the checkout root, '
                         'which is the interpreter directory inside a wheel: '
                         + str(sorted(found - self.KNOWN)))
        self.assertNotIn('paths=0', lines[0],
                         'a zero-population report is not evidence that the tree is clean')


if __name__ == '__main__':
    unittest.main()
