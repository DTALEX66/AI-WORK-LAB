// Control Surface thin shell. Everything on screen comes from the service answer for this request,
// never from a client-side guess: a submit shows RUNNING, and only an ACCEPTED result with a receipt and
// a readback is worded as done. A NOT_IMPLEMENTED operation is listed with its reason and cannot be sent,
// because the backend already refuses it — and the refusal reason is the useful part.
// Two write paths live here: a direct Work Unit, and materializing an authorized PlanningCandidate. The
// second one carries no authority: whatever the pasted JSON or this page claims, the service re-checks the
// candidate against its own local authorization record and answers with the verdict it actually reached.
"use strict"

const state = { descriptor: null, idempotencyKey: "", materializeKey: "" }

const el = (id) => document.getElementById(id)

// The operation identity travels in the URL and nowhere else: this page stores nothing, so a reload that
// keeps `?operation=` can ask the service what that identity already did instead of minting a fresh key
// and writing a second time.
function operationFromUrl() {
  return (new URLSearchParams(location.search).get("operation") || "").trim()
}

function carryOperationInUrl(taskId) {
  const params = new URLSearchParams(location.search)
  params.set("operation", taskId)
  history.replaceState(null, "", `?${params.toString()}`)
}

function clearOperationInUrl() {
  const params = new URLSearchParams(location.search)
  if (!params.has("operation")) return
  params.delete("operation")
  const query = params.toString()
  history.replaceState(null, "", query ? `?${query}` : location.pathname)
}

function newIdempotencyKey(taskId) {
  const random = (() => {
    const buffer = new Uint8Array(8)
    if (globalThis.crypto && crypto.getRandomValues) {
      crypto.getRandomValues(buffer)
    } else {
      for (let index = 0; index < buffer.length; index += 1) buffer[index] = Math.floor(Math.random() * 256)
    }
    return Array.from(buffer, (byte) => byte.toString(16).padStart(2, "0")).join("")
  })()
  return `ctl-${(taskId || "unit").replace(/[^A-Za-z0-9._-]/g, "-").slice(0, 40)}-${random}`
}

function supportOf(operation) {
  const entry = ((state.descriptor && state.descriptor.operations) || [])
    .find((item) => item.operation === operation)
  if (!entry) return { support: "UNKNOWN", reason: "descriptor 未到达，支持度未知" }
  return entry
}

function applySupport(operation, buttonId, hintId) {
  const { support, reason } = supportOf(operation)
  const button = el(buttonId)
  const hint = el(hintId)
  if (support === "IMPLEMENTED") {
    button.disabled = false
    hint.textContent = "后端支持度：IMPLEMENTED（仍由服务端复核授权与范围）"
    hint.className = "hint ok"
    return
  }
  button.disabled = support !== "UNKNOWN"
  hint.textContent = support === "UNKNOWN"
    ? "后端支持度 UNKNOWN（还没读到 descriptor，不推断能不能写）"
    : `后端支持度 ${support}：${reason || "未给出原因"}`
  hint.className = "hint warn"
}

function renderTransport() {
  const line = el("transport")
  if (!state.descriptor) {
    line.textContent = "状态 UNKNOWN（尚未读到 descriptor）"
    line.className = "tag warn"
    return
  }
  const ceiling = state.descriptor.evidence_ceiling || "UNKNOWN"
  line.textContent = `已连接 · loopback-only · 证据上限 ${ceiling}（本地写不会自称 REAL）`
  line.className = "tag ok"
}

// The authorization record is what makes a candidate verifiable. Its content stays on the server; the
// shell only shows whether it could be read and how many grants resolved, so "nothing was signed" is
// visible before a submit rather than only inside a refusal.
function renderGrantRecord() {
  const line = el("grant-record")
  const record = state.descriptor && state.descriptor.authorization_record
  if (!record) {
    line.textContent = "本地授权记录 UNKNOWN（descriptor 未到达或未声明该字段）——候选核验不会因此被放行。"
    line.className = "hint warn"
    return
  }
  line.textContent = record.readable
    ? `本地授权记录：已读取 ${record.path}，有效 grant ${record.grants} 条（过期 ${record.expired} / 形状不合 ${record.malformed}）。内容不外投影。`
    : `本地授权记录：未读通（${record.note || "原因未给出"}）。没有可读的 grant，任何候选都会被拒。`
  line.className = record.readable ? "hint ok" : "hint warn"
}

function renderOperations() {
  const list = el("operations")
  list.textContent = ""
  const operations = (state.descriptor && state.descriptor.operations) || []
  if (!operations.length) {
    const empty = document.createElement("li")
    empty.textContent = "操作清单 UNKNOWN（descriptor 未到达）"
    list.appendChild(empty)
    return
  }
  for (const operation of operations) {
    const item = document.createElement("li")
    item.className = operation.support === "IMPLEMENTED" ? "op supported" : "op unsupported"

    const name = document.createElement("span")
    name.className = "mono"
    name.textContent = operation.operation
    item.appendChild(name)

    const badge = document.createElement("span")
    badge.className = operation.support === "IMPLEMENTED" ? "tag ok" : "tag muted"
    badge.textContent = operation.support === "IMPLEMENTED" ? "可提交" : "不可用（后端未实现）"
    item.appendChild(badge)

    const reason = document.createElement("p")
    reason.textContent = `${operation.reason_code} · ${operation.reason}`
    item.appendChild(reason)

    if (operation.next_action) {
      const next = document.createElement("p")
      next.className = "next"
      next.textContent = `下一步：${operation.next_action}`
      item.appendChild(next)
    }
    list.appendChild(item)
  }
}

async function loadDescriptor() {
  try {
    const response = await fetch("/api/control/descriptor", { headers: { Accept: "application/json" } })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    state.descriptor = await response.json()
  } catch (error) {
    state.descriptor = null
    el("transport").textContent = `后端不可达：${error.message}（保持 UNKNOWN，不假装可写）`
    el("transport").className = "tag error"
  }
  renderTransport()
  renderGrantRecord()
  renderOperations()
  applySupport("work-unit.create", "submit", "create-support")
  applySupport("work-unit.materialize", "materialize", "materialize-support")
}

// A transport-level refusal (403 NOT_LOOPBACK, 413 BODY_TOO_LARGE, 400 UNPARSEABLE_REQUEST) answers with
// the error shape, which carries a reason_code but no status. Showing "undefined" there would hide the
// only useful fact on screen, so it is normalised into a REFUSED line instead of a blank.
function normalizeAnswer(answer) {
  if (answer && answer.status) return answer
  return {
    ...answer,
    status: "REFUSED",
    reason_code: (answer && answer.reason_code) || "ANSWER_WITHOUT_STATUS",
    reason: (answer && answer.reason) || "后端给了一个没有状态的答案，按未执行处理。",
    evidence_level: (answer && answer.evidence_level) || "NO_EVIDENCE",
  }
}

function statusLine(result) {
  const receipt = result.receipt
    ? `回执 ${result.receipt.receipt_id} · ${result.receipt.kind} · digest ${String(result.receipt.digest).slice(0, 12)}`
    : "无回执（计划或未执行）"
  const verdict = {
    ACCEPTED: "已写入并读回",
    PLANNED: "只是计划，未写入",
    REFUSED: "被拒绝",
    NEEDS_HUMAN: "等待人工门",
    NOT_IMPLEMENTED: "后端未实现",
    READBACK_MISMATCH: "写入未能读回",
    FAILED: "失败",
  }[result.status] || result.status
  return [
    `状态 ${result.status} · ${verdict}`,
    `原因 ${result.reason_code} · ${result.reason}`,
    `证据等级 ${result.evidence_level}`,
    receipt,
    result.next_action ? `下一步 ${result.next_action}` : "下一步 UNKNOWN",
  ].join("\n")
}

// Readback is shown, never hidden. A refusal or an unimplemented answer carries readback=null by contract,
// and the shell then says the readback is UNKNOWN with the reason beside it, instead of going blank.
function renderReadback(result, targetId) {
  const line = el(targetId)
  if (!result || !result.readback) {
    line.textContent = `读回 UNKNOWN：${result ? result.status : "没有答案"} · `
      + `${result && result.reason ? result.reason : "后端未给出原因"}（合同规定这类答案不携带读回）`
    line.className = "readback warn"
    return
  }
  const record = result.readback
  const where = `?view=work&taskId=${encodeURIComponent(record.taskId || "")}`
  const lines = []
  lines.push(record.replayed
    ? `重放到已存在的记录 ${record.taskId}（状态 ${record.status}）。`
    : `读回记录 ${record.taskId}：项目 ${record.projectId} · 状态 ${record.status} · `
      + `checkpoint ${record.checkpointPresent ? `键 ${(record.checkpointKeys || []).join("/")}` : "无"}`
      + ` · 摘要 ${String(record.checkpointDigest || "UNKNOWN").slice(0, 12)}`)
  if (record.source === "planning-candidate") {
    lines.push(`候选身份 ${record.candidateId} · 修订 ${record.taskRevision} · 内容摘要 `
      + `${String(record.candidateDigest || "UNKNOWN").slice(0, 12)} · 变更 ${record.changesCount} 项 / `
      + `验收 ${record.verificationCount} 项`)
    lines.push(`授权来源 ${record.authorizationSource} · grant scope ${record.grantScope || "UNKNOWN"} · `
      + `能力核验 ${record.capabilityCheck}（声明 ${record.capabilityDeclared || "无"}）`)
    lines.push(record.planExecuted
      ? "计划已被执行（这一条不该出现在本轮，出现即为谎报）"
      : `计划本身未执行：${record.executorDispatch}`)
    lines.push((record.ignoredSelfClaims && record.ignoredSelfClaims.length)
      ? `已忽略的自我授权声明：${record.ignoredSelfClaims.join("/")}`
      : "请求里没有自我授权声明")
  }
  if (record.plan_only) {
    lines.push(record.written ? "计划已落盘" : "这是一份计划，written=false，没有写任何东西")
  }
  lines.push(`在 Observer 的 Work 泳道用 ${where} 读回（只读投影：键名与摘要，无正文）。`)
  line.textContent = lines.join("\n")
  line.className = "readback"
}

function scopeFromForm() {
  return {
    boundaries: [el("boundary").value.trim()].filter(Boolean),
    granted_by: el("granted-by").value.trim(),
  }
}

// Three separated outcomes, read from the service, never inferred from one another: a write that landed
// says nothing about a native client loading it, and neither says anything about the target behaving.
function identityLines(answer) {
  const lines = []
  if (!answer.found) {
    lines.push(`身份 ${answer.task_id}：${answer.reason_code} · ${answer.reason}`)
  } else {
    lines.push(`身份 ${answer.task_id}：账本状态 ${answer.status} · 项目 ${answer.project_id} · `
      + `回执 ${(answer.receipts || []).length} 条 · 投影摘要 ${String(answer.record_digest).slice(0, 12)}`)
    lines.push(answer.idempotency_key_present
      ? `沿用账本里的幂等键 ${answer.idempotency_key}（重发同键只会重放，不会再写一条）`
      : "读回：账本行存在但没有幂等键记录，本页不会自造一个")
  }
  for (const outcome of answer.outcomes || []) {
    lines.push(`· ${outcome.label}：${outcome.state}（判据 ${outcome.basis}）${outcome.detail ? ` — ${outcome.detail}` : ""}`)
  }
  return lines
}

async function restoreOperation(taskId, view) {
  const line = el(view.result)
  line.textContent = `按身份读回中 · ${taskId}（只查询，不重发写）`
  try {
    const response = await fetch(`/api/control/operations/${encodeURIComponent(taskId)}`,
                                 { headers: { Accept: "application/json" } })
    const answer = await response.json().catch(() => null)
    if (!answer || answer.schema_version !== "worklab/control-operation-identity/v1") {
      line.textContent = `状态 UNKNOWN · 身份读回返回的不是身份合同（HTTP ${response.status}），`
        + "不据此推断这条操作写过或没写过"
      return
    }
    line.textContent = identityLines(answer).join("\n")
    if (answer.found && answer.idempotency_key) {
      state.idempotencyKey = answer.idempotency_key
      el(view.idem).textContent = `idempotency ${state.idempotencyKey}（来自账本读回）`
      el("task-id").value = answer.task_id
    }
  } catch (error) {
    line.textContent = `状态 FAILED · 身份读回传输失败：${error.message}\n证据等级 NO_EVIDENCE\n`
      + "下一步 确认控制服务仍在运行；本页不会因为没有读到就自造一个新键重写"
  }
}

function buildRequest() {
  const taskId = el("task-id").value.trim()
  return {
    schema_version: "worklab/control-operation/v1",
    operation: "work-unit.create",
    project_id: el("project-id").value.trim(),
    task_id: taskId,
    revision: null,
    attempt: null,
    scope: scopeFromForm(),
    expected_version: null,
    idempotency_key: state.idempotencyKey || newIdempotencyKey(taskId),
    actor: "control-shell",
    // The contract demands an RFC3339 instant; a clock that is unavailable is not a licence to send "".
    requested_at: new Date().toISOString(),
    payload: { goal: el("goal").value.trim() },
  }
}

// The candidate is sent as content, nothing more. task_id is taken from the candidate's own workUnitId so
// the page cannot point an authorized plan at a different unit of work; revision and the reasoned-against
// baseline come from the candidate too. Any `authorized` / `scope` text inside it is left exactly where it
// is: the service re-checks and names it as ignored if it was there.
function buildMaterializeRequest(candidate) {
  const workUnitId = String(candidate.workUnitId || "")
  const baseline = candidate.baseline || {}
  return {
    schema_version: "worklab/control-operation/v1",
    operation: "work-unit.materialize",
    project_id: el("project-id").value.trim(),
    task_id: workUnitId,
    revision: Number.isInteger(candidate.taskRevision) ? candidate.taskRevision : null,
    attempt: null,
    scope: scopeFromForm(),
    expected_version: baseline.commit || baseline.digest || null,
    idempotency_key: state.materializeKey || newIdempotencyKey(workUnitId),
    actor: "control-shell",
    requested_at: new Date().toISOString(),
    payload: { candidate },
  }
}

async function submit(request, view) {
  el(view.pending).hidden = false
  el(view.button).disabled = true
  el(view.result).textContent = "提交中 · RUNNING（完成与否由后端回执与读回决定）"
  try {
    const response = await fetch("/api/control/operations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    })
    const answer = await response.json().catch(() => ({ status: "FAILED", reason_code: "UNPARSEABLE_ANSWER",
      reason: `HTTP ${response.status} 的响应不是 JSON`, evidence_level: "NO_EVIDENCE" }))
    const result = normalizeAnswer(answer)
    el(view.result).textContent = statusLine(result)
    renderReadback(result, view.readback)
    // Whatever the service named as the operation's task_id becomes the page's address for that
    // operation, so the next reload reads THIS one back instead of starting a fresh identity.
    if (result.task_id) carryOperationInUrl(result.task_id)
    if (result.status === "ACCEPTED" && result.readback && !result.readback.replayed) {
      // one record keeps one identity: after a verified create, the same click must not silently replay
      const key = newIdempotencyKey(request.task_id)
      if (view.operation === "work-unit.materialize") state.materializeKey = key
      else state.idempotencyKey = key
      el(view.idem).textContent = `idempotency ${key}`
    }
  } catch (error) {
    el(view.result).textContent = `状态 FAILED · 传输失败\n原因 ${error.message}\n证据等级 NO_EVIDENCE\n下一步 确认控制服务仍在运行（本页由它提供服务）`
    renderReadback(null, view.readback)
  } finally {
    el(view.pending).hidden = true
    applySupport(view.operation, view.button, view.support)
  }
}

function readCandidate() {
  const raw = el("candidate-json").value
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { error: "候选必须是一个 JSON 对象" }
    }
    return { candidate: parsed }
  } catch (error) {
    return { error: `本地 JSON 解析失败：${error.message}（不发送一个自己都读不懂的候选）` }
  }
}

function main() {
  const createView = { operation: "work-unit.create", button: "submit", pending: "pending",
    result: "result", readback: "readback", idem: "idem", support: "create-support" }
  const materializeView = { operation: "work-unit.materialize", button: "materialize",
    pending: "materialize-pending", result: "materialize-result", readback: "materialize-readback",
    idem: "materialize-idem", support: "materialize-support" }
  const restored = operationFromUrl()
  if (restored) {
    // A page that arrives with an identity does not mint one: minting here is the shape of the mistake
    // this path exists to prevent, because a new key on an existing task_id is a refused write, not a
    // second look at the first one.
    el("task-id").value = restored
    state.idempotencyKey = ""
    el("idem").textContent = `idempotency 待读回（URL 给了身份 ${restored}，先问账本）`
  } else {
    state.idempotencyKey = newIdempotencyKey(el("task-id").value.trim())
    el("idem").textContent = `idempotency ${state.idempotencyKey}`
  }
  state.materializeKey = newIdempotencyKey("")
  el("materialize-idem").textContent = `idempotency ${state.materializeKey}`
  el("regen").addEventListener("click", () => {
    state.idempotencyKey = newIdempotencyKey(el("task-id").value.trim())
    el("idem").textContent = `idempotency ${state.idempotencyKey}`
    clearOperationInUrl()
  })
  el("task-id").addEventListener("input", () => {
    state.idempotencyKey = newIdempotencyKey(el("task-id").value.trim())
    el("idem").textContent = `idempotency ${state.idempotencyKey}`
    clearOperationInUrl()
  })
  el("create-form").addEventListener("submit", (event) => {
    event.preventDefault()
    void submit(buildRequest(), createView)
  })
  el("regen-materialize").addEventListener("click", () => {
    state.materializeKey = newIdempotencyKey("")
    el("materialize-idem").textContent = `idempotency ${state.materializeKey}`
  })
  el("materialize-form").addEventListener("submit", (event) => {
    event.preventDefault()
    const { candidate, error } = readCandidate()
    if (error) {
      el("materialize-result").textContent = `状态 REFUSED · 本页未发送\n原因 CANDIDATE_UNPARSEABLE · ${error}\n证据等级 NO_EVIDENCE\n无回执（没有请求，就没有写）`
      renderReadback(null, "materialize-readback")
      return
    }
    void submit(buildMaterializeRequest(candidate), materializeView)
  })
  void loadDescriptor()
  if (restored) void restoreOperation(restored, createView)
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", main)
} else {
  main()
}
