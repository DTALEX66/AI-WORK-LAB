# SPDX-License-Identifier: MIT
"""DL-UI-PLAN: one honest roll-up per project, for the desk's front page.

The 2026-10-22 Stitch design (screen D01) asks every project row to show what the project already
holds, what is waiting for a named human decision, and when it last moved. ``GET /api/projects``
answered that with ``{id, name, created_at}`` only, so a page could either guess or fan out one
request per project per resource.

Two rules the shape follows, both because the alternative is a lie the UI cannot see:

* a surface whose table has never been created on this checkout reports ``null`` and is named in
  ``absentSurfaces`` -- never ``0``. "This project holds none of that" and "nobody has opened that
  surface here" are different facts; the same split ``design-lab/schemas/native-runtime-readback.schema.json``
  makes with ABSENT/PRESENT, and the failure mode this project keeps hitting (an empty branch that
  counts as a verdict);
* the acceptance numbers are not re-derived here. Prompt-result signature states come from
  :meth:`design_lab.prompt_results.PromptResults.pending_counts`, which shares its ``_state_of``
  predicate with the prompt-result read-back, and the candidate counters come from that resource's
  own read-back. A roll-up that re-implements a verdict is how a front page and a detail page start
  disagreeing about who signed what.

``research_finding`` has no timestamp column, so it contributes a count and never a date; the native
``job`` table is not project-keyed, so native work is not counted here at all -- the native runtime
read-back is the surface that owns it.
"""
from __future__ import annotations

from contextlib import closing
import json
import sqlite3
from pathlib import Path

from .interop import load_schema, schema_errors
from .runtime.state_resources import repo_resource

PROJECT_LIST_VERSION = 'design-lab/project-list/v1'
# Read through `repo_resource`, not `PROJECT_ROOT`: three levels above an installed
# `site-packages/design_lab/runtime` is the interpreter's own `Lib`, so a `PROJECT_ROOT` read would
# make the desk's front page 500 on a wheel -- the same D09 defect the research and rights contracts
# already hit.
SCHEMA_PATH = repo_resource('schemas/project-list-v1.schema.json')

#: (key shown to the UI, table, timestamp column or None, count only the newest revision)
_SURFACES = (
    ('assets', 'asset', 'created_at', False),
    ('briefs', 'design_brief', 'created_at', False),
    ('currentBriefs', 'design_brief', 'created_at', 'live'),
    ('directions', 'design_direction', 'created_at', False),
    ('designSystemBindings', 'design_system_binding', 'created_at', False),
    ('designLayerEvents', 'design_layer_event', 'created_at', False),
    ('promptResults', 'prompt_result', 'created_at', False),
    ('knowledgeCandidates', 'knowledge_candidate', 'recorded_at', 'latest'),
    ('juryRecords', 'jury_record', 'decided_at', False),
    ('rightsDecisions', 'rights_decision', 'decided_at', False),
    ('researchFindings', 'research_finding', None, False),
    ('creativeJobs', 'creative_job', 'created_at', False),
    ('modelSelectionRevisions', 'model_selection', 'recorded_at', False),
    ('qualityRecords', 'quality_record', 'created_at', False),
)

SURFACE_RULE = ('计数为 null 表示该表面的表在此检出从未创建（见 absentSurfaces）；'
                '0 表示表在、这个项目里确实一条都没有。两者不可互换。')

DOES_NOT_SAY = (
    '对象计数说的是这台服务此刻存了多少条记录，不是这个项目完成了多少，也不是它被谁验收过。',
    'waiting 里的数字是"还没有一个具名人对它签过字"；签过字的ACCEPTED不证明被导出、被发送或被任何模型执行。',
    'absentSurfaces 列出的表面在此检出上从未建表，所以它的计数是 null，不是 0，也不是"没有内容"。',
    'last_activity_at 是本项目已存记录里最晚的那个时间戳，只覆盖本投影读到的表；原生 job 不按项目建键，'
    '不在此列，它的事实由 native-runtime 读回负责。',
)


class ProjectIndexError(ValueError):
    """The roll-up contradicts its own contract; the route answers 500 with this code."""


class ProjectIndex:
    """Project rows plus the counts and pending decisions the desk needs to show them honestly."""

    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def list(self) -> dict:
        rows = self.service.list_projects()
        if not rows:
            return _checked({'schemaVersion': PROJECT_LIST_VERSION, 'projects': [],
                             'surfaceRule': SURFACE_RULE, 'does_not_say': list(DOES_NOT_SAY)})
        with closing(sqlite3.connect(
                f'file:{self.paths.database_path(self.service.database)}?mode=ro',
                uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            present = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            projects = [self._one(conn, present, row) for row in rows]
        return _checked({'schemaVersion': PROJECT_LIST_VERSION, 'projects': projects,
                         'surfaceRule': SURFACE_RULE, 'does_not_say': list(DOES_NOT_SAY)})

    def _one(self, conn, present, row) -> dict:
        project_id = row['id']
        objects, absent, stamps = {}, [], []
        for key, table, stamp, mode in _SURFACES:
            if table not in present:
                objects[key] = None
                absent.append(key)
                continue
            objects[key] = _count(conn, table, project_id, mode)
            if stamp is not None:
                latest = _latest(conn, table, stamp, project_id, mode)
                if latest:
                    stamps.append(latest)
        return {
            **row,
            'objects': objects,
            'absentSurfaces': absent,
            'last_activity_at': max(stamps) if stamps else None,
            'waiting': self._waiting(conn, project_id, present),
        }

    def _waiting(self, conn, project_id, present) -> dict:
        """Counts nobody has decided yet, taken from the resources that own those verdicts."""
        from .knowledge_review import KnowledgeReview
        from .prompt_results import PromptResults

        waiting = {'promptResultsUnsigned': None, 'promptResultsNotCurrent': None,
                   'knowledgeCandidatesPendingReview': None,
                   'knowledgeCandidatesExportReady': None}
        if 'prompt_result' in present:
            counts = PromptResults(self.service).pending_counts(project_id)
            # Unsigned and "signed but describes other bytes" both need a person; they are counted
            # apart because the remedy differs -- one is a first decision, the other a re-check.
            waiting['promptResultsUnsigned'] = counts['unreviewed']
            waiting['promptResultsNotCurrent'] = counts['not_current']
        if 'knowledge_candidate' in present:
            review = KnowledgeReview(self.service).list(project_id)
            waiting['knowledgeCandidatesPendingReview'] = review['pending_review_count']
            waiting['knowledgeCandidatesExportReady'] = review['export_ready_count']
        return waiting


def _count(conn, table, project_id, mode) -> int:
    if mode == 'latest':
        return conn.execute(
            'SELECT COUNT(*) FROM {table} k WHERE k.project_id = ? AND k.revision = ('
            ' SELECT MAX(m.revision) FROM {table} m'
            ' WHERE m.project_id = k.project_id AND m.candidate_id = k.candidate_id)'
            .format(table=table), (project_id,)).fetchone()[0]
    if mode == 'live':
        return conn.execute(
            f'SELECT COUNT(*) FROM {table} WHERE project_id = ?'
            ' AND superseded_by IS NULL', (project_id,)).fetchone()[0]
    return conn.execute(f'SELECT COUNT(*) FROM {table} WHERE project_id = ?',
                        (project_id,)).fetchone()[0]


def _latest(conn, table, stamp, project_id, mode) -> str | None:
    if mode == 'live':
        return conn.execute(
            f'SELECT MAX({stamp}) FROM {table} WHERE project_id = ?'
            ' AND superseded_by IS NULL', (project_id,)).fetchone()[0]
    return conn.execute(f'SELECT MAX({stamp}) FROM {table} WHERE project_id = ?',
                        (project_id,)).fetchone()[0]


def _checked(envelope: dict) -> dict:
    """Refuse to ship a roll-up that contradicts its own contract file."""
    from .interop import InteropError

    try:
        problems = schema_errors(load_schema(SCHEMA_PATH), envelope)
    except InteropError as exc:
        raise ProjectIndexError(f'project list contract cannot be applied: {exc}') from None
    if problems:
        raise ProjectIndexError(
            f'{PROJECT_LIST_VERSION} violated by its own roll-up: '
            + json.dumps(problems[:3], ensure_ascii=False))
    return envelope
