// WUI-21 (2026-10-12) — the isolated-trial read surfaces: 方案 / 失败 / 读回.
//
// Three lanes, one component. What the pages are NOT allowed to do is write the pack's own rules:
//   · a stage is shown as `status（basis）`, never as a bare status. `basis=NO_PRODUCER` means nothing in
//     this repository observed that stage, and that must be legible next to any word that looks friendly;
//   · 超时只写「未知或超时」. UNKNOWN_OR_TIMEOUT is never folded into FAILED, because a lease expiring is
//     not an observation of failure;
//   · a missing section (producer not wired) and an empty section (wired, nothing there) are two
//     different statements and are rendered as two different sentences;
//   · no count is ever padded to 0, and there is no control on this surface at all — the Observer is
//     read-only, and a retry/stop button here would be a write affordance wearing a report's face.
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/states'
import type { IsolatedTrialRecord, OperationProgressRecord, SnapshotV3 } from '@/types'

export type TrialScene = 'plan' | 'failure' | 'readback'

const SCENE_TITLE: Record<TrialScene, string> = {
  plan: '隔离试用 · 方案',
  failure: '隔离试用 · 失败',
  readback: '隔离试用 · 读回',
}

const SCENE_DESCRIPTION: Record<TrialScene, string> = {
  plan: '每个任务在账本里的阶段、最后一次可信进度及其依据，以及本仓无法回答的阶段。',
  failure: '只有账本或已核对外部效应给出的失败才写失败；租约过期写「未知或超时」，取消后晚到结果不复活计划。',
  readback: '分离读回：写入、原生读回、目标行为各自带依据。没有依据的阶段只能显示 UNKNOWN，不能汇总成一句成功。',
}

function stage(st: { status: string; basis: string; note?: string } | undefined) {
  if (!st) return { text: 'UNKNOWN（NO_PRODUCER）', tone: 'muted' as const, note: '' }
  const note = st.note ? ` · ${st.note}` : ''
  if (st.basis === 'NO_PRODUCER') return { text: `${st.status}（NO_PRODUCER）`, tone: 'muted' as const, note }
  return { text: `${st.status}（${st.basis}）`, tone: 'info' as const, note }
}

function GapList({ gaps }: { gaps: string[] }) {
  if (!gaps || gaps.length === 0) return <span className="text-[12px] text-muted">本仓无声明缺口</span>
  return (
    <span className="font-mono text-xs text-muted">{gaps.join(' · ')}</span>
  )
}

function ProgressRows({ rows }: { rows: OperationProgressRecord[] }) {
  return (
    <div className="list">
      {rows.map((p) => (
        <div className="list-item" key={p.task_id ?? 'UNRESOLVED'} data-trial-progress={p.task_id ?? 'UNRESOLVED'}>
          <span className="font-mono text-xs">{p.task_id ?? 'UNRESOLVED'}</span>
          <span className="text-[12px]">
            <span data-progress-state={p.state}>{p.state}</span>
            {p.ledger_status ? ` · 账本 ${p.ledger_status}` : ' · 账本状态未读到'}
          </span>
          <span className="text-[12px] text-muted">
            最后可信进度：{p.last_trusted_progress.state ?? '—'} @ {p.last_trusted_progress.at ?? '—'}
            （{p.last_trusted_progress.basis}）
          </span>
        </div>
      ))}
    </div>
  )
}

function TrialRows({ rows, scene }: { rows: IsolatedTrialRecord[]; scene: TrialScene }) {
  return (
    <div className="list">
      {rows.map((t) => {
        const s = t.separated_results
        const shown =
          scene === 'failure'
            ? { write: stage(s.write), native: stage(s.native_readback), behaviour: stage(s.target_behaviour) }
            : scene === 'readback'
              ? { write: stage(s.write), native: stage(s.native_readback), behaviour: stage(s.target_behaviour) }
              : { write: stage(s.write), native: stage(s.native_readback), behaviour: stage(s.target_behaviour) }
        return (
          <div className="list-item flex-col items-start gap-1" key={t.trial_id ?? 'ABSENT'} data-trial-id={t.trial_id ?? 'ABSENT'}>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs">{t.trial_id ?? 'ABSENT'}</span>
              <span className="text-[12px] text-muted">
                父任务 {t.parent_task_id ?? '—'} · 子任务 {t.child_task_id ?? '—'} · 隔离{' '}
                {t.isolation?.basis === 'NONE' ? '未投影' : `${t.isolation?.basis}=${t.isolation?.value ?? '—'}`}
              </span>
            </div>
            <div className="flex flex-wrap gap-3 text-[12px]">
              <span data-trial-stage="write">写入 {shown.write.text}{shown.write.note}</span>
              <span data-trial-stage="native_readback">原生读回 {shown.native.text}{shown.native.note}</span>
              <span data-trial-stage="target_behaviour">目标行为 {shown.behaviour.text}{shown.behaviour.note}</span>
            </div>
            <GapList gaps={t.producer_gaps} />
          </div>
        )
      })}
    </div>
  )
}

export function IsolatedTrialView({ snap, scene = 'plan' }: { snap: SnapshotV3 | null; scene?: TrialScene }) {
  const progress = snap?.operationProgress
  const trials = snap?.isolatedTrials
  const progressAbsent = progress === undefined
  const trialsAbsent = trials === undefined

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={SCENE_TITLE[scene]} description={SCENE_DESCRIPTION[scene]} />

      <Card>
        <div className="mb-3.5 flex items-center justify-between gap-3">
          <h3 className="m-0">操作进度（worklab/operation-progress/v1）</h3>
          {progressAbsent ? (
            <span className="tag" data-state="SOURCE_GAP">生产者未投影</span>
          ) : progress && progress.length > 0 ? (
            <span className="tag info" data-state="PROJECTED">已投影</span>
          ) : (
            <span className="tag" data-state="EMPTY">已查询 · 无记录</span>
          )}
        </div>
        <CardContent>
          {progressAbsent ? (
            <EmptyState
              title="快照未携带该读模型"
              description="本仓尚未把 worklab/operation-progress/v1 投影进 v3 快照。Observer 保持 UNKNOWN，不以空列表冒充『无进行中操作』。"
            />
          ) : !progress || progress.length === 0 ? (
            <EmptyState title="已查询 · 无任务记录" description="生产者已投影该段，且账本里没有可回答的任务。这是『没有记录』，不是『都通过了』。" />
          ) : (
            <ProgressRows rows={progress} />
          )}
        </CardContent>
      </Card>

      <Card>
        <div className="mb-3.5 flex items-center justify-between gap-3">
          <h3 className="m-0">隔离试用（worklab/isolated-trial/v1）</h3>
          {trialsAbsent ? (
            <span className="tag" data-state="SOURCE_GAP">生产者未投影</span>
          ) : trials && trials.length > 0 ? (
            <span className="tag info" data-state="PROJECTED">已投影</span>
          ) : (
            <span className="tag" data-state="EMPTY">已查询 · 无记录</span>
          )}
        </div>
        <CardContent>
          {trialsAbsent ? (
            <EmptyState
              title="快照未携带该读模型"
              description="本仓尚未把 worklab/isolated-trial/v1 投影进 v3 快照。三个阶段都没有可核对的依据，因此这里只能是 UNKNOWN。"
            />
          ) : !trials || trials.length === 0 ? (
            <EmptyState title="已查询 · 无试用记录" description="生产者已投影该段，且没有可核对的试用。试用不存在与试用等待中，是两句话。" />
          ) : (
            <TrialRows rows={trials} scene={scene} />
          )}
        </CardContent>
      </Card>

      <div className="panel">
        <h3>失效条件与边界</h3>
        <div className="muted text-xs">
          计划在源/目标/范围/适配器/方案版本任一项变更时失效；本页只读，不提供发起、取消或重试入口——发起写入需要 owner 先决定授权目标面。
          超时只写「未知或超时」，取消后晚到的结果不复活计划；三方分离阶段没有聚合成功字段，任何一句结论都必须能指回它的 basis。
        </div>
      </div>
    </div>
  )
}

/* The three registry lanes. They forward the snapshot the shell already holds — a wrapper that closed
   over `snap={null}` would make every lane permanently read as "producer not wired". */
export const TrialPlanView = (props: { snap: SnapshotV3 | null }) => <IsolatedTrialView {...props} scene="plan" />
export const TrialFailureView = (props: { snap: SnapshotV3 | null }) => <IsolatedTrialView {...props} scene="failure" />
export const TrialReadbackView = (props: { snap: SnapshotV3 | null }) => <IsolatedTrialView {...props} scene="readback" />
