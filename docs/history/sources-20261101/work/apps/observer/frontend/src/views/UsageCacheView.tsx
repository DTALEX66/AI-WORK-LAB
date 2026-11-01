// WUI-05 · 用量缓存与质量页面（「用量缓存」这一目的地的落点）。
//
// 这一页回答四件母版画在一起、实际不能混的事：Token 计了多少、这个计数的质量是什么、缓存能不能说、
// 费用与 Credits 是多少。v3 快照只携带前两件（生产者核实见 `lib/usageTruth.ts` 头部），
// 所以本页把四件事拆成四个独立区块，后两个区块只放命名缺口，一个数字都不出现。
//
// 三起源纪律沿用 `views/RecordInspector.tsx:42-60` 与 `:214-243`，只是多了一格：
//   PROJECTED  — 投影确实带了这个值（包括源自己报告的零，界面额外标注「源报告为零」）；
//   NULL_FIELD — 读到了源、这个字段是 null（缺失就是缺失，不显示零，也不从别的字段反推）；
//   SOURCE_GAP — 该维度不在合同里，附带生产者自己的行为作为理由。
// 页面不计算任何百分比：没有百分比字符出现，也不显示分子分母相除的结果。
//
// 只读边界用文字声明。Observer 严格只读，所以本页零按钮、零禁用控件（禁用控件仍会被读成
// 「有权限就能点」）；行上唯一的出口是链接，href 就是同一条地址，复制、新开、刷新结果一致。
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { DataTable } from '@/components/ui/table'
import { UnknownState } from '@/components/ui/states'
import { fmtTimestamp } from '@/lib/api'
import { EMPTY_FOCUS, recordLink, type RecordFocus } from '@/lib/recordFocus'
import type { SnapshotV3 } from '@/types'
import {
  gapsForBlock, projectUsageRows, qualitySubsetCounts, summaryQuality, summaryTokenFields,
  usageConsistency, coverageReading,
  USAGE_GAP_BLOCKS, USAGE_READONLY_BOUNDARY,
  type NumberReading, type ProjectUsageRow, type QualityReading, type UsageSourceGap,
} from '@/lib/usageTruth'

export interface UsageCacheViewProps {
  snap: SnapshotV3 | null
  /**
   * 本页是快照级聚合，不靠 focus 选记录。`focus.projectId` 只用来标出已定位的那一行并回显地址；
   * `onFocus` 只被行链接用来代替整页刷新。两者都可省略：没有 onFocus 时链接的 href 仍是同一条地址。
   */
  focus?: RecordFocus
  onFocus?: (next: RecordFocus) => void
  /** 地址里带了但被校验拒绝的标识与原因，逐条显示，不静默丢弃 */
  focusRejected?: string[]
}

/** The value cell — the one place that decides UNKNOWN versus a reported zero. */
function ValueCell({ reading }: { reading: NumberReading }) {
  if (reading.origin === 'NULL_FIELD') {
    return (
      <span
        data-usage-value="absent" data-origin="NULL_FIELD" data-reported-zero="false"
        className="font-mono text-[12px] text-muted"
      >
        UNKNOWN
      </span>
    )
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span
        data-usage-value="number" data-origin="PROJECTED"
        data-reported-zero={reading.reportedZero ? 'true' : 'false'}
        className="font-mono text-[12px] text-ink"
      >
        {reading.text}
      </span>
      {reading.reportedZero && <Badge variant="muted">源报告为零</Badge>}
      {!reading.reportedZero && reading.abbrevText && (
        <span className="text-[12px] text-muted">显示缩写 {reading.abbrevText}</span>
      )}
    </span>
  )
}

/** label · value · unit/precision/completeness · the producer path it came from. */
function FieldRow({ reading, testId }: { reading: NumberReading; testId?: string }) {
  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-dim={reading.key} data-origin={reading.origin} {...(testId ? { 'data-testid': testId } : {})}
    >
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{reading.label}</div>
      <ValueCell reading={reading} />
      <div className="text-[12px] text-muted">
        单位 {reading.unit} · 精度 {reading.precision} · 完整性 {reading.completeness}
      </div>
      {reading.note && <div className="text-[12px] text-muted">{reading.note}</div>}
      <div className="break-all font-mono text-[12px] text-muted">来源 {reading.source}</div>
    </div>
  )
}

function QualityRow({ reading, testId }: { reading: QualityReading; testId?: string }) {
  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-dim={reading.key} data-origin={reading.origin} {...(testId ? { 'data-testid': testId } : {})}
    >
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{reading.label}</div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span data-usage-quality={reading.value} className="font-mono text-[12px] text-ink">{reading.text}</span>
        {reading.isUnknownVerdict && <Badge variant="warning">未知判定</Badge>}
      </div>
      <div className="text-[12px] text-muted">{reading.note}</div>
      <div className="break-all font-mono text-[12px] text-muted">来源 {reading.source}</div>
    </div>
  )
}

/** A question the contract does not answer. It carries no value cell at all. */
function GapRow({ gap }: { gap: UsageSourceGap }) {
  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-dim={gap.key} data-gap-key={gap.key} data-origin="SOURCE_GAP"
    >
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{gap.question}</div>
      <div className="flex items-start gap-1.5 text-[12px] text-warning">
        <span className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-secondary" aria-hidden="true" />
        <span>来源缺口（当前 v3 快照未携带 · {gap.reason}）</span>
      </div>
    </div>
  )
}

/** A non-numeric projected string (scope, transport, a timestamp). */
function StringRow({ dimKey, label, value, note }: { dimKey: string; label: string; value: string; note?: string }) {
  const absent = !value || value === 'UNKNOWN'
  return (
    <div className="list-item flex-col items-stretch gap-1" data-dim={dimKey} data-origin={absent ? 'NULL_FIELD' : 'PROJECTED'}>
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{label}</div>
      <div className="whitespace-pre-wrap break-words text-[12px] text-ink">{absent ? 'UNKNOWN' : value}</div>
      {note && <div className="text-[12px] text-muted">{note}</div>}
    </div>
  )
}

const TRANSPORT_TEXT: Record<string, string> = {
  LIVE: '实时', DELAYED: '滞后', OFFLINE: '离线', CONNECTING: '连接中', UNKNOWN: '未知',
  FRESH: '新鲜', STALE: '陈旧',
}

export function UsageCacheView({
  snap, focus = EMPTY_FOCUS, onFocus, focusRejected = [],
}: UsageCacheViewProps) {
  const search = typeof window !== 'undefined' ? window.location.search : ''
  const summaryFields = summaryTokenFields(snap)
  const quality = summaryQuality(snap)
  const coverage = coverageReading(snap)
  const rows = projectUsageRows(snap)
  const counts = qualitySubsetCounts(snap)
  const consistency = usageConsistency(snap)
  const wanted = focus.projectId ?? null
  const wantedMatched = wanted !== null && rows.some((row) => row.projectId === wanted)

  const detailHref = (projectId: string) =>
    recordLink('project-detail', { ...EMPTY_FOCUS, projectId }, search)
  const openDetail = (projectId: string) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    // A link first: without a shell callback the href already is the address.
    if (!onFocus) return
    event.preventDefault()
    onFocus({ taskId: null, executionId: null, projectId })
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="用量缓存"
        description="逐字段显示快照投影的 Token 计数与质量标签：真实零与缺失分开，单位、精度与完整性随每个值一起给出。Credits、费用、缓存占比、命中率、资源与守恒身份都不在投影里，本页把它们作为命名缺口列出，不计算任何比率。只读投影，不重算、不补采、不写回。"
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
          <CardHeader><span>用量缓存</span></CardHeader>
          <CardContent>
            <UnknownState
              title="数据源未接入"
              description="快照未到达，Token 计数与质量标签全部保持 UNKNOWN：这里不预填零，也不预填任何比率。下方的缓存、Credits、费用、资源与守恒缺口是合同层面的事实，与连接状态无关，因此仍然列出。"
            />
          </CardContent>
        </Card>
      )}

      <Card data-value-scope="token-summary">
        <CardHeader>
          <span>Token 计数 · 快照汇总（tokenSummary）</span>
          <span className="text-[12px] text-muted">逐字段判定完整性</span>
        </CardHeader>
        <CardContent>
          <div className="mb-3 text-[12px] text-muted">
            本页每个数值都带单位、精度与完整性三件事：单位是 token（整数计数），精度按源报告的小数位原样显示，
            完整性逐字段判定 —— 一个字段缺失不影响另一个字段已报告的事实。k 与 M 只是显示缩写，精确整数始终单独列出。
          </div>
          <div className="list">
            {summaryFields.map((reading) => (
              <FieldRow key={reading.key} reading={reading} testId={`usage-value-${reading.key}`} />
            ))}
            <QualityRow reading={quality} testId="usage-value-costQuality" />
          </div>
          <div className="mt-3 text-[12px] text-muted">
            没有用量样本时这三个字段都是 null，界面显示 UNKNOWN 而不是零；有样本但某字段从未声明时，
            该字段同样是 UNKNOWN，其余字段照常显示已报告的值。汇总把全部用量样本相加，包括没有项目归属的样本。
          </div>
        </CardContent>
      </Card>

      <Card data-value-scope="quality-subsets">
        <CardHeader>
          <span>精确 / 估算 / 未知子集 · 逐行数出来</span>
          <span className="text-[12px] text-muted">不读快照汇总标签</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            {counts.readings.map((reading) => (
              <FieldRow key={reading.key} reading={reading} testId={`usage-count-${reading.key}`} />
            ))}
          </div>
          <div className="mt-3 text-[12px] text-muted">
            {counts.note} 快照级质量标签是 {counts.summaryQuality}，它是按全部样本算出来的判定，
            不是这里的行数；两边不互相推导，也不在这里相除。
          </div>
        </CardContent>
      </Card>

      <Card data-value-scope="coverage">
        <CardHeader>
          <span>覆盖范围与观测时间</span>
          <span className="text-[12px] text-muted">分子与分母并列，不相除</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            <FieldRow reading={coverage.numerator} testId="usage-value-coverageNumerator" />
            <FieldRow reading={coverage.denominator} testId="usage-value-coverageDenominator" />
            <StringRow
              dimKey="coverageScope" label="覆盖口径（scope）"
              value={coverage.scope.text} note={coverage.scope.note}
            />
            <StringRow
              dimKey="revision" label="快照修订（revision）"
              value={snap ? String(snap.revision) : 'UNKNOWN'}
              note="这是快照自己的修订，不是用量的修订；用量修订序列未投影，见下方守恒缺口。"
            />
            <StringRow
              dimKey="generatedAt" label="投影生成时间"
              value={fmtTimestamp(snap?.generatedAt)}
              note="时间戳不合 RFC 头部格式时显示 UNKNOWN，不做本地猜测。"
            />
            <StringRow
              dimKey="sourceWatermark" label="来源水位时间"
              value={fmtTimestamp(snap?.sourceWatermark)}
              note="来源水位是后端读到的最新事件时间，不等于某个项目的观测时刻。"
            />
            <StringRow
              dimKey="transport" label="传输状态"
              value={TRANSPORT_TEXT[snap?.transport?.transportState ?? ''] ?? (snap?.transport?.transportState || 'UNKNOWN')}
              note="滞后或离线不推出用量为零，只表示这一页的读数不再新鲜。"
            />
          </div>
          <div className="mt-3 text-[12px] text-muted">{coverage.note}</div>
        </CardContent>
      </Card>

      <Card data-value-scope="token-rows">
        <CardHeader>
          <span>项目 Token 明细 · 逐项目累加</span>
          <span className="text-[12px] text-muted">{rows.length} 行 · 按 projectId 寻址</span>
        </CardHeader>
        <CardContent>
          <DataTable<ProjectUsageRow>
            density="compact"
            rows={rows}
            rowKey={(row) => row.projectId}
            columns={[
              {
                key: 'project',
                header: '项目',
                cell: (row) => (
                  <div className="flex flex-col gap-1">
                    <strong className="text-[12px] font-semibold text-ink">{row.displayName || row.projectId}</strong>
                    <small className="break-all font-mono text-[12px] text-muted">{row.projectId}</small>
                    {row.displayName && (
                      <small className="text-[12px] text-muted">显示名不参与寻址</small>
                    )}
                    {wanted === row.projectId && (
                      <Badge variant="info">当前定位</Badge>
                    )}
                  </div>
                ),
              },
              {
                key: 'inputTokens', header: '输入 Token', align: 'right',
                cell: (row) => <ValueCell reading={row.fields.find((f) => f.key.endsWith(':inputTokens'))!} />,
              },
              {
                key: 'outputTokens', header: '输出 Token', align: 'right',
                cell: (row) => <ValueCell reading={row.fields.find((f) => f.key.endsWith(':outputTokens'))!} />,
              },
              {
                key: 'totalTokens', header: '总 Token（源报告）', align: 'right',
                cell: (row) => <ValueCell reading={row.fields.find((f) => f.key.endsWith(':totalTokens'))!} />,
              },
              {
                key: 'costQuality', header: '成本质量',
                cell: (row) => (
                  <div className="flex flex-col gap-1">
                    <Badge variant={row.quality.value === 'EXACT' ? 'success' : row.quality.value === 'ESTIMATED' ? 'warning' : 'muted'}>
                      {row.quality.text}
                    </Badge>
                    <small className="text-[12px] text-muted">{row.quality.note}</small>
                  </div>
                ),
              },
              {
                key: 'completeness', header: '字段完整性',
                cell: (row) => (
                  <div className="flex flex-col gap-1">
                    <span className="text-[12px] text-ink">已报告 {row.reportedFieldCount} 项</span>
                    {!row.hasAnyReportedNumber && (
                      <span className="text-[12px] text-warning">
                        {row.looksLikeNoSample
                          ? '三个 Token 字段都未报告：投影里这个项目名下没有样本，不等于该项目零用量'
                          : '三个 Token 字段都未报告：不等于零用量'}
                      </span>
                    )}
                  </div>
                ),
              },
              {
                key: 'detail', header: '对象详情',
                cell: (row) => (
                  <a
                    href={detailHref(row.projectId)}
                    onClick={openDetail(row.projectId)}
                    className="text-[12px] text-secondary-ink"
                    data-usage-detail-link={row.projectId}
                  >
                    项目详情
                  </a>
                ),
              },
            ]}
            empty={
              snap
                ? '快照已接入，但项目集合为空（注册表没有投影出项目行）。这与「没有用量样本」是两件事：汇总仍然统计全部样本，未登记 projectId 的样本没有对应行。'
                : 'UNKNOWN · 快照未到达，无从列出项目行'
            }
          />
          {wanted !== null && !wantedMatched && (
            <div className="mt-3 text-[12px] text-warning">
              地址要求 projectId={wanted}，本页投影的项目行里没有这个身份，因此不选中任何一行、也不改选别的行。
              原身份保留供复制：<span className="font-mono text-ink">{wanted}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card data-value-scope="consistency-check">
        <CardHeader>
          <span>口径核对 · 界面派生，不是第二个真源</span>
          <span className="text-[12px] text-muted">缺失不按零相加</span>
        </CardHeader>
        <CardContent>
          <div className="list">
            <StringRow
              dimKey="rowsTotal" label="项目行总 Token 合计（界面派生）"
              value={consistency.rowsTotal.text}
              note={consistency.rowsTotal.note}
            />
            <StringRow dimKey="verdict" label="核对结论" value={consistency.verdict} />
          </div>
          <div className="mt-3 text-[12px] text-muted">
            这个合计只用于说明两侧口径是否相同，任何情况下都不覆盖快照汇总或项目行的投影值；
            只要有一行未报告总 Token，合计就是不可计算，界面不把它写成零。
          </div>
        </CardContent>
      </Card>

      {USAGE_GAP_BLOCKS.map((block) => (
        <Card key={block.key} data-gap-block={block.key}>
          <CardHeader>
            <span>{block.title}</span>
            <span className="text-[12px] text-warning">本节无数值</span>
          </CardHeader>
          <CardContent>
            <div className="mb-3 text-[12px] text-muted">{block.lead}</div>
            <div className="list">
              {gapsForBlock(block.key).map((gap) => <GapRow key={gap.key} gap={gap} />)}
            </div>
          </CardContent>
        </Card>
      ))}

      <Card>
        <CardHeader><span>只读边界</span></CardHeader>
        <CardContent className="flex flex-col gap-1.5">
          <ul className="list m-0 flex flex-col gap-1.5">
            {USAGE_READONLY_BOUNDARY.map((line) => (
              <li key={line} className="list-item text-[12px] text-muted">{line}</li>
            ))}
          </ul>
          <div className="mt-1 text-[12px] text-muted">
            本页不提供任何控件，包括禁用态控件；计量真源与写入路径属 Workflow 侧的 canonical store，
            观测侧只做投影。
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
