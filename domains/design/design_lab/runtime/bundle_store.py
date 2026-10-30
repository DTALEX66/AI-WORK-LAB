# SPDX-License-Identifier: MIT
"""Deterministic multi-file delivery archives published as one immutable version.

No rights/Jury approval is inferred. Native host relinking and UI integration
are separate from the archive's byte integrity and atomic publication.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re
import uuid
import zipfile

from . import asset_store as assets
from .paths import resolve_paths

MANIFEST = 'bundle-manifest.json'
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024


def _names(names):
    if (not 1 <= len(names) <= 512 or not all(isinstance(n,str) and n for n in names)
        or len({n.casefold() for n in names}) != len(names)):
        raise ValueError('invalid bundle inventory')
    for name in names:
        path = PurePosixPath(name)
        if (not isinstance(name, str) or path.as_posix() != name or path.is_absolute()
            or len(path.parts) > 8 or any(not assets._portable_name(p) for p in path.parts)
            or any(p in {'.', '..'} for p in path.parts)):
            raise ValueError('unsafe bundle member name')
        if any('/'.join(path.parts[:i]).casefold() in {n.casefold() for n in names}
               for i in range(1, len(path.parts))):
            raise ValueError('bundle file/directory collision')


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _info(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    return info


def verify_bundle(path, *, project_root=None):
    """Bounded readback of every member, without extracting archive paths."""
    path = resolve_paths(project_root=project_root).checked_path(path)
    if path.stat().st_size > MAX_TOTAL + 1024 * 1024:
        raise ValueError('oversized bundle')
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        _names([i.filename for i in infos])
        if any(i.compress_type != zipfile.ZIP_STORED or i.file_size > MAX_FILE for i in infos):
            raise ValueError('unsupported or oversized member')
        if sum(i.file_size for i in infos) > MAX_TOTAL:
            raise ValueError('oversized bundle content')
        if archive.getinfo(MANIFEST).file_size > 256 * 1024:
            raise ValueError('oversized manifest')
        raw = archive.read(MANIFEST)
        manifest = json.loads(raw)
        if _json(manifest) != raw or set(manifest) != {'schemaVersion', 'primary', 'files', 'metadata'}:
            raise ValueError('noncanonical or invalid manifest')
        if manifest['schemaVersion'] != 'design-lab/asset-bundle/v1' or manifest['primary'] not in manifest['files']:
            raise ValueError('invalid bundle identity or primary')
        if set(archive.namelist()) != {MANIFEST, *manifest['files']}:
            raise ValueError('manifest/member mismatch')
        for name, expected in manifest['files'].items():
            if set(expected) != {'sha256', 'byte_size', 'role'}:
                raise ValueError('invalid member record')
            with archive.open(name) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != expected['sha256'] or archive.getinfo(name).file_size != expected['byte_size']:
                raise ValueError('bundle member hash/size mismatch')
    return manifest


def publish_bundle(conn, asset_id, files, *, primary, metadata, store_root,
                   holder_attempt_id, generation, project_root=None):
    """Publish the whole archive using the existing fenced publication journal."""
    if not isinstance(files, dict) or not isinstance(metadata, dict) or primary not in files:
        raise ValueError('bundle files, metadata and primary are required')
    _names([MANIFEST, *files])
    if len(_json(metadata)) > 64 * 1024:
        raise ValueError('oversized bundle metadata')
    paths = resolve_paths(project_root=project_root)
    records, sources = {}, {}
    for name, entry in sorted(files.items()):
        if (not isinstance(entry, dict) or set(entry) != {'path', 'sha256', 'role'}
            or not isinstance(entry['role'], str) or not entry['role'].strip()
            or not isinstance(entry['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
            raise ValueError('invalid bundle source declaration')
        source = paths.checked_path(entry['path'])
        size = source.stat().st_size
        if not source.is_file() or not 0 < size <= MAX_FILE or assets._file_hash(source) != 'sha256:' + entry['sha256']:
            raise ValueError('bundle source hash/size mismatch')
        records[name] = {'sha256': entry['sha256'], 'byte_size': size, 'role': entry['role']}
        sources[name] = source
    manifest = {'schemaVersion': 'design-lab/asset-bundle/v1', 'primary': primary, 'files': records, 'metadata': metadata}
    raw = _json(manifest)
    if len(raw) > 256 * 1024 or sum(r['byte_size'] for r in records.values()) + len(raw) > MAX_TOTAL:
        raise ValueError('oversized bundle content')
    # Candidate archives are project-owned recovery evidence, never user inputs.
    candidate = paths.category_dir('runtime', 'bundle-candidates', uuid.uuid4().hex + '.zip')
    candidate.parent.mkdir(parents=True, exist_ok=True)
    with candidate.open('xb') as output, zipfile.ZipFile(output, 'w') as archive:
        archive.writestr(_info(MANIFEST), raw)
        for name, source in sources.items():
            with source.open('rb') as incoming, archive.open(_info(name), 'w') as outgoing:
                digest = hashlib.sha256(); size = 0
                for block in iter(lambda: incoming.read(1024 * 1024), b''):
                    size += len(block)
                    if size > records[name]['byte_size']:
                        raise ValueError('bundle source grew while copying')
                    digest.update(block); outgoing.write(block)
                if size != records[name]['byte_size'] or digest.hexdigest() != records[name]['sha256']:
                    raise ValueError('bundle source changed while copying')
    verify_bundle(candidate, project_root=project_root)
    return assets.publish_version(conn, asset_id, candidate, store_root=store_root, artifact_name='delivery.zip',
                                  expected_sha256=assets._file_hash(candidate), holder_attempt_id=holder_attempt_id,
                                  generation=generation, project_root=project_root)
