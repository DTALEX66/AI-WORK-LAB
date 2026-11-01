#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prove the published source distribution can rebuild the wheel it is supposed to contain.

Owner audit at 7671ec70 found `uv build --sdist` produced a tarball from which `uv build --wheel`
dies at `FileNotFoundError: Forced include not found: …/design-lab/domain-packs`. The wheel
force-includes 71 repository paths and the sdist's `only-include` carried 17 of them, so the
artefact this project publishes could not be rebuilt by anyone who downloaded it -- while CI stayed
green, because it built the wheel straight from the checkout and never from the sdist.

Two modes:
  static (default)  re-derives the coverage relation from pyproject itself. Cheap enough to run in
                    the aggregate on every commit; it is the rule "a force-include source needs an
                    sdist root", not a hand-copied list.
  --build           actually runs the round trip (sdist -> extract -> wheel) in a temporary tree,
                    which is the acceptance the audit wrote: verify from the source distribution,
                    not from the repository.
"""
from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_map(pyproject_text: str) -> tuple:
    """(force-include sources, sdist only-include entries, sdist excludes) read from the TOML."""
    data = tomllib.loads(pyproject_text)
    targets = data.get('tool', {}).get('hatch', {}).get('build', {}).get('targets', {})
    forced = sorted((targets.get('wheel', {}) or {}).get('force-include', {}) or {})
    sdist = targets.get('sdist', {}) or {}
    return forced, list(sdist.get('only-include', []) or []), list(sdist.get('exclude', []) or [])


def covered(source: str, only_include: list) -> bool:
    """True when `source` would land in the sdist: an exact entry, or under one that is a directory."""
    return any(source == entry or source.startswith(entry.rstrip('/') + '/')
               for entry in only_include)


def excluded(source: str, excludes: list) -> bool:
    """Hatch matches excludes as glob patterns against the in-archive path.

    `fnmatch.fnmatch` already normalises separators; there is no `fnmatch.match`, and calling one
    here is exactly the kind of attribute that only shows up when the gate is actually run.
    """
    return any(fnmatch.fnmatch(source, pattern) for pattern in excludes)


def findings(forced: list, only_include: list, excludes: list, repo: Path = REPO) -> list:
    problems = []
    for source in forced:
        if not (repo / source).exists():
            problems.append(f'force-include source is not in the repository: {source}')
            continue
        if not covered(source, only_include):
            problems.append(f'wheel needs it but the sdist will not carry it: {source}')
        elif excluded(source, excludes):
            problems.append(f'the sdist lists it and then excludes it away: {source}')
    for entry in only_include:
        if not (repo / entry).exists():
            problems.append(f'sdist only-include names a path that does not exist: {entry}')
    return problems


def build_round_trip(repo: Path) -> list:
    """sdist -> extract -> wheel, in a throwaway tree. Returns problem strings (empty means it built)."""
    problems = []
    if shutil.which('uv') is None:
        # Refuse loudly. A build mode that quietly returns "no problems" is how a machine without
        # the builder reports a green round trip it never performed.
        return ['uv is not on PATH, so the --build round trip cannot be performed here; this is a '
                'refusal, not a pass']
    with tempfile.TemporaryDirectory(prefix='sdist-roundtrip-') as tmp:
        work = Path(tmp)
        sdist_dir = work / 'sd'
        sdist_dir.mkdir()
        built = subprocess.run(['uv', 'build', '--sdist', '--out-dir', str(sdist_dir)],
                               cwd=str(repo), capture_output=True, text=True)
        if built.returncode != 0:
            return [f'sdist build failed: {(built.stderr or built.stdout)[-400:]}']
        archives = sorted(sdist_dir.glob('*.tar.gz'))
        if not archives:
            return ['no sdist archive was produced']
        extract = work / 'x'
        extract.mkdir()
        with tarfile.open(archives[0]) as handle:
            handle.extractall(extract)
        roots = [p for p in extract.iterdir() if p.is_dir()]
        if len(roots) != 1:
            return [f'the sdist did not unpack to a single top-level directory: {roots}']
        tree = roots[0]
        missing = [s for s in load_map((tree / 'pyproject.toml').read_text(encoding='utf-8'))[0]
                   if not (tree / s).exists()]
        if missing:
            problems.append(f'{len(missing)} force-include source(s) absent from the unpacked '
                            f'sdist, first five: {missing[:5]}')
        wheel_dir = work / 'whl'
        wheel = subprocess.run(['uv', 'build', '--wheel', '--out-dir', str(wheel_dir)],
                               cwd=str(tree), capture_output=True, text=True)
        if wheel.returncode != 0 or not list(wheel_dir.glob('*.whl')):
            problems.append('the wheel cannot be rebuilt from the source distribution: '
                            + (wheel.stderr or wheel.stdout)[-400:])
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true',
                    help='also run the real sdist -> wheel round trip (slower, this is the '
                         'acceptance the audit asked for)')
    ap.add_argument('--repo', type=Path, default=REPO)
    args = ap.parse_args(argv)

    text = (args.repo / 'pyproject.toml').read_text(encoding='utf-8')
    forced, only_include, excludes = load_map(text)
    if not forced:
        print('SDIST_PACKAGING=FAIL the wheel declares no force-include sources; either this '
              'verifier stopped parsing the right table or the packaging moved without it')
        return 1
    if not only_include:
        print('SDIST_PACKAGING=FAIL the sdist has no only-include list, so this check would pass '
              'on whatever hatch happens to include')
        return 1
    problems = findings(forced, only_include, excludes, args.repo)
    if not problems and args.build:
        problems = build_round_trip(args.repo)
    if problems:
        for item in problems:
            print(f'  SDIST_PROBLEM {item}')
        print(f'SDIST_PACKAGING=FAIL wheel_sources={len(forced)} '
              f'sdist_roots={len(only_include)} problems={len(problems)} '
              f'mode={"build" if args.build else "static"}')
        return 1
    print(f'SDIST_PACKAGING=OK wheel_sources={len(forced)} covered={len(forced)} missing=0 '
          f'sdist_roots={len(only_include)} mode={"build" if args.build else "static"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
