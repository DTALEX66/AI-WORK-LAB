/**
 * WUI-18(e)/WUI-11: read the per-collector delivery and refusal section as three different statements.
 *
 * The snapshot's `collectors` key can be absent, an empty list, or a list of rows — and those mean
 * "health was never read", "health was read and no collector is registered", and "here is what each
 * collector delivered and refused". Collapsing the first two is the error WUI-11 refuses to render
 * (无数据 / 不存在 / 未连接 are separate explanations), so the classification lives here, tested, instead of
 * in a component's `??` chain.
 *
 * No percentage is computed, deliberately. The producer publishes `deliveredRows` and `refusedRows`; it does
 * not publish "rows offered" as its own figure, and a rate built from the two counters would be presented as
 * a loss ratio the payload never claimed. Counts are rendered as counts.
 */
import type { CollectorDelivery } from '@/types'

export type CollectorReading =
  | { state: 'gap'; message: string }
  | { state: 'unregistered'; message: string }
  | { state: 'reporting'; rows: CollectorRowReading[] }

export interface CollectorRowReading {
  key: string
  name: string
  delivered: string
  refused: string
  dropped: string
  runs: string
  /** '新鲜' | '连续失败 N 次' | '熔断打开' — the breaker and the streak are different facts */
  freshness: string
  refusal: string | null
  refusing: boolean
  fresh: boolean
}

export const GAP_MESSAGE = '来源缺口：快照没有 collectors 字段——采集健康表未被读取。'
  + '这不表示没有采集器，也不表示采集器没有产出。'
export const UNREGISTERED_MESSAGE = '已读取采集健康表：当前没有登记任何采集器（worker 尚未记录过任何一个）。'
export const NO_RATE_NOTE = '这里不算比率：生产者只发布交付与拒绝的累计行数，没有发布“应到行数”，'
  + '把两个计数器相除会造出一个 payload 从未声称的损失率。'

const count = (value: number): string => `${value} 行`

function freshness(row: CollectorDelivery): string {
  if (row.circuitOpen) return '熔断打开'
  if (row.consecutiveFailures > 0) return `连续失败 ${row.consecutiveFailures} 次`
  if (row.fresh) return '新鲜'
  return '不新鲜（无成功记录）'
}

export function readCollectorDelivery(
  collectors: CollectorDelivery[] | undefined,
): CollectorReading {
  if (collectors === undefined) return { state: 'gap', message: GAP_MESSAGE }
  if (collectors.length === 0) return { state: 'unregistered', message: UNREGISTERED_MESSAGE }
  return {
    state: 'reporting',
    rows: collectors.map((row) => ({
      key: row.collector,
      name: row.collector,
      delivered: count(row.deliveredRows),
      refused: count(row.refusedRows),
      dropped: count(row.droppedEvents),
      runs: `${row.totalRuns} 次`,
      freshness: freshness(row),
      // A null reason means "no refusal has been recorded with a reason", not "refused nothing":
      // render it as 无 rather than dropping the line, so the row keeps saying what it knows.
      refusal: row.lastRefusalReason === null ? '无具名拒绝原因记录' : row.lastRefusalReason,
      refusing: row.refusedRows > 0,
      fresh: row.fresh,
    })),
  }
}

/** True when a fresh collector is still refusing rows — the combination coverage alone cannot express. */
export function freshButRefusing(rows: CollectorRowReading[]): CollectorRowReading[] {
  return rows.filter((row) => row.fresh && row.refusing)
}
