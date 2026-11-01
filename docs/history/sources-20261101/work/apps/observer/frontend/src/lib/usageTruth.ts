// WUI-05 · 用量缓存 read model — 只投影 v3 快照真正携带的计量字段。
//
// 这个模块是本页唯一的字段解释者，规则和 `lib/projectIdentity.ts`（WUI-04）与
// `views/RecordInspector.tsx:42-60`（三起源纪律）一致：一个数字要么是被投影的值，要么是
// 字段为 null，要么这个维度根本不在合同里。三者不互相顶替。
//
// 生产者事实（读代码核实，不在界面绕过）：
//
//   * `packages/client-neutral-core/scripts/snapshot_api.py:337-363`（`_token_summary`）只投影
//     `inputTokens` / `outputTokens` / `totalTokens` / `costQuality`；没有用量样本时四个字段全为
//     null / UNKNOWN，某字段在每条样本里都缺失时保持 null，绝不补零（P0-3 纪律）；
//     质量标签只有每条样本都声明 EXACT 才是 EXACT，任一条 ESTIMATED 即 ESTIMATED，否则 UNKNOWN。
//   * 项目级用量来自 `snapshot_api.py:277-282` + `_rollup_usage`（同文件 320-334）：
//     逐项目累加，字段缺失则该字段保持 null；没有样本的项目得到全 null 与 UNKNOWN。
//   * 项目行本身来自注册表（`snapshot_api.py:84` 遍历 `projects`），用量样本来自
//     `usage_samples` 表，`_rollup_usage` 把缺 projectId 的样本归到 `unknown` 桶 —— 那个桶没有项目行。
//   * `canonical_store.py:201-223` 的 usage 行确实有 `cache_read_tokens`、`cache_write_tokens`、
//     `reasoning_tokens`、`tool_tokens`、`subagent_tokens`、`billing_type`、`cost_estimate`、
//     `cost_reconciled` 这些列，`snapshot_api.py` 一个都不投影；Credits 与配额连列都没有。
//   * `apps/observer/scripts/usage_rollup.py:79-128` 在快照路径之外算 `cacheReadTokens` /
//     `cacheWriteTokens` 与指纹去重，其结果从不进入 `/api/v1/snapshot`，所以界面读不到。
//
// 因此本页：不计算任何百分比或比率（缺分母就不算，有分母也不在这里算）；不把 Credits、金额、
// 资源与 Token 互相换算；不用输入加输出反推总量；不把快照自身的 revision 当作用量修订。
// 任务包母版里的演示算术（把几段相加得到一个总量、几成缓存占比、几成命中率）是示例，
// 不是本模块的输出形态，任何演示数字都不出现在这里。
import type { CostQuality, Project, SnapshotV3 } from '@/types'
import { fmtCostQuality, fmtTokens } from '@/lib/api'

/** The two origins a projected number can have — a SOURCE_GAP is never a NumberReading. */
export type UsageFieldOrigin = 'PROJECTED' | 'NULL_FIELD'

export const TOKEN_UNIT = 'token'
export const TOKEN_PRECISION = '整数计数（源按整数累加，无小数位）'
export const ROWS_UNIT = '行'
export const ROWS_PRECISION = '整数计数（界面逐行数出来的派生值，不是投影字段）'
export const UNKNOWN_TEXT = 'UNKNOWN'

/** thousands-separated integer, deterministic (jsdom locales vary) */
export function groupInteger(n: number): string {
  const sign = n < 0 ? '-' : ''
  return sign + String(Math.abs(n)).replace(/\B(?=(\d{3})+$)/g, ',')
}

/**
 * One number field exactly as the projection reports it.
 *
 * `completeness` is per field, not per record: a sample can carry 总 Token while carrying no
 * 输入 Token at all (`_rollup_usage` only adds fields that are ints), so a row can be partly
 * reported. That is why completeness lives next to every single value instead of once per card.
 */
export interface NumberReading {
  key: string
  label: string
  origin: UsageFieldOrigin
  /** the exact number, or null whenever origin is NULL_FIELD */
  value: number | null
  /** true ONLY when the source itself reported 0 — the UI labels it 源报告为零 */
  reportedZero: boolean
  /** what the value cell prints: the exact number, or UNKNOWN */
  text: string
  /** the k/M display abbreviation, or null when there is no number to abbreviate */
  abbrevText: string | null
  unit: string
  precision: string
  completeness: '已报告' | '未报告'
  /** which snapshot path this field comes from, so a reader can go check the producer */
  source: string
  note: string
}

export function readNumberField(args: {
  key: string
  label: string
  raw: unknown
  source: string
  unit?: string
  precision?: string
  note?: string
  /**
   * A count the UI derived by counting rows is NOT a source-reported value, so its zero must not borrow
   * the "this zero came from the source" sentence. Without this flag the two zeros read identically,
   * which is the exact confusion WUI-05 exists to prevent.
   */
  derived?: boolean
}): NumberReading {
  const { key, label, raw, source } = args
  const unit = args.unit ?? TOKEN_UNIT
  const isNumber = typeof raw === 'number' && Number.isFinite(raw)

  if (!isNumber) {
    return {
      key, label, origin: 'NULL_FIELD', value: null, reportedZero: false,
      text: UNKNOWN_TEXT, abbrevText: null,
      unit, precision: args.precision ?? TOKEN_PRECISION,
      completeness: '未报告', source,
      // A null is the source reporting nothing. It is not a zero and not an empty cache. The field's own
      // note is appended, never substituted: "this field is a separate field" and "this value was not
      // reported, so it is not counted as zero" are two different claims and a null must carry both.
      note: MISSING_NULL_NOTE + (args.note ? ' ' + args.note : ''),
    }
  }

  const value = raw as number
  const integer = Number.isInteger(value)
  return {
    key, label, origin: 'PROJECTED', value,
    reportedZero: value === 0,
    text: integer ? groupInteger(value) : String(value),
    abbrevText: unit === TOKEN_UNIT ? fmtTokens(value) : null,
    unit,
    // A non-integer reaching the UI is shown with its own decimals, never rounded away.
    precision: integer
      ? (args.precision ?? TOKEN_PRECISION)
      : '源给出了非整数：小数位原样显示，界面不四舍五入',
    completeness: '已报告', source,
    // Same rule as the null branch: a source-reported zero keeps its own sentence AND the field's note.
    // A count the UI derived by counting rows is not source-reported, so it keeps only its own note —
    // otherwise "0 estimated rows" would read as "the source reported zero", which is a different claim.
    note: value === 0 && !args.derived
      ? REPORTED_ZERO_NOTE + (args.note ? ' ' + args.note : '')
      : (args.note ?? ''),
  }
}

/** The one sentence every unreported numeric field must carry, whatever the field's own note says. */
const MISSING_NULL_NOTE = '源未报告该字段（null）：缺失就是缺失，界面不按零计，也不从别的字段反推。'

/** And the one sentence a reported zero must carry — the two are the pair the reader tells apart. */
const REPORTED_ZERO_NOTE = '这个零是源报告的值，不是缺失。'

const SUMMARY_SOURCE = 'packages/client-neutral-core/scripts/snapshot_api.py::_token_summary → tokenSummary'
const NO_SNAPSHOT = '快照未到达，字段无从读取（不是零）'

const TOKEN_FIELDS = [
  { key: 'inputTokens', label: '输入 Token', note: '输入 Token 单独成字段：总量不由它加出来。' },
  { key: 'outputTokens', label: '输出 Token', note: '输出 Token 单独成字段。' },
  {
    key: 'totalTokens', label: '总 Token（源报告的总量）',
    note: '总 Token 是源端报告的 total_tokens 合计，界面不用输入加输出反推总量。',
  },
] as const

/** The three projected token totals, one reading per field (never merged into one number). */
export function summaryTokenFields(snap: SnapshotV3 | null): NumberReading[] {
  const summary: SnapshotV3['tokenSummary'] | null = snap?.tokenSummary ?? null
  return TOKEN_FIELDS.map((field) => readNumberField({
    key: field.key,
    label: field.label,
    raw: summary ? summary[field.key] : undefined,
    source: summary ? SUMMARY_SOURCE : NO_SNAPSHOT,
    note: field.note,
  }))
}

/**
 * The cost-quality verdict.
 *
 * It is a label, not an amount: v3 carries no monetary field, so 质量 is the only cost truth here
 * (`fmtCostQuality` in `lib/api.ts:238`). UNKNOWN is a legitimate projected verdict — the field IS
 * present and its answer is "unknown" — which is a different statement from a null token field.
 */
export interface QualityReading {
  key: string
  label: string
  origin: UsageFieldOrigin
  value: CostQuality
  text: string
  /** UNKNOWN here means the verdict itself is unknown, not that the key is missing */
  isUnknownVerdict: boolean
  source: string
  note: string
}

const QUALITY_NOTE = '质量标签的算法：每条用量样本都声明精确才是 EXACT，任一条估算即 ESTIMATED，没有样本或没有声明即 UNKNOWN。它是标签，不是金额，也不是准确率。'

export function summaryQuality(snap: SnapshotV3 | null): QualityReading {
  const summary = snap?.tokenSummary ?? null
  if (!summary) {
    return {
      key: 'costQuality', label: '成本质量', origin: 'NULL_FIELD', value: 'UNKNOWN',
      text: UNKNOWN_TEXT, isUnknownVerdict: true, source: NO_SNAPSHOT, note: QUALITY_NOTE,
    }
  }
  const value = (summary.costQuality ?? 'UNKNOWN') as CostQuality
  return {
    key: 'costQuality', label: '成本质量', origin: 'PROJECTED', value,
    text: fmtCostQuality(value), isUnknownVerdict: value === 'UNKNOWN',
    source: `${SUMMARY_SOURCE}.costQuality`, note: QUALITY_NOTE,
  }
}

/**
 * Coverage, kept as its two numbers.
 *
 * The snapshot does carry `coverage.numerator` / `coverage.denominator`, so a percentage would be
 * arithmetically possible — and is still refused: coverage's own scope string is what makes those two
 * numbers comparable, and this page has no cache or request denominators to pair with them. So nothing
 * here divides anything. 分母为零 and 分母未知 are stated as two different sentences (数据合同 §计量).
 */
export interface CoverageReading {
  numerator: NumberReading
  denominator: NumberReading
  scope: { value: string | null; text: string; note: string }
  /** always null by design: this page prints no ratio, so there is nothing to compare against */
  ratioText: null
  note: string
}

const COVERAGE_SOURCE = 'snapshot_api.py → coverage{numerator,denominator,scope}'

export function coverageReading(snap: SnapshotV3 | null): CoverageReading {
  const cov = snap?.coverage ?? null
  const unit = '计数'
  return {
    numerator: readNumberField({
      key: 'coverageNumerator', label: '覆盖分子', unit, precision: '整数计数',
      raw: cov?.numerator, source: cov ? COVERAGE_SOURCE : NO_SNAPSHOT,
      note: '分子是被覆盖的对象数，口径由 scope 说明。',
    }),
    denominator: readNumberField({
      key: 'coverageDenominator', label: '覆盖分母', unit, precision: '整数计数',
      raw: cov?.denominator, source: cov ? COVERAGE_SOURCE : NO_SNAPSHOT,
      note: cov?.denominator === 0
        ? '分母为零：源报告没有可覆盖的对象。这与分母未知是两句话，界面不把它读成未知，也不读成百分之百缺失。'
        : '分母未知时不算任何比率。',
    }),
    scope: {
      value: cov?.scope ?? null,
      text: cov?.scope || UNKNOWN_TEXT,
      note: cov?.scope
        ? 'scope 是分子分母共同的口径名；口径不一致的两个数不在本页并列比较。'
        : 'scope 为 null：口径未说明，所以这两个数只是两个数。',
    },
    ratioText: null,
    note: '本页不把分子分母相除，也不显示任何百分比：可比的比率需要源端同口径定义，界面不自建。',
  }
}

/** One project's usage, as the per-project rollup reports it. */
export interface ProjectUsageRow {
  projectId: string
  displayName: string | null
  fields: NumberReading[]
  quality: QualityReading
  /** how many of the three token fields the source actually reported */
  reportedFieldCount: number
  hasAnyReportedNumber: boolean
  /** all three fields null and quality UNKNOWN — the projection's shape for "no sample for this id" */
  looksLikeNoSample: boolean
}

export function projectUsageRows(snap: SnapshotV3 | null): ProjectUsageRow[] {
  const projects: Project[] = snap?.projects ?? []
  return projects.map((project) => {
    const token = project?.token ?? null
    const source = `snapshot_api.py::_project_projection → projects[${project.projectId}].token`
    const fields = TOKEN_FIELDS.map((field) => readNumberField({
      key: `${project.projectId}:${field.key}`,
      label: field.label,
      raw: token ? token[field.key] : undefined,
      source: token ? source : `${source}（快照没带 token 对象）`,
      note: field.note,
    }))
    const quality = summaryQualityOf(token?.costQuality, source)
    const reportedFieldCount = fields.filter((f) => f.origin === 'PROJECTED').length
    return {
      projectId: project.projectId,
      displayName: project.displayName ?? null,
      fields, quality, reportedFieldCount,
      hasAnyReportedNumber: reportedFieldCount > 0,
      looksLikeNoSample: reportedFieldCount === 0 && quality.value === 'UNKNOWN',
    }
  })
}

function summaryQualityOf(value: CostQuality | null | undefined, source: string): QualityReading {
  const verdict = (value ?? 'UNKNOWN') as CostQuality
  return {
    key: 'costQuality', label: '成本质量',
    origin: value ? 'PROJECTED' : 'NULL_FIELD',
    value: verdict, text: fmtCostQuality(verdict), isUnknownVerdict: verdict === 'UNKNOWN',
    source: `${source}.costQuality`,
    note: 'UNKNOWN 有两种来源：这个项目名下没有用量样本，或样本没有声明质量。投影不区分两者，所以本页不推断。',
  }
}

/**
 * The exact / estimated / unknown subsets, counted row by row.
 *
 * The counts come from `snap.projects[].token.costQuality`, never from the snapshot-level label:
 * a summary reading EXACT says nothing about how many project rows say EXACT (`_token_summary`
 * weights samples, the rows are a registry projection). A row count is also not a sample count —
 * the projection carries no per-project sample totals, which is stated in `basis`.
 */
export interface QualitySubsetCounts {
  rows: number
  exact: number
  estimated: number
  unknown: number
  rowsWithoutAnyReportedNumber: number
  summaryQuality: CostQuality
  basis: string
  note: string
  readings: NumberReading[]
}

const ROW_COUNT_SOURCE = '界面逐行数 projects[].token.costQuality（派生计数，不是投影字段）'

export function qualitySubsetCounts(snap: SnapshotV3 | null): QualitySubsetCounts {
  const rows = projectUsageRows(snap)
  const exact = rows.filter((r) => r.quality.value === 'EXACT').length
  const estimated = rows.filter((r) => r.quality.value === 'ESTIMATED').length
  const unknown = rows.filter((r) => r.quality.value === 'UNKNOWN').length
  const withoutSample = rows.filter((r) => !r.hasAnyReportedNumber).length
  const readings = [
    readNumberField({ key: 'rows', label: '已投影项目行数', raw: rows.length, unit: ROWS_UNIT, precision: ROWS_PRECISION, derived: true, source: ROW_COUNT_SOURCE, note: '零行是注册表没投影项目，不等于没有用量样本。' }),
    readNumberField({ key: 'exact', label: '精确（EXACT）行', raw: exact, unit: ROWS_UNIT, precision: ROWS_PRECISION, derived: true, source: ROW_COUNT_SOURCE, note: '按行数出，样本数不在投影里。' }),
    readNumberField({ key: 'estimated', label: '估算（ESTIMATED）行', raw: estimated, unit: ROWS_UNIT, precision: ROWS_PRECISION, derived: true, source: ROW_COUNT_SOURCE, note: '估算不等于错误，也不等于已扣款。' }),
    readNumberField({ key: 'unknown', label: '未知（UNKNOWN）行', raw: unknown, unit: ROWS_UNIT, precision: ROWS_PRECISION, derived: true, source: ROW_COUNT_SOURCE, note: '未知里混着「无样本」与「样本未声明质量」两种来源，见下方无计数行。' }),
    readNumberField({ key: 'noReportedField', label: '其中三个 Token 字段全未报告的行', raw: withoutSample, unit: ROWS_UNIT, precision: ROWS_PRECISION, derived: true, source: ROW_COUNT_SOURCE, note: '全未报告是缺失，不表示这些项目零用量。' }),
  ]
  return {
    rows: rows.length, exact, estimated, unknown,
    rowsWithoutAnyReportedNumber: withoutSample,
    summaryQuality: summaryQuality(snap).value,
    basis: ROW_COUNT_SOURCE,
    note: '行数不等于样本数：快照不投影每个项目名下有多少条用量样本，也不投影样本时间窗。',
    readings,
  }
}

/**
 * The one consistency check the projection makes possible, labelled as an interface cross-read.
 *
 * `tokenSummary` totals every usage sample; the project rows only cover ids the registry projected
 * (`_rollup_usage` buckets samples with no projectId under `unknown`, which has no row). So the two
 * numbers may legitimately differ, and a gap between them is a statement about attribution — never a
 * value that overwrites either side. Nulls are never summed as zero: one unreported row makes the whole
 * row-side total not computable.
 */
export interface RowsTotalReading {
  computable: boolean
  value: number | null
  text: string
  rowsMissing: number
  note: string
}

export interface ConsistencyReading {
  summaryTotal: NumberReading
  rowsTotal: RowsTotalReading
  verdict: string
}

export function usageConsistency(snap: SnapshotV3 | null): ConsistencyReading {
  const summaryTotal = summaryTokenFields(snap).find((f) => f.key === 'totalTokens')!
  const rows = projectUsageRows(snap)
  const totalField = (row: ProjectUsageRow) => row.fields.find((f) => f.key.endsWith(':totalTokens'))!
  const missing = rows.filter((row) => totalField(row).origin === 'NULL_FIELD').length

  let rowsTotal: RowsTotalReading
  if (rows.length === 0) {
    rowsTotal = {
      computable: false, value: null, text: UNKNOWN_TEXT, rowsMissing: 0,
      note: '没有项目行可加。这不表示总量缺失，也不表示总量为零。',
    }
  } else if (missing > 0) {
    rowsTotal = {
      computable: false, value: null, text: '不可计算', rowsMissing: missing,
      note: `${missing} 行未报告总 Token。缺失不按零相加，因此界面不求出这个合计。`,
    }
  } else {
    const sum = rows.reduce((acc, row) => acc + (totalField(row).value as number), 0)
    rowsTotal = {
      computable: true, value: sum, text: groupInteger(sum), rowsMissing: 0,
      note: '界面把每行都报告了的总 Token 相加，只为核对口径；相加结果不覆盖任何投影值。',
    }
  }

  let verdict: string
  if (!snap) verdict = '快照未到达，两侧都没有值，无从核对。'
  else if (!rowsTotal.computable) verdict = '行侧合计不可计算，本页不做比较。'
  else if (summaryTotal.origin === 'NULL_FIELD') verdict = '快照汇总未报告总量，本页不做比较。'
  else if (summaryTotal.value === rowsTotal.value) verdict = '行侧合计与快照汇总相同（界面核对结论，不是第二个真源）。'
  else verdict = `两者相差 ${groupInteger(Math.abs((summaryTotal.value as number) - (rowsTotal.value as number)))}（界面派生差值）。汇总覆盖全部用量样本，行侧只覆盖注册表投影出来的项目身份，缺 projectId 的样本没有对应行。差值只说明口径不同，不修正任何一个投影值。`

  return { summaryTotal, rowsTotal, verdict }
}

// ---------------------------------------------------------------------------
// The named source gaps. Every entry is a question WUI-05 has to answer and the
// v3 snapshot cannot, carrying WHAT THE PRODUCER ACTUALLY DOES as the reason.
// ---------------------------------------------------------------------------

export type UsageGapBlockKey =
  | 'cache' | 'credits' | 'cost' | 'resource' | 'conservation' | 'requestDenominator'

export interface UsageSourceGap {
  key: string
  question: string
  /** the producer's own behaviour, so the reader can tell a gap from a design choice */
  reason: string
  block: UsageGapBlockKey
}

const STORE_COLS = 'canonical_store.py 的 usage_samples 行里有这列'
const NOT_PROJECTED = 'snapshot_api.py 的 _token_summary 只投影 input / output / total 与质量标签，不投影它'
const ROLLUP_OUTSIDE = 'apps/observer/scripts/usage_rollup.py 在快照路径之外累计它，结果从不进入 /api/v1/snapshot'

export const USAGE_SOURCE_GAPS: UsageSourceGap[] = [
  {
    key: 'cacheReadTokens',
    question: '缓存读取 Token 有多少？',
    reason: `${STORE_COLS} cache_read_tokens；${NOT_PROJECTED}。${ROLLUP_OUTSIDE}，所以界面读不到，本页不放任何缓存数值。`,
    block: 'cache',
  },
  {
    key: 'cacheWriteTokens',
    question: '缓存写入 Token 有多少？',
    reason: `${STORE_COLS} cache_write_tokens；${NOT_PROJECTED}。缓存写入按合同不算读命中，界面也不把它并入输入总量。`,
    block: 'cache',
  },
  {
    key: 'cacheInputShare',
    question: '缓存占完整输入的比是多少？',
    reason: '占比需要同口径的两个数：缓存读输入之和与完整输入之和。后者在快照里（tokenSummary.inputTokens），前者根本没有被投影；缺一个数就不算比率，界面不用别的字段凑。',
    block: 'cache',
  },
  {
    key: 'reasoningTokens',
    question: '推理 Token 有多少？',
    reason: `${STORE_COLS} reasoning_tokens；${NOT_PROJECTED}。界面不用总量减输入输出反推它 —— 总量本身是源报告的另一个字段，相减得到的既不是推理 Token 也不是别的东西。`,
    block: 'cache',
  },
  {
    key: 'toolTokens',
    question: '工具调用 Token 有多少？',
    reason: `${STORE_COLS} tool_tokens；${NOT_PROJECTED}。工具载荷属采集白名单，界面不从正文估算 Token。`,
    block: 'cache',
  },
  {
    key: 'subagentTokens',
    question: '子 Agent Token 有多少？',
    reason: `${STORE_COLS} subagent_tokens；${NOT_PROJECTED}。子 Agent 轨迹默认不采集，因此也没有可投影的计量。`,
    block: 'cache',
  },
  {
    key: 'credits',
    question: 'Credits 用了多少？',
    reason: 'usage_samples 没有 Credits 列，快照也不带任何 Credits 字段。合同规定 Credits 不与 Token 任意换算，所以本页既不显示 Credits 数值，也不显示折算率。',
    block: 'credits',
  },
  {
    key: 'creditConsumptionOrder',
    question: '额度按什么顺序消耗（套餐内、额外、免费）？',
    reason: '消耗顺序是源端计费状态，快照未投影，界面不预测下一步会扣哪一类额度。',
    block: 'credits',
  },
  {
    key: 'quota',
    question: '还剩多少配额 / 何时重置？',
    reason: '配额与重置时间既不在 usage 行也不在快照投影里；前端没有获准的配额来源，因此不做推断，也不显示进度条。',
    block: 'credits',
  },
  {
    key: 'costEstimate',
    question: '费用估算是多少？',
    reason: `${STORE_COLS} cost_estimate；${NOT_PROJECTED}，快照只投影质量标签。合同要求估算不冒充实际扣款，所以本页两个金额都不给。`,
    block: 'cost',
  },
  {
    key: 'costReconciled',
    question: '实际扣款 / 对账金额是多少？',
    reason: `${STORE_COLS} cost_reconciled 与 billing_type；${NOT_PROJECTED}。没有对账来源与对账时间，界面不显示金额，也不显示「已扣」。`,
    block: 'cost',
  },
  {
    key: 'priceAndFx',
    question: '用了哪个单价与汇率？',
    reason: '单价目录与汇率既不在 usage 行也不在快照里；既有约束（U07）禁止前端做金额与汇率计算，本页因此不出现任何货币符号。',
    block: 'cost',
  },
  {
    key: 'resources',
    question: 'CPU / 内存 / 磁盘占用是多少？',
    reason: 'v3 快照没有资源序列字段，历史前端的资源面板就是因此被判为幻影模型。界面不估算资源占用。',
    block: 'resource',
  },
  {
    key: 'latency',
    question: '耗时或延迟是多少？',
    reason: `${ROLLUP_OUTSIDE}（同一脚本在快照之外累计 latencyMs），投影里没有时长字段，所以本页不显示任何延迟。`,
    block: 'resource',
  },
  {
    key: 'ingestionMode',
    question: '这条用量是增量还是累计？',
    reason: '快照不声明采集模式，usage 行也没有该标记。合同要求前端只读源端统一后的增量贡献、不自行相加累计值，因此本页不做任何相加，只逐字段显示。',
    block: 'conservation',
  },
  {
    key: 'usageRevisions',
    question: '同一用量的修订历史在哪里？',
    reason: '用量修订序列未投影；快照顶层的 revision 是快照自己的修订，不是用量的修订，不拿它冒充。先估算后实报应替代，但界面收不到替代事件，因此无法确认替代已发生。',
    block: 'conservation',
  },
  {
    key: 'parentChildRollup',
    question: '父子项目或父子会话的用量怎么汇总？',
    reason: '父子汇总归属未投影，界面无法把子用量并入父总量，也不能反向把父总量拆到子项；本页因此只显示单个 projectId 的行。',
    block: 'conservation',
  },
  {
    key: 'forkReplayDedupe',
    question: '重试、fork、replay 与重复上传是否只计一次？',
    reason: `${ROLLUP_OUTSIDE}（去重指纹同样在那条路径里）。投影里没有指纹也没有去重标记，所以本页不声称总量守恒，只说明无法证明。`,
    block: 'conservation',
  },
  {
    key: 'requestSampleCount',
    question: '有多少条用量样本、其中多少条能判断缓存读？',
    reason: '快照不投影样本条数与可判断请求数，只有按项目累加后的值。行数不等于样本数，界面不用项目行数冒充请求数。',
    block: 'requestDenominator',
  },
  {
    key: 'cacheHitRate',
    question: '请求级缓存命中率是多少？',
    reason: '命中率需要两个同口径计数：可判断请求数，以及其中缓存读大于零的请求数。usage 行以样本为单位、没有请求级行，两个数都不在投影里；合同还规定缓存写入不算读命中、不平均会话百分比，所以本页连分母都无法命名，只显示这个缺口。',
    block: 'requestDenominator',
  },
  {
    key: 'perModelProviderSplit',
    question: '按模型与提供商怎么拆分？',
    reason: `${STORE_COLS} provider 与 model；${NOT_PROJECTED}，快照没有按模型或提供商拆分的字段。界面因此不做模型间比较，也不从名称推断口径。`,
    block: 'requestDenominator',
  },
]

export interface UsageGapBlock {
  key: UsageGapBlockKey
  title: string
  /** what the block can say at all — always "nothing numeric" for these blocks */
  lead: string
}

/** Ordered block list. Token numbers never appear inside one of these. */
export const USAGE_GAP_BLOCKS: UsageGapBlock[] = [
  { key: 'cache', title: '缓存 · 读取与写入', lead: '缓存 Token 与缓存占比都不在快照投影里：本节只列命名缺口，不放任何数值。' },
  { key: 'requestDenominator', title: '请求级分母与命中率', lead: '比率需要同口径分母。本节说明缺的是哪一个数，不显示百分比，也不平均任何百分比。' },
  { key: 'credits', title: 'Credits 与配额', lead: 'Credits 与配额是独立口径，不与 Token 换算；本节没有任何可投影的字段。' },
  { key: 'cost', title: '费用与实际扣款', lead: '快照只投影质量标签（精确 / 估算 / 未知），不投影金额。估算不冒充扣款，因此本节不出现货币数值。' },
  { key: 'resource', title: '资源与时长', lead: 'CPU、内存、磁盘与耗时不在 v3 快照里，也不由界面估算。' },
  { key: 'conservation', title: '守恒 · 增量与累计、修订、父子汇总、去重', lead: '守恒需要源端身份。投影没有提供，所以本节不声称总量守恒，只说明哪一环缺证据。' },
]

export function gapsForBlock(block: UsageGapBlockKey): UsageSourceGap[] {
  return USAGE_SOURCE_GAPS.filter((gap) => gap.block === block)
}

/** A gap key that no block claims would disappear from the page; the tests use this guard. */
export function gapBlockKeysInUse(): UsageGapBlockKey[] {
  return [...new Set(USAGE_SOURCE_GAPS.map((gap) => gap.block))]
}

/**
 * The read-only boundary, in words instead of controls.
 *
 * Observer is strictly read-only, so this surface ships no button at all — not even a disabled one,
 * because a disabled action still reads as "available if only I had the rights". These are the things a
 * reader might expect this page to do and it never does.
 */
export const USAGE_READONLY_BOUNDARY: string[] = [
  '不触发重算、重新采集或对账：用量的产生与统一都在 Workflow 侧的 canonical store。',
  '不修改任何字段，也不把界面算出的合计写回快照。',
  '不申请配额、不购买 Credits、不提交成本调整单。',
  '不把缺失改写成零，不在缺分母时补一个百分比。',
  '行链接只跳转地址（项目详情），不发起任何操作；链接的 href 就是同一个地址，复制、新开与刷新结果一致。',
]
