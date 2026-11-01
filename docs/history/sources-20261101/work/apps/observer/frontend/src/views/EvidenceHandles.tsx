// WUI-15 · 证据把手（快照声明，不读内容）
//
// Split out of `views/EvidenceView.tsx` by the 2026-10-20 refactoring review (item ⑤): the handle block
// was 329-826 of a 1042-line file — 48% of the lane's bytes for one card. The lane keeps the slice read
// (`EvidenceColumns`) and the primitives both surfaces share (`Field`, `num`/`bool`/`text`, `FactOrigin`),
// which this module imports instead of copying, so there is still exactly one 未提供 renderer.
//
// The producer publishes two top-level keys next to the evidence shelf: `artifactHandles` (identity rows)
// and `artifactHandlesSummary` (the scope report that says how the rows were chosen). Both were measured on
// a live v3 snapshot and both were invisible here. The rules this block follows, in order:
//
//  * no content, ever, in any direction. `contentIncluded=false` is a statement about the payload, so the
//    block renders no preview, no open-file affordance, no read-bytes link — the range endpoint is the only
//    thing that can return bytes, and it needs its own address;
//  * no re-ordering. The snapshot owns the order and publishes `orderingRule` saying so; the front end
//    shows the rule and keeps the rows in the sequence it received (a sort here would silently disagree
//    with the disclosure two lines above it);
//  * no padded numbers. A missing count prints 未提供 with its origin, and a count whose runtime shape is
//    not a number — the live `refused.droppedOnVerification` is an object — prints no number at all. A key
//    that is simply ABSENT is a source gap, which is a different statement from a measured 0 and must not
//    borrow the empty default of the map beside it (review item ②);
//  * absence is not emptiness. `artifactHandles` undefined is a source gap; `artifactHandles: []` is an
//    enumerated surface with nothing on it. `snap === null` is a third thing again;
//  * the truncation is disclosed, not hidden: 快照下发 / 枚举 / 省略 / 敏感名拒 / 再生目录剪 ride the header
//    so a reader never mistakes a capped window for the whole repository. "投影" is reserved for what a
//    value's origin marker says (取自快照投影 = `data-origin="PROJECTED"`), and the row count of this card
//    says 窗口内 — three different facts, three different words (review item ③);
//  * a refusal is a fact, not an incident. The producer declines sensitive names and prunes regenerable
//    directories on every run (measured on the live snapshot), so this state stays in the vocabulary —
//    `artifactHandlesSummary.refused` IS the partial-failure signal — and wears the compact presentation
//    (left-aligned strip, no page-level band, no 64px icon circle). Same words, same counts, less weight
//    (review item ④): a card that always shouts is a card nobody reads.
//
// No capacity number is written in this file — every one of them is read from the summary. That is what
// `evidenceHandles.contract.test.tsx` fails on when a literal is typed in here, and the reason the test
// reads THIS file's source after the split.
import * as React from 'react'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState, ProductStateCard, UnknownState } from '@/components/ui/states'
import { cn } from '@/lib/utils'
import type { ArtifactHandle, ArtifactHandlesSummary, SnapshotV3 } from '@/types'
import { fmtTimestamp } from '@/lib/api'
import {
  CONTROL_CHARS, EVIDENCE_PARAM_NAMES, fmtBytes, isRecord,
} from '@/lib/evidenceRange'
import { Field, bool, num, text, type FactOrigin } from '@/views/EvidenceView'

type Snap = SnapshotV3 | null

/** One summary fact: the printed value, and when there is none, why there is none. */
interface Fact { value: string | null; missing: string; origin: FactOrigin }

const absentFact = (label: string): Fact => ({
  value: null,
  missing: `生产者没有给出 ${label} 字段（来源缺口，不预填）`,
  origin: 'SOURCE_GAP',
})

/** A count. Non-numeric runtime shapes keep their shape in the reason and produce no number. */
function countFact(raw: unknown, label: string): Fact {
  if (raw === undefined) return absentFact(label)
  if (raw === null) return { value: null, missing: `${label} 在快照投影里是 null —— 未记录，不等于 0`, origin: 'NULL_FIELD' }
  if (typeof raw !== 'number') {
    return {
      value: null,
      missing: `${label} 的形态不是计数（实测 ${Array.isArray(raw) ? 'array' : typeof raw}），不折算成 0`,
      origin: 'NULL_FIELD',
    }
  }
  const value = num(raw)
  return value === null
    ? { value: null, missing: `${label} 不是可表示的数值`, origin: 'NULL_FIELD' }
    : { value, missing: '', origin: 'PROJECTED' }
}

function stringFact(raw: unknown, label: string): Fact {
  if (raw === undefined) return absentFact(label)
  const value = text(typeof raw === 'string' ? raw : null)
  return value === null
    ? { value: null, missing: `${label} 未取自快照投影（不是字符串形态）`, origin: 'NULL_FIELD' }
    : { value, missing: '', origin: 'PROJECTED' }
}

/** A declared boolean, printed with its raw token so the reader can check the wording against the field. */
function flagFact(raw: unknown, label: string, yes: string, no: string): Fact {
  if (raw === undefined) return absentFact(label)
  const value = bool(typeof raw === 'boolean' ? raw : null, yes, no)
  return value === null
    ? { value: null, missing: `${label} 未取自快照投影（不是布尔形态）`, origin: 'NULL_FIELD' }
    : { value: `${String(raw)} · ${value}`, missing: '', origin: 'PROJECTED' }
}

const seg = (label: string, fact: Fact): string => `${label} ${fact.value ?? 'UNKNOWN'}`

/** The row's `digest` / `digestSource`. `types.ts::ArtifactHandle` names the seven schema keys only, and
 *  the producer attaches these two to the rows whose digest was recorded — read here rather than
 *  re-declared, so the schema stays the single type authority. */
const rowField = (row: ArtifactHandle, key: 'digest' | 'digestSource'): string | null =>
  text((row as unknown as Record<string, unknown>)[key] as string | null | undefined)

const HANDLES_DIGEST_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'recorded', label: '已登记摘要' },
  { value: 'unrecorded', label: '未登记摘要' },
] as const

type HandlesDigestFilter = 'all' | 'recorded' | 'unrecorded'

/** Kept alive while a filter link is followed: the shell's own state, the addressed slice, the filters.
 *  `evidenceHref()` in `lib/evidenceRange.ts` owns the artifact address and its own preserve list; this
 *  lane-local copy exists because a filter must not be able to drop a read that is already addressed.
 *  The handle names themselves are imported, never retyped here — the two lists drifting apart is exactly
 *  how one click on a source started to lose the filter (review item ⑥). */
const HANDLES_PRESERVED_PARAMS = ['theme', 'layout', 'palette', 'api', 'shell', 'taskId', 'executionId',
  ...EVIDENCE_PARAM_NAMES] as const

const HANDLES_MAX_SURFACE_LENGTH = 128

interface HandlesFilterVerdict { surface: string | null; digest: HandlesDigestFilter; rejected: string[] }

/** The same discipline as `readEvidenceAddress()`: an illegal value is reported, never applied, and never
 *  answered by falling back to the first option. */
function readHandlesFilters(search: string, knownSurfaces: string[]): HandlesFilterVerdict {
  let params: URLSearchParams
  try { params = new URLSearchParams(search) } catch { return { surface: null, digest: 'all', rejected: [] } }
  const rejected: string[] = []

  const rawSurface = params.get('handlesSurface')
  let surface: string | null = null
  if (rawSurface !== null && rawSurface.trim() !== '') {
    const value = rawSurface.trim()
    if (value.length > HANDLES_MAX_SURFACE_LENGTH) {
      rejected.push(`handlesSurface 超过 ${HANDLES_MAX_SURFACE_LENGTH} 个字符，已拒绝`)
    } else if (CONTROL_CHARS.test(value)) {
      rejected.push('handlesSurface 含控制字符，已拒绝')
    } else if (knownSurfaces.length > 0 && !knownSurfaces.includes(value)) {
      rejected.push(`handlesSurface 不是取自快照投影的证据面（收到 ${value.slice(0, 32)}）：过滤未应用，也不回退成「全部」或第一个面`)
    } else {
      surface = value
    }
  }

  const rawDigest = (params.get('handlesDigest') ?? '').trim()
  let digest: HandlesDigestFilter = 'all'
  if (rawDigest !== '' && rawDigest !== 'all') {
    if (rawDigest === 'recorded' || rawDigest === 'unrecorded') digest = rawDigest
    else rejected.push(`handlesDigest 只接受 all / recorded / unrecorded（收到 ${rawDigest.slice(0, 24)}），已拒绝`)
  }
  return { surface, digest, rejected }
}

/** Filter state travels in the query string — web storage is forbidden in this project — so every filter
 *  click is an address, shareable and stable across a refresh. */
function handlesHref(
  search: string,
  updates: Partial<Record<'handlesSurface' | 'handlesDigest', string | null>>,
): { href: string; search: string } {
  const current = new URLSearchParams(search)
  for (const [name, value] of Object.entries(updates)) {
    if (value === null || value === undefined || value === '') current.delete(name)
    else current.set(name, value)
  }
  const params = new URLSearchParams()
  params.set('view', current.get('view') ?? 'evidence')
  for (const name of HANDLES_PRESERVED_PARAMS) {
    const value = current.get(name)
    if (value !== null && value !== '') params.set(name, value)
  }
  const qs = params.toString()
  const href = `${window.location.pathname}${qs ? `?${qs}` : ''}`
  return { href, search: qs ? `?${qs}` : '' }
}

function handlesChipClass(active: boolean): string {
  return cn(
    'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[12px] no-underline',
    active ? 'border-primary/70 bg-panel2 text-ink' : 'border-border/60 text-muted hover:text-ink',
  )
}

export function EvidenceHandles({ snap, search }: { snap: Snap; search: string }) {
  const rows: ArtifactHandle[] | null = snap && Array.isArray(snap.artifactHandles) ? snap.artifactHandles : null
  const summary: ArtifactHandlesSummary | null = snap?.artifactHandlesSummary ?? null
  // The URL is the state: it is read once at mount (so a refresh with `?handlesDigest=unrecorded` in the
  // address still arrives filtered) and rewritten on every filter click.
  const [filterSearch, setFilterSearch] = React.useState(search)

  const knownSurfaces = React.useMemo(() => {
    const found = new Set<string>()
    for (const row of rows ?? []) {
      if (typeof row.surface === 'string' && row.surface !== '') found.add(row.surface)
    }
    return Array.from(found).sort()
  }, [rows])

  const filters = React.useMemo(
    () => readHandlesFilters(filterSearch, knownSurfaces),
    [filterSearch, knownSurfaces],
  )

  const applyFilter = (
    updates: Partial<Record<'handlesSurface' | 'handlesDigest', string | null>>,
  ) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
      || event.shiftKey || event.altKey) return
    event.preventDefault()
    const next = handlesHref(filterSearch, updates)
    window.history.replaceState(null, '', next.href)
    setFilterSearch(next.search)
  }

  const visible = (rows ?? []).filter((row) => {
    if (filters.surface !== null && row.surface !== filters.surface) return false
    if (filters.digest === 'recorded') return row.digestRecorded === true
    if (filters.digest === 'unrecorded') return row.digestRecorded === false
    return true
  })
  // A row without the flag is neither recorded nor unrecorded, so it takes part in no digest filter and
  // says so rather than being counted on the side that happens to be smaller.
  const unflagged = (rows ?? []).filter((row) => typeof row.digestRecorded !== 'boolean').length

  const projectedCount = countFact(summary?.projectedCount, 'projectedCount')
  const enumeratedCount = countFact(summary?.enumeratedCount, 'enumeratedCount')
  const omittedCount = countFact(summary?.omittedCount, 'omittedCount')
  const refusedFacts = summary !== null && isRecord(summary.refused) ? summary.refused : null
  const sensitiveNames = countFact(refusedFacts?.sensitiveNames, 'refused.sensitiveNames')
  const prunedDirectories = countFact(refusedFacts?.prunedRegenerableDirectories, 'refused.prunedRegenerableDirectories')
  const notRegularFiles = countFact(refusedFacts?.notRegularFiles, 'refused.notRegularFiles')
  const reparseDirectories = countFact(refusedFacts?.reparseDirectories, 'refused.reparseDirectories')
  const unreadableEntries = countFact(refusedFacts?.unreadableEntries, 'refused.unreadableEntries')
  // `droppedOnVerification` is a per-reason map, so the card's one number is the map's own sum — but only
  // when the map is actually there. Summing `?? {}` printed "核对时丢弃 0" for a key the producer never
  // published, which is the padded-zero shape this whole lane exists to refuse (review item ②). A key that
  // is absent is ABSENT: 未提供 with its origin, and it contributes nothing to the total either.
  const droppedRaw = refusedFacts?.droppedOnVerification
  const droppedMap = isRecord(droppedRaw) ? droppedRaw : null
  const droppedEntries = droppedMap === null
    ? 0
    : Object.values(droppedMap).reduce((total, count) => total + (typeof count === 'number' ? count : 0), 0)
  const droppedValue = refusedFacts === null || droppedRaw === undefined
    ? undefined
    : droppedMap === null
      ? droppedRaw
      : droppedEntries
  const droppedCount = countFact(droppedValue, 'refused.droppedOnVerification')
  // A refusal total is only meaningful when the producer published a refusal record at all; an absent
  // `refused` map stays null so the card cannot appear with invented zeroes.
  const refusalTotal = refusedFacts
    ? [refusedFacts.notRegularFiles, refusedFacts.reparseDirectories, refusedFacts.sensitiveNames,
       refusedFacts.unreadableEntries, refusedFacts.prunedRegenerableDirectories]
        .reduce((total: number, raw) => total + (typeof raw === 'number' ? raw : 0), 0)
      + droppedEntries
    : null
  const capacityLine = [
    seg('快照下发', projectedCount), seg('枚举', enumeratedCount), seg('省略', omittedCount),
    seg('敏感名拒', sensitiveNames), seg('再生目录剪', prunedDirectories),
  ].join(' / ')

  const digestIndex = summary !== null && isRecord(summary.digestIndex) ? summary.digestIndex : null
  const cost = summary !== null && isRecord(summary.cost) ? summary.cost : null
  const content = flagFact(
    summary?.contentIncluded, 'contentIncluded',
    '随快照下发（本区块仍然只列身份，内容渲染归区间读那一侧）',
    '不随快照下发（本区块没有预览 / 打开 / 读取字节的入口）',
  )

  return (
    <Card data-testid="evidence-handles">
      <CardHeader>
        <span>证据把手（快照声明，不读内容）</span>
        <span className="text-[12px] text-muted" data-testid="evidence-handles-count">
          {snap === null ? '把手清单 UNKNOWN · 数据源未接入'
            : rows === null ? '把手清单 UNKNOWN · 快照没有该字段'
            : `可见 ${visible.length} 行 / 窗口内 ${rows.length} 行`}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {snap === null ? (
          <UnknownState
            title="证据把手 UNKNOWN（数据源未接入）"
            description="没有快照就没有把手清单，也没有容量事实：这里不预填行数、不预填枚举量，也不把「读不到」画成「一个把手都没有」。"
            className="py-6"
          />
        ) : (
          <>
            <p className="m-0 text-[12px] text-muted" data-testid="evidence-handles-capacity" data-origin={summary ? 'PROJECTED' : 'SOURCE_GAP'}>
              {capacityLine}
              {summary === null ? ' —— 容量事实未知：快照没有 artifactHandlesSummary 字段，上述每一项都保持 UNKNOWN，不补 0。' : ''}
            </p>

            <div className="flex flex-wrap items-center gap-1.5" data-testid="evidence-handles-truncation">
              <Badge variant="muted">{`顺序 · ${stringFact(summary?.orderingKey, 'orderingKey').value ?? 'UNKNOWN'}`}</Badge>
              <span className="text-[12px] text-muted">
                列表顺序就是快照顺序（生产者按 orderingRule 发布，前端不再排序）。
              </span>
            </div>

            {summary?.truncated === true && (
              <p className="m-0 text-[12px] text-muted" data-testid="evidence-handles-window" data-origin="PROJECTED">
                {`窗口披露：快照下发 ${projectedCount.value ?? 'UNKNOWN'} 行 / 上限 ${countFact(summary.cap, 'cap').value ?? 'UNKNOWN'}，省略 ${omittedCount.value ?? 'UNKNOWN'} 行 —— 截断是 cap 的设计行为，不是故障；看到的是窗口，不是仓库全量。`}
              </p>
            )}
            {refusalTotal !== null && refusalTotal > 0 && (
              <ProductStateCard
                state="partial-failure"
                subject="证据把手枚举"
                detail={`生产者拒绝或剪枝 ${refusalTotal} 个条目：敏感名 ${sensitiveNames.value ?? '未提供'}、再生目录剪枝 ${prunedDirectories.value ?? '未提供'}、非普通文件 ${notRegularFiles.value ?? '未提供'}、重解析目录 ${reparseDirectories.value ?? '未提供'}、读不动条目 ${unreadableEntries.value ?? '未提供'}、核对时丢弃 ${droppedCount.value ?? '未提供'}。这些位置没有把手行，也没有被折算成"不存在"。`}
                compact
              />
            )}

            <div className="flex flex-wrap gap-3" data-testid="evidence-handles-filters">
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="按证据面过滤把手">
                <span className="text-[12px] uppercase tracking-[0.12em] text-muted">面 handlesSurface</span>
                <a
                  href={handlesHref(filterSearch, { handlesSurface: null }).href}
                  onClick={applyFilter({ handlesSurface: null })}
                  className={handlesChipClass(filters.surface === null)}
                  aria-current={filters.surface === null ? 'true' : undefined}
                  data-filter-kind="surface"
                  data-filter-value="all"
                >
                  全部面
                </a>
                {knownSurfaces.map((surface) => (
                  <a
                    key={surface}
                    href={handlesHref(filterSearch, { handlesSurface: surface }).href}
                    onClick={applyFilter({ handlesSurface: surface })}
                    className={handlesChipClass(filters.surface === surface)}
                    aria-current={filters.surface === surface ? 'true' : undefined}
                    data-filter-kind="surface"
                    data-filter-value={surface}
                  >
                    {surface}
                  </a>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="按摘要登记状态过滤把手">
                <span className="text-[12px] uppercase tracking-[0.12em] text-muted">摘要 handlesDigest</span>
                {HANDLES_DIGEST_OPTIONS.map((option) => (
                  <a
                    key={option.value}
                    href={handlesHref(filterSearch, { handlesDigest: option.value === 'all' ? null : option.value }).href}
                    onClick={applyFilter({ handlesDigest: option.value === 'all' ? null : option.value })}
                    className={handlesChipClass(filters.digest === option.value)}
                    aria-current={filters.digest === option.value ? 'true' : undefined}
                    data-filter-kind="digest"
                    data-filter-value={option.value}
                  >
                    {option.label}
                  </a>
                ))}
              </div>
            </div>

            {filters.rejected.length > 0 && (
              <div className="list" data-testid="evidence-handles-filter-rejected">
                {filters.rejected.map((reason) => (
                  <div key={reason} className="list-item" data-origin="NULL_FIELD">
                    <span className="text-[12px] text-warning">{reason}</span>
                  </div>
                ))}
              </div>
            )}

            {unflagged > 0 && (
              <p className="m-0 text-[12px] text-warning" data-origin="SOURCE_GAP" data-testid="evidence-handles-unflagged">
                {`其中 ${unflagged} 行没有 digestRecorded 字段：它既不是「已登记」也不是「未登记」，不参与摘要过滤，也不并入任何一侧的计数。`}
              </p>
            )}

            {rows === null ? (
              <div data-testid="evidence-handles-unknown">
                <UnknownState
                  title="证据把手 UNKNOWN（字段缺失）"
                  description="来源缺口：v3 快照没有 artifactHandles 字段（生产者没有发布把手清单）。这与「发布了但一个把手都没有」是两件事，所以这里不画 0 行，也不画空清单。"
                  className="py-6"
                />
              </div>
            ) : rows.length === 0 ? (
              <EmptyState
                title="没有把手行（这是查询结果）"
                description="artifactHandles 是空数组：把手枚举跑了，声明的证据面上没有可登记的把手。空列表是答案，不是缺源。"
                className="py-6"
              />
            ) : visible.length === 0 ? (
              <p className="m-0 text-[12px] text-muted" data-testid="evidence-handles-filter-empty" data-origin="PROJECTED">
                {`过滤后没有行：handlesSurface=${filters.surface ?? 'all'} · handlesDigest=${filters.digest} 在窗口内的 ${rows.length} 行里没有匹配。这是本次过滤的查询结果，窗口本身并没有变空。`}
              </p>
            ) : (
              <div className="list" data-testid="evidence-handles-rows" data-ordering="projected">
                {visible.map((row) => (
                  <HandleRow key={row.handle} row={row} />
                ))}
              </div>
            )}

            {summary === null ? (
              <div className="list">
                <div
                  className="list-item flex-col items-stretch gap-1"
                  data-testid="evidence-handles-summary-gap"
                  data-origin="SOURCE_GAP"
                >
                  <div className="text-[12px] uppercase tracking-[0.12em] text-muted">artifactHandlesSummary · 范围报告</div>
                  <div className="flex items-center gap-1.5 text-[12px] text-warning">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-secondary" aria-hidden="true" />
                    来源缺口（当前 v3 快照未携带 artifactHandlesSummary · 生产者没有发布把手的范围报告，
                    cap / 拒绝 / 摘要索引的每一格都保持 UNKNOWN，这里不逐格补 0）
                  </div>
                </div>
              </div>
            ) : (
              <div className="list" data-testid="evidence-handles-summary">
                <Field field="handlesContentIncluded" label="contentIncluded · 内容是否随快照下发" {...factProps(content)} />
                <Field field="handlesEnumerationScope" label="enumerationScope · 枚举范围" {...factProps(stringFact(summary.enumerationScope, 'enumerationScope'))} />
                <Field field="handlesCap" label="cap · 窗口上限" {...factProps(countFact(summary.cap, 'cap'))} />
                <Field field="handlesComplete" label="complete · 枚举是否走完" {...factProps(flagFact(summary.complete, 'complete', '已走完', '未走完'))} />
                <Field field="handlesTruncated" label="truncated · 是否截断" {...factProps(flagFact(summary.truncated, 'truncated', '已截断', '未截断'))} />
                <Field field="handlesGeneratedAt" label="generatedAt · 把手生成时间（整秒精度）" {...factProps(generatedFact(summary.generatedAt))} />
                <Field field="handlesOrderingRule" label="orderingRule · 排序规则（快照原文）" {...factProps(stringFact(summary.orderingRule, 'orderingRule'))} />
                <Field field="handlesRowsWithDigest" label="digestIndex.rowsWithDigest · 有摘要的行" {...factProps(countFact(digestIndex?.rowsWithDigest, 'digestIndex.rowsWithDigest'))} />
                <Field field="handlesRowsWithoutDigest" label="digestIndex.rowsWithoutDigest · 无摘要的行" {...factProps(countFact(digestIndex?.rowsWithoutDigest, 'digestIndex.rowsWithoutDigest'))} />
                <Field field="handlesComputedByHashing" label="digestIndex.computedByHashing · 是否由哈希得到" {...factProps(flagFact(digestIndex?.computedByHashing, 'computedByHashing', '由本侧哈希计算', '取自登记的摘要，界面侧不做哈希'))} />
                <Field field="handlesRecordsScanned" label="digestIndex.recordsScanned · 扫过的登记记录" {...factProps(countFact(digestIndex?.recordsScanned, 'digestIndex.recordsScanned'))} />
                <Field field="handlesRecordsUnreadable" label="digestIndex.recordsUnreadable · 读不动的记录" {...factProps(countFact(digestIndex?.recordsUnreadable, 'digestIndex.recordsUnreadable'))} />
                <Field field="handlesPairsIndexed" label="digestIndex.pairsIndexed · 建索的对数" {...factProps(countFact(digestIndex?.pairsIndexed, 'digestIndex.pairsIndexed'))} />
                <Field field="handlesElapsedMs" label="cost.elapsedMs · 生产者枚举耗时（毫秒）" {...factProps(countFact(cost?.elapsedMs, 'cost.elapsedMs'))} />
                <Field field="handlesEntriesScanned" label="cost.entriesScanned · 扫过的条目" {...factProps(countFact(cost?.entriesScanned, 'cost.entriesScanned'))} />
                <Field field="handlesNotRegularFiles" label="refused.notRegularFiles · 非普通文件" {...factProps(countFact(refusedFacts?.notRegularFiles, 'refused.notRegularFiles'))} />
                <Field field="handlesReparseDirectories" label="refused.reparseDirectories · 重解析目录" {...factProps(countFact(refusedFacts?.reparseDirectories, 'refused.reparseDirectories'))} />
                <Field field="handlesUnreadableEntries" label="refused.unreadableEntries · 读不动的条目" {...factProps(countFact(refusedFacts?.unreadableEntries, 'refused.unreadableEntries'))} />
                <Field field="handlesDroppedOnVerification" label="refused.droppedOnVerification · 核对时丢弃" {...factProps(countFact(refusedFacts?.droppedOnVerification, 'refused.droppedOnVerification'))} />
                <Field field="handlesSchemaVersion" label="schemaVersion · 摘要契约版本" {...factProps(stringFact(summary.schemaVersion, 'schemaVersion'))} />
              </div>
            )}

            <p className="m-0 text-[12px] text-muted" data-testid="evidence-handles-boundary">
              每一行只有身份元数据：handle / kind / surface / surfaceRoot / sizeBytes / modifiedAt / digestRecorded；
              digest 与 digestSource 只出现在登记过摘要的那部分行上，其数量由上面的
              digestIndex.rowsWithDigest / rowsWithoutDigest 披露，本视图不自己数行。
              时间戳是整秒精度，同一秒内的先后按快照自己的 orderingRule 决定（原文见上），本视图不补毫秒、不补时区，
              也不把缺失的摘要显示成空串。快照声明 contentIncluded=false，
              所以这里没有任何预览、打开文件或读取字节的入口：字节只能由区间读端点按地址返回。
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

/** `generatedAt` is an RFC3339 string; a value that fails the shape check stays UNKNOWN via fmtTimestamp. */
function generatedFact(raw: unknown): Fact {
  const base = stringFact(raw, 'generatedAt')
  if (base.value === null || base.origin !== 'PROJECTED') return base
  return fmtTimestamp(base.value) === 'UNKNOWN'
    ? { value: null, missing: 'generatedAt 不是可解析的 RFC3339 时间', origin: 'NULL_FIELD' }
    : { value: `${fmtTimestamp(base.value)} · 源值 ${base.value} · 整秒`, missing: '', origin: 'PROJECTED' }
}

function factProps(fact: Fact): { value: string | null; missing: string; origin: FactOrigin } {
  return { value: fact.value, missing: fact.missing, origin: fact.origin }
}

/** One projected handle. No link: the row is a declaration of identity, and turning it into a byte read
 *  would be exactly the affordance `contentIncluded=false` forbids this block from offering. */
function HandleRow({ row }: { row: ArtifactHandle }) {
  // `null` and "no key" stay different facts: a projected null is a NULL_FIELD, an absent key is a source gap.
  const size = countFact(row.sizeBytes, 'sizeBytes')
  const modified = stringFact(row.modifiedAt, 'modifiedAt')
  // Measured on the live window (see 05-artifact-handles-shape.json: every row of the projected window
  // carries surfaceRoot), so this row says what it carries and, when it carries nothing, names that as
  // THIS row's gap. The copy used to claim the producer never emits surfaceRoot — a sentence the snapshot
  // contradicts (review item ①).
  const surfaceRoot = stringFact(row.surfaceRoot, 'surfaceRoot')

  const timeCell = (() => {
    if (modified.value === null) {
      return { text: `时间未提供（${modified.missing}）`, origin: modified.origin, precision: undefined as 'second' | undefined }
    }
    const formatted = fmtTimestamp(modified.value)
    if (formatted === 'UNKNOWN') {
      return {
        text: `时间未提供（modifiedAt 不是可解析的 RFC3339 时间：源值 ${modified.value}）`,
        origin: 'NULL_FIELD' as FactOrigin,
        precision: undefined as 'second' | undefined,
      }
    }
    return {
      text: `${formatted} · 整秒精度 · 源值 ${modified.value}`,
      origin: 'PROJECTED' as FactOrigin,
      precision: 'second' as const,
    }
  })()

  const digestCell = (() => {
    const recorded = rowField(row, 'digest')
    if (row.digestRecorded === true) {
      if (recorded !== null) {
        const source = rowField(row, 'digestSource')
        return {
          text: `摘要已登记 · ${recorded}${source ? ` · 来源 ${source}` : ' · 摘要来源未取自快照投影'}`,
          origin: 'PROJECTED' as FactOrigin,
        }
      }
      return {
        text: '摘要登记为已记录，但快照投影里没有摘要值 · 不显示空串冒充摘要',
        origin: 'NULL_FIELD' as FactOrigin,
      }
    }
    if (row.digestRecorded === false) {
      return { text: '摘要未记录 · 该把手没有登记摘要（不是空摘要，也不是零）', origin: 'NULL_FIELD' as FactOrigin }
    }
    return {
      text: '摘要状态未取自快照投影 · 该行没有 digestRecorded 字段，既不按已记录也不按未记录处理',
      origin: 'SOURCE_GAP' as FactOrigin,
    }
  })()

  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-handle-row={row.handle}
      data-handles-surface={text(row.surface) ?? ''}
      data-digest-recorded={typeof row.digestRecorded === 'boolean' ? String(row.digestRecorded) : 'absent'}
    >
      <div className="flex min-w-0 flex-wrap items-baseline justify-between gap-2">
        <span className="min-w-0 break-all font-mono text-[12px] text-ink">{text(row.handle) ?? '未提供（handle 字段缺失）'}</span>
        <span className="text-[12px] text-muted tabular-nums" data-handles-cell="size" data-origin={size.origin}>
          {size.value !== null ? `${fmtBytes(row.sizeBytes)} · 源值 ${size.value} B` : `大小未提供（${size.missing}）`}
        </span>
      </div>
      <div className="flex min-w-0 flex-wrap gap-2 text-[12px] text-muted">
        <span data-handles-cell="surface" data-origin={text(row.surface) === null ? 'NULL_FIELD' : 'PROJECTED'}>
          面 {text(row.surface) ?? '未提供'}
        </span>
        <span className="break-all" data-handles-cell="surfaceRoot" data-origin={surfaceRoot.origin}>
          根（surfaceRoot） {surfaceRoot.value ?? `未提供（${surfaceRoot.missing}）`}
        </span>
        <span data-handles-cell="kind" data-origin={text(row.kind) === null ? 'NULL_FIELD' : 'PROJECTED'}>
          类 {text(row.kind) ?? '未提供'}
        </span>
        <span
          data-handles-cell="modifiedAt"
          data-origin={timeCell.origin}
          {...(timeCell.precision ? { 'data-precision': timeCell.precision } : {})}
        >
          {timeCell.text}
        </span>
        <span data-handles-cell="digest" data-origin={digestCell.origin}>{digestCell.text}</span>
      </div>
    </div>
  )
}
