// WUI-01 · the project collection that makes 项目监控 the home page (master page 01_projects).
//
// The landing lane used to open on KPI cards, a trend panel with no series behind it and a signal map of
// six hardcoded nodes. None of that answered the owner's question for the home page — which projects are
// involved, which software took part, what is blocking them, how fresh is what we see, what is already
// known about their usage. So this table replaces the decoration, and every cell is a projected field:
//
// * 工作 / 健康 / 观测 stay three columns, because WUI-04 and the data contract forbid one merged dot;
// * a null stays a named absence (未投影 / 未测量), never 0 — the repo's UNKNOWN-not-0 rule;
// * the row's action is a LINK to the object detail, so selecting a project cannot trigger a business task.
import * as React from 'react'
import { DataTable, type DataTableColumn } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { UnknownState } from '@/components/ui/states'
import { fmtTokens, fmtCostQuality, fmtTimestamp } from '@/lib/api'
import { recordLink } from '@/lib/recordFocus'
// WUI-04: one identity module for the home and the detail, so the same-name rule is stated once.
import { duplicateDisplayNames, participantsOf } from '@/lib/projectIdentity'
import type { Execution, Project, SnapshotV3 } from '@/types'

const ACTIVITY_TEXT: Record<string, string> = {
  ACTIVE: '运行中', REGISTERED: '已登记', IDLE: '空闲', UNKNOWN: '未知',
}

/** A missing field is named as a missing field. Rendering `—` would read as "measured, nothing there". */
const NOT_PROJECTED = '未投影'

interface Row {
  project: Project
  executions: Execution[]
}

function blockedOf(executions: Execution[]): Execution[] {
  return executions.filter((e) => e.state === 'BLOCKED'
    || e.state === 'WAITING_USER' || e.state === 'WAITING_APPROVAL' || e.state === 'FAILED')
}

export interface ProjectSummaryTableProps {
  snap: SnapshotV3 | null
  /** the query string is read here so a detail link keeps theme / layout / api params */
  search?: string
}

export function ProjectSummaryTable({ snap, search = '' }: ProjectSummaryTableProps) {
  const [query, setQuery] = React.useState('')
  const rows: Row[] = React.useMemo(() => {
    if (!snap) return []
    const executionsByProject = new Map<string, Execution[]>()
    for (const execution of snap.executions ?? []) {
      if (!execution.anchorProjectId) continue
      const bucket = executionsByProject.get(execution.anchorProjectId)
      if (bucket) bucket.push(execution)
      else executionsByProject.set(execution.anchorProjectId, [execution])
    }
    return (snap.projects ?? []).map((project) => ({
      project,
      executions: executionsByProject.get(project.projectId) ?? [],
    }))
  }, [snap])

  // Filtering is display-only: it never asks the source for more data, and never starts a task.
  const needle = query.trim().toLowerCase()
  const visible = needle
    ? rows.filter(({ project }) => [project.projectId, project.displayName ?? '', project.agentPlatform ?? '']
      .some((value) => value.toLowerCase().includes(needle)))
    : rows
  // WUI-04: two projects may share a display name. The row keeps both and marks the collision, because a
  // name-only link is exactly how the wrong project gets opened.
  const duplicateNames = React.useMemo(
    () => duplicateDisplayNames(snap?.projects ?? []),
    [snap],
  )

  const columns: DataTableColumn<Row>[] = [
    {
      key: 'project',
      header: '项目',
      cell: ({ project }) => (
        <div className="min-w-0">
          <div className="truncate text-[12px] font-semibold text-ink">
            {project.displayName || NOT_PROJECTED}
          </div>
          <div className="truncate font-mono text-[12px] text-muted">{project.projectId}</div>
          {project.displayName && duplicateNames.has(project.displayName) && (
            <div className="text-[12px] text-warning" data-testid={`same-name-${project.projectId}`}>
              同名未合并 · 按 projectId 区分
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'software',
      header: '参与软件',
      cell: ({ project }) => {
        const names = snap ? participantsOf(snap, project) : []
        if (!names.length) return <span className="text-[12px] text-warning">{NOT_PROJECTED}</span>
        return <span className="text-[12px] text-ink">{names.join(' · ')}</span>
      },
    },
    {
      key: 'work',
      header: '工作轴',
      cell: ({ project }) => (
        <Badge variant={project.activityState === 'ACTIVE' ? 'info' : 'muted'}>
          {ACTIVITY_TEXT[project.activityState] ?? project.activityState}
          <span className="ml-1 tabular-nums text-[12px] text-muted">
            {project.activeExecutionCount == null ? NOT_PROJECTED : `活跃 ${project.activeExecutionCount}`}
          </span>
        </Badge>
      ),
    },
    {
      key: 'health',
      header: '健康轴',
      cell: ({ project }) => (
        <span className="text-[12px] text-ink">
          {project.attentionState || NOT_PROJECTED}
          <span className="ml-1 text-muted">· git {project.git?.matchState ?? NOT_PROJECTED}</span>
        </span>
      ),
    },
    {
      key: 'observation',
      header: '观测轴',
      cell: ({ project }) => (
        <span className="text-[12px] text-ink">
          {project.git?.freshness || NOT_PROJECTED}
          <span className="ml-1 text-muted">· 观测 {project.git?.observedAt ? fmtTimestamp(project.git.observedAt) : NOT_PROJECTED}</span>
        </span>
      ),
    },
    {
      key: 'freshness',
      header: '最后强证据',
      cell: ({ project }) => (
        <span className="text-[12px] text-ink">
          {project.lastStrongEvidenceAt ? fmtTimestamp(project.lastStrongEvidenceAt) : '无强证据时间'}
        </span>
      ),
    },
    {
      key: 'usage',
      header: '已知用量',
      align: 'right',
      cell: ({ project }) => (
        <span className="text-[12px] text-ink">
          {fmtTokens(project.token?.totalTokens ?? null)}
          <span className="ml-1 text-muted">{fmtCostQuality(project.token?.costQuality)}</span>
        </span>
      ),
    },
    {
      key: 'blocker',
      header: '主要阻碍',
      cell: ({ executions }) => {
        const blocked = blockedOf(executions)
        if (!blocked.length) {
          return <span className="text-[12px] text-muted">本投影内无受阻执行（不等于无阻碍）</span>
        }
        return (
          <span className="text-[12px] text-error">
            {blocked.length} 条 · {blocked.map((e) => e.state).join(' / ')}
          </span>
        )
      },
    },
    {
      key: 'detail',
      header: '详情',
      cell: ({ project }) => (
        <a
          href={recordLink('project-detail', { taskId: null, executionId: null, projectId: project.projectId }, search)}
          className="text-[12px] text-secondary-ink"
          data-testid={`project-detail-link-${project.projectId}`}
        >
          打开项目详情
        </a>
      ),
    },
  ]

  if (!snap) {
    return (
      <UnknownState
        title="项目集合未到达"
        description="快照未接入，因此没有任何项目行。这里不预填项目，也不显示空表冒充「已查询且为空」。"
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-[12px] text-muted" htmlFor="project-filter">
          筛选项目（只改变显示，不请求更多源端采集）
        </label>
        <input
          id="project-filter"
          type="search"
          className="input min-w-[200px] flex-1"
          value={query}
          placeholder="项目名 / projectId / 软件名"
          onChange={(event) => setQuery(event.target.value)}
        />
        <span className="text-[12px] text-muted tabular-nums" data-testid="project-row-count">
          {visible.length} / {rows.length} 个项目
        </span>
      </div>
      <DataTable
        columns={columns}
        rows={visible}
        rowKey={(row) => row.project.projectId}
        empty={needle
          ? `筛选「${needle}」没有匹配到项目行（快照里有 ${rows.length} 个项目），不清空已有投影，也不改用别的筛选条件重述结果`
          : '快照已查询，项目集合为空 —— 这是「无项目」，不是「未投影」'}
      />
    </div>
  )
}
