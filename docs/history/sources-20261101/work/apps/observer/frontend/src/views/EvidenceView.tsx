// REQ-RANGE-20261007 · the evidence slice lane: three columns per artifact.
//
// Evidence used to reach this surface as opaque references (an `evidenceKind` string in the Inspector).
// The sidecar now answers exact byte intervals, so a reader can be shown enough to trust one artifact:
//
//   身份 — which artifact this is (handle, the digest the caller recorded for it, its size);
//   切片 — what a range read actually returned (offset, limit, endOffset, eof, the digest of those bytes);
//   判定 — whether the recorded digest agrees, and the backend's typed reason when the read was refused.
//
// What this lane refuses to do:
// * treat HTTP 200 as success. The verdict is `status` / `reason_code` in the body, and the codes are the
//   reader's (`evidence_range_reader.py::REFUSALS`), not labels invented here;
// * show an empty pane where a refusal lives. A REFUSED result carries `content: null`, so the content
//   block is not rendered at all and the reason takes its place;
// * print 0 for a field the result does not carry (an refused read has no offset, no endOffset, no slice
//   digest — `未提供` is the honest cell);
// * offer a hand-typed path field. There is no `<input>` here: an artifact is addressed by a link, the same
//   single `?view=` mechanism the Work lane uses, and the projected shelf is the only source of handles.
//
// WUI-15 (2026-10-20) adds the fourth honest surface of this lane: 证据把手. `artifactHandles` plus
// `artifactHandlesSummary` ride the live v3 payload — a cap-bounded window of identity rows over a much
// larger enumeration — and nothing rendered either key, so a reader could not see which artifacts the
// projection even claims to know about, nor that the window was truncated. That block is mounted below and
// lives in `views/EvidenceHandles.tsx` (2026-10-20 refactoring review item ⑤: it was 48% of this file).
// This file keeps what both surfaces need — the never-padding cell (`Field`), its three origin markers
// (`FactOrigin`), the `num`/`bool`/`text` readers and the three-column slice verdict — and the handle lane
// imports them instead of carrying a second copy.
import * as React from 'react'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dim } from '@/views/RecordInspector'
import { EvidenceHandles } from '@/views/EvidenceHandles'
import type { SnapshotV3 } from '@/types'
import type { RecordFocus } from '@/lib/recordFocus'
import { evidenceRangeEndpoint } from '@/lib/api'
import {
  EVIDENCE_RANGE_SCHEMA_VERSION, EVIDENCE_MAX_LIMIT, isRegisteredReasonCode, digestVerdictOf, fmtBytes,
  makeHttpSliceReader, readEvidenceAddress, readEvidenceShelf, evidenceHref,
  type EvidenceAddress, type EvidenceRangeResult, type SliceReader, type EvidenceSliceOutcome,
} from '@/lib/evidenceRange'

type Snap = SnapshotV3 | null

export interface EvidenceViewProps {
  snap: Snap
  focus?: RecordFocus
  onFocus?: (next: RecordFocus) => void
  focusRejected?: string[]
  /** test seam: the slice reader. Production default is the validated loopback GET — never another method. */
  readSlice?: SliceReader
  /** the address to read from; defaults to the live URL search. */
  search?: string
}

const PREVIEW_LIMIT = 1200

/** The three origins the projection can actually distinguish (same vocabulary as RecordInspector/UsageCache).
 *  Exported because the handle lane labels every one of its cells with the same three words — a second
 *  private copy of this union is how two lanes start meaning two things. */
export type FactOrigin = 'PROJECTED' | 'NULL_FIELD' | 'SOURCE_GAP'

/** A cell that never pads: a value the result does not carry stays 未提供 with the reason it is absent.
 *  `origin` writes the DOM contract marker (`data-origin`) so a reader — and the render-level test — can
 *  tell a projected value from an absent field without reading the prose. Exported for the handle lane:
 *  one renderer for 未提供 in this lane, not two that can disagree. */
export function Field({ label, value, missing, field, origin }: {
  label: string
  value: string | null
  missing: string
  field?: string
  origin?: FactOrigin
}) {
  return (
    <div
      className="list-item flex-col items-stretch gap-1"
      data-field={field ?? label}
      {...(origin ? { 'data-origin': origin } : {})}
    >
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{label}</div>
      {value !== null ? (
        <div className="break-words font-mono text-[12px] text-ink">{value}</div>
      ) : (
        <div className="flex items-center gap-1.5 text-[12px] text-warning">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-secondary" aria-hidden="true" />
          未提供（{missing}）
        </div>
      )}
    </div>
  )
}

/** The three "is this value actually there" readers, shared with the handle lane: an absent field and a
 *  fabricated one must not be decided twice in one file-family. */
export const num = (value: number | null | undefined): string | null =>
  typeof value === 'number' && Number.isFinite(value) ? String(value) : null

export const bool = (value: boolean | null | undefined, yes: string, no: string): string | null =>
  typeof value === 'boolean' ? (value ? yes : no) : null

export const text = (value: string | null | undefined): string | null =>
  value === null || value === undefined || value === '' ? null : value

function statusTone(status: EvidenceRangeResult['status']): 'success' | 'warning' | 'error' {
  return status === 'OK' ? 'success' : status === 'REFUSED' ? 'error' : 'warning'
}

const DIGEST_TONE: Record<string, 'success' | 'warning' | 'error' | 'muted'> = {
  AGREE: 'success', MISMATCH: 'error', UNDETERMINED: 'warning', NOT_REQUESTED: 'muted',
}

const DIGEST_LABEL: Record<string, string> = {
  AGREE: '一致', MISMATCH: '不一致', UNDETERMINED: '未判定', NOT_REQUESTED: '未请求核对',
}

type ReadState =
  | { kind: 'IDLE' }
  | { kind: 'READING' }
  /** `outcome: null` is the no-trusted-endpoint case: a read that could not even be issued. */
  | { kind: 'DONE'; outcome: EvidenceSliceOutcome | null }

export function EvidenceView({
  snap, focus = { taskId: null, executionId: null }, focusRejected = [], readSlice, search,
}: EvidenceViewProps) {
  const initialSearch = search ?? (typeof window === 'undefined' ? '' : window.location.search)
  const verdict = React.useMemo(() => readEvidenceAddress(initialSearch), [initialSearch])
  const [address, setAddress] = React.useState<EvidenceAddress | null>(
    verdict.kind === 'addressed' ? verdict.address : null,
  )
  const [state, setState] = React.useState<ReadState>({ kind: 'IDLE' })

  const endpoint = React.useMemo(() => evidenceRangeEndpoint(), [])
  // The reader lives in a ref on purpose: a caller that passes an inline function must not be able to
  // re-trigger the read on every render (an effect keyed on its identity would loop: read -> state ->
  // new closure -> read). The addressed slice is the only thing that drives a read.
  const readerRef = React.useRef<SliceReader | null>(
    readSlice ?? (endpoint ? makeHttpSliceReader(endpoint.url, endpoint.authoritative) : null),
  )
  readerRef.current = readSlice ?? readerRef.current
  const hasReader = Boolean(readSlice) || endpoint !== null

  // The address is the input; the read follows it. Re-running only happens when the addressed slice changes.
  const addressKey = address ? JSON.stringify(address) : ''
  React.useEffect(() => {
    if (!address) { setState({ kind: 'IDLE' }); return }
    const reader = readerRef.current
    if (!reader) { setState({ kind: 'DONE', outcome: null }); return }
    let cancelled = false
    setState({ kind: 'READING' })
    reader({
      handle: address.handle,
      offset: address.offset, limit: address.limit,
      expectedDigest: address.expectedDigest,
    }).then((outcome) => { if (!cancelled) setState({ kind: 'DONE', outcome }) })
    return () => { cancelled = true }
  }, [addressKey, hasReader])

  const shelf = readEvidenceShelf(snap)

  const navigate = (next: EvidenceAddress | null) => (event: React.MouseEvent) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey
      || event.shiftKey || event.altKey) return
    event.preventDefault()
    const href = evidenceHref(next, initialSearch)
    window.history.replaceState(null, '', href)
    setAddress(next)
  }

  const rejected = verdict.kind === 'rejected' ? verdict.reasons : []
  const result = state.kind === 'DONE' ? state.outcome : null

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
      <div className="flex min-w-0 flex-col gap-4">
        {focusRejected.length > 0 && (
          <Card>
            <CardHeader><span>定位被拒绝</span></CardHeader>
            <CardContent>
              <div className="list">
                {focusRejected.map((reason) => (
                  <div key={reason} className="list-item"><span className="text-warning">{reason}</span></div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {rejected.length > 0 && (
          <Card>
            <CardHeader><span>区间地址被拒绝</span></CardHeader>
            <CardContent>
              <div className="list">
                {rejected.map((reason) => (
                  <div key={reason} className="list-item"><span className="text-warning">{reason}</span></div>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">
                被拒绝的地址不参与任何读取：这里不会把它拼成一个看起来像把手的东西，也不会退回清单第一条。
              </p>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <span>证据产物 · 取自快照投影的来源</span>
            <span className="text-[12px] text-muted">
              {shelf.kind === 'sources' ? `${shelf.items.length} 条 · 来自 workspace.sources` : '无投影'}
            </span>
          </CardHeader>
          <CardContent>
            {shelf.kind === 'no-snapshot' ? (
              <div className="empty py-8">
                <div className="icon" aria-hidden="true">◎</div>
                <p className="m-0 text-sm font-semibold text-ink">数据源未接入（保持 UNKNOWN，不预填来源清单）</p>
              </div>
            ) : shelf.kind === 'not-provided' ? (
              <div className="text-xs text-warning">
                来源缺口：v3 快照没有 workspace.sources 字段（生产者未加载仓库证据面），
                因此没有可寻址的把手（handle）。这与「加载了但一个来源都没有」是两件事。
              </div>
            ) : shelf.items.length === 0 ? (
              <div className="text-xs text-muted">已加载证据面，但没有登记任何来源（空列表是查询结果，不是缺源）</div>
            ) : (
              <div className="list">
                {shelf.items.map((item, index) => {
                  const handle = item.path
                  const rowAddress: EvidenceAddress | null = handle
                    ? { handle, offset: null, limit: null, expectedDigest: null }
                    : null
                  const href = evidenceHref(rowAddress, initialSearch)
                  const active = handle !== null && address?.handle === handle
                  return (
                    <div key={`${handle ?? 'row'}-${index}`} className="list-item">
                      <span className="min-w-0 break-words text-[12px] text-ink">
                        {handle
                          ? (
                            <a href={href} onClick={navigate(rowAddress)} className="font-mono" aria-current={active ? 'true' : undefined}>
                              {handle}
                            </a>
                          )
                          : <span className="text-warning">来源缺口：该条目没有 path 字段，无法寻址</span>}
                        {active ? <span className="ml-1.5 text-[12px] text-secondary-ink">已寻址</span> : null}
                      </span>
                      <span className="text-right text-[12px] text-muted">
                        {item.evidenceKind || 'UNKNOWN'} · {item.loadedAt || 'UNKNOWN'}
                        {item.generatedAt ? ` · 生成 ${item.generatedAt}` : ''}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
            <p className="mt-2 text-[12px] text-muted">
              取自快照投影的 path 是仓库相对路径，而区间读要求的是绝对路径的把手（handle），并只在声明的证据面上提供内容。
              点开一条不在证据面上的来源，会得到后端的类型化拒绝，而不是一块空白。
            </p>
            {(focus.taskId || focus.executionId) && (
              <p className="mt-2 text-[12px] text-warning" data-testid="evidence-record-binding">
                记录定位（{[focus.taskId && `taskId=${focus.taskId}`, focus.executionId && `executionId=${focus.executionId}`]
                  .filter(Boolean).join(' · ')}）不会自动变成产物清单：v3 快照没有 record↔artifact 外键，
                绑定它就是把别人的字节挂到这条任务上。证据仍按自己的地址寻址。
              </p>
            )}
          </CardContent>
        </Card>

        <EvidenceHandles snap={snap} search={initialSearch} />

        <Card>
          <CardHeader>
            <span>区间读 · 三列</span>
            <span className="text-[12px] text-muted" data-testid="evidence-endpoint">
              {endpoint
                ? `${endpoint.url} · ${endpoint.authoritative ? '权威注入端点' : '非权威 static-preview 端点'}`
                : '端点不可信（未派生自环回描述符），不发起读取'}
            </span>
          </CardHeader>
          <CardContent>
            <EvidenceColumns address={address} state={state} rejectedCount={rejected.length} result={result} />
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader><span>契约 · worklab/evidence-range-result/v1</span></CardHeader>
          <CardContent>
            <div className="list">
              <Dim label="判定住在 body" value={`status / reason_code；HTTP 200 不等于读取成功（当前 schema ${EVIDENCE_RANGE_SCHEMA_VERSION}）`} />
              <Dim label="拒绝时的内容" value="REFUSED / OUT_OF_RANGE 携带 content=null，本视图不渲染内容块，也不留空白" />
              <Dim label="地址" value="artifact / offset / limit / expectedDigest 全部走 ?view=evidence 同一条链接机制，没有手填入口" />
              <Dim label="未提供" value="结果里没有的字段显示 未提供，不补 0，也不补 false" />
              <Dim label="上限" value={`单次 ${EVIDENCE_MAX_LIMIT.toLocaleString('en-US')} 字节：超限由后端拒绝（LIMIT_TOO_LARGE），这一侧不做静默截断`} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><span>只读说明</span></CardHeader>
          <CardContent className="text-xs text-muted">
            本视图只发起 <span className="font-mono">GET</span>：没有批准 / 派发 / 重试 / 回滚 / apply 的任何入口，
            也没有写深链。读取失败、被拒绝与未送达是三件不同的事，分别如实呈现；
            项目内部不等于阅读许可 —— 不在声明证据面上的把手、凭证样名称都由后端拒绝，本视图把拒绝原样展示。
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function EvidenceColumns({
  address, state, rejectedCount, result,
}: {
  address: EvidenceAddress | null
  state: ReadState
  rejectedCount: number
  result: EvidenceSliceOutcome | null
}) {
  const nothingAddressed = address === null

  if (nothingAddressed) {
    return (
      <div className="three-col" data-testid="evidence-columns" data-state={rejectedCount > 0 ? 'rejected' : 'unaddressed'}>
        <Card data-column="identity">
          <CardHeader><span>身份 · Identity</span></CardHeader>
          <CardContent>
            <Field label="handle" value={null} missing={rejectedCount > 0 ? '地址被拒绝，没有可用把手' : '地址里没有 artifact 参数，未指定把手'} />
            <Field label="记录摘要" value={null} missing="未指定把手，谈不上摘要" />
            <Field label="大小" value={null} missing="未发起读取" />
          </CardContent>
        </Card>
        <Card data-column="slice">
          <CardHeader><span>切片 · Slice</span></CardHeader>
          <CardContent>
            <Field label="offset" value={null} missing="未发起读取" />
            <Field label="limit" value={null} missing="未发起读取" />
            <Field label="endOffset" value={null} missing="未发起读取" />
            <Field label="eofReached" value={null} missing="未发起读取" />
            <Field label="sliceDigest" value={null} missing="未发起读取" />
          </CardContent>
        </Card>
        <Card data-column="verdict">
          <CardHeader><span>判定 · Verdict</span></CardHeader>
          <CardContent>
            <div className="text-xs text-muted" role="status">
              {rejectedCount > 0
                ? '无判定：地址在校验处就被拒绝，读取未发起。被拒绝的值不会被拼成一个看起来像把手的东西，也不会退回清单第一条。'
                : '无判定：没有把手就没有对象。选择左侧清单里的一条来源，或直接使用带 artifact 参数的地址。'}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (state.kind === 'IDLE' || state.kind === 'READING') {
    return (
      <div className="three-col" data-testid="evidence-columns" data-state="reading" role="status">
        <Card data-column="identity">
          <CardHeader><span>身份 · Identity</span></CardHeader>
          <CardContent><Field label="handle" value={address?.handle ?? null} missing="地址被拒绝" /></CardContent>
        </Card>
        <Card data-column="slice">
          <CardHeader><span>切片 · Slice</span></CardHeader>
          <CardContent>
            <div className="text-xs text-muted">
              正在按精确区间读取（{state.kind === 'READING' ? '请求已发出，尚无判定' : '请求未发出：无可用端点'}）。
              在判定到达之前不显示任何计数，避免把「还没读」画成「读到 0」。
            </div>
          </CardContent>
        </Card>
        <Card data-column="verdict">
          <CardHeader><span>判定 · Verdict</span></CardHeader>
          <CardContent>
            <Badge variant="muted">{state.kind === 'READING' ? '读取中' : '无端点'}</Badge>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="three-col" data-testid="evidence-columns" data-state="no-endpoint">
        <Card data-column="identity">
          <CardHeader><span>身份 · Identity</span></CardHeader>
          <CardContent><Field label="handle" value={address?.handle ?? null} missing='地址里没有 artifact' /></CardContent>
        </Card>
        <Card data-column="slice">
          <CardHeader><span>切片 · Slice</span></CardHeader>
          <CardContent><Field label="offset" value={null} missing="读取未发起" /></CardContent>
        </Card>
        <Card data-column="verdict">
          <CardHeader><span>判定 · Verdict</span></CardHeader>
          <CardContent>
            <div className="text-xs text-warning">来源缺口：没有可信的环回端点，未发起读取（这不是拒绝，也不是空结果）</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (result.kind !== 'RESULT') {
    // A read that never arrived is not a refusal: no reason_code may be written for it.
    const detail = result.kind === 'UNREACHABLE' ? result.detail : result.why
    return (
      <div className="three-col" data-testid="evidence-columns" data-state="unreachable">
        <Card data-column="identity">
          <CardHeader><span>身份 · Identity</span></CardHeader>
          <CardContent>
            <Field label="handle" value={address?.handle ?? null} missing="地址未被解析" />
            <Field label="钉住摘要" value={address?.expectedDigest ?? null} missing="地址未提供 expectedDigest" />
            <Field label="大小" value={null} missing="未送达，没有实测大小" />
          </CardContent>
        </Card>
        <Card data-column="slice">
          <CardHeader><span>切片 · Slice</span></CardHeader>
          <CardContent>
            <Field label="offset" value={num(address?.offset ?? undefined)} missing="地址未提供 offset（后端使用其默认）" />
            <Field label="limit" value={num(address?.limit ?? undefined)} missing="地址未提供 limit（后端使用其默认）" />
            <Field label="endOffset" value={null} missing="没有返回字节" />
            <Field label="sliceDigest" value={null} missing="没有返回字节" />
          </CardContent>
        </Card>
        <Card data-column="verdict">
          <CardHeader><span>判定 · Verdict</span></CardHeader>
          <CardContent>
            <div className="list-item flex-col items-stretch gap-1">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">状态</div>
              <div className="text-[12px] text-warning">
                无判定（读取未送达） · {detail}
                {result.kind === 'UNREACHABLE' && result.httpStatus !== null ? ` · HTTP ${result.httpStatus}` : ''}
              </div>
            </div>
            <div className="text-[12px] text-muted">
              后端没有给出判定码，所以这里不写拒绝码、不写判定结果，也不写字节计数。
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const item = result.result
  const identity = item.identity
  const cost = item.cost
  const digest = digestVerdictOf(item)
  const sizeBytes = typeof identity?.sizeBytes === 'number' ? identity.sizeBytes : (typeof cost?.fileSize === 'number' ? cost.fileSize : null)
  const pinnedDigest = text(identity?.expectedDigest) ?? text(address?.expectedDigest)
  const measuredDigest = text(identity?.wholeDigest)
  const isOk = item.status === 'OK'

  return (
    <div className="three-col" data-testid="evidence-columns" data-state={item.status} data-reason={item.reason_code}>
      <Card data-column="identity">
        <CardHeader><span>身份 · Identity</span></CardHeader>
        <CardContent>
          <Field field="handle" label="handle" value={text(item.handle) ?? text(address?.handle)} missing="结果未回传把手" />
          <Field field="pinnedDigest" label="钉住摘要（调用方声明）" value={pinnedDigest} missing="地址未提供 expectedDigest，本次没有请求身份核验" />
          <Field field="measuredDigest" label="实测摘要（读取器计算）" value={measuredDigest} missing="读取器未实测整文件摘要，身份未核验" />
          <Field field="digestSource" label="摘要来源" value={text(identity?.digestSource)} missing="该判定未走到摘要核对" />
          <Field field="size" label="大小" value={sizeBytes !== null ? fmtBytes(sizeBytes) : null} missing="结果未携带文件大小" />
        </CardContent>
      </Card>

      <Card data-column="slice">
        <CardHeader><span>切片 · Slice</span></CardHeader>
        <CardContent>
          <Field field="offset" label="offset" value={num(item.offset)} missing={`${item.reason_code} 未走到区间定位`} />
          <Field field="limit" label="limit" value={num(item.limit) ?? num(address?.limit ?? undefined)} missing="地址与结果都没有 limit，后端使用其默认上限" />
          <Field field="bytesRequested" label="bytesRequested" value={num(item.bytesRequested)} missing={`${item.reason_code} 没有请求字节数`} />
          <Field field="endOffset" label="endOffset" value={num(item.endOffset)} missing={`${item.reason_code} 没有返回区间`} />
          <Field field="eofReached" label="eofReached" value={bool(item.eofReached, '是（已到文件尾）', '否（仍有后续字节）')} missing={`${item.reason_code} 没有返回区间`} />
          <Field field="sliceDigest" label="sliceDigest" value={text(item.sliceDigest)} missing="没有返回字节，因此没有切片摘要" />
          <Field field="bytesRead" label="本次读取" value={isOk && typeof cost?.bytesRead === 'number' ? `${fmtBytes(cost.bytesRead)} / ${fmtBytes(sizeBytes)}` : null} missing={`${item.status} 不是读取成功：拒绝信封里的 bytesRead 是占位值，不是一次读取的成本`} />
          <Field field="wholeRead" label="是否整读" value={isOk && typeof cost?.wholeFileWasRead === 'boolean' ? (cost.wholeFileWasRead ? '是（整份文件被读完）' : '否（只读了这一段）') : null} missing={`${item.status} 没有走到读取，因此没有整读与否的实测`} />
        </CardContent>
      </Card>

      <Card data-column="verdict">
        <CardHeader><span>判定 · Verdict</span></CardHeader>
        <CardContent>
          <div className="list-item flex-col items-stretch gap-1">
            <div className="text-[12px] uppercase tracking-[0.12em] text-muted">状态 / 判定码</div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={statusTone(item.status)}>{`${item.status} · ${item.reason_code}`}</Badge>
              {!isRegisteredReasonCode(item.reason_code) && (
                <span className="text-[12px] text-warning">未登记的判定码（后端新增，UI 未镜像）</span>
              )}
            </div>
            <div className="break-words text-[12px] text-ink">{item.reason || '后端未给出原因文本'}</div>
            <div className="text-[12px] text-muted">
              传输层 HTTP {result.httpStatus} —— 判定取自响应体，不取自状态码
            </div>
          </div>

          <div className="list-item flex-col items-stretch gap-1" data-testid="evidence-digest-verdict">
            <div className="text-[12px] uppercase tracking-[0.12em] text-muted">摘要一致性</div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={DIGEST_TONE[digest.kind]}>{`${DIGEST_LABEL[digest.kind]} · ${digest.kind}`}</Badge>
            </div>
            <div className="break-words text-[12px] text-ink">{digest.detail}</div>
          </div>

          {isOk && typeof item.content === 'string' ? (
            <div className="list-item flex-col items-stretch gap-1" data-testid="evidence-content">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">
                返回字节预览 · [{num(item.offset)}, {num(item.endOffset)})
              </div>
              <pre className="m-0 max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] text-ink">
                {item.content.length > PREVIEW_LIMIT ? `${item.content.slice(0, PREVIEW_LIMIT)}…（预览截断，完整区间由 sliceDigest 署名）` : item.content}
              </pre>
            </div>
          ) : (
            <div className="list-item flex-col items-stretch gap-1" data-testid="evidence-no-content">
              <div className="text-[12px] uppercase tracking-[0.12em] text-muted">内容</div>
              <div className="text-[12px] text-warning">
                没有返回字节（{item.status === 'REFUSED' ? '后端拒绝携带内容' : '空区间'}），因此这里没有内容块可看。
                拒绝是判定，不是空面板。
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
