// WUI-02 · the object-detail surface for a project (master page 02_project_detail).
//
// The taskpack's first slice asks for 对象详情骨架 with collaboration living INSIDE it, and the data
// contract (docs/history/owner-inputs/20261009/ui-readable/docs/03_数据与状态合同.md) says a detail is
// read by full namespace identity — a name, a remote or a PID is not an identity. So this page is
// addressed by `?projectId=`, on the same single URL mechanism that already carries taskId /
// executionId, and it resolves against `snap.projects` by that id and nothing else.
//
// What it refuses to do:
// * fall back to "the first project" when the addressed id is absent — a wrong identity is worse than
//   an empty page, so the wanted id is kept and named in the message;
// * merge 工作 / 健康 / 观测 into one status dot; each axis states its own source and its own UNKNOWN;
// * invent a collaboration record. Nothing has been sent to a peer in this slice, so the summary says
//   未接入 with the reason, per WUI-11 ("协作未接入不伪造接收").
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState, UnknownState } from '@/components/ui/states'
import { Dim } from '@/views/RecordInspector'
import { fmtTimestamp, fmtTokens, fmtCostQuality } from '@/lib/api'
import { resolveFocus, recordLink, EMPTY_FOCUS, type RecordFocus } from '@/lib/recordFocus'
// WUI-04: identity facts and the named limits of the projection, from one module the home and the
// detail share so the two pages cannot disagree about what `projectId` can and cannot answer.
import { PROJECT_IDENTITY_GAPS, duplicateDisplayNames, participantsOf } from '@/lib/projectIdentity'
import type { Execution, Project, SnapshotV3 } from '@/types'

export interface ProjectDetailViewProps {
  snap: SnapshotV3 | null
  focus?: RecordFocus
  /**
   * Deliberately absent: `onFocus`. Every way out of this page is a LINK (the clear/fallback affordances
   * below and the row links on 项目监控), so the detail surface never needs to write the address through
   * a callback. Registering a prop it does not use would be a control that looks wired and is not.
   */
  focusRejected?: string[]
}

const ACTIVITY_TEXT: Record<string, string> = {
  ACTIVE: '运行中', REGISTERED: '已登记', IDLE: '空闲', UNKNOWN: '未知',
}

const ATTENTION_TEXT: Record<string, string> = {
  NONE: '无提示', WAITING: '等待输入', BLOCKED: '受阻', DRIFT: '漂移', FAILED: '失败',
}

const GIT_TEXT: Record<string, string> = {
  MATCH: '本地=远端', UNVERIFIED: '未核验', DRIFT: '漂移', UNKNOWN: '未知',
}

/** Distinct participating software comes from `lib/projectIdentity`, shared with the home table. */

export function ProjectDetailView({
  snap, focus = EMPTY_FOCUS, focusRejected = [],
}: ProjectDetailViewProps) {
  const wanted = focus.projectId ?? null
  const state = resolveFocus(wanted, snap?.projects ?? [], (p) => p.projectId)
  const search = typeof window !== 'undefined' ? window.location.search : ''

  const executionsForProject = (projectId: string): Execution[] =>
    (snap?.executions ?? []).filter((e) => e.anchorProjectId === projectId)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="项目详情"
        description="按完整命名空间身份读取单个项目：目录/worktree 归属、参与软件、三轴状态、来源新鲜度、已知用量与协作摘要。只读投影，不派工、不改状态。"
      />

      {focusRejected.length > 0 && (
        <Card>
          <CardHeader><span>地址被拒绝</span></CardHeader>
          <CardContent>
            <ul className="list m-0 flex flex-col gap-1.5 text-[12px] text-warning">
              {focusRejected.map((reason) => <li key={reason} className="list-item">{reason}</li>)}
            </ul>
          </CardContent>
        </Card>
      )}

      {!snap && (
        <Card>
          <CardHeader><span>项目详情</span></CardHeader>
          <CardContent>
            <UnknownState
              title="数据源未接入"
              description="快照未到达，项目身份无从解析。保持 UNKNOWN：不预选任何一个项目。"
            />
          </CardContent>
        </Card>
      )}

      {snap && state.kind === 'unasked' && (
        <Card>
          <CardHeader><span>未定位项目</span></CardHeader>
          <CardContent>
            <EmptyState
              title="地址里没有 projectId"
              description={
                snap.projects.length
                  ? `快照投影了 ${snap.projects.length} 个项目，但详情页需要一条明确的项目身份 —— 同名项目可能有多个目录。`
                  : '快照已接入，但项目集合为空（已查询，无项目）—— 这不是缺源。'
              }
              action={(
                <a
                  href={recordLink('overview', { taskId: null, executionId: null }, search)}
                  className="text-secondary-ink text-[12px]"
                  data-testid="project-detail-goto-home"
                >
                  从项目监控选择
                </a>
              )}
            />
          </CardContent>
        </Card>
      )}

      {snap && (state.kind === 'backend-not-provided' || state.kind === 'not-found') && (
        <Card>
          <CardHeader><span>项目身份无法解析</span></CardHeader>
          <CardContent>
            <UnknownState
              title={state.kind === 'not-found' ? '该项目不在投影里' : '后端未提供项目集合'}
              description={
                state.kind === 'not-found'
                  ? // The addressed id is echoed back verbatim and NOTHING else is rendered in its place.
                    `地址要求 projectId=${state.wanted}，快照的 projects 中没有这个身份（未投影 / 属其他来源 / 已注销）。这里不会改选同名或最像的另一项目。`
                  : '快照没有携带 projects 字段，因此无从按身份解析。这与「查询过但没有项目」是两件事。'
              }
            />
            {state.kind === 'not-found' && (
              <div className="mt-2 text-[12px] text-muted">
                原身份保留供复制：<span className="font-mono text-ink">{state.wanted}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {snap && state.kind === 'matched' && (() => {
        const project = state.record
        const executions = executionsForProject(project.projectId)
        const blocked = executions.filter((e) => e.state === 'BLOCKED'
          || e.state === 'WAITING_USER' || e.state === 'WAITING_APPROVAL' || e.state === 'FAILED')
        const platforms = participantsOf(snap, project)
        const duplicateNames = duplicateDisplayNames(snap.projects ?? [])
        return (
          <>
            <Card>
              <CardHeader>
                <span>身份（命名空间）</span>
                <span className="text-[12px] text-muted">projectId · 唯一寻址键</span>
              </CardHeader>
              <CardContent>
                <div className="list">
                  <Dim label="Project ID" value={project.projectId} />
                  <Dim label="显示名" value={project.displayName}
                       hint="显示名可为 null，身份只认 projectId" />
                  <Dim label="身份状态" value={project.identityState} />
                  <Dim label="可见性" value={project.visibility} />
                  <Dim label="数据质量" value={project.quality} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>目录 / worktree 归属</span>
                <span className="text-[12px] text-muted">非 Git、多目录与多 worktree 不合并</span>
              </CardHeader>
              <CardContent>
                <div className="list">
                  <Dim label="工作区（workingAreas）"
                       value={project.workingAreas.length ? project.workingAreas.join(' · ') : null}
                       hint="由执行记录聚合：空列表表示没有执行登记过工作区，不等于项目没有目录" />
                  {/* The producer reads `repositories` with a default of [] from a row builder that never
                      writes the key, so an empty list is a producer gap. Claiming 已投影·结果为空 here
                      would be the exact lie this page exists to avoid. */}
                  <Dim label="仓库条目" value={null}
                       hint={'snapshot_api.py 以 project.get("repositories", []) 读取，composition_root.py 的行构造器从不写该键 —— 空数组是生产者缺口，不是「无仓库」'} />
                  <Dim label="分支" value={project.git.branch} />
                  <Dim label="本地 SHA" value={project.git.localSha} />
                  <Dim label="远端 SHA" value={project.git.remoteSha} />
                  <Dim label="本地/远端一致性"
                       value={project.git.matchState ? GIT_TEXT[project.git.matchState] ?? project.git.matchState : null} />
                  <Dim label="脏文件计数"
                       value={project.git.dirtyCount == null ? null : String(project.git.dirtyCount)}
                       hint="git.dirtyCount 为 null：未测量，不是 0" />
                  <Dim label="来源引用"
                       value={project.sourceRefs.length ? project.sourceRefs.join(' · ') : null}
                       hint="sourceRefs 为空 —— 这条项目身份没有可点名的来源" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>身份能回答到什么程度</span>
                <span className="text-[12px] text-muted">生产者缺口，不由界面补全</span>
              </CardHeader>
              <CardContent>
                {/* WUI-04 asks for non-Git / multi-directory / worktree / same-name to stay unmerged.
                    The snapshot answers with one key; these are the questions it does not, stated with
                    the reason rather than resolved by a guess in the browser. */}
                <div className="list">
                  {PROJECT_IDENTITY_GAPS.map((gap) => (
                    <Dim key={gap.key} label={gap.question} value={null} hint={gap.reason} />
                  ))}
                </div>
                {duplicateNames.size > 0 && (
                  <div className="mt-3 text-[12px] text-warning">
                    快照中有 {duplicateNames.size} 个显示名被多个 projectId 共用，因此本页只按 projectId
                    读取；同名项目不会被合并或互相顶替。
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>参与软件</span>
                <span className="text-[12px] text-muted">
                  {platforms.length ? `${platforms.length} 个已投影名称` : '无名称投影'}
                </span>
              </CardHeader>
              <CardContent>
                {platforms.length === 0 ? (
                  <UnknownState
                    title="参与软件集合未投影"
                    description="项目与执行都没有携带可命名的 agent / platform 字段。缺失即 UNKNOWN，不代表该项目没有被软件参与。"
                  />
                ) : (
                  <div className="status-stack">
                    {platforms.map((name) => <Badge key={name} variant="info">{name}</Badge>)}
                  </div>
                )}
                <div className="mt-3 text-[12px] text-muted">
                  安装身份、版本与字段资格属于「软件环境」，本页不重复投影，也不把参与名称当作已接入证据。
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>三轴状态（分开，不合并成一个点）</span>
                <span className="text-[12px] text-muted">工作 · 健康 · 观测</span>
              </CardHeader>
              <CardContent>
                <div className="list">
                  <Dim label="工作轴 · 活动"
                       value={ACTIVITY_TEXT[project.activityState] ?? project.activityState} />
                  <Dim label="工作轴 · 活跃执行计数"
                       value={String(project.activeExecutionCount)}
                       hint="计数为 null 时不补 0" />
                  <Dim label="工作轴 · 执行状态分布"
                       value={executions.length
                         ? executions.map((e) => `${e.state}×1`).join(' · ')
                         : '该项目名下快照未带执行记录（已查询）'} />
                  <Dim label="健康轴 · 关注度"
                       value={ATTENTION_TEXT[project.attentionState] ?? project.attentionState} />
                  <Dim label="健康轴 · Git 质量" value={project.git.quality} />
                  <Dim label="健康轴 · 受阻 / 待输入的执行"
                       value={blocked.length
                         ? blocked.map((e) => `${e.executionId || 'exec'}(${e.state})`).join(' · ')
                         : '0 条（来自上面的执行分布，不是推测）'} />
                  <Dim label="观测轴 · 传输" value={snap.transport?.transportState ?? null} />
                  <Dim label="观测轴 · 新鲜度" value={snap.transport?.freshnessState ?? null} />
                  <Dim label="观测轴 · 最后强证据时间"
                       value={project.lastStrongEvidenceAt ? fmtTimestamp(project.lastStrongEvidenceAt) : null}
                       hint="lastStrongEvidenceAt 为 null —— 没有强证据时间，不等于从未观测" />
                </div>
                <div className="mt-3 text-[12px] text-muted">
                  断连、滞后或窗口关闭都不推出「软件已停止」；本页只表达最后可见快照。
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>已知用量</span>
                <span className="text-[12px] text-muted">质量随字段，不补 0</span>
              </CardHeader>
              <CardContent>
                <div className="list">
                  <Dim label="输入 Token" value={fmtTokens(project.token?.inputTokens ?? null)} />
                  <Dim label="输出 Token" value={fmtTokens(project.token?.outputTokens ?? null)} />
                  <Dim label="总 Token" value={fmtTokens(project.token?.totalTokens ?? null)} />
                  <Dim label="成本质量" value={fmtCostQuality(project.token?.costQuality)} />
                  <Dim label="缓存口径 / 命中率" value={null}
                       hint="v3 快照未投影缓存读取分母与可判断请求数，不在前端造比率" />
                </div>
                <div className="mt-3 text-[12px] text-muted">
                  缓存写入不算读命中；没有同口径分母时不显示百分比。计量细节属于「用量缓存」。
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <span>协作摘要</span>
                <span className="tag warn">未接入</span>
              </CardHeader>
              <CardContent>
                {/* WUI-11: a collaboration summary that has not been wired says so. Each stage of the
                    chain is its own claim, so "candidate exists" can never read as "peer received it". */}
                <div className="list">
                  <Dim label="本方候选" value={null} hint="本轮未生成本对象的候选件" />
                  <Dim label="出域授权" value={null} hint="未申请，未获准，因此没有发送" />
                  <Dim label="对端接收" value={null} hint="无真实对端回执 —— 不代表对端拒绝" />
                  <Dim label="技术校验" value={null} hint="未在同版本上跑过校验" />
                  <Dim label="专业接受 / 真人学习" value={null}
                       hint="属 DESIGN-LAB 与 AAOS 的判断，不由本界面推断" />
                </div>
                <div className="mt-3 text-[12px] text-muted">
                  协作是按需通道，不是本页的前置。核心观测与详情不依赖任何对端存在。
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><span>只读边界</span></CardHeader>
              <CardContent className="text-xs text-muted">
                本页仅投影 v3 快照已携带的字段：不发起执行、不改任务状态、不写回配置，
                也不把项目级 CI 运行冒充为项目当前结论。未携带的维度显式标记为来源缺口。
              </CardContent>
            </Card>
          </>
        )
      })()}
    </div>
  )
}
