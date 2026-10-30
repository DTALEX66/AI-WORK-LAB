# SPDX-License-Identifier: MIT
"""Read-only pinned file inventory validation. Never imports model code.

WEIGHTS_COMPLETE is only relative to a reviewed upstream manifest. Directory
names, config files, or self-authored inferred hashes cannot qualify a model.
Load/inference evidence is a separate controlled runtime operation.
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat

from jsonschema import Draft202012Validator
from ..runtime.paths import PROJECT_ROOT, resolve_paths

STAGES = ('ABSENT', 'METADATA_ONLY', 'WEIGHTS_COMPLETE', 'LOAD_VERIFIED', 'INFERENCE_VERIFIED')
SCHEMA = PROJECT_ROOT / 'design-lab/schemas/model-manifest.schema.json'
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10))}


def _parts_safe(parts):
    return all(p not in ('', '.', '..') and not p.endswith(('.', ' '))
               and p.split('.')[0].upper() not in RESERVED
               and not any(ord(c) < 32 or c in ':<>"|?*' for c in p) for p in parts)


def _no_links(path):
    # Top down: do not inspect a child through an unverified directory link.
    for part in reversed((path, *path.parents)):
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        if (getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)
                or stat.S_ISLNK(metadata.st_mode)):
            raise ValueError('directory/link traversal is not allowed')


def checked_cache_root(value, *, project_root=None):
    layout = resolve_paths(project_root=project_root)
    raw = os.fspath(value).replace('\\', '/')
    if raw.startswith('//') or any(c in raw for c in ('%', '$', '~', '\x00')):
        raise ValueError('unsafe cache root')
    if PureWindowsPath(raw).drive.casefold() == 'e:':
        raise ValueError('protected drive is not a model probe scope')
    path = Path(raw)
    if not path.is_absolute():
        if PureWindowsPath(raw).drive or raw.startswith('/'):
            raise ValueError('invalid relative cache root')
        path = layout.project_root / path
    if not _parts_safe(path.parts[1:]):
        raise ValueError('unsafe cache root components')
    allowed = [layout.local_root]
    shared = layout.shared_inputs.get('model-library')
    if shared and PureWindowsPath(shared).drive.casefold() != 'e:':
        allowed.append(Path(shared))
    if not any(path.is_relative_to(root) for root in allowed):
        raise ValueError('cache root must be project-local or the declared read-only model library')
    _no_links(path)
    return path


def _relative(value):
    if (not isinstance(value, str) or '\\' in value or ':' in value
            or not _parts_safe(value.split('/')) or PurePosixPath(value).is_absolute()):
        raise ValueError('unsafe manifest file selector')
    if any(part.startswith('.') or part.casefold() in {
        'auth.json', 'credentials.json', 'keychain', 'cookies', 'sessions', 'memories', 'private'
    } for part in value.split('/')):
        raise ValueError('private state is not model inventory')
    return PurePosixPath(value)


def _file(root, relative):
    path = root / _relative(relative)
    _no_links(path.parent)
    metadata = path.lstat()
    symlink = path.is_symlink()
    if not symlink and getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
        raise ValueError('non-symlink reparse file rejected')
    if symlink:
        target = os.readlink(path).replace('\\', '/')
        if target.startswith('//') or PureWindowsPath(target).drive.casefold() == 'e:':
            raise ValueError('external blob link rejected')
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = path.parent / target_path
        target_path = Path(os.path.normpath(target_path))
        if not target_path.is_relative_to(root):
            raise ValueError('blob link escapes model root')
        _relative(target_path.relative_to(root).as_posix())
        _no_links(target_path)
        path = target_path
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError('missing, non-file or hardlinked model payload')
    return path


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _json(data):
    return json.loads(data, object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def _trusted(manifest, digest, project_root):
    """An owner-controlled registry, separate from the supplied model manifest."""
    registry = (Path(project_root) if project_root is not None else PROJECT_ROOT) / 'design-lab/config/model-manifest-trust.json'
    try:
        _no_links(registry)
        if not registry.is_file() or registry.stat().st_nlink != 1 or registry.stat().st_size > 1024**2:
            return False
        content = _json(registry.read_text(encoding='utf-8'))
        if (not isinstance(content, dict) or set(content) != {'schema_version', 'approved'}
                or content['schema_version'] != 'design-lab/model-manifest-trust/v1'
                or not isinstance(content['approved'], list) or len(content['approved']) > 1000):
            return False
        seen = set(); matching = None
        for row in content['approved']:
            if (not isinstance(row, dict) or set(row) != {'model_id', 'revision', 'manifest_sha256',
                                                         'approved_by', 'source', 'observed_at', 'expires_at'}
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in row.values())):
                return False
            key = (row['model_id'], row['revision'])
            if key in seen:
                return False
            seen.add(key)
            if key == (manifest['model_id'], manifest['revision']):
                matching = row
        if matching is None or matching['manifest_sha256'] != digest:
            return False
        observed = datetime.fromisoformat(matching['observed_at'].replace('Z', '+00:00'))
        expires = datetime.fromisoformat(matching['expires_at'].replace('Z', '+00:00'))
        return observed.tzinfo is not None and expires.tzinfo is not None and observed <= datetime.now(timezone.utc) < expires
    except (OSError, ValueError, TypeError, UnicodeError):
        return False


def verify_model_files(root, manifest=None, *, project_root=None, max_total_bytes=128 * 1024**3):
    root = checked_cache_root(root, project_root=project_root)
    if type(max_total_bytes) is not int or max_total_bytes < 1:
        raise ValueError('positive byte budget required')
    result = {'schema_version': 'design-lab/model-probe/v1', 'search_scope': str(root),
              'state': 'ABSENT' if not root.is_dir() else 'METADATA_ONLY',
              'verified_files': [], 'issues': [], 'load': 'NOT_EXECUTED', 'inference': 'NOT_EXECUTED'}
    def issue(code, detail):
        result['issues'].append({'code': code, 'detail': detail})
    if result['state'] == 'ABSENT':
        issue('SCOPED_NOT_FOUND', 'No model directory at this exact path; other caches were not searched.')
        return result
    if manifest is None:
        issue('MANIFEST_MISSING', 'No reviewed pinned file inventory; no payload scan performed.')
        return result
    try:
        validator = Draft202012Validator(_json(SCHEMA.read_text(encoding='utf-8')))
        if not validator.is_valid(manifest):
            raise ValueError('model manifest schema mismatch')
        json.dumps(manifest, allow_nan=False)
        files = manifest['files']
        selectors = [_relative(f['path']).as_posix() for f in files]
        if len({s.casefold() for s in selectors}) != len(selectors):
            raise ValueError('duplicate case-insensitive file path')
        if not any(f['role'] == 'weight' for f in files):
            raise ValueError('manifest contains no weight payload')
    except (ValueError, TypeError, RecursionError) as exc:
        issue('MANIFEST_INVALID', str(exc))
        return result
    result.update(model_id=manifest['model_id'], revision=manifest['revision'], source=manifest['source'],
                  manifest_sha256=hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':'),
                                                          allow_nan=False).encode()).hexdigest())
    if sum(f['size'] for f in files) > max_total_bytes:
        issue('BYTE_BUDGET', 'Manifest payload exceeds the explicit read budget.')
        return result
    if not _trusted(manifest, result['manifest_sha256'], project_root):
        issue('MANIFEST_UNTRUSTED', 'No current independent approval for this exact manifest digest; no payload read.')
        return result
    # Validate every selector/link/size before any payload read.
    paths = {}
    for entry in files:
        try:
            path = _file(root, entry['path'])
            if path.stat().st_size != entry['size']:
                raise ValueError('size mismatch')
            if entry['role'] == 'index' and entry['size'] > 16 * 1024**2:
                raise ValueError('index exceeds 16 MiB')
            paths[entry['path']] = path
        except (OSError, ValueError) as exc:
            issue('FILE_INVALID', entry['path'] + ': ' + str(exc))
    if result['issues']:
        return result
    indexes = []
    snapshots = {}
    for entry in files:
        try:
            path = _file(root, entry['path'])
            before = path.stat()
            digest = hashlib.sha256(); count = 0; chunks = []
            with path.open('rb') as stream:
                while chunk := stream.read(min(1024**2, entry['size'] - count + 1)):
                    count += len(chunk)
                    if count > entry['size']:
                        raise ValueError('file grew while hashing')
                    digest.update(chunk)
                    if entry['role'] == 'index':
                        chunks.append(chunk)
            after = path.stat()
            signature = lambda st: (st.st_ino, st.st_size, st.st_mtime_ns)
            if count != entry['size'] or signature(before) != signature(after) or digest.hexdigest() != entry['sha256']:
                raise ValueError('hash or stability mismatch')
            snapshots[entry['path']] = (path, signature(after))
            result['verified_files'].append({'path': entry['path'], 'sha256': digest.hexdigest(), 'size': count})
            if entry['role'] == 'index':
                indexes.append((entry['path'], _json(b''.join(chunks))))
        except (OSError, ValueError, UnicodeError) as exc:
            issue('FILE_INVALID', entry['path'] + ': ' + str(exc))
    weights = {entry['path'] for entry in files if entry['role'] == 'weight'}
    indexed = set()
    for name, index in indexes:
        try:
            mapping = index.get('weight_map') if isinstance(index, dict) else None
            if not isinstance(mapping, dict) or not mapping:
                raise ValueError('index weight_map missing or empty')
            for tensor, shard in mapping.items():
                if not isinstance(tensor, str) or not tensor:
                    raise ValueError('invalid tensor name')
                target = (PurePosixPath(name).parent / _relative(shard)).as_posix()
                if target not in weights:
                    raise ValueError('index target is not a declared weight shard: ' + target)
                indexed.add(target)
        except ValueError as exc:
            issue('INDEX_INVALID', str(exc))
    if indexes and indexed != weights:
        issue('INDEX_INCOMPLETE', 'Index does not cover all declared weight shards.')
    for name, (old_path, signature) in snapshots.items():
        try:
            path = _file(root, name); stat = path.stat()
            if path != old_path or (stat.st_ino, stat.st_size, stat.st_mtime_ns) != signature:
                raise ValueError('payload changed before probe completed')
        except (ValueError, OSError) as exc:
            issue('FILE_CHANGED', name + ': ' + str(exc))
    if not _trusted(manifest, result['manifest_sha256'], project_root):
        issue('MANIFEST_UNTRUSTED', 'Manifest approval changed or expired during the probe.')
    if not result['issues']:
        result['state'] = 'WEIGHTS_COMPLETE'
    return result


def verify_manifest_file(root, manifest_file, *, project_root=None):
    root = checked_cache_root(root, project_root=project_root)
    path = _file(root, manifest_file)
    if path.suffix.lower() != '.json':
        raise ValueError('manifest must be an explicit JSON file')
    with path.open('rb') as stream:
        data = stream.read(1024**2 + 1)
    if len(data) > 1024**2:
        raise ValueError('manifest exceeds 1 MiB')
    return verify_model_files(root, _json(data), project_root=project_root)
