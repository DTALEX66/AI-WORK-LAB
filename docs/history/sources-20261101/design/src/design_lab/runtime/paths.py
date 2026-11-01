# SPDX-License-Identifier: MIT
"""Project-owned paths with provenance; resolution itself never creates files.

Explicit root > PROJECT_LOCAL_ROOT > .project/paths.json > defaults. Every
write root remains inside this checkout's .project-local, even for overrides.
Shared input declarations are not filesystem probes or migration permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'{p}{n}' for p in ('COM', 'LPT') for n in range(1, 10))}


class PathPolicyError(ValueError):
    """A proposed path is unsafe or conflicts with project ownership."""


def _component(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', value)
            or value.endswith('.') or value.split('.')[0].upper() in _RESERVED):
        raise PathPolicyError('invalid task path component')
    return value


def _no_links(path, root):
    if not path.is_relative_to(root):
        raise PathPolicyError('path is not inside its project root')
    chain = [path, *path.parents]
    chain = chain[:chain.index(root) + 1]
    # Inspect ancestors before descendants; lstat works for Windows junctions
    # on Python 3.11 too, unlike the newer Path.is_junction convenience API.
    for part in reversed(chain):
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(metadata.st_mode) or
                getattr(metadata, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)):
            raise PathPolicyError('project paths may not traverse links or junctions')


def _local_path(root, value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise PathPolicyError('runtime root must be a nonempty path')
    value = value.replace('\\', '/')
    if value.startswith('//') or any(c in value for c in ('%', '$', '~', '\x00')):
        raise PathPolicyError('network and shell-expanded runtime paths are rejected')
    # Reject foreign drive paths lexically, before resolve/stat can touch them.
    drive = PureWindowsPath(value).drive
    if drive and drive.lower() != PureWindowsPath(str(root)).drive.lower():
        raise PathPolicyError('runtime root is outside the owning project')
    path = Path(value)
    if not path.is_absolute():
        if drive or value.startswith('/'):
            raise PathPolicyError('drive-relative runtime paths are rejected')
        path = root/path
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise PathPolicyError('runtime root is outside the owning project') from exc
    if not relative.parts or relative.parts[0] != '.project-local':
        raise PathPolicyError('runtime root must remain in project .project-local')
    for part in relative.parts:
        if (part in ('.', '..') or part.endswith(('.', ' ')) or ':' in part
                or part.split('.')[0].upper() in _RESERVED or any(ord(c) < 32 or c in '<>"|?*' for c in part)):
            raise PathPolicyError('unsafe runtime path component')
    _no_links(path, root)
    if not path.resolve().is_relative_to(root/'.project-local'):
        raise PathPolicyError('resolved path escapes project boundary')
    return path


def _load_config(root):
    config_path = root/'.project/paths.json'
    _no_links(config_path, root)
    if not config_path.exists():
        return {}
    if config_path.stat().st_size > 65536:
        raise PathPolicyError('project paths configuration is oversized')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PathPolicyError('duplicate project paths configuration key')
            result[key] = value
        return result
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PathPolicyError('invalid project paths configuration') from exc
    if (not isinstance(config, dict)
            or config.get('schemaVersion') not in {'design-lab/project-paths/v1',
                                                   'design-lab/project-paths/v2'}
            or set(config) - {'schemaVersion', 'project_local_root', 'shared_inputs', 'tools'}):
        raise PathPolicyError('unsupported project paths configuration')
    inputs = config.get('shared_inputs', {})
    if not isinstance(inputs, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in inputs.items()):
        raise PathPolicyError('shared inputs must be named path declarations')
    tools = config.get('tools', {})
    if not isinstance(tools, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in tools.items()):
        raise PathPolicyError('tool bindings must be named path declarations')
    # The version keeps its meaning: `tools` is a v2 field, so a v1 document may
    # not carry it even though the key itself would parse.
    if tools and config.get('schemaVersion') != 'design-lab/project-paths/v2':
        raise PathPolicyError('tool bindings require project paths schema v2')
    return config


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    local_root: Path
    sources: dict[str, str]
    shared_inputs: dict[str, str]
    tools: dict[str, str] = field(default_factory=dict)

    @property
    def runtime_root(self):
        return self.local_root/'task-runtime'

    @property
    def evidence_root(self):
        return self.local_root/'task-artifacts'

    @property
    def projects_root(self):
        return self.local_root/'projects'

    @property
    def model_cache(self):
        return self.local_root/'cache/models'

    def task_dir(self, namespace, run_id, *, evidence=False):
        parent = self.evidence_root if evidence else self.runtime_root
        target = parent/_component(namespace)/_component(run_id)
        _no_links(target, self.project_root)
        return target

    def checked_path(self, path):
        """Validate an explicit write target against the selected root, without mkdir."""
        target = _local_path(self.project_root, os.fspath(path))
        if target == self.local_root or not target.is_relative_to(self.local_root):
            raise PathPolicyError('write target is outside the selected project-local root')
        if target.is_file() and target.stat().st_nlink != 1:
            raise PathPolicyError('write target may not be a hardlinked file')
        return target

    def category_dir(self, category, *components):
        parents = {'runtime': self.runtime_root, 'evidence': self.evidence_root,
                   'projects': self.projects_root, 'model_cache': self.model_cache}
        if category not in parents:
            raise PathPolicyError('unknown project data category')
        return self.checked_path(parents[category].joinpath(*(_component(p) for p in components)))

    def database_path(self, path):
        target = self.checked_path(path)
        for suffix in ('-wal', '-shm', '-journal'):
            self.checked_path(str(target) + suffix)
        return target

    def child_environment(self, namespace, run_id):
        task = self.task_dir(namespace, run_id)
        return {'PROJECT_LOCAL_ROOT': str(self.local_root), 'TEMP': str(task/'tmp'),
                'TMP': str(task/'tmp'), 'XDG_CACHE_HOME': str(self.local_root/'cache'),
                'HF_HOME': str(self.model_cache/'huggingface'), 'TORCH_HOME': str(self.model_cache/'torch')}

    def tool_bindings(self):
        """Classify every `.project/paths.json` `tools` entry without running it.

        A binding must sit inside one of the declared shared-input roots. Without
        that rule `tools` would be an arbitrary executable path the project trusts,
        which is a worse version of the problem it solves: the point is to stop
        reporting *registered* software as missing, not to widen what can be run.
        """
        roots = {name: Path(raw).as_posix().rstrip('/').casefold()
                 for name, raw in self.shared_inputs.items()}
        out = {}
        for name, raw in self.tools.items():
            if not isinstance(raw, str) or not raw.strip():
                out[name] = {'path': raw, 'owner': None, 'status': 'DECLARED_VALUE_INVALID'}
                continue
            posix = Path(raw).as_posix().rstrip('/')
            folded = posix.casefold()
            owner = next((label for label, base in roots.items()
                          if folded == base or folded.startswith(base + '/')), None)
            if owner is None:
                status, reason = 'DECLARED_OUTSIDE_SHARED_ROOT', \
                    'binding is not under any declared shared-input root, so it is not trusted'
            else:
                candidate = Path(raw)
                if candidate.is_file():
                    status, reason = 'BOUND', None
                elif candidate.exists():
                    status, reason = 'DECLARED_PATH_NOT_A_FILE', None
                else:
                    status, reason = 'DECLARED_PATH_MISSING', \
                        'registered path is absent; the tool may still be on PATH'
            out[name] = {'path': posix, 'owner': owner, 'status': status,
                         **({'reason': reason} if reason else {})}
        return out

    def describe(self):
        roots = {'runtime': self.runtime_root, 'evidence': self.evidence_root,
                 'projects': self.projects_root, 'model_cache': self.model_cache}
        return {'schemaVersion': 'design-lab/path-diagnostic/v1', 'status': 'PATHS_RESOLVED',
                'project_root': self.project_root.as_posix(), 'project_local_root': self.local_root.as_posix(),
                'sources': self.sources,
                'roots': {name: {'path': path.as_posix(), 'ownership': 'project', 'writable': True}
                          for name, path in roots.items()},
                'shared_inputs': {name: {'path': path, 'writable': False, 'status': 'DECLARED_NOT_PROBED'}
                                  for name, path in self.shared_inputs.items()},
                'tools': self.tool_bindings(),
                'agent_profile': {'status': 'PRIVATE_NOT_INSPECTED', 'writable': False},
                'write_trace': 'NOT_EXECUTED', 'migration': 'NOT_EXECUTED'}


def _ambient_root_is_above_project(candidate, root):
    """True when an inherited PROJECT_LOCAL_ROOT names a directory containing `root`.

    Lexical, and deliberately narrow: it only recognises the shape of a value inherited
    from an enclosing checkout, where the named project root sits below it. It never
    widens what a caller may point at, so every other ambient value is still judged by
    `_local_path`, including protected and escaping ones.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        return False
    path = Path(candidate.replace('\\', '/'))
    if not path.is_absolute():
        path = root/path
    return root == path or path in root.parents


def resolve_paths(*, project_root=None, environ=None, project_local_root=None):
    root = Path(project_root if project_root is not None else PROJECT_ROOT).absolute()
    if not root.is_absolute() or not (root/'AGENTS.md').is_file():
        raise PathPolicyError('owning project marker is missing')
    _no_links(root, root)
    config = _load_config(root)
    env = os.environ if environ is None else environ
    source = 'default'
    value = '.project-local'
    if 'project_local_root' in config:
        value, source = config['project_local_root'], 'config:.project/paths.json'
    ignored_ambient = None
    if 'PROJECT_LOCAL_ROOT' in env:
        candidate = env['PROJECT_LOCAL_ROOT']
        if _ambient_root_is_above_project(candidate, root):
            # child_environment() exports PROJECT_LOCAL_ROOT, so every child inherits the
            # enclosing checkout's own .project-local. When the caller names a project
            # root below that value — a synthetic fixture nested inside the real
            # .project-local, or a second checkout — the inherited value cannot be this
            # project's runtime root. Honouring it raised "runtime root is outside the
            # owning project" and failed seven test_audit_trail cases in CI only.
            # Everything else still goes through the policy untouched, so an escaping or
            # protected ambient value ('../escape', 'E:/protected') keeps failing closed.
            value, source = '.project-local', 'default'
            ignored_ambient = candidate
        else:
            value, source = candidate, 'environment:PROJECT_LOCAL_ROOT'
    if project_local_root is not None:
        value, source = project_local_root, 'explicit'
    local_root = _local_path(root, value)
    provenance = {'project_local_root': source}
    if ignored_ambient is not None:
        provenance['ambient_project_local_root_ignored'] = ignored_ambient
    return ProjectPaths(root, local_root, provenance,
                        config.get('shared_inputs', {}), config.get('tools', {}))
