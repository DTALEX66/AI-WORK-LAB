#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The cross-wave pointer register: which archived material two or more waves both claim, and where
its bytes actually are.

Why this exists instead of a merge that moves files: `docs/history/**` is frozen byte-for-byte by
`design-lab/config/task-document-states.json` (prefixRule, basis HISTORY-FREEZE-RULES), and eight
archive/source manifests each declare their own member list. Several of those waves re-register
material an earlier wave already archived, so a reader who lands on the older row cannot tell
whether the bytes exist twice or whether they are looking at an alias of one canonical copy.
Measured 2026-10-28 over the whole tracked `docs/` population: 566 member rows, 510 distinct
digests, 49 of them claimed by more than one wave. Deleting anything to "merge" the waves would
rewrite frozen originals for a fraction of a MiB; that is an owner ruling, not an engineering gap.
So this script writes the pointer layer only.

The census spans all of `docs/`, not the frozen family alone, and that is a correction rather than
a widening for its own sake: the first cut listed six manifests by hand, all under `docs/history`,
and the two it missed sit in `docs/taskpacks`. Together they hid 175 member rows, 170 digests and
one real cross-wave claim (the 2026-10-23 requirement HTML, 59,898 bytes, claimed both by
`docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json` and by
`docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json`). `discover_manifests` now enumerates the
tracked population and refuses in both directions, so the scope cannot silently come back down to
a directory someone happened to think of.

Every digest here is read from `git cat-file blob HEAD:<path>`, never from the worktree, because
`core.autocrlf=true` on this machine means a checked-out file is not the committed bytes -- a
register that hashed local files would state values no fresh clone reproduces (the same reason
scripts/generate_archive_record_register.py hashes blobs).

    python design-lab/scripts/verify_record_archive_crosswave.py --check
    python design-lab/scripts/verify_record_archive_crosswave.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / 'design-lab' / 'config' / 'record-archive-crosswave.json'
SCHEMA = 'design-lab/record-archive-crosswave/v1'

#: Every archive/source manifest that enumerates archived material, whatever directory it lives in.
#: Two of these waves sit in `docs/taskpacks/`, not in the frozen `docs/history/` family, and the
#: first cut of this register read only the six under `docs/history` -- a census that stops at one
#: directory reports "no overlap" about waves it never opened. `discover_manifests` below now
#: enumerates the tracked population and refuses if this tuple and that set ever disagree, so a
#: ninth wave cannot be forgotten the way these two were.
MANIFESTS = (
    'docs/history/record-archive-2026-10-09/ARCHIVE-MANIFEST.json',
    'docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json',
    'docs/history/record-archive-2026-10-27-stitch-boards/ARCHIVE-MANIFEST.json',
    'docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json',
    'docs/history/taskpacks/20261009-inputs/ARCHIVE-MANIFEST.json',
    'docs/history/taskpacks/20261009-r2-inputs/ui-r2/ARCHIVE-MANIFEST.json',
    'docs/taskpacks/20261019-direction/SOURCE-MANIFEST.json',
    'docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json',
)
#: Canonical copies are searched across all of `docs/`, because the two `docs/taskpacks` waves point
#: at tracked files inside their own taskpack directory, not under `docs/history`.
SCOPE_ROOT = 'docs'
MANIFEST_BASENAMES = ('ARCHIVE-MANIFEST.json', 'SOURCE-MANIFEST.json')


def committed_blobs():
    """{path: sha256 of the committed blob} for every tracked file under the scope root.

    `git ls-tree HEAD` is the committed view, and `git cat-file --batch` fed with the object ids is
    one round trip for the whole tree. The worktree is never read: with `core.autocrlf=true` a
    checked-out file is not the bytes a fresh clone reproduces.
    """
    # `-z` keeps the Chinese member paths of these packs as real bytes: the default output quotes
    # non-ASCII paths, and a line-splitting reader then invents or loses files (this project has
    # already been bitten by that in `git ls-files`).
    listing = subprocess.run(
        ['git', 'ls-tree', '-r', '-z', 'HEAD', '--', SCOPE_ROOT],
        cwd=str(REPO), capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    path_to_oid = OrderedDict()
    for record in listing.split('\0'):
        if not record.strip():
            continue
        meta, _, path = record.partition('\t')
        parts = meta.split()
        if len(parts) != 3 or parts[1] != 'blob':
            continue
        path_to_oid[path] = parts[2]
    oids = sorted(set(path_to_oid.values()))
    if not oids:
        return {}
    proc = subprocess.run(['git', 'cat-file', '--batch'],
                          input=('\n'.join(oids) + '\n').encode('ascii'),
                          cwd=str(REPO), capture_output=True, check=True)
    data = proc.stdout
    content = {}
    i = 0
    while i < len(data):
        newline = data.find(b'\n', i)
        if newline < 0:
            break
        header = data[i:newline].decode('ascii', 'replace').split()
        i = newline + 1
        if len(header) == 3 and header[1] == 'blob':
            size = int(header[2])
            content[header[0]] = hashlib.sha256(data[i:i + size]).hexdigest()
            i += size
        if i < len(data) and data[i:i + 1] == b'\n':
            i += 1
    return {path: content[oid] for path, oid in path_to_oid.items() if oid in content}


def members_of(document):
    """Every declared member of one manifest, as (package_or_None, row).

    The record-archive waves carry a top-level `source_files`; the taskpack waves nest members
    under `packages`; the two `docs/taskpacks` SOURCE-MANIFEST waves put `members` at the top
    level. Reading only one shape would silently drop a whole wave from the census, and a census
    that drops a wave reports "no overlap" as a true fact about a population it never read.
    """
    found = []
    direct = document.get('source_files')
    if isinstance(direct, list):
        found.extend((None, row) for row in direct if isinstance(row, dict))
    top = document.get('members')
    if isinstance(top, list):
        found.extend((None, row) for row in top if isinstance(row, dict))
    packages = document.get('packages')
    if isinstance(packages, list):
        for package in packages:
            if not isinstance(package, dict):
                continue
            for key in ('members', 'files'):
                rows = package.get(key)
                if isinstance(rows, list):
                    found.extend((package, row) for row in rows if isinstance(row, dict))
    return found


#: Per-wave key spellings, read from the manifests themselves rather than guessed. The record-archive
#: waves describe where a member landed (`landed_as`); the taskpack waves carry both the ZIP-internal
#: name (`member`) and the tracked in-repo copy of the same bytes (`repository_text`); the
#: `docs/taskpacks` SOURCE-MANIFEST waves use `landingPath` / `path` for the tracked copy and
#: `member` / `archiveName` for the ZIP-internal name. A register that dropped those would say
#: "two waves claim this" without saying what either of them pointed at.
PATH_KEYS = ('repository_text', 'landed_as', 'landingPath', 'path', 'source_relative', 'member',
             'name')
#: The pack-internal spelling, kept separate from `pointsAt` because the two are different claims:
#: one is "where the bytes are in the clone", the other is "what the delivery called them".
PACKAGE_NAME_KEYS = ('member', 'name', 'archiveName')


def claim_of(manifest, package, row):
    """The (digest, claim) pair of one member row, or None when the row declares no digest."""
    digest = None
    for key in ('sha256', 'digest', 'content_sha256'):
        value = row.get(key)
        if isinstance(value, str) and len(value) >= 32:
            digest = value.lower().removeprefix('sha256:')
            break
    if digest is None:
        return None
    claim = {'manifest': manifest}
    for key in PATH_KEYS:
        if isinstance(row.get(key), str):
            claim['pointsAt'] = row[key]
            break
    for key in PACKAGE_NAME_KEYS:
        if isinstance(row.get(key), str):
            claim.setdefault('insidePackage', row[key])
    for key, label in (('source_relative', 'sourceRelative'), ('bytes', 'bytes'),
                       ('local_copy', 'outsideCloneCopy')):
        if isinstance(row.get(key), (str, int)):
            claim[label] = row[key]
    if isinstance(package, dict) and isinstance(package.get('source'), str):
        # Which delivery the member came from is the cross-wave fact worth keeping; the absolute
        # path on the owner's volume is already in the manifest, and copying it into a derived
        # register would only add a second place for it to be wrong.
        claim['package'] = package['source'].replace('\\', '/').rsplit('/', 1)[-1]
    return digest, claim


def discover_manifests():
    """Every tracked archive/source manifest in the repository, enumerated from git.

    This is the guard the first cut only claimed to have. The census is a claim about *all* the
    waves, so its population cannot come from a hand-maintained tuple: the six that were read lived
    under `docs/history`, and the two that were missed lived under `docs/taskpacks` -- a scope named
    after a directory, instead of the thing itself.
    """
    listing = subprocess.run(
        ['git', 'ls-files', '-z', '--', 'docs'],
        cwd=str(REPO), capture_output=True, check=True).stdout.decode('utf-8', 'replace')
    return sorted(path for path in listing.split('\0')
                  if path and path.rsplit('/', 1)[-1] in MANIFEST_BASENAMES)


def manifest_enumeration_problems():
    declared = sorted(MANIFESTS)
    on_disk = discover_manifests()
    problems = []
    missing = sorted(set(on_disk) - set(declared))
    stale = sorted(set(declared) - set(on_disk))
    if missing:
        problems.append('MANIFEST_NOT_CENSUSED %s' % missing)
    if stale:
        problems.append('MANIFEST_DECLARED_BUT_ABSENT %s' % stale)
    return problems


def build():
    claims = OrderedDict()
    waves = []
    for manifest in MANIFESTS:
        path = REPO / manifest
        if not path.is_file():
            raise SystemExit('MANIFEST_MISSING %s' % manifest)
        document = json.loads(path.read_text(encoding='utf-8'))
        rows = []
        for package, row in members_of(document):
            claim_pair = claim_of(manifest, package, row)
            if claim_pair is None:
                continue
            digest, claim = claim_pair
            claims.setdefault(digest, []).append(claim)
            rows.append(digest)
        waves.append({'manifest': manifest, 'declaredMembers': len(rows),
                      'date': (document.get('date') or document.get('recordedAt')
                               or document.get('adoptedAt')),
                      'supersedes': document.get('supersedes')})
    digests = committed_blobs()
    tracked = sorted(digests)
    by_digest = {}
    for p, digest in digests.items():
        by_digest.setdefault(digest, []).append(p)
    shared = OrderedDict()
    unbacked = OrderedDict()
    for digest, claimants in claims.items():
        if len({c['manifest'] for c in claimants}) < 2:
            continue
        copies = sorted(by_digest.get(digest, []))
        entry = {
            'sha256': digest,
            'canonicalPaths': copies,
            'bytes': next((c.get('bytes') for c in claimants if c.get('bytes')), None),
            'claimedBy': claimants,
        }
        # Two waves claiming a member whose bytes are in no clone is a real state, not a defect:
        # AGENTS.md records that the large objects of these packs live in `.project-local/` and do
        # not travel with Git. Refusing on it would make the register un-writable, and dropping it
        # would hide exactly the material a machine migration has to fetch by digest.
        (shared if copies else unbacked)[digest] = entry
    return {
        'schemaVersion': SCHEMA,
        'purpose': 'Pointer layer only: which archived material several waves claim, and where its '
                   'committed bytes actually sit. No frozen original is moved, renamed or rewritten '
                   'by anything in this file.',
        'freezeRule': 'docs/history/** is byte-for-byte frozen by '
                      'design-lab/config/task-document-states.json (prefixRule, HISTORY-FREEZE-RULES), '
                      'so a cross-wave relation may only be written here.',
        'censusScope': 'Every tracked ARCHIVE-MANIFEST/SOURCE-MANIFEST under docs/, found by '
                       'git ls-files and checked against the declared tuple on every run; canonical '
                       'copies are searched across all of docs/ because two waves land inside their '
                       'own docs/taskpacks directory.',
        'digestSource': 'git cat-file blob HEAD:<path> (never the worktree: core.autocrlf makes a '
                        'checked-out file differ from the committed bytes)',
        'waves': waves,
        'counts': {
            'manifests': len(waves),
            'declaredMemberRows': sum(w['declaredMembers'] for w in waves),
            'distinctDigests': len(claims),
            'crossWaveDigests': len(shared) + len(unbacked),
            'crossWaveWithBytesInClone': len(shared),
            'crossWaveWithoutBytesInClone': len(unbacked),
            'trackedFilesScanned': len(tracked),
        },
        'crossWave': list(shared.values()),
        'crossWaveOutsideClone': list(unbacked.values()),
        'crossWaveOutsideCloneMeans': 'Two or more waves claim these bytes and no tracked file '
                                      'under docs/ carries them. That is the large-object '
                                      'state AGENTS.md records for these packs (the originals live '
                                      'in .project-local/ and do not travel with the clone), so a '
                                      'machine migration must fetch them by digest. It is not '
                                      '"the material does not exist" and it is not a pass.',
    }


def serialise(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--check', action='store_true')
    options = parser.parse_args()
    if not (options.write or options.check):
        parser.error('choose --check or --write')
    document = build()
    payload = serialise(document)
    counts = document['counts']
    # Population guards first: a register built from a census that read nothing is not a pass.
    problems = manifest_enumeration_problems()
    if counts['manifests'] != len(MANIFESTS):
        problems.append('MANIFEST_POPULATION %s' % counts['manifests'])
    # Floors are set below the measured population on purpose (1625 tracked files under docs/,
    # 510 distinct declared digests, 49 of them cross-wave as of 2026-10-28, from 8 manifests):
    # their job is to convict a scanner that silently stops seeing a subtree, not to pin today's
    # count. The first cut of this file measured 643/340/48 because it censused only docs/history.
    if counts['trackedFilesScanned'] < 1200:
        problems.append('TRACKED_POPULATION %d' % counts['trackedFilesScanned'])
    if counts['distinctDigests'] < 450:
        problems.append('DIGEST_POPULATION %d' % counts['distinctDigests'])
    if counts['crossWaveDigests'] < 40:
        problems.append('CROSSWAVE_POPULATION %d' % counts['crossWaveDigests'])
    if counts['crossWaveWithBytesInClone'] + counts['crossWaveWithoutBytesInClone'] \
            != counts['crossWaveDigests']:
        problems.append('CROSSWAVE_SPLIT_DOES_NOT_ADD_UP %s' % counts)
    if options.write:
        if problems:
            print('\n'.join('REFUSE ' + p for p in problems))
            return 1
        REGISTER.write_bytes(payload.encode('utf-8'))
        print('CROSSWAVE=WRITTEN %s digests=%d' % (REGISTER.name, counts['crossWaveDigests']))
        return 0
    if problems:
        # Before the drift comparison: a census that stopped seeing a subtree is a more specific
        # and more dangerous finding than "the file differs", and reporting the latter first would
        # send a reader to diff the register instead of fixing the scanner.
        print('CROSSWAVE=FAIL reason=POPULATION ' + '; '.join(problems))
        return 1
    if not REGISTER.is_file():
        print('CROSSWAVE=FAIL reason=REGISTER_ABSENT')
        return 1
    committed = REGISTER.read_text(encoding='utf-8')
    if committed != payload:
        current = json.loads(committed)
        drift = [k for k in ('counts', 'crossWave', 'waves') if current.get(k) != document.get(k)]
        print('CROSSWAVE=FAIL reason=DRIFT fields=%s' % (drift or ['top_level']))
        return 1
    print('CROSSWAVE=OK manifests=%d distinct=%d crossWave=%d inClone=%d outsideClone=%d tracked=%d'
          % (counts['manifests'], counts['distinctDigests'], counts['crossWaveDigests'],
             counts['crossWaveWithBytesInClone'], counts['crossWaveWithoutBytesInClone'],
             counts['trackedFilesScanned']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
