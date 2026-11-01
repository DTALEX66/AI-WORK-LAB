// WUI-09 (20261009) · 规则适配与三方差异界面 —— 落点页。
//
// 01_页面与交互清单.md 把它拆成两行：`09_rules`（规则意图、原生投影、写入/加载/验证、漂移）与
// `10_rule_diff`（前态/发布态/原生现态、目标与摘要、最小差异、恢复条件 → 保留现态、限定合并方案）。
// 02_视觉与组件规范.md 给这一族组件的名字是 `RuleProjection / ThreeWayDiff`，状态词是
// 「写入、加载、验证、冲突」，边界是「保护现态，限定恢复」。本页是这两行在同一个车道里的落点。
//
// 既有的规则适配车道是 `src/views/RulesPolicyView.tsx`（治理家族状态带）。本页不重写它、不删它：
// 家族状态沿用同一判据（UNKNOWN 就是 UNKNOWN，drift null 不是 0），本页补的是它没有答的那几问 ——
// 五阶段、三方差异、归属范围与写/恢复边界。
//
// 三态口径来自 `src/views/RecordInspector.tsx` 的 renderDimension（PROJECTED / NULL_FIELD /
// SOURCE_GAP），一行一 origin，缺口带生产者原因。真值判定全部在 `src/lib/ruleProjectionTruth.ts`，
// 这里只负责把它画出来，因此本页没有业务分支可以造假。
//
// 只读纪律（apps/observer/AGENTS.md）：本页不渲染任何写控件 —— 没有 Button、没有 input、没有 form，
// 出路只有 `<a>` 链接（清除定位）。写资格由服务端判定（WUI-10），本页明说「本界面不能授予写权限」。
import * as React from 'react'
import type { SnapshotV3 } from '@/types'
import type { RecordFocus } from '@/lib/recordFocus'
import { EMPTY_FOCUS, recordLink } from '@/lib/recordFocus'
import {
  driftReadbackRow, familySummary, ownershipRows, PRODUCER, READ_ONLY_STATEMENT, ruleFamilies,
  stageProjectedCount, stageRows, threeWayRows, THREE_WAY_GAP,
} from '@/lib/ruleProjectionTruth'
import { renderDimension } from '@/views/RecordInspector'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { PageHeader } from '@/components/ui/page-header'
import { UnknownState } from '@/components/ui/states'
import { StatusPill } from '@/components/ui/status'
import type { FamilyState } from '@/types'

type Snap = SnapshotV3 | null

export interface RuleAdaptationViewProps {
  snap: Snap
  /** 地址里的记录定位；本页的治理面是快照级，不按项目切分，所以只用于如实说明这一点。 */
  focus?: RecordFocus
  onFocus?: (next: RecordFocus) => void
  /** 地址被校验层拒绝的标识与原因，逐条显示，不静默丢弃。 */
  focusRejected?: string[]
}

/** 家族状态词与 RulesPolicyView 同一套可见词汇（干净/漂移/未知），只是绝不把 UNKNOWN 画成前者。 */
function stateVariant(s: FamilyState): 'success' | 'warning' | 'muted' {
  switch (s) {
    case 'CLEAN': return 'success'
    case 'DRIFT': return 'warning'
    default: return 'muted'
  }
}

function stateLabel(s: FamilyState): string {
  switch (s) {
    case 'CLEAN': return '干净'
    case 'DRIFT': return '漂移'
    default: return '未知'
  }
}

const search = (): string => (typeof window === 'undefined' ? '' : window.location.search)

export function RuleAdaptationView({
  snap, focus = EMPTY_FOCUS, onFocus = () => {}, focusRejected = [],
}: RuleAdaptationViewProps) {
  const families = ruleFamilies(snap)
  const summary = familySummary(snap)
  const stages = stageRows(snap)
  const stagesProjected = stageProjectedCount(snap)
  const threeWay = threeWayRows(snap)
  const driftRow = driftReadbackRow(snap)
  const ownership = ownershipRows(snap)
  const clearHref = recordLink('', EMPTY_FOCUS, search())
  const clearFocus = (event: React.MouseEvent) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
      || event.shiftKey || event.altKey) return
    event.preventDefault()
    onFocus(EMPTY_FOCUS)
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="规则适配 · 三方差异"
        description={
          '规则/配置治理的五阶段（意图 / 投影生成 / 写入 / 原生加载 / 行为验证）、'
          + '前态-本方发布态-原生现态的三方比较、归属范围与恢复边界。严格只读投影：'
          + '快照里没有的字段一律渲染为具名来源缺口并附生产者原因，不渲染成空表、不写成「无漂移」、不写成「已验证」。'
        }
      />

      {focusRejected.length > 0 && (
        <Card>
          <CardHeader><span>定位被拒绝</span></CardHeader>
          <CardContent>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {focusRejected.map((reason) => (
                <li key={reason} className="list-item text-[12px] text-warning">{reason}</li>
              ))}
            </ul>
            <p className="mt-2 text-[12px] text-muted">
              非法标识不参与任何查询；本页的治理面本身也不接受按记录定位。
              <a href={clearHref} onClick={clearFocus} className="ml-1" data-testid="rule-adaptation-clear">清除定位</a>
            </p>
          </CardContent>
        </Card>
      )}

      {focus.projectId && (
        <Card>
          <CardHeader><span>地址里的项目</span></CardHeader>
          <CardContent>
            <p className="m-0 text-[12px] text-ink">
              定位 projectId={focus.projectId} —— 但本页回答的是快照级治理面：governance.families 是四个全局家族
              （{PRODUCER.snapshotGovernance}），快照没有 project↔rule 外键，所以这条规则集不属于、也不针对该项目。
              项目级事实请看「项目详情」车道。
            </p>
            <a href={clearHref} onClick={clearFocus} className="mt-1 inline-block text-[12px]"
              data-testid="rule-adaptation-project-focus-clear">清除项目定位</a>
          </CardContent>
        </Card>
      )}

      {/* ---------------- 家族状态带（与 RulesPolicyView 同一判据） ---------------- */}
      <Card data-block="families">
        <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
          <h3 className="m-0">治理家族状态（只读投影）</h3>
          <span className="flex items-center gap-2">
            <StatusPill variant={summary.anyEvidence ? 'info' : 'muted'}>
              {summary.anyEvidence ? '携带真实明细' : '无明细（UNKNOWN）'}
            </StatusPill>
            <span className="text-[12px] text-muted">
              governance.state：{summary.governanceState ?? '未知（快照未到达）'}
            </span>
          </span>
        </div>
        <CardContent>
          {!snap && (
            <UnknownState
              title="数据源未接入"
              description="快照未到达，四族状态与五阶段全部保持 UNKNOWN；本页不预选、不补零、不推断。"
            />
          )}
          <div className="list">
            {families.map((family) => (
              <div key={family.key} className="list-item" data-family={family.key}
                data-state={family.state} data-evidence={family.hasEvidence ? 'present' : 'gap'}>
                <div className="min-w-0">
                  <strong className="block text-[13px] font-semibold text-ink">{family.label}</strong>
                  <span className="block text-[12px] text-secondary-ink">
                    漂移计数：{family.driftText}
                  </span>
                  <span className="block text-[12px] text-muted">
                    current：{family.currentText}
                    {family.note ? ` · ${family.note}` : ''}
                  </span>
                </div>
                <StatusPill variant={stateVariant(family.state)}>{stateLabel(family.state)}</StatusPill>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-muted">
            这一族状态带与既有「规则适配」车道（src/views/RulesPolicyView.tsx）同源同判据；
            本页不因某族 CLEAN 就把任何阶段推进为通过（见下方阶段块）。
          </p>
        </CardContent>
      </Card>

      {/* ---------------- 五阶段 ---------------- */}
      <Card data-block="stages">
        <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
          <h3 className="m-0">五阶段状态（意图 / 投影生成 / 写入 / 原生加载 / 行为验证）</h3>
          <StatusPill variant={stagesProjected > 0 ? 'info' : 'muted'}>
            {stagesProjected > 0 ? `${stagesProjected} / ${stages.length} 行来自投影` : '无一行来自投影字段'}
          </StatusPill>
        </div>
        <CardContent>
          {/* 每行的可定位标记是 renderDimension 给的 data-dim（stage.* / threeway.* / ownership.*）加
              data-origin —— 测试同时钉住标记与可见文本，光有标记不是证据。 */}
          <div className="list">
            {stages.map((row) => (
              <React.Fragment key={row.key}>{renderDimension(row)}</React.Fragment>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-muted">
            阶段推进的读回来自服务端事务（{PRODUCER.writeOwner}，WUI-10）：写入、原生加载、行为验证分别更新、
            分别判定；本页只投影已经到货的字段，条件缺失时给具体原因与可行下一步，而不是灰掉一个动作。
          </p>
        </CardContent>
      </Card>

      {/* ---------------- 三方差异 ---------------- */}
      <Card data-block="three-way">
        <CardHeader><span>三方差异（前态 / 本方发布态 / 原生现态）</span></CardHeader>
        <CardContent>
          <p className="m-0 whitespace-pre-wrap text-[12px] text-ink">
            具名来源缺口，不是空表：{THREE_WAY_GAP.summary}
          </p>
          <div className="list mt-2">
            {threeWay.map((row) => (
              <React.Fragment key={row.key}>{renderDimension(row)}</React.Fragment>
            ))}
            {renderDimension(driftRow)}
          </div>
          <p className="mt-2 whitespace-pre-wrap text-[12px] text-muted">{THREE_WAY_GAP.nearestTruth}</p>
          <p className="mt-2 text-[12px] text-muted">
            目标与摘要、最小差异、恢复条件（10_rule_diff 要求的这四问）都建立在三方正文之上；
            三方正文不在 v3 契约里，所以本页不画 diff 条、不算最小差异，也不给出「保留现态 / 限定合并」的结果 ——
            那是受管事务的判定面。
          </p>
        </CardContent>
      </Card>

      {/* ---------------- 归属范围 ---------------- */}
      <Card data-block="ownership">
        <CardHeader><span>归属范围（快照实际携带了什么）</span></CardHeader>
        <CardContent>
          <div className="list">
            {ownership.map((row) => (
              <React.Fragment key={row.key}>{renderDimension(row)}</React.Fragment>
            ))}
          </div>
          <p className="mt-2 text-[12px] text-muted">
            字段级唯一权威是 {PRODUCER.ownershipAuthority}（layers × operation_modes × adapter_defaults，
            preserve_unknown: true，default_unknown=OBSERVE_QUARANTINE）。它不是快照投影，
            所以本页能报计数与客户端级声明默认，不能逐条报「这条规则归哪一层」。
          </p>
        </CardContent>
      </Card>

      {/* ---------------- 写资格与恢复边界 ---------------- */}
      <Card data-block="boundary">
        <CardHeader><span>写资格与恢复边界</span></CardHeader>
        <CardContent>
          {/* Prose, not PermissionState: `laneStateMatrix.sweep.test.tsx` reserves that block for a lane
              refusing an action an approval row actually offered. This refusal is global and row-
              independent, so presenting it as a per-row permission state would advertise a decision point
              this surface never had. */}
          <p className="m-0 text-[12px] text-muted" data-boundary="write-qualification">
            {READ_ONLY_STATEMENT.qualification} —— {READ_ONLY_STATEMENT.qualificationWhy}
            {' '}{READ_ONLY_STATEMENT.realAnswer}
            {' '}本页仍然给出：{READ_ONLY_STATEMENT.restore} —— {READ_ONLY_STATEMENT.restoreWhy}
          </p>
          <div className="list mt-3">
            <div className="list-item flex-col items-stretch gap-1" data-boundary="restore-scope">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">恢复边界</div>
              <p className="m-0 whitespace-pre-wrap text-[12px] text-ink">
                {READ_ONLY_STATEMENT.restore}：本页不执行恢复，也不提供恢复控件。需要恢复时走服务端受管事务，
                由它核对主体 / 范围 / 前态 / 版本 / 幂等后再落盘读回；范围之外的内容一律不碰（保留现态）。
              </p>
            </div>
            <div className="list-item flex-col items-stretch gap-1" data-boundary="user-edit">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">用户编辑</div>
              <p className="m-0 whitespace-pre-wrap text-[12px] text-ink">
                {READ_ONLY_STATEMENT.userEdit}：{READ_ONLY_STATEMENT.userEditWhy}
              </p>
            </div>
            <div className="list-item flex-col items-stretch gap-1" data-boundary="conflict">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">冲突检测</div>
              <p className="m-0 whitespace-pre-wrap text-[12px] text-warning">
                本页不显示「无冲突」：冲突裁决需要发布态与原生现态两侧正文，两者都不在 v3 契约里
                （{PRODUCER.familyThreeKeys}）。它已作为具名缺口列在归属块。
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ---------------- 出处 ---------------- */}
      <Card data-block="provenance">
        <CardHeader><span>出处（本页每一句话来自哪里）</span></CardHeader>
        <CardContent>
          <div className="list">
            {[
              ['治理块投影', PRODUCER.snapshotGovernance],
              ['生产调用', PRODUCER.noGovernanceArg],
              ['UNKNOWN 常量块', PRODUCER.unknownBlock],
              ['家族记录形状', PRODUCER.familyThreeKeys],
              ['DRIFT 判定', PRODUCER.driftRule],
              ['契约计数', PRODUCER.workspaceContracts],
              ['字段级归属权威', PRODUCER.ownershipAuthority],
              ['写资格与恢复的属主', PRODUCER.writeOwner],
            ].map(([label, text]) => (
              <div key={label} className="list-item flex-col items-stretch gap-1">
                <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{label}</div>
                <div className="break-words whitespace-pre-wrap text-[12px] text-ink">{text}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
