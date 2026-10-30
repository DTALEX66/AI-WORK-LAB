# SPDX-License-Identifier: MIT
"""R3 current reports: one task ledger, four evidence axes, checked projections."""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import warnings

from jsonschema import Draft202012Validator, FormatChecker
from design_lab.runtime.paths import resolve_paths

LEDGER = 'design-lab/config/task-ledger-r3.json'
SCHEMA = 'design-lab/schemas/task-ledger-r3.schema.json'
TASK_SOURCE = 'docs/history/taskpacks/r3-tasks-2026-09-06.json'
HOST_TASKS = {'R3-' + number for number in ('02', '08', '10', '11', '12', '13', '14', '15',
                                           '16', '17', '18', '19', '20', '21', '22', '23')}
DELIVERY_TASKS = {'R3-04', 'R3-15', 'R3-24'}
INDEX = 'design-lab/config/current-report-index.json'
CURRENT = 'reports/current/'
REPORTS = ('CLOUD_BASELINE.json', 'CLOUD_BASELINE.md', 'PROJECT_STATUS.json', 'PROJECT_STATUS.md',
           'TASK_PROGRESS.json', 'ADAPTER_EVIDENCE_RECONCILIATION.json', 'KNOWLEDGE_INVENTORY.json',
           'DOMAIN_PACK_READINESS.json', 'RELEASE_READINESS.json')
KINDS = {'implementation': {'structural', 'local_test', 'host_live'}, 'unit': {'local_test'},
         'host_live': {'host_live'}, 'delivery': {'delivery'}}


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f'nonfinite JSON value: {value}')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _safe(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('expected a public repository-relative POSIX path')
    rel = PurePosixPath(relative)
    # Public roots an evidence receipt or projection input may cite.
    #
    # This set is now EXACTLY the repository roots AUTHORITY.md §7 declares
    # ("仓库责任"): apps, src, packages, integrations, design-lab, fixtures,
    # research, vendor, docs, reports, scripts, .project, .project-local.
    # `.project-local` is admitted only for task-artifacts/ (see below), and
    # `.project` is the tracked governance root.
    #
    # `apps` was added 2026-09-27 because AUTHORITY.md §3 declares the Workbench
    # the first-class user-visible front end ("DESIGN-LAB 有前端：apps/workbench/").
    # Without it NO evidence receipt could cite the front end at all, so the R5
    # ledger could not record a single front-end fact — a governance gap, not a
    # safety property.
    #
    # `research` and `vendor` were added in the same pass: an audit of this set
    # against §7 found them missing too, the identical defect class. Leaving them
    # out would have re-created the gap for §7's own declared roots.
    #
    # Owner intent: 2026-09-27, "加入，全部开始" (answering the finding recorded in
    # the project survey). Rationale: a receipt may cite what the Authority
    # already declares repository-authoritative. Superseded: the previous 8-root
    # and 10-root sets. Impact: apps/**, research/** and vendor/** become
    # citable; nothing else widens.
    #
    # The secret guard is deliberately NOT widened: `denied` below still applies
    # to every path component, so `.env*` / auth.json / credentials.json /
    # tokens.json / id_rsa remain rejected ANYWHERE in the tree — verified for
    # `apps/workbench/.env` and `apps/auth.json`. apps/, research/, vendor/ and
    # services/ were audited for this change and hold no credential-named path.
    allowed = {'src', 'scripts', 'design-lab', 'docs', 'reports', 'integrations',
               'packages', 'fixtures', '.project', 'apps', 'research', 'vendor'}
    denied = {'.git', '.hermes', '.openhuman', 'auth.json', 'credentials.json', 'tokens.json', 'id_rsa'}
    def permitted(parts):
        return not any(p.lower() in denied or p.lower().startswith('.env') for p in parts)
    if rel.is_absolute() or '..' in rel.parts or not permitted(rel.parts):
        raise ValueError('private or escaping evidence path rejected')
    workflow_source = (len(rel.parts) == 3 and rel.parts[:2] == ('.github', 'workflows')
                       and rel.suffix in {'.yml', '.yaml'})
    if rel.parts[0] not in allowed and relative not in {'AGENTS.md', 'README.md', 'pyproject.toml', 'uv.lock'}:
        if not workflow_source and not (rel.parts[0] == '.project-local' and 'task-artifacts' in rel.parts[1:-1]):
            raise ValueError('evidence path outside declared public artifact/source roots')
    target = root.joinpath(*rel.parts)
    for ancestor in (target, *target.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink() or (hasattr(ancestor, 'is_junction') and ancestor.is_junction()):
            raise ValueError('evidence paths may not traverse links or junctions')
    resolved = target.resolve()
    if not resolved.is_relative_to(root.resolve()) or not permitted(resolved.relative_to(root.resolve()).parts):
        raise ValueError('resolved evidence path escaped public roots')
    return target


class Reader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.hashes = {}
        self.relocated = {}
        self._relocations = None

    def _relocation_map(self):
        """`from -> to` for every document moved by an archive pass.

        Frozen ledgers keep their recorded path (rewriting them would break the
        SHA-256 they are pinned by), so a path that no longer exists is resolved
        through the archive manifest instead of being 'fixed' in the frozen bytes.
        Absent from the manifest stays a hard FileNotFoundError.
        """
        if self._relocations is None:
            table = {}
            for manifest in sorted(self.root.glob('docs/history/archive-*/MANIFEST.json')):
                try:
                    data = _json(manifest.read_bytes())
                except (ValueError, UnicodeDecodeError):
                    continue
                for group in data.get('groups', []):
                    for entry in group.get('files', []):
                        table[entry['from']] = entry['to']
            self._relocations = table
        return self._relocations

    def read(self, relative, optional=False):
        path = _safe(self.root, relative)
        try:
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('report input exceeds bounded read size')
            raw = path.read_bytes()
        except FileNotFoundError:
            target = self._relocation_map().get(relative)
            if target is not None:
                relocated = _safe(self.root, target)
                try:
                    if relocated.stat().st_size > 32 * 1024 * 1024:
                        raise ValueError('report input exceeds bounded read size')
                    raw = relocated.read_bytes()
                    self.relocated[relative] = target
                    digest = hashlib.sha256(raw).hexdigest()
                    if relative in self.hashes and self.hashes[relative] != digest:
                        raise ValueError(f'input changed while projecting: {relative}')
                    self.hashes[relative] = digest
                    return raw
                except FileNotFoundError:
                    pass
            if not optional:
                raise
            raw = None
        digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
        if relative in self.hashes and self.hashes[relative] != digest:
            raise ValueError(f'input changed while projecting: {relative}')
        self.hashes[relative] = digest
        return raw

    def json(self, relative, optional=False):
        raw = self.read(relative, optional)
        return _json(raw) if raw is not None else None

    def stable(self):
        for relative in list(self.hashes):
            self.read(relative, optional=True)


def _validate(reader, ledger):
    if ledger.get('schemaVersion') == 'design-lab/task-ledger/r5-v1':
        from design_lab.governance.r5_contract import validate
        return validate(reader, ledger, _validate)
    errors = sorted(Draft202012Validator(reader.json(SCHEMA), format_checker=FormatChecker()).iter_errors(ledger),
                    key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError(f'invalid task ledger: {errors[0].message}')
    tasks = {t['id']: t for t in ledger['tasks']}
    if len(tasks) != len(ledger['tasks']):
        raise ValueError('duplicate task IDs')
    raw_source = reader.read(TASK_SOURCE)
    # The supplied ZIP member has no final LF; the repository text copy adds one.
    if ledger['source']['tasks_sha256'] not in {
            hashlib.sha256(raw_source).hexdigest(),
            hashlib.sha256(raw_source.removesuffix(b'\n')).hexdigest()}:
        raise ValueError('frozen task source hash mismatch')
    source = _json(raw_source)
    if source['id'] != ledger['taskpack'] or source['baselineSha'] != ledger['baseline_sha']:
        raise ValueError('taskpack identity differs from frozen source')
    originals = {task['id']: task for task in source['tasks']}
    if set(originals) != set(tasks):
        raise ValueError('task inventory differs from frozen source')
    for tid, original in originals.items():
        if any(tasks[tid].get(key) != value for key, value in original.items() if key != 'status'):
            raise ValueError(f'task definition differs from frozen source: {tid}')
    receipts = {e['id']: e for e in ledger['evidence']}
    if len(receipts) != len(ledger['evidence']):
        raise ValueError('duplicate evidence IDs')
    visiting, visited, order = set(), set(), []
    def visit(tid):
        if tid not in tasks:
            raise ValueError(f'unknown task dependency: {tid}')
        if tid in visiting:
            raise ValueError('cyclic task dependencies')
        if tid in visited:
            return
        visiting.add(tid)
        task = tasks[tid]
        required = {'implementation', 'unit'}
        if tid in HOST_TASKS:
            required.add('host_live')
        if tid in DELIVERY_TASKS:
            required.add('delivery')
        if set(task['required_axes']) != required:
            raise ValueError(f'required evidence axes differ from R3 acceptance: {tid}')
        for axis, value in task['axes'].items():
            if axis != 'implementation' and value['state'] == 'IMPLEMENTED_LOCAL':
                raise ValueError('implementation state cannot qualify testing, host or delivery')
            if axis in task['required_axes'] and value['state'] == 'NOT_REQUIRED':
                raise ValueError('required axis cannot be waived')
            if any(eid not in receipts for eid in value['evidence']):
                raise ValueError('unknown evidence reference')
        for dependency in task['depends_on']:
            visit(dependency)
        visiting.remove(tid)
        visited.add(tid)
        order.append(tid)
    for tid in tasks:
        visit(tid)
    reader.read(ledger['plan_path'])
    return tasks, receipts, order


class _CommitReader:
    """Blob access for receipts bound to commits, with the object reads batched per commit.

    Measured 2026-10-08 at one `git show` per claim: 10.0s cold for 502 claims, which is not a
    surface a person can ask a question of. One `git cat-file --batch` per distinct commit pulls the
    same bytes out of the same objects in milliseconds. The per-claim read stays as the fallback for
    anything this protocol cannot carry, because a wrongly-absent blob would be reported as
    PATH_NOT_IN_BOUND_COMMIT -- a file the commit supposedly lacks.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self._blobs = {}
        self._commits = {}
        self._modified = {}
        self._tracked = None

    def _run(self, *args):
        return subprocess.run(['git', '-c', 'color.ui=false', '-C', str(self.root), *args],
                              capture_output=True)

    def has_commit(self, sha):
        if sha not in self._commits:
            self._commits[sha] = self._run('cat-file', '-e', f'{sha}^{{commit}}').returncode == 0
        return self._commits[sha]

    def blob(self, sha, relative):
        key = (sha, relative)
        if key not in self._blobs:
            result = self._run('show', f'{sha}:{relative}')
            self._blobs[key] = result.stdout if result.returncode == 0 else None
        return self._blobs[key]

    def prefetch(self, sha, relatives):
        """Fill the cache for every claim of one commit in a single git process."""
        todo = sorted({path for path in relatives
                       if (sha, path) not in self._blobs
                       and '\n' not in path and '\r' not in path})
        if not todo:
            return
        if not self.has_commit(sha):
            for path in todo:
                self._blobs[(sha, path)] = None
            return
        request = ''.join(f'{sha}:{path}\n' for path in todo).encode('utf-8')
        result = subprocess.run(['git', '-c', 'color.ui=false', '-C', str(self.root),
                                 'cat-file', '--batch'], input=request, capture_output=True)
        if result.returncode != 0:
            return
        self._absorb(sha, todo, result.stdout)

    def _absorb(self, sha, ordered, out):
        """Read `git cat-file --batch` output: one block per request, in request order."""
        cursor = 0
        for path in ordered:
            end = out.find(b'\n', cursor)
            if end < 0:
                break
            header = out[cursor:end].decode('utf-8', 'surrogateescape')
            cursor = end + 1
            parts = header.split(' ')
            if len(parts) == 3 and parts[1] == 'blob' and parts[2].isdigit():
                size = int(parts[2])
                self._blobs[(sha, path)] = out[cursor:cursor + size]
                cursor += size + 1
            elif header.endswith(' missing'):
                self._blobs[(sha, path)] = None
            else:
                break
        # Anything the parse did not reach is read the slow unambiguous way rather than guessed at.
        for path in ordered:
            if (sha, path) not in self._blobs:
                self.blob(sha, path)

    def locally_modified(self, sha):
        """Paths whose working-tree bytes differ from `sha` -- a dirty tree is not today's bytes."""
        if sha not in self._modified:
            result = self._run('diff', '--name-only', '-z', sha, '--')
            if result.returncode != 0:
                raise ValueError(f'git inspection failed: diff {sha}')
            self._modified[sha] = {line for line in
                                   result.stdout.decode('utf-8', 'surrogateescape').split('\0')
                                   if line}
        return self._modified[sha]

    def tracked_today(self, relative):
        """Is this path version controlled at all, on any branch, right now?

        One `git ls-files -z` for the whole checkout rather than one process per claim: a projection
        asks this hundreds of times and the answer set is the same question asked repeatedly.
        """
        if self._tracked is None:
            result = self._run('ls-files', '-z')
            if result.returncode != 0:
                raise ValueError('git inspection failed: ls-files')
            self._tracked = {line for line in result.stdout.decode('utf-8', 'surrogateescape')
                             .split('\0') if line}
        return relative in self._tracked

RUNTIME_ARTIFACT_ROOT = '.project-local/task-artifacts/'
COMMIT_BINDING = 'COMMIT'
WORKTREE_BINDING = 'WORKTREE_FILES'
DIGEST_CONFLICT = 'DIGEST_CONFLICT_FOR_SAME_PATH'


class Claims(tuple):
    """(claimed, runtime, conflicts, pairs) -- every byte a receipt states, and how to read it.

    `claimed` maps path -> digest over BOTH digest lists, deduplicated; `runtime` is the subset of
    those paths that lives under the runtime artefact root, where no commit can hold bytes;
    `conflicts` are paths claimed with two different digests; `pairs` counts the raw entries, so a
    consumer can show that deduplication is not silently dropping claims.
    """

    __slots__ = ()

    def __new__(cls, claimed, runtime, conflicts, pairs):
        return super().__new__(cls, (claimed, runtime, conflicts, pairs))

    @property
    def claimed(self):
        return self[0]

    @property
    def runtime(self):
        return self[1]

    @property
    def conflicts(self):
        return self[2]

    @property
    def pairs(self):
        return self[3]

    def versioned(self):
        """The paths a commit could actually be asked to hold."""
        return {path: digest for path, digest in self[0].items() if path not in self[1]}


def basis(receipt) -> str:
    """Which basis this receipt's byte claims must be re-checked against, defaulting to stricter.

    `WORKTREE_FILES` is the record's own disclaimer -- the schema says it "may never be presented as
    a commit" -- so no component may judge those bytes by the object database and call the difference
    a defect. On 2026-10-08 the binding gate did exactly that and parked four of the resulting lines
    in its waiver list, which is a basis error being paid for as evidence debt.
    """
    return WORKTREE_BINDING if receipt.get('binding') == WORKTREE_BINDING else COMMIT_BINDING


def claims(receipt) -> Claims:
    """Enumerate a receipt's byte claims once, for every consumer that has to recompute them.

    The projection and the binding gate both recompute digests, and each kept its own copy of "which
    paths count as a byte claim" -- which is how they came to disagree about what was verified. This
    function is the single owner of that enumeration; the verdicts stay with the consumers.
    """
    pairs = [(path, digest) for path, digest in (receipt.get('subject_files') or {}).items()]
    pairs += [(item['path'], item['sha256']) for item in (receipt.get('artifacts') or [])]
    claimed, runtime, conflicts = {}, set(), []
    for path, digest in pairs:
        wanted = str(digest).removeprefix('sha256:')
        if path.startswith(RUNTIME_ARTIFACT_ROOT):
            runtime.add(path)
        seen = claimed.setdefault(path, wanted)
        if seen != wanted:
            conflicts.append(path)
    return Claims(claimed, frozenset(runtime), sorted(set(conflicts)), len(pairs))

def _receipt_findings(receipt, subject_sha, reader, commits):
    """Re-check a receipt on the basis its own `binding` declares, then ask if it still speaks for today.

    INTEGRITY -- are the bytes this receipt hashed where it says they came from?
      A COMMIT receipt claims a commit, so only that commit's blobs can re-check it. The old code
      compared a COMMIT receipt's digests against the working tree of whichever commit the projection
      was generated at, which convicted a row for the CRLF normalisation its git attributes impose and
      for drift it never claimed to rule out -- and it could not prove the bytes it was checking were
      the bytes the receipt hashed. Measured 2026-10-08 that made every receipt unverifiable: 0 of 73
      `verified`, so no axis could ever be promoted and the flag carried no information. Re-checked
      against the bound commit, 406 of 411 claimed digests reproduce; the five that do not are
      convicted below by name instead of hidden in a wall of red.
      A WORKTREE_FILES receipt admits its bytes came off a dirty tree, so only this disk can show
      them, and only while that tree is still the tree it was taken from.
    CURRENCY -- does the receipt still describe the bytes the projection is speaking for?
      Intact history about files that have since moved is honest but is not evidence about today's
      code, so it must not promote an axis. That decay is what
      docs/decisions/R3-REPORT-OBSERVATION-SEMANTICS-2026-09-07 declares; it could not be expressed
      while integrity and currency shared one flag that was already red at every SHA.
    """
    integrity, currency = [], []
    if receipt['outcome'] != 'PASS':
        integrity.append('OUTCOME_NOT_PASS')
    state = claims(receipt)
    for relative in state.conflicts:
        integrity.append(f'{DIGEST_CONFLICT}:{relative}')
    binding = basis(receipt)
    bound = receipt['subject_sha']
    if binding == COMMIT_BINDING and not commits.has_commit(bound):
        integrity.append(f'SUBJECT_COMMIT_ABSENT:{bound}')
        return integrity, currency
    in_subject = binding == COMMIT_BINDING and commits.has_commit(subject_sha)
    modified = commits.locally_modified(subject_sha) if in_subject else set()
    for relative, expected in state.claimed.items():
        # Every path is still read from disk so a file that changes mid-projection trips Reader.
        raw = reader.read(relative, optional=True)
        if relative in state.runtime:
            if raw is None:
                integrity.append(f'RUNTIME_ARTIFACT_ABSENT_ON_THIS_MACHINE:{relative}')
            elif hashlib.sha256(raw).hexdigest() != expected:
                integrity.append(f'RUNTIME_ARTIFACT_DIGEST_DIFFERS:{relative}')
            continue
        if binding == COMMIT_BINDING:
            blob = commits.blob(bound, relative)
            if blob is None:
                # Two different lies. A path version controlled today simply was not in the commit the
                # row names, so the row bound the wrong SHA. A path no commit ever held cannot be
                # re-read at any SHA: measured 2026-10-08, 63 of the 472 commit-basis claims are of
                # this kind -- 57 `__pycache__/*.pyc` byte-compiled caches and 6 audio bytes under
                # `fixtures/domains/game-visual/android-minigame/`, which that directory's own
                # .gitignore excludes -- spread over 14 receipts dated 2026-09-28.
                integrity.append(f'PATH_NOT_IN_BOUND_COMMIT:{relative}' if commits.tracked_today(relative)
                                 else f'ARTIFACT_IS_NOT_VERSIONED:{relative}')
            elif hashlib.sha256(blob).hexdigest() != expected:
                integrity.append(f'DIGEST_NOT_REPRODUCIBLE_AT_BOUND_COMMIT:{relative}')
            elif not in_subject:
                currency.append(f'PROJECTION_SUBJECT_NOT_A_COMMIT:{subject_sha}')
            elif relative in modified:
                currency.append(f'LOCALLY_MODIFIED_SINCE_SUBJECT:{relative}')
            elif commits.blob(subject_sha, relative) != blob:
                currency.append(f'MOVED_SINCE_BOUND_COMMIT:{relative}')
        else:
            if bound != subject_sha:
                currency.append('STALE_SUBJECT_SHA')
            if raw is None:
                integrity.append(f'EVIDENCE_FILE_MISSING:{relative}')
            elif hashlib.sha256(raw).hexdigest() != expected:
                integrity.append(f'EVIDENCE_DIGEST_DIFFERS:{relative}')
    return integrity, currency


def project_ledger(root, ledger, subject_sha, *, reader=None):
    reader = reader or Reader(root)
    tasks, receipts, order = _validate(reader, ledger)
    commits = _CommitReader(root)
    # Every claim of every commit this projection will look at, pulled in one git process each.
    wanted = {}
    for receipt in receipts.values():
        paths, _runtime, _conflicts, _worktree = claims(receipt)
        wanted.setdefault(receipt['subject_sha'], set()).update(paths)
        wanted.setdefault(subject_sha, set()).update(paths)
    for sha, paths in wanted.items():
        commits.prefetch(sha, paths)
    evaluated = {}
    for eid, receipt in receipts.items():
        integrity, currency = _receipt_findings(receipt, subject_sha, reader, commits)
        evaluated[eid] = {**receipt, 'verified': not integrity,
                          'current': not integrity and not currency,
                          'integrity_reasons': integrity, 'currency_reasons': currency,
                          'reasons': integrity + currency}
    projected = {}
    for tid in order:
        task = tasks[tid]
        axes = {}
        for axis, declaration in task['axes'].items():
            reasons = []
            state = declaration['state']
            if state in {'PASS', 'IMPLEMENTED_LOCAL'}:
                good = [eid for eid in declaration['evidence'] if evaluated[eid]['verified']
                        and evaluated[eid]['current'] and tid in evaluated[eid]['task_ids']
                        and evaluated[eid]['kind'] in KINDS[axis]]
                if not good:
                    state = 'UNVERIFIED'
                    reasons.append('no current evidence of the required kind')
            axes[axis] = {**declaration, 'state': state, 'declared_state': declaration['state'], 'reasons': reasons}
        unmet = [dep for dep in task['depends_on'] if projected[dep]['status'] != 'DONE_LOCAL']
        conditions = task.get('definition', {}).get('conditional_dependencies', {})
        decisions = task.get('condition_decisions', {})
        unresolved = [name for name in conditions if name not in decisions]
        for name, dependency in conditions.items():
            if decisions.get(name, {}).get('required') and projected[dependency]['status'] != 'DONE_LOCAL':
                if dependency not in unmet:
                    unmet.append(dependency)
        satisfied = all(axes[axis]['state'] in {'IMPLEMENTED_LOCAL', 'PASS'} for axis in task['required_axes'])
        started = any(a['state'] not in {'NOT_EXECUTED', 'NOT_REQUIRED'} for a in axes.values())
        status = 'DONE_LOCAL' if satisfied and not unmet and not unresolved else 'PARTIAL' if started else 'TODO'
        projected[tid] = {'id': tid, 'title': task['title'], 'status': status, 'depends_on': task['depends_on'],
                          'unmet_dependencies': unmet, 'required_axes': task['required_axes'], 'axes': axes}
        if 'definition' in task:
            projected[tid].update(definition=task['definition'],
                                  predecessor_task_ids=task['predecessor_task_ids'],
                                  reassessment=task['reassessment'], condition_decisions=decisions,
                                  unresolved_conditions=unresolved)
    return {'schemaVersion': ledger['schemaVersion'].replace('task-ledger/', 'task-progress/'), 'taskpack': ledger['taskpack'],
            'subjectSha': subject_sha, 'ledgerUpdatedAt': ledger['updated_at'],
            'tasks': [projected[t['id']] for t in ledger['tasks']], 'evidence': list(evaluated.values()),
            'counts': dict(Counter(t['status'] for t in projected.values())),
            'note': 'DONE_LOCAL concerns the declared task axes and dependencies, not a product release or hosted CI.'}


def _git(root, *args):
    result = subprocess.run(['git', '-c', 'color.ui=false', '-C', str(root), *args], capture_output=True,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    if result.returncode:
        raise ValueError(f'git inspection failed: {args[0]}')
    return result.stdout.decode('utf-8', errors='strict').rstrip('\r\n')


def git_snapshot(root):
    if Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != Path(root).resolve():
        raise ValueError('report root must be the owning Git root')
    # Unified content-bound digest (DL-AUDIT-20260914-01). Generated reports and
    # private/runtime roots are excluded by the module's declared scope, so
    # writing a projection never changes the digest of the subject it describes.
    # The digest now binds HEAD + every normalized change to its SHA-256 content,
    # replacing the old "porcelain status string only" digest.
    from design_lab.governance.worktree_digest import analyze
    description = analyze(root)
    dirty = not description['clean']
    try:
        origin = _git(root, 'rev-parse', 'origin/main')
    except ValueError:
        origin = None
    sha = description['head_sha']
    return {'sha': sha, 'branch': description['branch'],
            'origin_main': origin, 'source_worktree_clean': not dirty,
            'worktree_digest': description['digest'],
            'worktree_changes': description['changes'],
            'tracked_files': len([p for p in _git(root, 'ls-files', '-z').split('\0') if p])}


def environment_fingerprint():
    """What produced this projection: interpreter and platform, not a test result."""
    import platform
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine()}


def test_run_binding(reader):
    """A bound test run, or an explicit statement that none is bound.

    The projection must not imply that a test ran. Until a test wrapper writes
    the record, the field stays null with a stated meaning.
    """
    record = reader.json('.project-local/task-artifacts/test-run/last-run.json', optional=True)
    if not isinstance(record, dict):
        return {'testRunId': None,
                'testRunMeaning': 'no bound test run; this projection does not claim a test result'}
    return {'testRunId': record.get('run_id'),
            'testRunMeaning': f"bound run: {record.get('command', 'unknown command')}",
            'testRunAt': record.get('finished_at'),
            'testRunResult': record.get('result')}


def _dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _build(reader, snapshot, generated_at):
    ledger = reader.json(LEDGER)
    progress = project_ledger(reader.root, ledger, snapshot['sha'], reader=reader)
    # DLDS-B050: every projection must name its exact subject. A dirty tree is a
    # WORKTREE subject and may never be presented as a commit.
    authority = reader.json('reports/current/DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json', optional=True)
    common = {'subjectType': 'COMMIT' if snapshot.get('source_worktree_clean') else 'WORKTREE',
              'subjectSha': snapshot['sha'], 'generatedAt': generated_at,
              'worktreeDigest': snapshot.get('worktree_digest'),
              'worktreeClean': bool(snapshot.get('source_worktree_clean')),
              'taskpackId': ledger['taskpack'],
              'taskpackHash': (ledger.get('source') or {}).get('sha256'),
              'authorityTaskpackId': (authority or {}).get('taskpack', {}).get('taskpack_id'),
              'authorityTaskpackHash': (authority or {}).get('taskpack', {}).get('taskpack_sha256'),
              'environmentFingerprint': environment_fingerprint(),
              **test_run_binding(reader),
              'subjectMeaning': 'subjectType=WORKTREE means the tree was dirty at generation; '
                                'worktreeDigest covers HEAD plus the non-generated changes',
              'fresh': bool(snapshot.get('source_worktree_clean') and snapshot.get('origin_main') == snapshot['sha']),
              'freshnessMeaning': 'at generation only; check verifies bound-input integrity, not current Git or cloud state',
              'gitStateMeaning': 'generation-time observation, not current HEAD'}
    adapters = reader.json('integrations/adapter-registry.json', optional=True)
    evidence_index = reader.json('design-lab/config/capability-evidence-current.json', optional=True)
    sources = reader.json('design-lab/research/global-absorption/SOURCE_REGISTRY.json', optional=True)
    quarantine = reader.json('design-lab/research/global-absorption/QUARANTINE_REGISTRY.json', optional=True)
    def count(data, key):
        return len(data.get(key, [])) if data is not None else None
    defined = 0
    for path in sorted((reader.root/'design-lab/tests').glob('test_*.py')):
        raw = reader.read(path.relative_to(reader.root).as_posix())
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(raw.decode('utf-8-sig'))
        defined += sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_') for node in ast.walk(tree))
    status = {**common, 'schemaVersion': 'design-lab/project-status/v2', 'taskpack': ledger['taskpack'],
              'ledger': LEDGER, 'plan': ledger['plan_path'], 'git': snapshot, 'taskCounts': progress['counts'],
              'sources': {'activeRegistryEntries': count(sources, 'entries'), 'quarantinedSources': count(quarantine, 'entries')},
              'tests': {'definedTestMethodCount': defined, 'executed': 'see individual verified ledger receipts'},
              'hostLive': 'derived from host_live axis only', 'releaseStatus': 'NOT_RELEASED'}
    table = ['| Task | Status | Implementation | Unit | Host live | Delivery |', '|---|---|---|---|---|---|']
    for task in progress['tasks']:
        table.append('| ' + ' | '.join([task['id'], task['status'], *(task['axes'][axis]['state'] for axis in KINDS)]) + ' |')
    markdown = '# PROJECT_STATUS（生成投影）\n\n'
    markdown += f"任务包：{ledger['taskpack']}；生成时观察 SHA（不是当前 HEAD）：`{snapshot['sha']}`。\n\n"
    markdown += (f"subject_type：`{common['subjectType']}`；worktree_clean：`{common['worktreeClean']}`；"
                 f"worktree_digest：`{str(common['worktreeDigest'])[:23]}…`；"
                 f"test_run_id：`{common['testRunId']}`。\n\n")
    markdown += f"唯一编辑源：`{LEDGER}`。生成时间 {generated_at} 不代表重新测试或实机验收。\n\n"
    markdown += '\n'.join(table) + '\n\n发布状态：NOT_RELEASED。原始观察时间与哈希见 TASK_PROGRESS.json。\n'
    for task in progress['tasks']:
        if 'definition' not in task:
            continue
        definition = task['definition']
        markdown += f"\n## {task['id']} — {task['title']}\n\n"
        markdown += '依赖：' + ', '.join(task['depends_on']) + '\n\n'
        markdown += '历史映射（不代表验收）：' + ', '.join(task['predecessor_task_ids']) + '\n\n'
        markdown += '增量实施：' + definition['implementation'] + '\n\n验收：\n\n'
        markdown += '\n'.join('- ' + item for item in definition['acceptance']) + '\n\n'
        markdown += '回退：' + definition['rollback'] + '\n\n'
        if task['unresolved_conditions']:
            markdown += '未决案例条件：' + ', '.join(task['unresolved_conditions']) + '\n\n'
    cloud = {**common, 'schemaVersion': 'design-lab/cloud-baseline/v2', 'local': snapshot,
             'remoteRef': 'origin/main (local tracking ref)', 'cloudReadback': 'NOT_EXECUTED',
             'unavailable': ['currentRemoteSha', 'exactShaCI', 'openPullRequests', 'branchProtection'],
             'note': 'No GitHub API query was run by this generator; tool installation is not inferred.'}
    reconciled = []
    for adapter in (adapters or {}).get('adapters', []):
        reconciled.append({'adapterId': adapter.get('adapter_id'), 'tool': adapter.get('tool'),
                           'declaredStatus': adapter.get('status'), 'historicalDeclaredLevel': adapter.get('evidence', {}).get('level'),
                           'currentHostQualification': 'NOT_EXECUTED', 'reason': 'registry declarations are not current host receipts'})
    packs = []
    pack_root = reader.root/'design-lab/domain-packs'
    if pack_root.is_dir():
        for pack in sorted(pack_root.iterdir()):
            if pack.is_dir() and not pack.is_symlink():
                manifests = [p for p in pack.glob('*.json') if p.is_file()]
                for path in manifests:
                    reader.read(path.relative_to(reader.root).as_posix())
                packs.append({'domain': pack.name, 'contractJsonFiles': len(manifests), 'status': 'STRUCTURAL_ONLY', 'hostLive': 'NOT_EXECUTED'})
    reports = {
        'PROJECT_STATUS.json': _dump(status), 'PROJECT_STATUS.md': (markdown.rstrip() + '\n').encode('utf-8'),
        'TASK_PROGRESS.json': _dump({**common, **progress}),
        'CLOUD_BASELINE.json': _dump(cloud),
        'CLOUD_BASELINE.md': (f"# CLOUD_BASELINE\n\nGeneration-time local HEAD (not current): `{snapshot['sha']}`\n\nGeneration-time local origin/main: `{snapshot.get('origin_main')}`\n\nGitHub live readback / exact-SHA CI: NOT EXECUTED.\n").encode(),
        'ADAPTER_EVIDENCE_RECONCILIATION.json': _dump({**common, 'schemaVersion':'design-lab/adapter-reconciliation/v2',
                                                     'adapters':reconciled, 'capabilityIndexEntries':count(evidence_index,'capabilities')}),
        'KNOWLEDGE_INVENTORY.json': _dump({**common, 'schemaVersion':'design-lab/knowledge-inventory/v1',
                                         **status['sources'], 'migrationStatus':'deferred'}),
        'DOMAIN_PACK_READINESS.json': _dump({**common, 'schemaVersion':'design-lab/domain-readiness/v2', 'domainPacks':packs}),
        'RELEASE_READINESS.json': _dump({**common, 'schemaVersion':'design-lab/release-readiness/v2', 'status':'NOT_RELEASED',
                                       'blockers':[('DL-R5-015' if ledger['taskpack'] == 'DL-TP-20260908-R5' else 'R3-15') + ' acceptance', 'host evidence', 'rights/quality/release gates', 'exact-SHA delivery']})}
    if set(reports) != set(REPORTS):
        raise ValueError('report inventory does not match generated outputs')
    from .current_execution import update_reports
    return update_reports(reader, ledger, reports, common)


def _index_input_digest(reader, snapshot, report_names):
    """FU-10: the tracked report's PRIMARY freshness binding is an input digest,
    not a commit SHA. Canonical SHA-256 over (the exact input files the
    projections read, the git tree scope, and the report set), so it is
    recomputable at check time and independent of any self-referential SHA. The
    commit SHA remains only as generation-time observation (exact-SHA evidence
    belongs to the CI artifact, not the tracked record)."""
    import json as _json
    scope = {
        'worktree_digest': snapshot.get('worktree_digest'),
        'tracked_files': snapshot.get('tracked_files'),
        'clean': snapshot.get('source_worktree_clean'),
        'worktree_changes': snapshot.get('worktree_changes'),
    }
    payload = _json.dumps({'inputFiles': reader.hashes, 'treeScope': scope,
                           'reports': sorted(report_names)}, sort_keys=True,
                          separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(payload).hexdigest()


def validate_ledger_contract(root):
    """Check the single mutable ledger against its frozen contract only.

    `generate(check=True)` additionally compares generated output against a
    generation-time git snapshot, which a clean CI checkout can never reproduce.
    This entry point keeps the part that can: schema, R5 task/axis/evidence rules.
    """
    reader = Reader(Path(root).resolve())
    _validate(reader, reader.json(LEDGER))


def generate(root, *, check=False, snapshot=None, generated_at=None):
    root = Path(root).resolve()
    reader = Reader(root)
    supplied_snapshot = snapshot is not None
    snapshot = snapshot or git_snapshot(root)
    live_snapshot = snapshot
    if check:
        if not (root/INDEX).is_file():
            return [INDEX]
        # Index is an output, not an input hash (avoid self-reference).
        old = _json((root/INDEX).read_bytes())
        generated_at = old.get('generatedAt')
        if not isinstance(generated_at, str):
            return [INDEX]
        if not supplied_snapshot:
            observation = old.get('gitObservation')
            if not isinstance(observation, dict) or not re.fullmatch(r'[0-9a-f]{40}', str(observation.get('sha', ''))):
                return [INDEX]
            # The stored observation must be in this checkout's actual history.
            # Missing shallow history cannot be promoted to a valid observation.
            try:
                _git(root, 'merge-base', '--is-ancestor', observation['sha'], live_snapshot['sha'])
            except ValueError:
                return [INDEX]
            snapshot = observation
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds')
    reports = _build(reader, snapshot, generated_at)
    reader.stable()
    if not supplied_snapshot and git_snapshot(root) != live_snapshot:
        raise ValueError('Git state changed during report generation')
    index = {'schemaVersion':'design-lab/current-report-index/v3',
             'subjectSha':snapshot['sha'],
             'subjectMeaning': 'generation-time git observation, not a freshness claim; exact-SHA evidence is the CI artifact',
             'inputDigest':_index_input_digest(reader, snapshot, REPORTS),
             'inputDigestMeaning': 'primary freshness binding: canonical SHA-256 over the exact input files the '
                                   'projections read plus the git tree scope; recomputed at check time (FU-10)',
             'generatedAt':generated_at,
             'gitObservation': snapshot, 'checkScope': 'bound-input-and-output-integrity; not current Git or cloud freshness',
             'ledger':LEDGER, 'reports':list(REPORTS), 'reportRoot':'../../reports/current/',
             'inputHashes':reader.hashes, 'outputHashes':{name:hashlib.sha256(raw).hexdigest() for name,raw in reports.items()}}
    outputs = {CURRENT+name:raw for name,raw in reports.items()}
    outputs[INDEX] = _dump(index)
    if check:
        return [rel for rel,raw in outputs.items() if not (root/rel).is_file() or (root/rel).read_bytes()!=raw]
    stage_root = resolve_paths(project_root=root).category_dir('runtime', 'current-reports')
    stage_root.mkdir(parents=True, exist_ok=True)
    for relative, raw in outputs.items():
        target = _safe(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=stage_root, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return []
