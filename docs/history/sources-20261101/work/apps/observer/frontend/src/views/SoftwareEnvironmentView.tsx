// WUI-06 · 软件环境页（母版 03_software / 04_software_detail / 15_first_run）— strictly read-only.
//
// This is the destination page for "这个软件在这台机器上是什么状态，适配器答到哪一步，还缺什么".
// It composes three things it does NOT re-implement:
//
//   * `SoftwareView` — the install-identity rows. It is not exported in pieces (its `Row`, `STATUS_LABEL`
//     and `statusVariant` are module-private), so it is rendered whole as a section rather than duplicated;
//     duplicating its markup would give the same field two renderings that can drift apart.
//   * `AdapterCapabilityCards` — the declared-vs-probed cards, including the verb dimension and its own
//     source-gap wording for an absent `adapterCapabilities` key.
//   * `lib/softwareQualification` — the four WUI-06 qualification dimensions (版本 / 形态 / 适配器 / 字段绑定),
//     the update-probed-or-not reading, limited-support and needs-revalidation wording, the first-run
//     stage ladder and the named source gaps. All of it reads snapshot fields.
//
// Three-origin discipline borrowed from the Inspector's `Dim` (views/RecordInspector.tsx:8-16): PROJECTED
// renders the value, NULL_FIELD renders "the source was read and this came back empty", SOURCE_GAP names
// the source that was not read. LOCATION_DRIFT / DUAL_INSTALLATION keep their raw tokens; nothing here
// says Healthy, 正常 or 最新 for an install identity.
//
// No control of any kind: not a button, not an input, not a link. Installing, updating, re-probing,
// relocating and launching are owned elsewhere (the sidecar / control shell and the software's own update
// authority). Native launch is observable from the executor live probe record; it is never dispatched here,
// and this page does not probe private sessions, credentials, browser data or model weights — those
// dimensions appear in the 来源缺口 list with the boundary that keeps them out.
import * as React from 'react'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SoftwareView } from '@/views/SoftwareView'
import { AdapterCapabilityCards } from '@/views/AdapterCapabilityCards'
import type { SnapshotV3 } from '@/types'
import {
  ADAPTER_DECLARED_SOURCES, FIRST_RUN_STAGE_KEYS, SOFTWARE_ACCEPTANCE_KEYS,
  SOFTWARE_QUALIFICATION_KEYS, SOFTWARE_SOURCE_GAPS,
  bitingSourceGaps, firstRunQualification, readCardExtras, summarizeSoftwareEnvironment,
  type FirstRunStageRow, type QualificationClaim, type QualificationOrigin, type SoftwareQualification,
} from '@/lib/softwareQualification'

const ORIGIN_TOKEN: Record<QualificationOrigin, string> = {
  PROJECTED: 'PROJECTED',
  NULL_FIELD: 'NULL_FIELD',
  SOURCE_GAP: 'SOURCE_GAP',
}

const ORIGIN_WORD: Record<QualificationOrigin, string> = {
  PROJECTED: '投影值',
  NULL_FIELD: '读过但为空',
  SOURCE_GAP: '来源缺口',
}

function originClass(origin: QualificationOrigin): string {
  if (origin === 'SOURCE_GAP') return 'text-[12px] text-warning'
  if (origin === 'NULL_FIELD') return 'text-[12px] text-muted'
  return 'text-[12px] text-ink'
}

/** One qualification claim. The raw origin token stays visible next to the Chinese wording so a reader can
 *  tell "the value was projected" from "the value is empty because the field is empty" without trusting
 *  colour, and the source handle is printed so the claim can be checked at the producer. */
export function Qual({ claim }: { claim: QualificationClaim }) {
  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-qualification-claim={claim.key}
      data-origin={claim.origin}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-semibold text-ink">{claim.label}</span>
        <span className="font-mono text-[12px] text-muted" data-testid={`origin-${claim.key}`}>
          {ORIGIN_TOKEN[claim.origin]}
        </span>
        <span className="text-[12px] text-muted">{ORIGIN_WORD[claim.origin]}</span>
      </div>
      <div className={'break-words ' + originClass(claim.origin)}>
        {claim.value ?? ORIGIN_WORD[claim.origin]}
      </div>
      {claim.source && (
        <div className="break-words font-mono text-[12px] text-muted">来源柄：{claim.source}</div>
      )}
      <div className="break-words text-[12px] text-muted">{claim.note}</div>
    </div>
  )
}

const ANSWER_WORD: Record<FirstRunStageRow['answer'], string> = {
  ANSWERABLE: '本快照可回答',
  PARTIAL: '只可部分回答',
  SOURCE_GAP: '本快照回答不了',
}

function answerVariant(answer: FirstRunStageRow['answer']): 'success' | 'warning' | 'muted' {
  if (answer === 'ANSWERABLE') return 'success'
  if (answer === 'PARTIAL') return 'warning'
  return 'muted'
}

function StageRow({ stage }: { stage: FirstRunStageRow }) {
  return (
    <div className="list-item flex-col items-stretch gap-1" data-stage={stage.key} data-answer={stage.answer}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-semibold text-ink">{stage.label}</span>
        <Badge variant={answerVariant(stage.answer)}>{ANSWER_WORD[stage.answer]}</Badge>
        <span className="font-mono text-[12px] text-muted">{stage.answer}</span>
      </div>
      <div className="break-words text-[12px] text-muted">可回答：{stage.answers}</div>
      <div className="break-words text-[12px] text-warning">回答不了：{stage.gap}</div>
    </div>
  )
}

function QualificationBlock({ qualification }: { qualification: SoftwareQualification }) {
  const acceptanceKeys = SOFTWARE_ACCEPTANCE_KEYS as readonly string[]
  return (
    <div className="panel" data-software-qualification={qualification.softwareId}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <strong className="text-sm font-semibold text-ink">
          {qualification.displayName || qualification.softwareId}
          <span className="ml-2 font-mono text-[12px] text-muted">{qualification.softwareId}</span>
        </strong>
        <span className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
          <Badge variant={qualification.needsRevalidation.required ? 'warning' : 'muted'}>
            待复验：{qualification.needsRevalidation.reasons.length} 项字段依据
          </Badge>
          <Badge variant={qualification.limitedSupport.isLimited ? 'warning' : 'muted'}>
            {qualification.limitedSupport.isLimited ? '有限支持' : '无字段限制声明'}
          </Badge>
          <Badge variant="info">
            已标记 MET 的层：{qualification.established.length ? qualification.established.join(' · ') : '无'}
          </Badge>
        </span>
      </div>
      <div className="list">
        {qualification.claims
          .filter((claim) => acceptanceKeys.includes(claim.key))
          .map((claim) => <Qual key={claim.key} claim={claim} />)}
        <div className="list-item flex-col items-stretch gap-1" data-qualification-group="beyond-acceptance">
          <div className="text-[12px] font-semibold text-ink">其余资格维度（更新 × 差异 × 原生）</div>
          {qualification.claims
            .filter((claim) => !acceptanceKeys.includes(claim.key))
            .map((claim) => <Qual key={claim.key} claim={claim} />)}
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-qualification-claim="support">
          <div className="text-[12px] font-semibold text-ink">有限支持由哪些字段推出</div>
          <div className="break-words text-[12px] text-muted">{qualification.limitedSupport.reasons.join('；')}</div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-qualification-claim="revalidation">
          <div className="text-[12px] font-semibold text-ink">更新待复验由哪些字段推出</div>
          <div className="break-words text-[12px] text-muted">
            {qualification.needsRevalidation.reasons.length
              ? qualification.needsRevalidation.reasons.join('；')
              : '没有字段说需要复验；这不构成"已复验"，只是本轮没有可引用的缺失'}
          </div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-qualification-claim="participating">
          <div className="text-[12px] font-semibold text-ink">参与项目（候选，非归属）</div>
          <div className="break-words text-[12px] text-ink">
            项目候选：{qualification.participating.projectIds.join(' · ') || '无匹配'}
            · 执行候选：{qualification.participating.executionIds.length} 条
          </div>
          <div className="break-words text-[12px] text-muted">{qualification.participating.basis}</div>
        </div>
      </div>
      {isDriftText(qualification) && (
        <div className="mt-2 break-words text-[12px] text-error" data-qualification-claim="drift-flag">
          安装身份冲突原样保留：{driftText(qualification)} — Observer 不迁移、不删除、不指定 canonical 实例。
        </div>
      )}
    </div>
  )
}

/** The drift callout reads the raw enum token, never the softened label: 位置漂移 alone could be rendered
 *  as a status pill and forgotten, while the token is what a reader can grep the producer for. */
function isDriftText(qualification: SoftwareQualification): boolean {
  const status = qualification.row.locationStatus
  return status === 'LOCATION_DRIFT' || status === 'DUAL_INSTALLATION' || status === 'MISSING_EXPECTED_INSTALL'
}

function driftText(qualification: SoftwareQualification): string {
  const row = qualification.row
  const expected = row.expectedLocation || '无记录'
  const observed = row.observedLocation || '无记录'
  if (row.locationStatus === 'DUAL_INSTALLATION') {
    return `DUAL_INSTALLATION · duplicateInstallation=${String(row.duplicateInstallation)} · 观测 ${observed}`
  }
  if (row.locationStatus === 'MISSING_EXPECTED_INSTALL') {
    return `MISSING_EXPECTED_INSTALL · 预期 ${expected} · 观测 ${observed}`
  }
  return `LOCATION_DRIFT · 预期 ${expected} · 观测 ${observed}`
}

function SummaryCard({ snap }: { snap: SnapshotV3 | null }) {
  const summary = summarizeSoftwareEnvironment(snap)
  const cardsAbsentNote = summary.cardsKeyPresent
    ? `能力卡 ${summary.cardCount} 张`
    : `adapterCapabilities 键缺席 —— 来源缺口：生产者未能读取 ${ADAPTER_DECLARED_SOURCES}。`
      + '本页对适配器数量不作任何断言，"没读成"不是"读到了空"。'
  const rowsAbsentNote = summary.softwareKeyPresent
    ? summary.softwareRowCount === 0
      ? 'software=[] 无法区分"注册表无条目"与"构建失败"（两条生产者路径都返回 []）'
      : `软件身份 ${summary.softwareRowCount} 行 · 更新未探测 ${summary.unprobedUpdateSoftwareIds.length} 行 · 位置冲突 ${summary.driftedSoftwareIds.length} 行`
    : 'software 键缺席 —— 发现层没有产出可读的东西'
  return (
    <Card>
      <CardHeader>
        <span>软件环境摘要（只读）</span>
        <span className="text-[12px] text-muted">快照修订 {snap?.revision ?? 'UNKNOWN'} · 生成于 {snap?.generatedAt ?? 'UNKNOWN'}</span>
      </CardHeader>
      <CardContent className="list">
        <div className="list-item flex-col items-stretch gap-1" data-testid="summary-software">
          <div className="text-[12px] text-muted">安装身份</div>
          <div className="break-words text-[12px] text-ink">{rowsAbsentNote}</div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-testid="summary-adapters">
          <div className="text-[12px] text-muted">适配器</div>
          <div className={'break-words ' + (summary.cardsKeyPresent ? 'text-[12px] text-ink' : 'text-[12px] text-warning')}>
            {cardsAbsentNote}
          </div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-testid="summary-rows-without-card">
          <div className="text-[12px] text-muted">读了卡但没有对应条目的软件</div>
          <div className="break-words text-[12px] text-muted">
            {summary.rowsWithoutCard.length ? summary.rowsWithoutCard.join(' · ') : '无（或卡列表本身缺席）'}
          </div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-testid="summary-ladder">
          <div className="text-[12px] text-muted">REGISTERED 之上被卡片自己标为 MET 的层</div>
          <div className="break-words text-[12px] text-ink">
            {summary.claimedAboveRegistered.length
              ? summary.claimedAboveRegistered.map((entry) => `${entry.clientId}:${entry.layer}`).join(' · ')
              : '无 —— 快照没有可引用的达成证据，本页不把任何更高层级说成达成'}
          </div>
        </div>
        <div className="list-item flex-col items-stretch gap-1" data-testid="summary-claim-keys">
          <div className="text-[12px] text-muted">每行软件渲染的资格维度</div>
          <div className="break-words font-mono text-[12px] text-muted">{SOFTWARE_QUALIFICATION_KEYS.join(' · ')}</div>
        </div>
      </CardContent>
    </Card>
  )
}

function FirstRunCard({ snap }: { snap: SnapshotV3 | null }) {
  const stages = firstRunQualification(snap)
  return (
    <Card>
      <CardHeader>
        <span>首次接入资格（按阶段判断，不代发起）</span>
        <span className="text-[12px] text-muted">{FIRST_RUN_STAGE_KEYS.length} 个阶段 · 阶段推进属操作员与执行侧</span>
      </CardHeader>
      <CardContent className="list">
        {stages.map((stage) => <StageRow key={stage.key} stage={stage} />)}
        <div className="list-item flex-col items-stretch gap-1" data-stage="boundary">
          <div className="text-[12px] font-semibold text-ink">这一页不会替你做的事</div>
          <div className="break-words text-[12px] text-muted">
            不安装、不更新、不启动、不迁移位置、不删除实例、不重新探测、不请求更多采集范围；
            原生启动只在探针记录里可被观察，派工由获准的执行侧负责。
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function SourceGapCard({ snap }: { snap: SnapshotV3 | null }) {
  const biting = new Set(bitingSourceGaps(snap))
  return (
    <Card>
      <CardHeader>
        <span>本页回答不了什么（命名缺口）</span>
        <span className="text-[12px] text-muted">共 {SOFTWARE_SOURCE_GAPS.length} 条 · 本轮命中 {biting.size} 条</span>
      </CardHeader>
      <CardContent className="list">
        {SOFTWARE_SOURCE_GAPS.map((gap) => (
          <div
            className="list-item flex-col items-stretch gap-1"
            key={gap.key}
            data-gap-key={gap.key}
            data-biting={biting.has(gap.key) ? 'yes' : 'no'}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] text-ink">{gap.key}</span>
              {gap.byDesign && <Badge variant="muted">按只读边界故意不采</Badge>}
              {biting.has(gap.key) && <Badge variant="warning">本轮命中</Badge>}
            </div>
            <div className="break-words text-[12px] text-ink">{gap.question}</div>
            <div className="break-words text-[12px] text-muted">{gap.reason}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function SoftwareEnvironmentView({ snap }: { snap: SnapshotV3 | null }) {
  const summary = summarizeSoftwareEnvironment(snap)
  const probedEntries = (snap?.adapterCapabilities ?? [])
    .filter((card) => readCardExtras(card).entryProbe !== null)
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <span>软件环境 · 接入资格</span>
          <span className="text-[12px] text-muted">母版 03_software / 04_software_detail / 15_first_run · 只读投影</span>
        </CardHeader>
        <CardContent className="text-[12px] text-muted">
          本页只投影后端已经算好的事实：版本、安装形态、适配器支持范围、字段归属默认，
          每一维各自带来源与状态，互不晋级。位置漂移与双安装按原始枚举值展示，不做任何改写；
          更新可用为 null 时写"未探测"，不写"是"也不写"否"。不读取凭据、鉴权面、私人会话、
          浏览器数据与模型权重 —— 这些维度在下方缺口列表里点名，而不是留白。
          {probedEntries.length > 0 && (
            <span className="ml-1">
              入口读回来自探针记录的软件声明，本页不代为发起（本轮可见 {probedEntries.length} 张卡带 entryProbe）。
            </span>
          )}
        </CardContent>
      </Card>

      <SummaryCard snap={snap} />

      <Card>
        <CardHeader>
          <span>逐软件资格（版本 / 形态 / 适配器 / 字段绑定）</span>
          <span className="text-[12px] text-muted">
            {summary.softwareKeyPresent ? `${summary.softwareRowCount} 行 · 真实投影` : 'software 键缺席 · 来源缺口'}
          </span>
        </CardHeader>
        <CardContent>
          {summary.qualifications.length === 0 ? (
            <div className="break-words text-[12px] text-warning" data-testid="qualification-empty">
              {summary.softwareKeyPresent
                ? 'software 是空列表：注册表里没有条目，或构建过程在 :83-84 / :156-159 任一路径上返回了 []。'
                  + '两种读法在 payload 里不可分辨，所以这里说"无法区分"，不说"这台机器没有软件"。'
                : '快照没有 software 字段（snapshot_api.py:106 只在读到列表时展开）。'
                  + '未提供不等于空列表，这里不伪造任何一行身份。'}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {summary.qualifications.map((qualification) => (
                <QualificationBlock key={qualification.softwareId} qualification={qualification} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div data-testid="section-install-identity">
        <SoftwareView snap={snap} />
      </div>

      <div data-testid="section-adapter-cards">
        <AdapterCapabilityCards snap={snap} />
      </div>

      <FirstRunCard snap={snap} />
      <SourceGapCard snap={snap} />

      <Card>
        <CardHeader><span>原则</span></CardHeader>
        <CardContent className="text-[12px] text-muted">
          资格判断的每一步都要落到一个字段与它的来源柄上；没有来源的判断不写进页面。
          声明 ≠ 检测 ≠ 可用 ≠ 调用 ≠ 原生验证，层级只按卡片自己标 MET 的行呈现，
          REGISTERED 之上不因邻层成功而晋级。本页不构成第二 Update Authority。
        </CardContent>
      </Card>
    </div>
  )
}
