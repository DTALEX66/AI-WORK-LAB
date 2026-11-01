# SPDX-License-Identifier: MIT
"""DL-FINAL-T05 — the capability library must work from an installed wheel.

What this card's acceptance actually claims: `/api/capabilities` and the declared core
journey are usable in a clean install, and the install test runs **outside** the repo CWD
with the source-tree fallback disabled. Before this module that claim was unmeasured: the
CI wheel job installed the wheel and launched the Workbench, but nothing ever called the
capability library from an installed layout, so a wheel that shipped without the four
resource files would still have passed every check that existed.

Three tests, each answering a different question:
  1. does the packaging declaration still list the four resources? (no toolchain needed,
     so it runs everywhere and catches a force-include edit immediately)
  2. does `build()` really read the packaged copies when the repository is out of reach?
     The probe runs in a subprocess whose CWD is a temp directory and whose `sys.path`
     points at an extracted wheel; the assertion is on the module path AND on
     `REPO_ROOT` not being the repository, because "it worked" is worthless if it worked
     by reading the checkout.
  3. does it fail closed when a packaged resource is missing? Without this, test 2 could
     pass through a silent fallback and we would not know which branch produced the data.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RES = 'design_lab/resources/capability-library'
SHIPPED = (
    f'{RES}/vendor/sources.lock.json',
    f'{RES}/vendor/sources.revisions.json',
    f'{RES}/design-lab/readiness/model-radar.json',
    f'{RES}/research/candidates/CANDIDATE-TAXONOMY.json',
)
PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from design_lab.analysis import capability_library as m
doc = m.build()
print(json.dumps({
    'module': m.__file__,
    'repo_root': str(m.REPO_ROOT),
    'capabilities': len(doc['capabilities']),
    'schema': doc['schemaVersion'],
    'sources': sorted(doc.get('sources', {}).keys()),
}))
"""


def _wheel() -> Path | None:
    """An installed-layout wheel: reuse dist/, else build one with uv when it exists."""
    # Build fresh when a builder exists: a wheel left in dist/ may predate the very
    # packaging change under test, and measuring stale bytes would be worse than not
    # measuring. Only fall back to dist/ when nothing can build here.
    out = Path(tempfile.mkdtemp(prefix='dl-t05-wheel-'))
    uv = shutil.which('uv')
    if not uv:
        existing = (sorted((REPO / 'dist').glob('design_lab-*.whl'))
                    if (REPO / 'dist').is_dir() else [])
        return existing[-1] if existing else None
    built = subprocess.run([uv, 'build', '--wheel', '--out-dir', str(out), str(REPO)],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
    wheels = sorted(out.glob('design_lab-*.whl'))
    return wheels[-1] if built.returncode == 0 and wheels else None


class PackagingDeclarationTests(unittest.TestCase):
    """The cheapest thing that can break, checked without a toolchain."""

    def setUp(self):
        self.pyproject = (REPO / 'pyproject.toml').read_text(encoding='utf-8')

    def test_force_include_names_every_capability_resource(self):
        missing = [name for name in SHIPPED
                   if name.split('/')[-1] not in self.pyproject
                   or name not in self.pyproject.replace('\\', '/')]
        self.assertEqual(missing, [],
                         'these packaged capability resources are no longer declared in '
                         f'pyproject force-include, so a wheel ships without them: {missing}')

    def test_the_declaration_does_not_drag_the_candidate_pool_or_user_assets(self):
        # The card forbids packaging the whole candidate pool, models, or user material.
        # CANDIDATE-TAXONOMY.json is the observation record the join needs; the pool
        # itself lives in research/candidates/*.md and must stay out of the wheel.
        block = self.pyproject.split('[tool.hatch.build.targets.wheel.force-include]', 1)[-1]
        block = block.split('\n[', 1)[0]
        offenders = [line for line in block.splitlines()
                     if 'research/candidates/' in line and '.json' not in line]
        self.assertEqual(offenders, [],
                         'the wheel would carry candidate-pool documents: ' + str(offenders))


class InstalledLayoutTests(unittest.TestCase):
    #: Windows refuses a plain path longer than 259 characters, and the runner's own temp root is
    #: already 133 characters long, so eight domain-pack benchmark pages physically cannot be
    #: created under it (measured: 8 of 377 members, all under this prefix, none of them a file the
    #: probe opens). They are skipped -- and the skip set is asserted, because an unbounded
    #: `except OSError` would let the extraction quietly drop a resource the probe does read, and
    #: the test would then report a packaged layout that no real install ever ships.
    BENCHMARK_PREFIX = 'design_lab/resources/repo/design-lab/domain-packs/'

    def _extract(self, wheel: Path) -> Path:
        target = Path(tempfile.mkdtemp(prefix='dl-t05-site-'))
        self.skipped = {}
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                try:
                    archive.extract(member, target)
                except OSError as exc:
                    # The name decides whether this is acceptable, not the errno: the same too-long
                    # path surfaces as WinError 206 from makedirs in one place and as a plain
                    # `[Errno 2]` from the open in another, so filtering on the code would silently
                    # re-break the next time Windows changes its mind.
                    self.skipped[member.filename] = str(exc)[-120:]
        self._assert_skips_are_harmless()
        return target

    def _assert_skips_are_harmless(self) -> None:
        offenders = sorted(name for name in self.skipped
                           if not name.startswith(self.BENCHMARK_PREFIX))
        self.assertEqual(offenders, [],
                         'these wheel members could not be created and are not benchmark pages, so '
                         f'the layout under test is not the layout an install carries: {offenders} '
                         f'{[self.skipped[name] for name in offenders[:2]]}')
        self.assertEqual([name for name in SHIPPED if name in self.skipped], [],
                          'a capability-library resource the probe reads was skipped; the '
                          'refusal test below would pass on a broken extraction instead of on a '
                          'missing resource')

    def test_an_unextractable_member_the_probe_needs_is_a_finding(self):
        """The skip allowance is safe only because a needed member cannot hide inside it.

        Without this pair of assertions the guard could be satisfied by an empty prefix test, and a
        future platform limit that bites a capability-library resource would look like a passing
        installed-layout run.
        """
        self.skipped = {SHIPPED[0]: '[WinError 206] 文件名或扩展名太长'}
        with self.assertRaises(self.failureException):
            self._assert_skips_are_harmless()
        self.skipped = {self.BENCHMARK_PREFIX
                        + 'uiux-design/benchmarks/x-golden/implementations/baseline.html':
                            '[Errno 2] No such file or directory'}
        self._assert_skips_are_harmless()
        self.skipped = {}
        self._assert_skips_are_harmless()

    def _run_probe(self, site: Path) -> dict:
        cwd = Path(tempfile.mkdtemp(prefix='dl-t05-cwd-'))
        script = cwd / 'probe.py'
        script.write_text(PROBE, encoding='utf-8')
        env = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
        result = subprocess.run([sys.executable, str(script), str(site)], cwd=str(cwd),
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', env=env)
        self.assertEqual(result.returncode, 0,
                         f'the installed library failed to run: {result.stderr[-800:]}')
        return json.loads(result.stdout.strip().splitlines()[-1])

    def _installed_site(self) -> Path | None:
        """Where the running interpreter would import design_lab from, if that is an
        install rather than the checkout. CI's `uv sync --locked` installs the project,
        so this is the real installed layout and needs no build step here; a source-tree
        checkout falls back to building a wheel."""
        probe = subprocess.run(
            [sys.executable, '-c',
             'import importlib.util,json; s=importlib.util.find_spec("design_lab");'
             'print(json.dumps(s.origin if s else None))'],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            env={k: v for k, v in os.environ.items() if k != 'PYTHONPATH'})
        try:
            origin = json.loads(probe.stdout.strip() or 'null')
        except json.JSONDecodeError:
            return None
        if not isinstance(origin, str):
            return None
        module = Path(origin)
        if REPO in module.parents:
            return None                      # source checkout: build a wheel instead
        return module.parent.parent          # .../site-packages/design_lab/__init__.py

    def test_build_reads_packaged_resources_with_the_repo_out_of_reach(self):
        site = self._installed_site()
        if site is None:
            wheel = _wheel()
            if wheel is None:
                self.skipTest('neither an installed design_lab nor a wheel builder is '
                              'available: the installed layout is NOT measured by this run')
            site = self._extract(wheel)
        report = self._run_probe(site)
        self.assertIn(str(site), report['module'].replace('/', os.sep),
                      'the probe imported design_lab from somewhere other than the '
                      f"extracted wheel: {report['module']}")
        self.assertNotEqual(Path(report['repo_root']).resolve(), REPO.resolve(),
                            'REPO_ROOT still points at the checkout, so a source-tree read '
                            'would have passed this test by accident')
        self.assertGreater(report['capabilities'], 0,
                           'the installed library projected zero capability records')
        self.assertEqual(report['schema'], 'design-lab/capability-library/v1')
        self.assertEqual(len(report['sources']), 3,
                         'the projection stopped reporting its three input sources')

    def test_missing_packaged_resource_fails_closed(self):
        """Falsification for the test above: with a resource gone, the library must refuse."""
        site = self._installed_site()
        built_wheel = False
        if site is None:
            wheel = _wheel()
            if wheel is None:
                self.skipTest('neither an installed design_lab nor a wheel builder is '
                              'available')
            site = self._extract(wheel)
            built_wheel = True
        target = site / SHIPPED[0]
        if not built_wheel:
            # Never delete out of a shared install: move it aside and put it back.
            backup = target.with_suffix('.json.t05-backup')
            shutil.move(str(target), str(backup))
        else:
            # A throwaway extraction: removing the file is the whole point, and the
            # first version of this branch silently skipped it, which made the probe
            # succeed for the wrong reason.
            target.unlink()
            backup = None
        try:
            self._assert_refuses(site)
        finally:
            if backup is not None:
                shutil.move(str(backup), str(target))

    def _assert_refuses(self, site: Path) -> None:
        cwd = Path(tempfile.mkdtemp(prefix='dl-t05-cwd-'))
        script = cwd / 'probe.py'
        script.write_text(PROBE, encoding='utf-8')
        env = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
        result = subprocess.run([sys.executable, str(script), str(site)], cwd=str(cwd),
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', env=env)
        self.assertNotEqual(result.returncode, 0,
                            'a wheel missing its source lock still produced a projection: '
                            + result.stdout[-400:])
        self.assertIn('capability library input missing', result.stderr,
                      'the failure was not the stated fail-closed path: '
                      + result.stderr[-400:])


if __name__ == '__main__':
    unittest.main(verbosity=2)
