// WUI-07 · 能力资产与评价详情 — the destination page for 05_assets / 06_asset_detail.
//
// One inventory, one evaluation detail per card, and the questions the projection cannot answer as
// named gaps. Three disciplines drive every pixel:
//
// * 四类宣称分开 (发现/登记 · 安装 · 加载·连接 · 调用) — each is its own claim with its own source;
//   none substitutes for another, and the page never merges them into one "可用" dot;
// * absent ≠ empty ≠ rows — `adapterCapabilities` absent is the producer's named source gap and never
//   a zero count; the verb dimension keeps "没看"(no key) / "看了·声明为零"([]) / rows as three
//   different renderings; `nativeStatus` is the constant NOT_IMPLEMENTED and never reads as a pass;
// * 没有字段的就不说 — the five provenance classes, licence, dependencies, applicability, failure
//   counter-examples, user judgement and migration status have NO FIELD in the snapshot; they render
//   as named gaps with their reasons (RecordInspector's Dim discipline), never as empty tabs.
//
// Strictly read-only (Observer §8): no install/apply/enable affordances, not even disabled buttons —
// the boundary is stated in words (PermissionState) instead of dressed up as inert controls.
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { UnknownState } from '@/components/ui/states'
import { Dim } from '@/views/RecordInspector'
import { EMPTY_FOCUS, type RecordFocus } from '@/lib/recordFocus'
import {
  CAPABILITY_DECLARED_SOURCES, CAPABILITY_SOURCE_GAPS, OWNERSHIP_DEFAULT_NOT_SOURCE_PATH,
  OWNERSHIP_DEFAULT_SOURCE_PATH, PRODUCER_CEILING, PROVENANCE_CLASSES,
  capabilityDeclarationsInSources, capabilityDeclarationsMissingFromSources, establishedFacts,
  groupAssetsByProvenance, workspaceSourceFacts,
  type EstablishedFacts, type WorkspaceSourceFacts,
} from '@/lib/capabilityAssets'
import { chainCounts, migrationChain } from '@/lib/capabilityMigration'
import type {
  AdapterCapabilityCard, AdapterVerbEvidenceRow, CapabilityLayerState, SnapshotV3,
} from '@/types'

type Snap = SnapshotV3 | null

export interface CapabilityAssetsViewProps {
  snap: Snap
  focus?: RecordFocus
  /**
   * Received for the registry's uniform props contract, deliberately NEVER called: cards on this lane
   * are keyed by `clientId`, and the only addressing contract (recordFocus) has slots for taskId /
   * executionId / projectId — no clientId slot. Writing a clientId into any of those would fuse a
   * capability identity onto a record identity, which is the exact 身份混用 WUI-07 forbids. In-page
   * movement therefore uses plain anchors; nothing here rewrites the address.
   */
  onFocus?: (next: RecordFocus) => void
  focusRejected?: string[]
}

const LAYER_LABEL: Record<string, string> = {
  REGISTERED: '已登记',
  INSTALLED: '已安装',
  LOADED_CONNECTED: '已加载·已连接',
  QUALIFIED: '已资格判定',
  ENABLED_FOR_TASK: '已按任务启用',
  NATIVE_PROJECTION: '原生投影',
  OBSERVED_IN_EXECUTION: '执行中观察',
}

const STATE_TEXT: Record<string, string> = {
  MET: '成立', NOT_PROBED: '未探测', NOT_SUPPORTED: '不支持',
}

function layerVariant(state: string): 'success' | 'warning' | 'muted' {
  if (state === 'MET') return 'success'
  if (state === 'NOT_SUPPORTED') return 'warning'
  return 'muted'
}

function LayerRow({ layer }: { layer: CapabilityLayerState }) {
  // A MET row still carries its reason: REGISTERED is MET with SYNTHETIC evidence and the reason says
  // why it is a declaration, not a probe — hiding it on MET would delete the loudest caveat on the card.
  const evidence = layer.state === 'MET'
    ? `${layer.evidenceLevel} · 来源 ${layer.source || 'UNKNOWN'}${layer.reason ? ` · ${layer.reason}` : ''}`
    : `${layer.evidenceLevel} · ${layer.reason}`
  return (
    <div className="list-item flex-col items-stretch gap-1" data-layer={layer.layer} data-state={layer.state}>
      <div className="flex items-center gap-2">
        <span className="text-[12px] text-ink">{LAYER_LABEL[layer.layer] || layer.layer}</span>
        <Badge variant={layerVariant(layer.state)}>{STATE_TEXT[layer.state] || layer.state}</Badge>
      </div>
      <div className="break-words text-[12px] text-muted">{evidence}</div>
    </div>
  )
}

function verbLabel(row: AdapterVerbEvidenceRow): string {
  if (row.state === 'MET') return '已作答'
  if (row.state === 'NOT_SUPPORTED') return '声明不支持'
  return row.attempted ? '已尝试·未采信' : '未尝试'
}

function verbVariant(row: AdapterVerbEvidenceRow): 'success' | 'warning' | 'muted' {
  if (row.state === 'MET') return 'success'
  if (row.state === 'NOT_SUPPORTED') return 'warning'
  return 'muted'
}

function VerbRow({ row }: { row: AdapterVerbEvidenceRow }) {
  const proof: string[] = []
  if (row.state === 'MET') {
    if (row.command && row.command.length) proof.push(`$ ${row.command.join(' ')}`)
    if (row.exitCode !== undefined && row.exitCode !== null) proof.push(`exit=${row.exitCode}`)
    if (row.outputDigest) proof.push(`digest=${row.outputDigest.slice(0, 12)}`)
  }
  const detail = row.state === 'MET' ? (row.source || 'UNKNOWN') : (row.reason || 'UNKNOWN')
  return (
    <div className="list-item flex-col items-stretch gap-1" data-verb={row.verb} data-verb-state={row.state}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[12px] text-ink">{row.verb}</span>
        <Badge variant={verbVariant(row)}>{verbLabel(row)}</Badge>
        <span className="text-[12px] text-muted">{row.evidenceLevel}</span>
      </div>
      <div className="break-words text-[12px] text-muted">{detail}</div>
      {proof.length > 0 && (
        <div className="break-words font-mono text-[12px] text-muted">{proof.join(' · ')}</div>
      )}
      {row.declaresDrift && (
        <div className="break-words text-[12px] text-warning">声明矛盾：{row.declaresDrift}</div>
      )}
    </div>
  )
}

/** 调用宣称：three shapes, two of them deliberately different sentences. */
function VerbClaim({ card }: { card: AdapterCapabilityCard }) {
  const facts = establishedFacts(card)
  if (facts.verbShape === 'ABSENT_KEY') {
    return (
      <div data-verb-shape="ABSENT_KEY" className="text-[12px] text-warning">
        动词证据来源缺口：卡上没有 verbEvidence 键 —— 生产者没有读取探针记录
        docs/audits/EXECUTOR_LIVE_PROBE_2026-10-08.json#verbProbe，这是「没看」。
        不渲染成 0 个动词：没看 ≠ 看了没声明 ≠ 不支持任何动词。
      </div>
    )
  }
  if (facts.verbShape === 'EMPTY_LIST') {
    return (
      <div data-verb-shape="EMPTY_LIST" className="text-[12px] text-warning">
        verbEvidence 为空列表 —— 语义：探针记录已读取，但其中声明的动词行为零。
        当前生产者合同不会产出这一形态（读不到时缺的是键本身），出现即按合同异常原样陈述。
        「看了 · 声明为零」与「没看」是两件事，也与「不支持」不是一件事。
      </div>
    )
  }
  const rows = card.verbEvidence ?? []
  const counts = card.verbEvidenceCounts
  const summary = counts
    ? `${counts.MET ?? 0} 已作答 · ${counts.NOT_PROBED ?? 0} 未探测 · ${counts.NOT_SUPPORTED ?? 0} 声明不支持`
    : `${rows.length} 行动词`
  return (
    <div className="flex flex-col gap-1.5" data-verb-shape="ROWS">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
        <span>接口动词作答（与阶梯正交：动词行永不晋级任何层）</span>
        <span className="font-mono">{summary}</span>
        {card.verbEvidenceProbedAt && <span>探测于 {card.verbEvidenceProbedAt}</span>}
      </div>
      <div className="list">
        {rows.map((row) => <VerbRow key={row.verb} row={row} />)}
      </div>
    </div>
  )
}

function NativeStatusLine({ card }: { card: AdapterCapabilityCard }) {
  // NOT_IMPLEMENTED is a constant of the producer, not a verdict; even the raw enum word for a pass
  // (NATIVELY_VERIFIED) would only ever be echoed as a projected string, never styled as success.
  return (
    <div className="list-item flex-col items-stretch gap-1" data-native-status={card.nativeStatus}>
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">原生状态（合同恒值，非判定结果）</div>
      <div className="break-words text-[12px] text-ink">
        <span className="font-mono">{card.nativeStatus}</span>
        <span className="ml-2 text-muted">
          当前生产者对 nativeStatus 恒发 NOT_IMPLEMENTED：原生验证通道未实现。
          这一行既不表示通过，也不表示失败，只转述字段。
        </span>
      </div>
    </div>
  )
}

function ProtocolLine({ card }: { card: AdapterCapabilityCard }) {
  const entries = Object.entries(card.protocolConformance)
  return (
    <div className="list-item flex-col items-stretch gap-1" data-protocol-conformance>
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">协议符合性（逐协议；ABSENT=未列入声明，不等于符合）</div>
      {entries.length === 0 ? (
        <div className="text-[12px] text-muted">protocolConformance 为空对象：声明里没有列出任何协议。</div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {entries.map(([protocol, status]) => (
            status === 'ABSENT' ? (
              <span key={protocol} data-protocol={protocol} data-status="ABSENT"
                    className="rounded border border-secondary px-1.5 py-0.5 text-[12px] text-warning">
                {protocol} · 未列出（ABSENT）—— 未列入符合性声明 ≠ 符合
              </span>
            ) : (
              <span key={protocol} data-protocol={protocol} data-status={status}
                    className="rounded border border-line px-1.5 py-0.5 font-mono text-[12px] text-ink">
                {protocol}={status}
              </span>
            )
          ))}
        </div>
      )}
    </div>
  )
}

function EntryProbeLine({ card }: { card: AdapterCapabilityCard }) {
  if (card.entryProbe === undefined) {
    return (
      <div data-entry-probe-shape="ABSENT_KEY">
        <Dim label="入口探针事实" value={null} hint="卡未携带 entryProbe 键 —— 生产者未投影探针事实，未读取不等于未发生" />
      </div>
    )
  }
  if (card.entryProbe === null) {
    return (
      <div className="list-item flex-col items-stretch gap-1" data-entry-probe-shape="NULL">
        <div className="text-[12px] uppercase tracking-[0.12em] text-muted">入口探针事实</div>
        <div className="text-[12px] text-muted">投影显式为 null：不存在任何探针记录（这是「没有探针记录」，不是「没读」）。</div>
      </div>
    )
  }
  const probe = card.entryProbe
  return (
    <div className="list-item flex-col items-stretch gap-1" data-entry-probe-shape="FACT">
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">入口探针事实（可执行文件应答过 · 不等于活跃会话）</div>
      <div className="break-words text-[12px] text-ink">
        {probe.status} · 入口 <span className="font-mono">{probe.entryPoint || 'UNKNOWN'}</span>
        {probe.argv.length > 0 && <> · argv <span className="font-mono">{probe.argv.join(' ')}</span></>}
        {` · exit=${probe.exitCode ?? 'UNKNOWN'} · 探测于 ${probe.probedAt || 'UNKNOWN'}`}
      </div>
      {probe.detail && <div className="break-words text-[12px] text-muted">{probe.detail}</div>}
    </div>
  )
}

/** 05_assets：一行一件资产，只投影卡上真实存在的键。 */
function AssetRow({ card, facts }: { card: AdapterCapabilityCard, facts: EstablishedFacts }) {
  const established = facts.metLayers.map((layer) => LAYER_LABEL[layer] || layer).join(' · ')
  const verbNote = facts.verbShape === 'ABSENT_KEY'
    ? '调用宣称：探针未读取（缺口）'
    : facts.verbShape === 'EMPTY_LIST'
      ? '调用宣称：探针已读 · 声明为零'
      : `调用宣称：${facts.verbsAnswered.length}/${(card.verbEvidence ?? []).length} 动词已作答`
  return (
    <div className="list-item flex-col items-stretch gap-1" data-asset-row={card.clientId}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] text-ink">{card.displayName}</span>
        <span className="font-mono text-[12px] text-muted">{card.clientId}</span>
        <Badge variant={card.supportLevel === 'deep' ? 'info' : 'muted'}>{card.supportLevel}</Badge>
        <Badge variant={card.registryStatus === 'active' ? 'success' : 'warning'}>{card.registryStatus}</Badge>
      </div>
      <div className="break-words text-[12px] text-muted">
        已确立（按投影原样，相邻层互不晋级）：{established || '无已成立层（按投影原样）'} · {verbNote}
        {facts.aboveCeilingMet.length > 0 && (
          <span className="text-warning"> · 异常：{facts.aboveCeilingMet.join('/')} 高于生产者上限</span>
        )}
      </div>
      <a className="text-[12px] text-secondary-ink" href={`#asset-${card.clientId}`}>查看评价详情 ↓</a>
    </div>
  )
}

/** 06_asset_detail：一张卡的全部宣称，四类各说各的。 */
function CardDetail({ card }: { card: AdapterCapabilityCard }) {
  const facts = establishedFacts(card)
  const layerOf = (name: string) => card.layers.find((l) => l.layer === name)
  return (
    <Card>
      <CardHeader>
        <span id={`asset-${card.clientId}`}>{card.displayName} · 能力详情</span>
        <span className="flex flex-wrap items-center gap-1.5 text-[12px] text-muted">
          寻址键 <span className="font-mono">{card.clientId}</span>
          <Badge variant={card.registryStatus === 'active' ? 'success' : 'warning'}>{card.registryStatus}</Badge>
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {facts.aboveCeilingMet.length > 0 && (
          <div className="text-[12px] text-warning" data-above-ceiling={facts.aboveCeilingMet.join(',')}>
            合同外形态：{facts.aboveCeilingMet.join(' / ')} 被投影为 MET，但生产者当前上限是
            {LAYER_LABEL[PRODUCER_CEILING]}（层 3–7 由投影硬编码 NOT_PROBED）。原样转述并标记异常，
            不据此晋级任何其他层，也不把它当作可用性证据。
          </div>
        )}

        <div className="text-[12px] text-muted">
          四类宣称分开成立：发现/登记 ≠ 安装 ≠ 加载·连接 ≠ 调用。每一块只写它自己的来源；
          声明 ≠ 检测 ≠ 可用 ≠ 调用 ≠ 原生验证。
        </div>

        <div className="list" data-claim="DISCOVERED">
          <div className="list-item flex-col items-stretch gap-1">
            <div className="text-[12px] font-semibold text-ink">宣称一 · 发现 / 登记</div>
            {layerOf('REGISTERED') ? <LayerRow layer={layerOf('REGISTERED')!} /> : (
              <div className="text-[12px] text-warning">卡未携带 REGISTERED 层行 —— 投影合同异常。</div>
            )}
            <div className="break-words text-[12px] text-muted">
              检测声明：{card.detectionMode || 'UNKNOWN'} / 证据态 {card.detectionEvidenceState}
              —— 来自声明文件的检测形态，不是本界面完成的检测。
            </div>
          </div>
        </div>

        <div className="list" data-claim="INSTALLED">
          <div className="list-item flex-col items-stretch gap-1">
            <div className="text-[12px] font-semibold text-ink">宣称二 · 安装</div>
            {layerOf('INSTALLED') && <LayerRow layer={layerOf('INSTALLED')!} />}
            <div className="break-words text-[12px] text-muted">
              版本身份：{card.declaredVersion
                ? <>声明 <span className="font-mono">{card.declaredVersion}</span>
                  · 读回方式 {card.versionReadbackMethod || 'UNKNOWN'}
                  · 观测于 {card.versionObservedAt || 'UNKNOWN'}
                  · 来源 {card.versionSource || 'UNKNOWN'}</>
                : '声明版本为 null：registry 里没有该客户端的版本值（投影为 null，不补写）。'}
            </div>
            {card.versionDrift === true && (
              <div className="break-words text-[12px] text-warning" data-version-drift="true">
                版本漂移：活入口读回与声明版本不一致。两个字符串都保留在上一行与本行，
                registry 不是真值，一个关于它的旧备注也不是。
              </div>
            )}
            <EntryProbeLine card={card} />
          </div>
        </div>

        <div className="list" data-claim="LOADED">
          <div className="list-item flex-col items-stretch gap-1">
            <div className="text-[12px] font-semibold text-ink">宣称三 · 加载 / 连接</div>
            {layerOf('LOADED_CONNECTED') ? <LayerRow layer={layerOf('LOADED_CONNECTED')!} /> : (
              <div className="text-[12px] text-warning">卡未携带 LOADED_CONNECTED 层行。</div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1.5" data-claim="INVOKED">
          <div className="text-[12px] font-semibold text-ink">宣称四 · 调用（接口动词维度）</div>
          <VerbClaim card={card} />
        </div>

        <div>
          <div className="mb-1.5 text-[12px] font-semibold text-ink">评价详情 · 七层阶梯（逐层独立，来源随层）</div>
          <div className="list" data-ladder>
            {card.layers.map((layer) => <LayerRow key={layer.layer} layer={layer} />)}
          </div>
        </div>

        <div className="list">
          <NativeStatusLine card={card} />
          <ProtocolLine card={card} />
          <div className="list-item flex-col items-stretch gap-1">
            <div className="text-[12px] uppercase tracking-[0.12em] text-muted">声明动词两清单（registry vs matrix）</div>
            <div className="break-words text-[12px] text-ink">
              {card.declaredOperations.length ? card.declaredOperations.join(' · ') : 'registry 侧：空清单（已投影，声明为零）'}
            </div>
            <div className="break-words text-[12px] text-ink">
              {card.matrixOperations.length ? card.matrixOperations.join(' · ') : 'capability-matrix 侧：空清单（已投影，声明为零）'}
            </div>
            {card.operationsDrift && (
              <div className="break-words text-[12px] text-warning">
                两份声明不一致：两处都原样展示，不替读者选择哪份作数。
              </div>
            )}
          </div>
          <div className="list-item flex-col items-stretch gap-1" data-ownership-source={OWNERSHIP_DEFAULT_SOURCE_PATH}>
            <div className="text-[12px] uppercase tracking-[0.12em] text-muted">
              配置归属默认（字段来源：{OWNERSHIP_DEFAULT_SOURCE_PATH} 的 config_ownership_default ——
              不是 {OWNERSHIP_DEFAULT_NOT_SOURCE_PATH} 的读取）
            </div>
            <div className="break-words text-[12px] text-ink">
              {card.configOwnershipDefault
                ? `${card.configOwnershipDefault.layer || 'UNKNOWN'} / ${card.configOwnershipDefault.mode || 'UNKNOWN'} / preserve_unknown=${String(card.configOwnershipDefault.preserve_unknown ?? 'UNKNOWN')}`
                : '矩阵里该客户端没有 config_ownership_default 条目（投影为 null）。'}
            </div>
          </div>
          <div className="break-words list-item text-[12px] text-muted">
            写策略 / 风险：writes={card.writePolicy} · risk={card.risk} ·
            运行时适配器 {card.runtimeAdapter || 'UNKNOWN'}
          </div>
          {card.clientNote && (
            <div className="break-words list-item text-[12px] text-muted">声明备注（registry 原文）：{card.clientNote}</div>
          )}
          <div className="break-words list-item text-[12px] text-muted">
            投影时间 {card.observedAt || 'UNKNOWN'} · 本页不刷新数据，只转述快照 revision 携带的内容。
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/** workspace.sources 真正展示的内容 —— 另一组源，不与卡混算。 */
function DeclaredSourcesCard({ facts }: { facts: WorkspaceSourceFacts }) {
  const shown = capabilityDeclarationsInSources(facts)
  const missing = capabilityDeclarationsMissingFromSources(facts)
  return (
    <Card>
      <CardHeader>
        <span>声明与加载面（workspace.sources 实际展示的）</span>
        <span className="text-[12px] text-muted">
          {facts.kind === 'ROWS' ? `${facts.rows.length} 行已投影`
            : facts.kind === 'EMPTY' ? '台账为空列表' : '台账键缺失'}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {facts.kind === 'ABSENT' && (
          <div className="text-[12px] text-warning" data-workspace-sources-shape="ABSENT">
            来源缺口：workspace.sources 键不存在 —— 本轮快照没有投影 sidecar 的加载台账。
            「没投影」不等于「什么都没加载」。
          </div>
        )}
        {facts.kind === 'EMPTY' && (
          <div className="text-[12px] text-muted" data-workspace-sources-shape="EMPTY">
            加载台账已投影且为空列表：sidecar 本轮没有登记任何加载面（读了，结果为零）。
          </div>
        )}
        {facts.kind === 'ROWS' && (
          <div className="list" data-workspace-sources-shape="ROWS">
            {facts.rows.map((row, i) => (
              <div key={`${row.path}-${i}`} className="list-item flex-col items-stretch gap-1">
                <div className="break-words font-mono text-[12px] text-ink">{row.path || '（无路径）'}</div>
                <div className="text-[12px] text-muted">
                  {row.evidenceKind || 'UNKNOWN'} · 加载于 {row.loadedAt || 'UNKNOWN'}
                  {row.generatedAt ? ` · 生成于 ${row.generatedAt}` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="text-[12px] text-muted">
          能力卡的声明源：{CAPABILITY_DECLARED_SOURCES.join(' / ')}。
          {facts.kind === 'ROWS' && shown.length === 0 && (
            <span className="text-warning">
              {' '}当前加载台账未列出其中任何一个（台账只覆盖仓库证据白名单 PLAN/STATIC_BASELINE/HISTORY 等）。
              卡能出现仅说明能力生产者读到了声明（字段缺失即缺源的另一半语义），本界面不据此伪造逐文件加载证据。
            </span>
          )}
          {facts.kind === 'ROWS' && shown.length > 0 && (
            <span> {' '}台账确认已加载：{shown.join(' · ')}；未列出：{missing.join(' · ') || '无'}。</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

/** 缺口块：05/06 问了、而快照没有任何字段的问题 —— 逐条命名 + 原因。 */
function GapBlock() {
  return (
    <Card>
      <CardHeader>
        <span>来源缺口（本页回答不了的问题 · 按合同命名，不是空标签页）</span>
        <span className="text-[12px] text-muted">{CAPABILITY_SOURCE_GAPS.length} 问 · 无对应字段</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="text-[12px] text-muted" data-provenance-unknown-note>
          来源类别（{PROVENANCE_CLASSES.join(' / ')}）没有任何卡字段承载，因此上面的清单整组标为「类别未知」，
          界面不猜测归类。下列每问都给出「为什么答不了」。
        </div>
        <div className="list">
          {CAPABILITY_SOURCE_GAPS.map((gap) => (
            <div key={gap.key} data-capability-gap={gap.key}>
              <Dim label={gap.question} value={null} hint={gap.reason} />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/** WUI-08：六步迁移链 —— 投影出来的两步说依据，未投影的四步点名属主，整块零可写控件。 */
function MigrationChainBlock({ cards }: { cards: AdapterCapabilityCard[] | undefined }) {
  const chains = (cards && cards.length > 0)
    ? cards.map((card) => ({ name: card.displayName, stages: migrationChain(card) }))
    : [{ name: null as string | null, stages: migrationChain(null) }]
  return (
    <Card>
      <CardHeader>
        <span>能力迁移与目标验证（WUI-08 六步链）</span>
        <span className="text-[12px] text-muted">源评价不代替目标验证</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {chains.map(({ name, stages }) => {
          const counts = chainCounts(stages)
          return (
            <div key={name ?? 'no-cards'} className="flex flex-col gap-2">
              <div className="text-[12px] text-muted" data-migration-chain={name ?? 'absent'}>
                {name === null
                  ? '没有能力卡可判：整条链按「未投影」呈现，不写成未开始'
                  : `客户端「${name}」——本链只描述该客户端；已投影 ${counts.projected} 步，未投影 ${counts.notProjected} 步`}
              </div>
              <div className="list">
                {stages.map((stage) => (
                  <div key={stage.id} className="list-item" data-migration-stage={stage.id}
                       data-stage-state={stage.state}>
                    <span>{stage.label}</span>
                    <Badge variant={stage.state === 'PROJECTED' ? 'muted' : 'warning'}>
                      {stage.state === 'PROJECTED' ? '已投影' : '未投影'}
                    </Badge>
                    <div className="text-[12px] text-muted">{stage.detail}</div>
                    <div className="text-[12px] text-muted">判据：{stage.basis} · 属主：{stage.owner}</div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

export function CapabilityAssetsView({
  snap, focus = EMPTY_FOCUS, focusRejected = [],
}: CapabilityAssetsViewProps) {
  const cards = snap?.adapterCapabilities
  const addressed = [focus.taskId && `taskId=${focus.taskId}`,
    focus.executionId && `executionId=${focus.executionId}`,
    focus.projectId && `projectId=${focus.projectId}`].filter(Boolean) as string[]
  const groups = cards ? groupAssetsByProvenance(cards) : []

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="能力资产与评价详情"
        description="能力资产清单（05_assets）与逐卡评价详情（06_asset_detail）：发现/安装/加载/调用四类宣称各自标注来源；快照没有字段的问题渲染为命名缺口。只读投影，不安装、不启用、不迁移。"
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

      {addressed.length > 0 && (
        <Card>
          <CardHeader><span>记录定位（上下文，不选择资产）</span></CardHeader>
          <CardContent>
            <div className="text-[12px] text-muted" data-focus-note>
              地址携带 {addressed.join(' · ')}。本泳道的资产按 clientId 寻址，而地址合同
              （recordFocus）没有 clientId 槽位，因此这里不按记录 id 筛选或顶替任何卡；
              记录详情请到「工作」泳道查看。
            </div>
          </CardContent>
        </Card>
      )}

      {snap === null && (
        <Card>
          <CardHeader><span>能力资产清单</span></CardHeader>
          <CardContent>
            <UnknownState
              title="快照未到达"
              description="数据源未接入，adapterCapabilities 无从谈起。这属于来源缺口，不输出任何资产计数，也不预选任何卡。"
            />
          </CardContent>
        </Card>
      )}

      {snap !== null && cards === undefined && (
        <Card>
          <CardHeader><span>能力资产清单</span></CardHeader>
          <CardContent>
            <div className="text-[12px] text-warning" data-testid="assets-absent-gap">
              来源缺口：快照没有 adapterCapabilities 字段 —— 生产者未能读取其声明输入
              （config/adapter-registry.json / capability-matrix.json / capability-conformance.json）。
              这不是「没有能力资产」，本界面不输出资产计数、不画空清单、也不以 0 顶替读不到的源。
            </div>
          </CardContent>
        </Card>
      )}

      {snap !== null && cards !== undefined && cards.length === 0 && (
        <Card>
          <CardHeader><span>能力资产清单</span></CardHeader>
          <CardContent>
            <div className="text-[12px] text-warning" data-testid="assets-empty-shape">
              合同形态异常：adapterCapabilities 是空列表。生产者语义里缺源时缺的是字段本身，
              空列表代表「已读取声明源、声明集合为零」—— 当前生产者不产出该形态。
              这里按形态原样陈述；它与上一条「字段缺失 · 没读取」是两句不同的话。
            </div>
          </CardContent>
        </Card>
      )}

      {snap !== null && cards !== undefined && cards.length > 0 && (
        <>
          <Card>
            <CardHeader>
              <span>能力资产清单</span>
              <span className="text-[12px] text-muted">{cards.length} 张卡 · 按 clientId 寻址</span>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {groups.map((group) => (
                <div key={group.key} className="flex flex-col gap-1.5">
                  <div className="text-[12px] font-semibold text-ink">{group.label}</div>
                  <div className="text-[12px] text-muted" data-provenance-unknown-note>{group.reason}</div>
                  <div className="list">
                    {group.cards.map((card) => (
                      <AssetRow key={card.clientId} card={card} facts={establishedFacts(card)} />
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="flex flex-col gap-4">
            {cards.map((card) => <CardDetail key={card.clientId} card={card} />)}
          </div>
        </>
      )}

      {snap !== null && <DeclaredSourcesCard facts={workspaceSourceFacts(snap)} />}

      <GapBlock />
      <MigrationChainBlock cards={cards} />

      <Card>
        <CardHeader><span>只读边界</span></CardHeader>
        <CardContent>
          {/* Prose, not PermissionState: the sweep in `laneStateMatrix.sweep.test.tsx` reserves the
              permission affordance for lanes that actually face a refused action row. This page has no
              action to refuse, so borrowing that block would advertise a decision point that does not
              exist — the same lie as a greyed-out button, in a nicer wrapper. */}
          <p className="m-0 text-[12px] text-muted">
            本页不安装、不启用、不 apply、不写配置、不发起探测、不迁移资产，也不提供置灰的按钮 ——
            Observer 是严格只读投影，任何资产写入与能力变更需要单独的 Task Grant 与受管执行通道。
            这里仍然可读的是：四类宣称各自的成立依据、逐层证据来源与未回答的动词，以及卡上的 clientId。
          </p>
          <div className="mt-2 text-[12px] text-muted">
            迁移评价（源→目标、差异损失、隔离试用、验证）属于 WUI-08 的合同，本页只保留其缺口命名。
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
