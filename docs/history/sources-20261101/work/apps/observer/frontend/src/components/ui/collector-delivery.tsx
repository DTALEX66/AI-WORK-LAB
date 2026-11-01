// WUI-11/WUI-18: the collector delivery section is one fact, so it is worded once.
//
// Settings, the diagnostics lane and the Work inspector all read the same snapshot
// key. Rendering it from this component keeps "absent / empty / reporting" and the
// no-rate rule identical everywhere instead of drifting into three paraphrases.
import { NO_RATE_NOTE, freshButRefusing, readCollectorDelivery } from '@/lib/collectorDelivery'
import type { CollectorDelivery } from '@/types'

export function CollectorDeliverySummary({
  collectors,
}: {
  collectors: CollectorDelivery[] | undefined
}) {
  const reading = readCollectorDelivery(collectors)
  if (reading.state === 'gap') {
    return <div className="text-[12px] text-warning" data-collector-gap="true">{reading.message}</div>
  }
  if (reading.state === 'unregistered') {
    return <div className="text-[12px] text-muted" data-collector-unregistered="true">{reading.message}</div>
  }
  const refusingFresh = freshButRefusing(reading.rows)
  return (
    <>
      <div className="list">
        {reading.rows.map((row) => (
          <div key={row.key} className="list-item flex-col items-stretch gap-1" data-collector-row={row.name}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[12px] font-semibold text-ink font-mono">{row.name}</span>
              <span className={row.fresh ? 'tag ok' : 'tag warn'}>{row.freshness}</span>
            </div>
            <div className="text-[12px] text-muted">
              交出 {row.delivered} · 拒绝 {row.refused} · 队列丢弃 {row.dropped} · 运行 {row.runs}
            </div>
            {row.refusing && (
              <div className="text-[12px] text-warning">拒绝原因：{row.refusal}</div>
            )}
          </div>
        ))}
      </div>
      {refusingFresh.length > 0 && (
        <div className="mt-2 text-[12px] text-warning" data-collector-fresh-but-refusing={refusingFresh.length}>
          {refusingFresh.length} 个采集器状态新鲜却仍在拒绝行：覆盖「新鲜」不等于「数据全进来了」。
        </div>
      )}
      <div className="mt-3 text-[12px] text-muted">{NO_RATE_NOTE}</div>
    </>
  )
}
