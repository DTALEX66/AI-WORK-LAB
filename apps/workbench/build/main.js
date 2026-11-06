let chosenDirection = null;
let designRequest = 0;
let boundSystems = [];
let submittedBrief = null;
let submittedDirection = null;
let briefBusy = false;
let directionBusy = false;
let bindBusy = false;
let revisionBriefTarget = null;
let revisionDirectionTarget = null;
let revisionBriefCarried = [];
let highlightBrief = null;
let highlightDirection = null;
let briefRevisionBusy = false;
let directionRevisionBusy = false;
let briefLineageRequest = 0;
let directionLineageRequest = 0;
const REVISION_BRIEF_IDLE = "在某一简报行点击「新版本」以载入该版本内容；保存会新增一个版本，不会改写旧版本。";
const REVISION_DIRECTION_IDLE = "在某一方向行点击「新版本」以载入该版本内容；保存会新增一个版本，不会改写旧版本。";
const uuid = () => crypto.randomUUID();
async function loadDesignSystems() {
  const current = epoch;
  const data = await api("/design-systems");
  if (current !== epoch) return;
  boundSystems = data.design_systems;
  const select = byId("design-system");
  select.replaceChildren(new Option("选择设计系统", ""));
  for (const system of boundSystems) select.append(new Option(`${system.title} · ${system.version} (${system.evidence_level})`, system.name));
  byId("design-systems").replaceChildren(
    ...boundSystems.map((system) => {
      const li = document.createElement("li");
      li.textContent = `${system.name} · ${system.title} · v${system.version} · ${system.evidence_level}`;
      return li;
    })
  );
}
const shortId = (id) => id.slice(-8);
function versionOf(id, versions) {
  const known = versions.get(id);
  return known === void 0 ? `未知版本（${shortId(id)}）` : `版本 ${known}（${shortId(id)}）`;
}
function versionState(supersededBy, versions) {
  return supersededBy === null ? "当前" : `已取代 → ${versionOf(supersededBy, versions)}`;
}
function rowButton(label, action) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.onclick = () => Promise.resolve(action()).catch((error) => setStatus(errMsg(error), true));
  return element;
}
function renderDesignLayer(data) {
  const layer = data.design_layer;
  const briefVersions = /* @__PURE__ */ new Map();
  for (const row of layer.briefs) briefVersions.set(row.brief_id, row.version);
  const directionVersions = /* @__PURE__ */ new Map();
  const directionsById = /* @__PURE__ */ new Map();
  for (const row of layer.directions) {
    directionVersions.set(row.direction_id, row.version);
    directionsById.set(row.direction_id, row);
  }
  const activeBindingId = layer.active_binding ? layer.active_binding.binding_id : null;
  const focusRows = [];
  byId("design-briefs").replaceChildren(
    ...layer.briefs.map((brief) => {
      const li = document.createElement("li");
      li.tabIndex = -1;
      const refs = brief.reference_asset_ids.length;
      li.textContent = `BRIEF · ${brief.title} · ${brief.goals.join(" / ")}${brief.constraints ? ` · ${brief.constraints}` : ""} · 参考 ${refs} · v${brief.version} · ${versionState(brief.superseded_by, briefVersions)} · ${brief.spec_sha256}`;
      li.append(
        rowButton("新版本", () => loadBriefRevision(brief)),
        rowButton("版本链", () => loadBriefLineage(brief.brief_id))
      );
      if (brief.brief_id === highlightBrief) {
        li.classList.add("highlight");
        focusRows.push(li);
      }
      return li;
    })
  );
  byId("design-directions").replaceChildren(
    ...layer.directions.map((direction) => {
      const li = document.createElement("li");
      li.tabIndex = -1;
      const live = direction.superseded_by === null;
      li.textContent = `DIRECTION · ${direction.title} · ${direction.chosen ? `CHOSEN by ${direction.actor}` : "open"} · v${direction.version} · ${versionState(direction.superseded_by, directionVersions)} · 简报 ${shortId(direction.brief_id)} · ${direction.spec_sha256}`;
      if (direction.chosen && live) chosenDirection = direction;
      if (live) {
        const choose = document.createElement("button");
        choose.type = "button";
        choose.textContent = `选为方向 · ${shortId(direction.direction_id)}`;
        choose.onclick = () => chooseDirection(direction).catch((error) => setStatus(errMsg(error), true));
        li.append(choose);
      }
      li.append(
        rowButton("新版本", () => loadDirectionRevision(direction)),
        rowButton("版本链", () => loadDirectionLineage(direction.direction_id))
      );
      if (direction.direction_id === highlightDirection) {
        li.classList.add("highlight");
        focusRows.push(li);
      }
      return li;
    })
  );
  byId("design-bindings").replaceChildren(
    ...layer.bindings.length ? layer.bindings.map((binding) => {
      const li = document.createElement("li");
      const owner = directionsById.get(binding.direction_id);
      const state = binding.binding_id === activeBindingId ? "生效中" : owner && owner.superseded_by !== null ? "未生效 · 绑定留在已被取代的方向版本上，需重新建立" : "未生效 · 当前选定方向不是它";
      li.textContent = `BINDING · ${binding.design_system_name} · 绑定记录 v${binding.version} · 方向 ${shortId(binding.direction_id)} · ${state} · ${binding.spec_sha256}`;
      return li;
    }) : [info("design-bindings-empty")]
  );
  const notice = byId("design-binding-active");
  const active = layer.active_binding;
  const chosen = chosenDirection;
  if (active) {
    notice.classList.remove("warn");
    notice.textContent = `当前方向已绑定设计系统：${active.design_system_name}（设计契约已固定）。`;
  } else if (chosen && layer.bindings.length) {
    notice.classList.add("warn");
    notice.textContent = `当前选定方向「${chosen.title} · 版本 ${chosen.version}」没有生效的设计契约：已有的绑定记录仍留在旧的方向版本上，不会随新版本自动跟随——绑定需重新建立（选定设计系统后点「绑定设计系统」）。`;
  } else {
    notice.classList.remove("warn");
    notice.textContent = "选择方向并绑定设计系统后，后续 Build/Review 才有固定设计契约。";
  }
  if (focusRows.length) focusRows[0].focus();
}
function info(id) {
  const li = document.createElement("li");
  li.id = id;
  li.className = "empty";
  li.textContent = "尚未绑定设计系统。";
  return li;
}
async function refreshDesign() {
  if (!project) return;
  const current = epoch;
  const request = ++designRequest;
  setStatus("正在读取设计层：Brief / Direction / DesignSystem…");
  const data = await api(`/projects/${project}/design-layer`).catch((error) => {
    if (current !== epoch || request !== designRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== designRequest) return;
  chosenDirection = null;
  const briefSelect = byId("direction-brief");
  briefSelect.replaceChildren(new Option("选择简报", ""));
  for (const brief of data.design_layer.briefs)
    briefSelect.append(new Option(`${brief.title} · ${brief.brief_id.slice(-8)}`, brief.brief_id));
  renderDesignLayer(data);
  setStatus("设计层已读取。方向选择与绑定不代表制作完成或质量验收。");
}
async function createBrief(draft) {
  if (!draft.owner) throw new Error("未选择项目。");
  const title = draft.title.trim();
  const goals = draft.goals.map((goal) => goal.trim()).filter(Boolean);
  if (!title || !goals.length) throw new Error("请填写简报标题与至少一条目标。");
  const constraints = draft.constraints && draft.constraints.trim() ? draft.constraints.trim() : null;
  const references = draft.references;
  const body = {
    title,
    goals,
    constraints,
    reference_asset_ids: references,
    idempotency_key: ""
  };
  const identity = JSON.stringify({ owner: draft.owner, title, goals, constraints, references });
  if (!submittedBrief || submittedBrief.owner !== draft.owner || submittedBrief.identity !== identity)
    submittedBrief = { owner: draft.owner, identity, key: uuid() };
  body.idempotency_key = submittedBrief.key;
  await api(`/projects/${draft.owner}/briefs`, body);
}
async function submitBrief() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const title = byId("brief-title").value;
  if (briefBusy) return;
  const goalsRaw = byId("brief-goals").value.trim();
  const goals = goalsRaw ? goalsRaw.split(",").map((s) => s.trim()).filter(Boolean) : [];
  const constraints = byId("brief-constraints").value.trim() || null;
  if (!title || !goals.length) {
    setStatus("请填写简报标题与至少一条目标。", true);
    return;
  }
  const references = selectedReferences();
  briefBusy = true;
  byId("brief-submit").disabled = true;
  try {
    await createBrief({ owner, title, goals, constraints, references });
    if (current !== epoch) return;
    byId("brief-title").value = "";
    byId("brief-goals").value = "";
    byId("brief-constraints").value = "";
    for (const box of Array.from(document.querySelectorAll('input[name="reference-asset"]')))
      box.checked = false;
    await refreshDesign();
    setStatus(`简报已持久化（引用 ${references.length} 个参考素材）；下一步在简报下立方向。`);
  } catch (error) {
    if (current === epoch) setStatus(`简报未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    briefBusy = false;
    byId("brief-submit").disabled = false;
  }
}
async function submitDirection() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  if (directionBusy) return;
  const brief = byId("direction-brief").value;
  const title = byId("direction-title").value.trim();
  const colorMood = byId("direction-color").value.trim() || null;
  const typeMood = byId("direction-type").value.trim() || null;
  if (!brief || !title) {
    setStatus("请选择简报并填写方向标题。", true);
    return;
  }
  const body = { brief_id: brief, title, style_notes: null, color_mood: colorMood, typography_mood: typeMood, idempotency_key: "" };
  const identity = JSON.stringify({ owner, brief, title, colorMood, typeMood });
  if (!submittedDirection || submittedDirection.owner !== owner || submittedDirection.identity !== identity)
    submittedDirection = { owner, identity, key: uuid() };
  body.idempotency_key = submittedDirection.key;
  directionBusy = true;
  byId("direction-submit").disabled = true;
  try {
    const data = await api(`/projects/${owner}/directions`, body);
    if (current !== epoch) return;
    byId("direction-title").value = "";
    await refreshDesign();
    setStatus(`方向已排队：${data.direction.direction_id.slice(-8)}。请选择该方向并绑定设计系统。`);
  } catch (error) {
    if (current === epoch) setStatus(`方向未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    directionBusy = false;
    byId("direction-submit").disabled = false;
  }
}
async function chooseDirection(direction) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const actor = "workbench-user";
  const actorKind = "human";
  const body = { actor, actor_kind: actorKind, idempotency_key: uuid() };
  try {
    const data = await api(`/projects/${owner}/directions/${direction.direction_id}/choose`, body);
    if (current !== epoch) return;
    await refreshDesign();
    setStatus(`方向已选定：${data.direction.direction_id.slice(-8)}（${data.direction.actor}）。下一步绑定设计系统。`);
  } catch (error) {
    if (current === epoch) setStatus(`方向选择未确认：${errMsg(error)}`, true);
  }
}
async function bindDesignSystem() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  if (bindBusy) return;
  const name = byId("design-system").value;
  const direction = chosenDirection;
  if (!name || !direction) {
    setStatus("请先选定方向，再选择要绑定的设计系统。", true);
    return;
  }
  const body = { design_system_name: name, idempotency_key: uuid() };
  bindBusy = true;
  byId("design-system-bind").disabled = true;
  try {
    const data = await api(`/projects/${owner}/directions/${direction.direction_id}/bind`, body);
    if (current !== epoch) return;
    await refreshDesign();
    setStatus(`设计系统已绑定：${data.binding.design_system_name}。设计契约已固定；制作与质量验收仍未执行。`);
  } catch (error) {
    if (current === epoch) setStatus(`设计系统绑定未确认：${errMsg(error)}`, true);
  } finally {
    bindBusy = false;
    byId("design-system-bind").disabled = false;
  }
}
function revisionHint(error) {
  const code = errMsg(error);
  if (code === "STALE_REVISION") return "该版本已被取代，服务端拒绝了这次修订（STALE_REVISION）。请从版本链里的最新版本继续。";
  if (code === "BRIEF_NOT_FOUND" || code === "DIRECTION_NOT_FOUND") return `该版本已不在当前项目中（${code}）；请刷新后重试。`;
  if (code === "UNAUTHORIZED") return "访问令牌无效或已过期（UNAUTHORIZED）；请断开后重新连接本机服务。";
  return `${code}；本次修订未被接受，服务端未写入任何内容。`;
}
function splitList(raw, maxLen, label) {
  const items = raw ? raw.split(",").map((value) => value.trim()).filter(Boolean) : [];
  if (items.some((item) => item.length > maxLen)) throw new Error(`${label}每项不能超过 ${maxLen} 个字符`);
  return items;
}
function loadBriefRevision(brief, focusForm = true) {
  revisionBriefTarget = brief;
  const boxes = Array.from(document.querySelectorAll('input[name="reference-asset"]'));
  const known = new Set(boxes.map((box) => box.value));
  for (const box of boxes) box.checked = brief.reference_asset_ids.includes(box.value);
  revisionBriefCarried = brief.reference_asset_ids.filter((id) => !known.has(id));
  byId("revision-brief-title").value = brief.title;
  byId("revision-brief-goals").value = brief.goals.join(", ");
  byId("revision-brief-constraints").value = brief.constraints ?? "";
  byId("revision-brief-target").textContent = `正在修订简报「${brief.title}」版本 ${brief.version}（${shortId(brief.brief_id)}）：内容已按该版本预填，勾选区对应它的参考素材。保存会新增一个版本，旧版本只保留为历史。` + (revisionBriefCarried.length ? `另有 ${revisionBriefCarried.length} 个参考素材不在当前勾选列表里，会原样保留。` : "") + (brief.superseded_by === null ? "" : " 注意：该版本已被取代，服务端会拒绝这次修订（STALE_REVISION），请改从版本链中的最新版本继续。");
  if (focusForm) byId("revision-brief-title").focus();
}
async function submitBriefRevision() {
  const current = epoch;
  const owner = project;
  const source = revisionBriefTarget;
  if (!owner || briefRevisionBusy) return;
  if (!source) {
    setStatus("请先在某一简报行点击「新版本」以载入要修订的内容。", true);
    return;
  }
  briefRevisionBusy = true;
  byId("brief-revision-submit").disabled = true;
  try {
    const title = byId("revision-brief-title").value.trim();
    const goals = splitList(byId("revision-brief-goals").value, 300, "目标");
    const constraints = byId("revision-brief-constraints").value.trim() || null;
    if (!title || !goals.length) throw new Error("修订需要标题与至少一条目标");
    const references = Array.from(/* @__PURE__ */ new Set([...selectedReferences(), ...revisionBriefCarried]));
    const data = await api(
      `/projects/${owner}/briefs/${source.brief_id}/revisions`,
      { title, goals, constraints, reference_asset_ids: references, idempotency_key: uuid() }
    );
    if (current !== epoch) return;
    highlightBrief = data.brief.brief_id;
    await refreshDesign();
    if (current !== epoch) return;
    await loadBriefLineage(data.brief.brief_id);
    if (current !== epoch) return;
    loadBriefRevision(data.brief, false);
    setStatus(`简报已保存为版本 ${data.brief.version}（${shortId(data.brief.brief_id)}）；版本 ${source.version} 只保留为历史，旧内容未被改写。`);
  } catch (error) {
    if (current === epoch) setStatus(`简报修订未确认：${revisionHint(error)}`, true);
  } finally {
    briefRevisionBusy = false;
    byId("brief-revision-submit").disabled = false;
  }
}
function loadDirectionRevision(direction, focusForm = true) {
  revisionDirectionTarget = direction;
  byId("revision-direction-title").value = direction.title;
  byId("revision-direction-notes").value = (direction.style_notes ?? []).join(", ");
  byId("revision-direction-color").value = direction.color_mood ?? "";
  byId("revision-direction-type").value = direction.typography_mood ?? "";
  byId("revision-direction-target").textContent = `正在修订方向「${direction.title}」版本 ${direction.version}（${shortId(direction.direction_id)}）：内容已按该版本预填。保存会新增一个版本，旧版本只保留为历史。` + (direction.chosen ? " 该版本是当前已选定方向：选定结论会随新版本带走，但设计系统绑定不会自动跟随，需重新建立。" : "") + (direction.superseded_by === null ? "" : " 注意：该版本已被取代，服务端会拒绝这次修订（STALE_REVISION），请改从版本链中的最新版本继续。");
  if (focusForm) byId("revision-direction-title").focus();
}
async function reviseDirection(draft) {
  if (!draft.owner) throw new Error("未选择项目。");
  if (!draft.directionId) throw new Error("请先选择要修订的方向版本。");
  const title = draft.title.trim();
  if (!title) throw new Error("修订需要方向标题");
  return api(
    `/projects/${draft.owner}/directions/${draft.directionId}/revisions`,
    {
      title,
      style_notes: draft.notes.length ? draft.notes : null,
      color_mood: draft.colorMood,
      typography_mood: draft.typeMood,
      idempotency_key: uuid()
    }
  );
}
async function submitDirectionRevision() {
  const current = epoch;
  const owner = project;
  const source = revisionDirectionTarget;
  if (!owner || directionRevisionBusy) return;
  if (!source) {
    setStatus("请先在某一方向行点击「新版本」以载入要修订的内容。", true);
    return;
  }
  directionRevisionBusy = true;
  byId("direction-revision-submit").disabled = true;
  try {
    const title = byId("revision-direction-title").value.trim();
    const notes = splitList(byId("revision-direction-notes").value, 300, "表现备注");
    const colorMood = byId("revision-direction-color").value.trim() || null;
    const typeMood = byId("revision-direction-type").value.trim() || null;
    if (!title) throw new Error("修订需要方向标题");
    const data = await reviseDirection({
      owner,
      directionId: source.direction_id,
      title,
      notes,
      colorMood,
      typeMood
    });
    if (current !== epoch) return;
    highlightDirection = data.direction.direction_id;
    await refreshDesign();
    if (current !== epoch) return;
    await loadDirectionLineage(data.direction.direction_id);
    if (current !== epoch) return;
    loadDirectionRevision(data.direction, false);
    setStatus(`方向已保存为版本 ${data.direction.version}（${shortId(data.direction.direction_id)}）；版本 ${source.version} 只保留为历史。` + (data.direction.chosen ? ` 选定结论已随新版本带走（${data.direction.actor}）；设计系统绑定未跟随，绑定需重新建立。` : ""));
  } catch (error) {
    if (current === epoch) setStatus(`方向修订未确认：${revisionHint(error)}`, true);
  } finally {
    directionRevisionBusy = false;
    byId("direction-revision-submit").disabled = false;
  }
}
async function loadBriefLineage(briefId) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const request = ++briefLineageRequest;
  setStatus("正在读取简报版本链…");
  const data = await api(`/projects/${owner}/briefs/${briefId}/lineage`).catch((error) => {
    if (current !== epoch || request !== briefLineageRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== briefLineageRequest) return;
  const versions = /* @__PURE__ */ new Map();
  for (const row of data.lineage.versions) versions.set(row.brief_id, row.version);
  const liveId = data.lineage.live_id;
  const live = liveId === null ? "—" : versionOf(liveId, versions);
  const first = data.lineage.versions.length ? data.lineage.versions[0] : null;
  byId("brief-lineage-title").textContent = `简报版本链 · 共 ${data.lineage.versions.length} 个版本 · 当前 ${live} · 起点 ${first ? `版本 ${first.version}` : "—"}`;
  byId("brief-lineage").replaceChildren(
    ...data.lineage.versions.map((row) => {
      const li = document.createElement("li");
      li.textContent = `版本 ${row.version} · ${versionState(row.superseded_by, versions)} · ${row.title} · ${row.goals.join(" / ")}${row.constraints ? ` · ${row.constraints}` : ""} · 参考 ${row.reference_asset_ids.length} · 记录于 ${row.created_at} · ${row.spec_sha256}`;
      return li;
    })
  );
  setStatus(`简报版本链已读回：共 ${data.lineage.versions.length} 个版本，当前 ${live}。`);
}
async function loadDirectionLineage(directionId) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const request = ++directionLineageRequest;
  setStatus("正在读取方向版本链…");
  const data = await api(`/projects/${owner}/directions/${directionId}/lineage`).catch((error) => {
    if (current !== epoch || request !== directionLineageRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== directionLineageRequest) return;
  const versions = /* @__PURE__ */ new Map();
  for (const row of data.lineage.versions) versions.set(row.direction_id, row.version);
  const liveId = data.lineage.live_id;
  const live = liveId === null ? "—" : versionOf(liveId, versions);
  const first = data.lineage.versions.length ? data.lineage.versions[0] : null;
  byId("direction-lineage-title").textContent = `方向版本链 · 共 ${data.lineage.versions.length} 个版本 · 当前 ${live} · 起点 ${first ? `版本 ${first.version}` : "—"}`;
  byId("direction-lineage").replaceChildren(
    ...data.lineage.versions.map((row) => {
      const li = document.createElement("li");
      li.textContent = `版本 ${row.version} · ${versionState(row.superseded_by, versions)} · ${row.title} · ${row.chosen ? `已选定（${row.actor}）` : "未选定"} · 色彩 ${row.color_mood ?? "未指定"} · 字体 ${row.typography_mood ?? "未指定"} · 记录于 ${row.created_at} · ${row.spec_sha256}`;
      return li;
    })
  );
  setStatus(`方向版本链已读回：共 ${data.lineage.versions.length} 个版本，当前 ${live}。`);
}
function resetDesignRevision() {
  revisionBriefTarget = revisionDirectionTarget = null;
  revisionBriefCarried = [];
  highlightBrief = highlightDirection = null;
  byId("revision-brief-target").textContent = REVISION_BRIEF_IDLE;
  byId("revision-direction-target").textContent = REVISION_DIRECTION_IDLE;
  byId("brief-lineage-title").textContent = "";
  byId("direction-lineage-title").textContent = "";
  byId("design-binding-active").textContent = "";
}
const byId = (id) => document.getElementById(id);
let token = "";
let connected = false;
let connectGeneration = 0;
let project = "";
let epoch = 0;
let taskCursor = null;
let eventCursor = null;
let eventJob = "";
let pendingImport = null;
let busy = false;
let nativeCursor = null;
let eventRequest = 0;
let previewRequest = 0;
let verificationRequest = 0;
let taskRequest = 0;
let nativeRequest = 0;
let refreshRequest = 0;
let plansRequest = 0;
let submittedPlan = null;
let planBusy = false;
let patchSource = null;
let submittedPatch = null;
let patchBusy = false;
const setStatus = (text, error = false) => {
  const el2 = byId("status");
  el2.textContent = text;
  el2.classList.toggle("error", error);
  const main = typeof document.querySelector === "function" ? document.querySelector("body > main") : null;
  if (main && main.hidden) {
    const live = document.querySelector(".sr-status");
    if (live) live.textContent = text;
  }
};
const errMsg = (error) => error instanceof Error ? error.message : String(error);
const dropSession = () => {
  token = "";
  connected = false;
  const badge = byId("connection");
  if (badge) badge.textContent = "未连接";
};
const READ_TIMEOUT_MS = 15e3;
const WRITE_TIMEOUT_MS = 45e3;
let pageGeneration = null;
const currentGeneration = () => pageGeneration ??= new AbortController();
function cancelPendingReads() {
  pageGeneration?.abort();
  pageGeneration = null;
}
class ReadDeadlineError extends Error {
}
class PageReadCancelledError extends Error {
}
class WriteOutcomeUnknownError extends Error {
  outcomeUnknown = true;
}
async function api(path, body, options = {}) {
  const isWrite = body !== void 0;
  const timeoutMs = options.timeoutMs ?? (isWrite ? WRITE_TIMEOUT_MS : READ_TIMEOUT_MS);
  const controller = new AbortController();
  let deadlineHit = false;
  const timer = setTimeout(() => {
    deadlineHit = true;
    controller.abort();
  }, timeoutMs);
  const cancel = () => controller.abort();
  const generation = isWrite ? null : currentGeneration();
  if (generation) generation.signal.addEventListener("abort", cancel, { once: true });
  options.signal?.addEventListener("abort", cancel, { once: true });
  let response;
  let bodySeen = false;
  let status = 0;
  let value;
  try {
    response = await fetch("/api" + path, {
      method: body ? "POST" : "GET",
      headers: { Authorization: "Bearer " + token, ...body ? { "Content-Type": "application/json" } : {} },
      ...body ? { body: JSON.stringify(body) } : {},
      cache: "no-store",
      signal: controller.signal
    });
    bodySeen = true;
    status = response.status;
    value = await response.json();
  } catch (error) {
    if (deadlineHit) {
      const seconds = timeoutMs >= 1e3 ? Math.round(timeoutMs / 1e3) : timeoutMs / 1e3;
      if (isWrite)
        throw new WriteOutcomeUnknownError(
          `提交已发出，但 ${seconds} 秒内没有答复：结果待核对，不是失败。请先读回该资源确认服务端是否已经落库，再决定是否重发；同一个幂等键重发是安全的，但不要不看读回就重发。`
        );
      throw new ReadDeadlineError(
        `读取超时（${seconds} 秒未答复）：本次读取已放弃。读取没有产生任何写入，可以直接重试。`
      );
    }
    if (controller.signal.aborted) {
      if (isWrite)
        throw new WriteOutcomeUnknownError(
          "提交已发出，但答复在读取过程中被取消：结果待核对，不是失败。请先读回该资源确认服务端是否已经落库，再决定是否重发。"
        );
      throw new PageReadCancelledError(
        "页面已切换，本次读取已取消（没有产生写入）。重新进入该页会重新读取。"
      );
    }
    if (bodySeen) {
      throw new Error(`服务回复无法解析（HTTP ${status}，${errMsg(error)}）`);
    }
    throw new Error(`无法连接本机设计服务（${errMsg(error)}）`);
  } finally {
    clearTimeout(timer);
    generation?.signal.removeEventListener("abort", cancel);
    options.signal?.removeEventListener("abort", cancel);
  }
  if (response.status === 401) dropSession();
  if (!response.ok) {
    if (value.error === "PROJECT_PATH_TOO_LONG")
      throw new Error("项目路径过长，Windows 无法保存。请将项目放在较短的目录后重试。");
    const failure = new Error(value.error || "SERVICE_ERROR");
    failure.serviceEnvelope = value;
    throw failure;
  }
  return value;
}
function setListNotice(listId, text) {
  const list = byId(listId);
  const li = document.createElement("li");
  li.className = "empty";
  li.textContent = text;
  list.replaceChildren(li);
}
function button(list, label, action) {
  const li = document.createElement("li");
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.onclick = () => action().catch((error) => setStatus(errMsg(error), true));
  li.append(b);
  byId(list).append(li);
}
function resetProject() {
  submittedPlan = null;
  patchSource = submittedPatch = null;
  byId("patch-source").textContent = "请从已完成的 Illustrator 或 Photoshop 任务选择修改来源。";
  epoch++;
  taskCursor = eventCursor = null;
  eventJob = "";
  pendingImport = null;
  nativeCursor = null;
  byId("native-info").textContent = "";
  for (const id of [
    "assets",
    "tasks",
    "events",
    "native-assets",
    "reference-picker",
    "design-briefs",
    "design-directions",
    "design-bindings",
    "brief-lineage",
    "direction-lineage",
    "recent-plans"
  ])
    byId(id).replaceChildren();
  byId("recent-plans-info").textContent = "未选项目，因此这一列没有读过任何方案。";
  resetDesignRevision();
  for (const id of ["preview", "retry-import", "more-tasks", "more-events", "more-native"]) byId(id).hidden = true;
  byId("preview").removeAttribute("src");
  byId("preview-empty").hidden = false;
  byId("asset-info").textContent = "";
}
async function projects() {
  const data = await api("/projects");
  byId("project").replaceChildren(new Option("选择项目", ""));
  for (const p of data.projects) byId("project").append(new Option(p.name, p.id));
  if (!project) {
    let remembered = "";
    try {
      remembered = window.localStorage.getItem("design-lab:active-project") || "";
    } catch {
    }
    if (data.projects.some((p) => p.id === remembered)) project = remembered;
    else if (data.projects.length === 1) project = data.projects[0].id;
  }
  if (data.projects.some((p) => p.id === project)) byId("project").value = project;
}
function rememberProject$1() {
  try {
    window.localStorage.setItem("design-lab:active-project", project);
  } catch {
  }
}
async function loadEvents(job, append = false) {
  if (append && job !== eventJob) return;
  const current = epoch;
  const owner = project;
  const request = ++eventRequest;
  if (!append) {
    eventJob = job;
    eventCursor = null;
    byId("events").replaceChildren();
    byId("more-events").hidden = true;
  }
  const data = await api(
    `/projects/${owner}/tasks/${job}/events` + (append && eventCursor !== null ? `?after=${eventCursor}` : "")
  ).catch((error) => {
    if (current !== epoch || request !== eventRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== eventRequest) return;
  for (const event of data.events) {
    const li = document.createElement("li");
    li.textContent = `${event.at} · attempt ${event.attempt_no} · ${event.from_state || "NEW"} → ${event.to_state}`;
    byId("events").append(li);
  }
  eventCursor = data.next_cursor;
  byId("more-events").hidden = eventCursor === null;
}
async function tasks(append = false) {
  if (append && taskCursor === null) return;
  if (!append) {
    taskCursor = null;
    byId("more-tasks").hidden = true;
  }
  const current = epoch;
  const owner = project;
  const request = ++taskRequest;
  const data = await api(
    `/projects/${owner}/tasks` + (append && taskCursor ? `?after=${taskCursor}` : "")
  ).catch((error) => {
    if (current !== epoch || request !== taskRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== taskRequest) return;
  if (!append) byId("tasks").replaceChildren();
  for (const task of data.tasks) {
    button("tasks", `${task.kind} · ${task.state} · attempt ${task.attempt.attempt_no} · ${task.job_id.slice(-12)}`, () => loadEvents(task.job_id));
    if (task.kind.endsWith("-native") && task.attempt.state === "RECEIPTED")
      button("tasks", `导出交付包 · ${task.job_id.slice(-12)} · rights/质量待审`, () => exportBundle(task));
    if (["illustrator-native", "photoshop-native"].includes(task.kind) && task.attempt.state === "RECEIPTED")
      button("tasks", `修改对象 · ${task.job_id.slice(-12)}`, async () => {
        if (current !== epoch) return;
        patchSource = { owner, job: task.job_id, attempt: task.attempt.attempt_id };
        byId("patch-source").textContent = `来源 ${task.job_id} · ${task.attempt.attempt_id}。将在新副本修改，不覆盖原件。`;
      });
    if (task.kind.endsWith("-native") && ["PENDING", "RUNNING", "OUTCOME_UNKNOWN"].includes(task.attempt.state))
      button("tasks", `请求取消 · ${task.job_id.slice(-12)}`, () => cancelTask(task));
    if (task.kind.endsWith("-native") && task.attempt.state === "PENDING")
      button("tasks", `启动任务 · ${task.job_id.slice(-12)}`, () => startTask(task));
  }
  if (!append && !data.tasks.length) setListNotice("tasks", "尚无任务。导入图片后可查看真实记录。");
  taskCursor = data.next_cursor;
  byId("more-tasks").hidden = taskCursor === null;
}
async function startTask(task) {
  const current = epoch;
  const owner = project;
  const data = await api(
    `/projects/${owner}/tasks/${task.job_id}/run`,
    { attempt_id: task.attempt.attempt_id }
  ).catch((error) => {
    if (current !== epoch) return null;
    throw error;
  });
  if (!data || current !== epoch) return;
  await tasks();
  if (current !== epoch) return;
  setStatus(`工作进程：${data.worker}；不代表制作成功，请刷新查看宿主读回状态。`);
}
async function cancelTask(task) {
  const current = epoch;
  const owner = project;
  const data = await api(
    `/projects/${owner}/tasks/${task.job_id}/cancel`,
    { attempt_id: task.attempt.attempt_id }
  ).catch((error) => {
    if (current !== epoch) return null;
    throw error;
  });
  if (!data || current !== epoch) return;
  await tasks();
  if (current !== epoch) return;
  setStatus(`取消请求读回：${data.task.attempt.state}；请求受理不代表宿主已停止。`);
}
async function exportBundle(task) {
  const current = epoch;
  const owner = project;
  const access = token;
  setStatus("正在核对原生文件并打包；此操作不代表设计验收。");
  const data = await api(`/projects/${owner}/tasks/${task.job_id}/bundle`, {});
  if (current !== epoch) return;
  const expected = new RegExp(`^/api/projects/${owner}/bundles/bundle-native-[0-9a-f]{64}/versions/v-[0-9a-f]{32}/content$`);
  if (!expected.test(data.download_path)) throw new Error("INVALID_BUNDLE_ROUTE");
  const response = await fetch(data.download_path, { headers: { Authorization: "Bearer " + access }, cache: "no-store" });
  if (!response.ok) throw new Error("BUNDLE_DOWNLOAD_UNVERIFIED");
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
  if (digest !== data.bundle.sha256 || bytes.byteLength !== data.bundle.byte_size) throw new Error("BUNDLE_HASH_MISMATCH");
  if (current !== epoch) return;
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `design-lab-${task.job_id.slice(-12)}.zip`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 3e4);
  setStatus("交付包下载 hash 已核对；字体、链接、rights 与质量仍需验收。");
}
async function preview(assetId) {
  const current = epoch;
  const request = ++previewRequest;
  const data = await api(`/projects/${project}/assets/${assetId}/content`).catch((error) => {
    if (current !== epoch || request !== previewRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== previewRequest) return;
  if (!["image/png", "image/jpeg"].includes(data.asset.media_type)) throw new Error("UNSUPPORTED_PREVIEW");
  byId("preview").src = `data:${data.asset.media_type};base64,${data.content_base64}`;
  byId("preview").hidden = false;
  byId("preview-empty").hidden = true;
  byId("asset-info").textContent = `${data.asset.width} × ${data.asset.height} · rights: ${data.asset.rights} · ${data.asset.sha256}`;
}
async function refresh() {
  if (!project) return;
  const current = epoch;
  const request = ++refreshRequest;
  setStatus("正在读取项目资产与任务…");
  const result = await Promise.all([api(`/projects/${project}/assets`), tasks(), nativeAssets(), recentPlans()]).catch((error) => {
    if (current !== epoch || request !== refreshRequest) return null;
    throw error;
  });
  if (!result || current !== epoch || request !== refreshRequest) return;
  const [data] = result;
  byId("assets").replaceChildren();
  for (const asset of data.assets)
    button("assets", `${asset.width} × ${asset.height} · ${asset.media_type} · ${asset.id.slice(-10)}`, () => preview(asset.id));
  populateReferencePicker(data.assets.map((asset) => asset.id));
  setStatus("已读取持久化状态。参考素材权利仍需审查。");
}
const RECENT_PLANS_LIMIT = 5;
async function recentPlans() {
  const info2 = byId("recent-plans-info");
  const list = byId("recent-plans");
  if (!project) {
    list.replaceChildren();
    info2.textContent = "未选项目，因此这一列没有读过任何方案。";
    return;
  }
  const current = epoch;
  const owner = project;
  const request = ++plansRequest;
  let data;
  try {
    data = await api(
      `/projects/${owner}/assistance-plans?limit=${RECENT_PLANS_LIMIT}`
    );
  } catch (error) {
    if (current !== epoch || request !== plansRequest) return;
    list.replaceChildren();
    info2.textContent = `最近方案没读到：${errMsg(error)}。这不代表这个项目没有方案。`;
    return;
  }
  if (current !== epoch || request !== plansRequest || owner !== project) return;
  if (!Array.isArray(data?.plans)) {
    list.replaceChildren();
    info2.textContent = "未读回：响应里没有 plans 数组，因此不能说这个项目没有方案。";
    return;
  }
  const rows = data.plans;
  if (!rows.length) {
    setListNotice("recent-plans", "还没有方案记录。设计辅助里可以立第一条。");
    info2.textContent = `这一页读到 ${data.returned} 条，这个项目共 ${data.total} 条。`;
    return;
  }
  list.replaceChildren(...rows.map((row) => {
    const li = document.createElement("li");
    li.className = "plan-line";
    const title = document.createElement("strong");
    title.textContent = row.objective;
    const meta = document.createElement("small");
    meta.textContent = `${row.created_at} · ${row.created_by}`;
    li.append(title, meta);
    return li;
  }));
  info2.textContent = `这一页读到 ${data.returned} 条，服务按写入时间倒序发回；这个项目共 ${data.total} 条` + (data.total > rows.length ? `，还有 ${data.total - rows.length} 条在这一页之外。` : "。");
}
function populateReferencePicker(assetIds) {
  const picker = byId("reference-picker");
  const selected = new Set(typeof document.querySelectorAll === "function" ? selectedReferences() : []);
  picker.replaceChildren();
  if (!assetIds.length) {
    const li = document.createElement("li");
    li.textContent = "尚未导入参考素材。先导入 PNG/JPEG，再回来为简报勾选。";
    picker.append(li);
    return;
  }
  for (const id of assetIds) {
    const li = document.createElement("li");
    const label = document.createElement("label");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.name = "reference-asset";
    box.value = id;
    box.checked = selected.has(id);
    label.append(box, document.createTextNode(" " + id));
    li.append(label);
    picker.append(li);
  }
}
function selectedReferences() {
  return Array.from(document.querySelectorAll('input[name="reference-asset"]:checked')).map((el2) => el2.value);
}
async function verifyNative(asset) {
  const current = epoch;
  const owner = project;
  const request = ++verificationRequest;
  byId("native-info").textContent = "正在读取原生文件并校验 hash…";
  const data = await api(`/projects/${owner}/native-assets/${asset.id}/verify`).catch((error) => {
    if (current !== epoch || request !== verificationRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== verificationRequest) return;
  byId("native-info").textContent = `${data.asset.kind.toUpperCase()} · ${data.asset.version_id} · ${data.asset.verification} · ${data.asset.byte_size} bytes · ${data.asset.sha256} · rights: ${data.asset.rights}。此校验不代替宿主重开或人工质量验收。`;
}
async function nativeAssets(append = false) {
  if (append && nativeCursor === null) return;
  if (!append) {
    nativeCursor = null;
    byId("more-native").hidden = true;
  }
  const current = epoch;
  const owner = project;
  const request = ++nativeRequest;
  const data = await api(
    `/projects/${owner}/native-assets` + (append && nativeCursor ? `?after=${nativeCursor}` : "")
  ).catch((error) => {
    if (current !== epoch || request !== nativeRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== nativeRequest) return;
  if (!append) byId("native-assets").replaceChildren();
  for (const asset of data.assets)
    button("native-assets", `校验 ${asset.kind.toUpperCase()} · v${asset.version_no} · ${asset.version_id} · 数据库记录`, () => verifyNative(asset));
  if (!append && !data.assets.length) setListNotice("native-assets", "暂无已登记的 AI/PSD。");
  nativeCursor = data.next_cursor;
  byId("more-native").hidden = nativeCursor === null;
}
async function sendImport() {
  if (!pendingImport || busy) return;
  const job = pendingImport;
  busy = true;
  byId("import-button").disabled = true;
  byId("retry-import").hidden = true;
  setStatus("正在导入并验证图片。关闭页面不撤销服务端操作。");
  try {
    await api(`/projects/${job.project}/assets`, job.body);
    if (pendingImport === job) pendingImport = null;
    if (project === job.project) await refresh();
    setStatus("导入已保存；选择资产查看服务器读回。");
  } catch (error) {
    setStatus(`导入未确认：${errMsg(error)}。可使用同一幂等键重试；不会自动重复创建。`, true);
    byId("retry-import").hidden = pendingImport !== job;
  } finally {
    busy = false;
    byId("import-button").disabled = false;
  }
}
async function connectLocalService(submittedToken = "") {
  const generation = ++connectGeneration;
  if (!submittedToken) {
    setStatus("正在连接本机设计服务…");
    try {
      const response = await fetch("/api/local-session", { cache: "no-store", signal: AbortSignal.timeout(8e3) });
      if (!response.ok) throw new Error("本机服务未开启自动连接，请使用官方 workbench 启动入口。");
      const session = await response.json();
      if (generation !== connectGeneration) return;
      submittedToken = session.token || "";
    } catch (error) {
      if (generation !== connectGeneration) return;
      setStatus(errMsg(error), true);
      return;
    }
  }
  if (!/^[0-9a-f]{64}$/.test(submittedToken)) {
    token = "";
    connected = false;
    setStatus("访问令牌格式不正确。", true);
    return;
  }
  token = submittedToken;
  try {
    await projects();
    if (generation !== connectGeneration || token !== submittedToken) return;
    connected = true;
    byId("login").hidden = true;
    byId("workspace").hidden = false;
    byId("connection").textContent = "本机已连接";
    setStatus("选择或新建项目。");
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function")
      window.dispatchEvent(new Event("hashchange"));
    if (project) {
      resetProject();
      void Promise.all([refresh(), loadDesignSystems(), refreshDesign()]).catch((error) => setStatus(`已连接，项目读回失败：${errMsg(error)}`, true));
    }
  } catch (error) {
    if (generation !== connectGeneration || token !== submittedToken) return;
    token = "";
    connected = false;
    setStatus(errMsg(error), true);
  }
}
byId("connect-form").onsubmit = async (event) => {
  event.preventDefault();
  const submittedToken = byId("token").value;
  byId("token").value = "";
  await connectLocalService(submittedToken);
};
byId("disconnect").onclick = () => {
  connectGeneration += 1;
  token = "";
  connected = false;
  project = "";
  resetProject();
  byId("workspace").hidden = true;
  byId("login").hidden = false;
  byId("connection").textContent = "未连接";
  setStatus("已清除页面内存中的访问令牌。");
};
byId("project").onchange = () => {
  project = byId("project").value;
  rememberProject$1();
  resetProject();
  refresh().catch((e) => setStatus(errMsg(e), true));
  loadDesignSystems().catch((e) => setStatus(errMsg(e), true));
  refreshDesign().catch((e) => setStatus(errMsg(e), true));
};
byId("refresh").onclick = () => {
  void refresh().catch((e) => setStatus(errMsg(e), true));
  void loadDesignSystems().catch((e) => setStatus(errMsg(e), true));
  void refreshDesign().catch((e) => setStatus(errMsg(e), true));
};
byId("open-assistant").onclick = () => {
  if (typeof window === "undefined" || !window.location) return;
  window.location.hash = "#/assistant";
};
let creatingProject = false;
byId("create-form").onsubmit = async (event) => {
  event.preventDefault();
  if (creatingProject) return;
  creatingProject = true;
  const form = byId("create-form");
  const submit = typeof form.querySelector === "function" ? form.querySelector("button") : null;
  if (submit) submit.disabled = true;
  try {
    const data = await api("/projects", { name: byId("project-name").value });
    project = data.project.id;
    rememberProject$1();
    resetProject();
    await projects();
    byId("project-name").value = "";
    await refresh();
  } catch (error) {
    setStatus(errMsg(error), true);
  } finally {
    creatingProject = false;
    if (submit) submit.disabled = false;
  }
};
byId("import-form").onsubmit = async (event) => {
  event.preventDefault();
  if (busy) return;
  const input = byId("file");
  const file = input.files && input.files[0];
  const owner = project;
  if (!owner || !file) {
    setStatus("请先选择项目和图片。", true);
    return;
  }
  if (!["image/png", "image/jpeg"].includes(file.type) || file.size > 32 * 1024 * 1024) {
    setStatus("仅支持不超过 32 MiB 的 PNG/JPEG。", true);
    return;
  }
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (owner !== project) throw new Error("项目已切换，请重新导入");
    let binary = "";
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    pendingImport = { project: owner, body: { content_base64: btoa(binary), idempotency_key: crypto.randomUUID() } };
    await sendImport();
  } catch (error) {
    setStatus(errMsg(error), true);
  }
};
byId("retry-import").onclick = () => {
  void sendImport();
};
byId("plan-form").onsubmit = async (event) => {
  event.preventDefault();
  if (planBusy) return;
  const current = epoch;
  const owner = project;
  try {
    if (!owner) throw new Error("请先选择项目");
    const raw = byId("plan-rir").value;
    const styles = byId("plan-styles").value;
    if (raw.length + styles.length > 39e5) throw new Error("对象计划过大");
    const body = {
      host: byId("plan-host").value,
      rir: JSON.parse(raw),
      text_styles: JSON.parse(styles)
    };
    const identity = JSON.stringify(body);
    if (!submittedPlan || submittedPlan.owner !== owner || submittedPlan.identity !== identity)
      submittedPlan = { owner, identity, key: crypto.randomUUID() };
    body.idempotency_key = submittedPlan.key;
    planBusy = true;
    byId("plan-submit").disabled = true;
    const data = await api(`/projects/${owner}/native-plans`, body);
    if (current !== epoch) return;
    await tasks();
    if (current !== epoch) return;
    setStatus(`对象计划已持久化：${data.task.attempt.state}。请从任务列表显式启动；未执行质量或权利验收。`);
  } catch (error) {
    if (current === epoch) setStatus(`计划提交未确认：${errMsg(error)}。内容不变时重试复用幂等键。`, true);
  } finally {
    planBusy = false;
    byId("plan-submit").disabled = false;
  }
};
byId("more-tasks").onclick = () => {
  void tasks(true).catch((e) => setStatus(errMsg(e), true));
};
byId("patch-form").onsubmit = async (event) => {
  event.preventDefault();
  if (patchBusy) return;
  const current = epoch;
  const owner = project;
  const source = patchSource;
  try {
    if (!source || source.owner !== owner) throw new Error("请先选择当前项目的 Illustrator 来源任务");
    const raw = byId("patch-json").value;
    if (raw.length > 9e5) throw new Error("局部修改过大");
    const body = { source_attempt_id: source.attempt, patch: JSON.parse(raw) };
    const identity = JSON.stringify({ source, body });
    if (!submittedPatch || submittedPatch.identity !== identity)
      submittedPatch = { identity, key: crypto.randomUUID() };
    body.idempotency_key = submittedPatch.key;
    patchBusy = true;
    byId("patch-submit").disabled = true;
    const data = await api(`/projects/${owner}/tasks/${source.job}/patch`, body);
    if (current !== epoch) return;
    await tasks();
    if (current !== epoch) return;
    setStatus(`局部修改已排队：${data.task.attempt.state} · 父版本 ${data.parent.version_id}。需显式启动，尚未执行或通过质量验收。`);
  } catch (error) {
    if (current === epoch) setStatus(`局部修改提交未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    patchBusy = false;
    byId("patch-submit").disabled = false;
  }
};
byId("more-events").onclick = () => {
  void loadEvents(eventJob, true).catch((e) => setStatus(errMsg(e), true));
};
byId("more-native").onclick = () => {
  void nativeAssets(true).catch((e) => setStatus(errMsg(e), true));
};
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === void 0) continue;
    if (key === "class") node.className = String(value);
    else if (key === "dataset") for (const [dk, dv] of Object.entries(value)) node.dataset[dk] = String(dv);
    else if (key.startsWith("on") || key === "type" || key === "value" || key === "placeholder")
      node[key] = value;
    else if (key === "style" && node.style) node.style.cssText = String(value);
    else node.setAttribute(key, String(value));
  }
  node.append(...children);
  return node;
}
function en(text) {
  return el("span", { lang: "en" }, text);
}
const SHAPE_MISSING = Symbol.for("design-lab/shape-missing");
const DISCONNECTED = Symbol.for("design-lab/disconnected");
function normaliseShape(live, template, prefix = "") {
  if (template === null || typeof template !== "object") return [];
  const missing = [];
  for (const [key, want] of Object.entries(template)) {
    const field = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(want)) {
      if (!Array.isArray(live[key])) {
        live[key] = [];
        missing.push(field);
      }
    } else if (want !== null && typeof want === "object") {
      if (live[key] === null || typeof live[key] !== "object") {
        live[key] = {};
        missing.push(field);
      }
      missing.push(...normaliseShape(live[key], want, field));
    }
  }
  return missing;
}
function shapeNoticeRows(...values) {
  const notes = values.map(shapeNotice).filter(Boolean);
  return notes.length ? [el("p", { class: "error" }, notes.join("；"))] : [];
}
function shapeNotice(value) {
  const missing = value?.[SHAPE_MISSING];
  return Array.isArray(missing) && missing.length ? `未读回：响应缺少 ${missing.join("、")}` : "";
}
function shapeFieldMissing(value, field) {
  const missing = value?.[SHAPE_MISSING];
  return Array.isArray(missing) && missing.includes(field);
}
function markDisconnected(payload) {
  const mark = (target) => {
    Object.defineProperty(target, DISCONNECTED, { value: true, enumerable: false });
  };
  mark(payload);
  for (const value of Object.values(payload)) {
    if (value !== null && typeof value === "object") mark(value);
  }
  return payload;
}
function disconnectedNotice(value) {
  return value?.[DISCONNECTED] === true ? "未读回：未连接本机设计服务" : "";
}
function emptyWording(value, noun, hint) {
  const offline = disconnectedNotice(value);
  return offline ? ["未读回", offline] : [noun, hint];
}
function emptyLi(value, noun, hint) {
  const [head, note] = emptyWording(value, noun, hint);
  return el("li", { class: "list-item" }, el("div", {}, el("strong", {}, head), el("small", {}, note)));
}
function emptyTd(value, noun, hint, colspan) {
  const [head, note] = emptyWording(value, noun, hint);
  return el("td", { colspan: String(colspan) }, `${head} ${note}`);
}
const PROJECT_DETAIL_RE = /^#\/projects\/([^/?#]+)$/;
const PROJECT_ID_RE = /^[0-9a-f]{32}$/;
function projectDetailId(hash) {
  const m = PROJECT_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return PROJECT_ID_RE.test(decoded) ? decoded : null;
}
function projectDetailHash(id) {
  return "#/projects/" + encodeURIComponent(id);
}
const CAPABILITY_DETAIL_RE = /^#\/capabilities\/([^/?#]+)$/;
const DETAIL_ID_RE = /^[a-z0-9][a-z0-9-]{0,79}$/;
function capabilityDetailId(hash) {
  const m = CAPABILITY_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return DETAIL_ID_RE.test(decoded) ? decoded : null;
}
function capabilityDetailHash(id) {
  return "#/capabilities/" + encodeURIComponent(id);
}
const DOMAIN_DETAIL_RE = /^#\/domains\/([^/?#]+)$/;
function domainDetailId(hash) {
  const m = DOMAIN_DETAIL_RE.exec(hash);
  if (!m || !m[1]) return null;
  let decoded;
  try {
    decoded = decodeURIComponent(m[1]);
  } catch {
    return null;
  }
  return DETAIL_ID_RE.test(decoded) ? decoded : null;
}
function domainDetailHash(packId) {
  return packId ? "#/domains/" + encodeURIComponent(packId) : null;
}
const HASH_SPLIT_RE = /^([^?]*)(?:\?(.*))?$/g;
function hashPath(hash) {
  const m = HASH_SPLIT_RE.exec(hash);
  HASH_SPLIT_RE.lastIndex = 0;
  return m ? m[1] : hash;
}
function hashCondition(hash, name) {
  const m = HASH_SPLIT_RE.exec(hash);
  HASH_SPLIT_RE.lastIndex = 0;
  const query = m && m[2];
  if (!query) return null;
  for (const pair of query.split("&")) {
    const eq = pair.indexOf("=");
    if (eq <= 0 || pair.slice(0, eq) !== name) continue;
    try {
      const value = decodeURIComponent(pair.slice(eq + 1));
      return value || null;
    } catch {
      return null;
    }
  }
  return null;
}
function capabilityHashForDomain(slug) {
  return slug ? "#/capabilities?domain=" + encodeURIComponent(slug) : "#/capabilities";
}
function declaredDomains(row) {
  const values = row?.axes?.domains;
  return Array.isArray(values) ? values.filter((value) => typeof value === "string") : [];
}
function domainsUnclassified(row) {
  const axes = row?.unclassifiedAxes;
  return Array.isArray(axes) && axes.includes("domains");
}
function devMode() {
  if (typeof document === "undefined" || typeof window === "undefined") return false;
  if (typeof document.querySelectorAll === "function" && document.querySelectorAll('script[src*="@vite/client"]').length > 0) return true;
  try {
    const qs = window.location.search;
    if (typeof qs === "string" && qs.includes("dev=1")) return true;
  } catch {
  }
  return false;
}
function apiOrEmpty(path, empty) {
  if (!token && devMode()) return Promise.resolve(markDisconnected(empty));
  return api(path).then((live) => {
    const missing = normaliseShape(live, empty);
    if (missing.length) Object.defineProperty(live, SHAPE_MISSING, { value: missing, enumerable: false });
    return live;
  });
}
const OFFLINE = {
  health: { status: "UNKNOWN", version: "—", scope: "dev-offline" },
  projects: { projects: [] },
  designSystems: { design_systems: [] },
  tokenDocuments: { token_documents: [] },
  capabilities: {
    schemaVersion: "design-lab/capability-library/v1",
    meaning: "未连接本机设计服务",
    unmeasuredMeans: "null = 未判定，不是 0",
    counts: {
      total: 0,
      byKind: {},
      byLicense: {},
      byRevisionState: {},
      qualificationVerdicts: 0,
      qualifiedTrue: 0,
      qualifiedFalse: 0,
      qualificationNotAdjudicated: 0
    },
    sources: {},
    capabilities: []
  },
  // The domain readback's honest empty: the counts are zero because nothing was read,
  // and rootState / checker.state say WHY instead of leaving a blank the page would
  // have to guess at. `validationVocabulary` is the service's own declaration of its
  // closed verdict set, so it is NOT filled in here: inventing it offline would put
  // words on the screen that no readback produced. The tally rows are built from
  // `counts.byValidation`, which is empty for exactly this reason.
  domains: {
    schemaVersion: "design-lab/domain-pack-readback/v1",
    meaning: "未连接本机设计服务",
    unmeasuredMeans: "null = 未声明 / 未判定，不是 0",
    root: "design-lab/domain-packs",
    rootState: "NOT_READ",
    validationVocabulary: [],
    checker: {
      path: "design-lab/scripts/verify_domain_pack_v2.py",
      state: "NOT_READ",
      note: "未连接本机设计服务"
    },
    sources: {},
    counts: { packs: 0, byValidation: {} },
    packs: []
  },
  // 自动化连接器登记的诚实空载荷：两个来源都"未读回"，不是"没有连接器"。计数全部为 0 且
  // evidence_ceiling 留空，因为离线时任何等级说法都不是从读回来的。
  automationConnectors: {
    meaning: "未连接本机设计服务",
    unprobedMeans: "未读回，因此不说明任何连接器的状态",
    registry_state: "NOT_READ",
    pack_state: "NOT_READ",
    counts: {
      connectors: 0,
      handshaked_in_pack_evidence: 0,
      tools_listed_total_in_pack_evidence: 0,
      native_tool_calls_executed: 0,
      probed_by_design_lab: 0,
      enabled: 0,
      project_adapters: 0
    },
    connectors: [],
    pack: {
      zip_bytes: null,
      zip_sha256: null,
      declared_connections: null,
      verification: null
    },
    not_activated: [],
    inert_instruction_blobs: null,
    evidence_ceiling: "",
    claims_not_made: []
  },
  tasks: { tasks: [], next_cursor: null },
  // DL-UI-U06: every section is NOT_READ, never ABSENT. "This service never recorded a native
  // attempt" is a claim about the database's table list, and a page that never reached the
  // database has no basis for it -- the same distinction the read-back itself keeps, carried
  // one layer further so an offline screen cannot borrow the service's honesty.
  nativeRuntime: {
    schemaVersion: "design-lab/native-runtime-readback/v1",
    project_id: "",
    host_guard: { table: "NOT_READ", rows: null },
    quiescence: { table: "NOT_READ", rows: null },
    reconciliation: { table: "NOT_READ", rows: null },
    recovery_protocol: { table: "NOT_READ", rows: null },
    executions: { table: "NOT_READ", rows: null },
    counts: {
      hosts_held: null,
      attempts_quiescent_receipted: null,
      reconciliations_open: null,
      executions_receipted: null,
      executions_with_result: null
    },
    budget: null,
    budget_reason: "未读回：没有问到预算，因此既不能说有，也不能说没有",
    proves_production_ready: false,
    is_host_action_performed: false,
    does_not_say: []
  },
  // DL-UI-U09. The zero counts here are "nothing was asked", not "the project has no
  // candidates": the offline marker on this payload says so, and the panel prints the
  // disconnected notice beside the counts. `does_not_say` is empty because the service
  // never spoke; inventing its boundary sentences would be the page testifying.
  knowledge: {
    schemaVersion: "design-lab/assurance-knowledge-candidate-readback/v1",
    project_id: "",
    candidates: [],
    candidate_count: 0,
    unreadable_count: 0,
    pending_review_count: 0,
    approved_count: 0,
    rejected_count: 0,
    revoked_count: 0,
    export_ready_count: 0,
    conflicts: [],
    revocation_receipts: [],
    head_sha: null,
    outbound: {
      transport: "NOT_CONNECTED",
      destination: "ArcheAxis",
      sent_count: 0,
      last_attempt_at: null,
      note: "未连接本机设计服务：sent_count 的 0 表示没有问到，不是一次失败的发送。"
    },
    does_not_say: []
  },
  bundles: { bundles: [] },
  // DL-KB-03: 知识库检索答案的诚实空载荷。两个列表都空是因为什么都没问到；台账数字为 0
  // 同样表示"没有问到"，由未连接标记说明。`entryTypes` / `licenseStates` 留空而不是手抄一份
  // 词表：离线页不显示类型选项，而不是编一套标签。`does_not_say` 也留空——服务没说话，
  // 页面不替它声明边界。
  knowledgeLibrary: {
    schemaVersion: "design-lab/knowledge-library/v1",
    query: null,
    filters: { type: null, domain: null, task: null, target: null },
    entryTypes: [],
    licenseStates: [],
    strategy: "BROWSE",
    matched_terms: [],
    total: 0,
    offset: 0,
    limit: 50,
    returned: 0,
    next_offset: null,
    entries: [],
    explanation: null,
    index: { rows: 0, indexed: 0, rebuilt_at: null },
    does_not_say: []
  },
  // DL-KB-08：输出类型词表的诚实空载荷。离线时不手抄六项标签——选择框显示"未读回"，
  // 也不把一个服务可能拒绝的词画成可选项。方案清单同理：空列表表示没有问到，不是"没有方案"。
  assistanceOutputTypes: {
    schemaVersion: "design-lab/assistance-plan-output-types/v1",
    output_types: []
  },
  assistancePlans: {
    schemaVersion: "design-lab/assistance-plan-list/v1",
    total: 0,
    offset: 0,
    limit: 20,
    returned: 0,
    next_offset: null,
    plans: []
  },
  // DL-KB-10：目标档案的两条只读接缝的诚实空载荷。词表留空而不是手抄一份 13 个字段名或
  // 7 条轴——离线时这一屏不显示选择维度，而不是把服务可能拒绝的词画成可选项。清单同理：
  // profiles 为空表示没问到，两个直方图为空表示一个状态都没数过；measured_fields 留成 0 是
  // 页面替服务说"实测过 0 项"，所以它写 0，由未连接标记说明这个 0 是"没问到"不是"数过"。
  targetProfileAxes: {
    schemaVersion: "design-lab/target-profile-axes/v1",
    capability_fields: [],
    axes: [],
    provenance_kinds: [],
    field_states: [],
    support_states: [],
    entry_kinds: [],
    validate_dimensions: [],
    verdicts: [],
    software: [],
    task_modes: [],
    measured_fields: 0,
    measured_note: "",
    executable: false
  },
  targetProfiles: {
    schemaVersion: "design-lab/target-profile-list/v1",
    total: 0,
    offset: 0,
    limit: 100,
    profiles: [],
    support_histogram: {},
    provenance_histogram: {},
    executable: false
  },
  // 提示词反推需要一条真实存在的图像资产，所以资产清单也走同一只读接缝：没有读到
  // assets 时说未读回，而不是"这个项目没有素材"。
  assets: { assets: [] },
  // 方案参考选择器读的三份项目内清单。空在这里只表示"没读到"，不表示"这个工作区没有
  // brief / 方向 / 提示词结果"——那句只有服务能回答，由 shapeNotice 写出来的缺字段说明负责。
  briefs: { briefs: [], next_cursor: null },
  directions: { directions: [], next_cursor: null },
  promptResults: { results: [] },
  designLayer: {
    design_layer: {
      briefs: [],
      directions: [],
      chosen_direction: null,
      bindings: [],
      active_binding: null,
      design_systems: []
    }
  },
  // 模型目录的诚实空载荷：两份清单都空、计数为零（零在这里表示"没有问到"，由上面的
  // 未连接标记说明），selection 的两个词位留空而不写服务端的值——离线时把
  // NOT_CONNECTED 或 USER_CHOSEN_NOT_LOCKED 画在屏上，就是页面在替服务说话。
  models: {
    schemaVersion: "design-lab/model-catalog/v1",
    observed_at: null,
    sources: {},
    hardware: {},
    policy: {},
    counts: {
      models: 0,
      endpoints: 0,
      qualified_local: 0,
      default_enabled_true: 0,
      weights_recorded: 0,
      weights_unstated: 0,
      weights_registered_none: 0,
      placement: {}
    },
    models: [],
    endpoints: [],
    join: { key: null, reason: "" },
    selection: { mode: "", rules: [], transport: "", executed: false },
    claims_not_made: []
  },
  environment: {
    schemaVersion: "v1",
    status: "OFFLINE",
    project_root: "—",
    project_local_root: ".project-local",
    sources: {},
    roots: {},
    shared_inputs: {},
    agent_profile: { status: "DISABLED", writable: false },
    write_trace: "NONE",
    migration: "NONE"
  }
};
const ROUTE_VIEWS = [
  // 设计辅助：拿到一个目标、看清它、找到参考与方法。
  { hash: "", view: "workbench", label: "工作台", entry: "设计辅助" },
  // DL-KB-08：日常入口本身。初始屏只露需求、参考附件与输出类型；结果是服务里的一条方案记录，
  // 四态（已保存／方案已提供／用户选用／外部未验证）由读回计算，页面不替服务下结论。
  { hash: "#/assistant", view: "assistant", label: "设计辅助", entry: "设计辅助" },
  { hash: "#/dashboard", view: "dashboard", label: "仪表盘", entry: "设计辅助" },
  { hash: "#/intake", view: "intake", label: "输入与目标", entry: "设计辅助" },
  { hash: "#/analysis", view: "analysis", label: "分析与方案", entry: "设计辅助" },
  { hash: "#/prompts", view: "prompt-intelligence", label: "提示词工程", entry: "设计辅助" },
  { hash: "#/research", view: "research", label: "研究洞察", entry: "设计辅助" },
  { hash: "#/capabilities", view: "capabilities", label: "能力目录", entry: "设计辅助" },
  { hash: "#/domains", view: "design-domains", label: "设计领域", entry: "设计辅助" },
  { hash: "#/brand-systems", view: "brand-systems", label: "品牌系统", entry: "设计辅助" },
  { hash: "#/tools", view: "creative-tools", label: "创作工具", entry: "设计辅助" },
  // 知识与提示词库：搜索是这一屏的主视觉，条目在服务里真实写入、修订与读回。
  { hash: "#/knowledge", view: "knowledge", label: "知识与提示词库", entry: "知识与提示词库" },
  // 我的方案：从项目到交付与证据，找回工作也在这里。
  { hash: "#/projects", view: "projects", label: "项目", entry: "我的方案" },
  { hash: "#/plan", view: "plan", label: "目标生成包", entry: "我的方案" },
  // R2 §2 把「制作记录与待继续」放在方案入口下：它是找回工作的入口，不是成果面。
  { hash: "#/records", view: "records", label: "制作记录与待继续", entry: "我的方案" },
  { hash: "#/deliverables", view: "deliverables", label: "交付中心", entry: "我的方案" },
  { hash: "#/evidence", view: "evidence", label: "证据系统", entry: "我的方案" },
  { hash: "#/preflight", view: "preflight-qa", label: "预检 / QA", entry: "我的方案" },
  // 设置与诊断：只收模型服务、目标工具档案、导入更新、备份与诊断。
  { hash: "#/settings", view: "settings", label: "系统设置", entry: "设置与诊断" },
  // 模型候选的唯一可读回来源是 GET /api/capabilities 里 kind='model' 的那批记录（其
  // sources.radar 指向 design-lab/readiness/model-radar.json）。这里不加任何模型名或族名：
  // 手抄一份雷达就是这个仓库反复gate掉的第二台账。
  { hash: "#/models", view: "model-selection", label: "模型选择", entry: "设置与诊断" },
  // DL-KB-10 屏幕三：目标组合选择面板。它读的是 DL-KB-09 刚上线的五个 /api/target-profile*
  // 路由。放在「模型选择」旁边而不是合并进去，是因为 08 line 9 那句「方案助手模型是另一种
  // 配置，不混进同一菜单」——两个菜单各管一件事：一处配助手模型，一处选外部制作目标。
  { hash: "#/target-profiles", view: "target-profiles", label: "目标组合", entry: "设置与诊断" },
  // owner 2026-10-28「取消冻结的自动化任务」「前端也同步上去自动化的菜单导航等」。次级入口，
  // 不加进画板钉住的那三个日常项；屏上只有读回，没有任何启动动作。
  { hash: "#/automation", view: "automation-connectors", label: "自动化连接器", entry: "设置与诊断" },
  { hash: "#/collaboration", view: "collaboration", label: "团队协作", entry: "设置与诊断" },
  { hash: "#/states", view: "ui-states", label: "界面状态", entry: "设置与诊断" },
  { hash: "#/components", view: "ui-components", label: "组件规范", entry: "设置与诊断" }
];
const NAV_DAILY_VIEWS = ["assistant", "knowledge", "projects", "settings"];
function viewLabel(view) {
  return ROUTE_VIEWS.find((route) => route.view === view)?.label ?? view;
}
const DETAIL_NAV_OWNER = {
  "project-detail": "projects",
  "capability-detail": "capabilities",
  "domain-detail": "design-domains"
};
function searchGroupRows(path, data) {
  switch (path) {
    case "/capabilities":
      return (data?.capabilities ?? []).map((c) => ({
        name: c.id,
        kind: `${c.kind}${c.license ? ` · ${c.license}` : ""}`,
        go: capabilityDetailHash(c.id)
      }));
    case "/projects":
      return (data?.projects ?? []).map((p) => ({
        name: p.name,
        kind: `项目 ${p.id.slice(0, 8)}`,
        go: projectDetailHash(p.id)
      }));
    case "/domains":
      return (data?.packs ?? []).map((k) => ({
        name: k.displayName ?? k.directory,
        kind: `领域 ${k.domain ?? "未声明"} · ${k.packId ?? k.directory}`,
        go: domainDetailHash(k.packId) ?? "#/domains"
      }));
    case "/design-systems":
      return (data?.design_systems ?? []).map((s) => ({
        name: s.name,
        kind: `设计系统${s.version ? ` v${s.version}` : ""}`,
        go: "#/brand-systems"
      }));
    default:
      return [];
  }
}
const VIEW_NOT_OPEN = {
  // 'research' left this table on 2026-10-08: GET/POST /api/projects/{id}/research is dispatched
  // by src/design_lab/http_service.py and renderResearch reads it back. A slot that has a route
  // may not keep a "no route" notice -- design-lab/scripts/verify_capability_self_description.py
  // now refuses the pair.
  "collaboration": "团队协作页未开放：本地单机服务尚无协作路由（本地单用户模型）。"
};
const CAPABILITY_REGISTRY = [
  {
    capabilityId: "research-insights",
    domain: "研究洞察",
    source: "IA 槽位 #/research",
    owner: "DESIGN-LAB design core",
    route: "GET /api/projects/{id}/research",
    slot: "research",
    contractRef: "design-lab/schemas/research-finding.schema.json · design-lab/schemas/state/design-lab-state-research-v1.sql · src/design_lab/assurance/research_store.py · src/design_lab/research_review.py",
    implementationState: "IMPLEMENTED",
    permission: "brief/reference 已持久化（/api/projects/{id}/assets 已有）",
    reason: "读回路由已落地：本项目已持久化的研究结论、来源覆盖与置信度分布由该路由给出，空读回说成空读回而不是 0 条判定。仍未闭合的是结论本身的验收——一条研究结论不证明设计质量，也不是知识导出，页面与服务端都不给完成词。",
    nextAction: "按 E2+ 用真实 brief 走一遍「采集→落库→读回→取代」，并把结论送入既有的 Direction/Quality 门；UI 读回无需再改。"
  },
  {
    capabilityId: "design-domain-model",
    domain: "设计领域",
    source: "IA 槽位 #/domains",
    owner: "DESIGN-LAB Domain Pack",
    route: "GET /api/domains",
    contractRef: "design-lab/schemas/domain-pack.schema.json · design-lab/domain-packs/DOMAIN_PACK_SPEC_V2.md · design-lab/scripts/verify_domain_pack_v2.py · src/design_lab/domain_packs.py",
    implementationState: "IMPLEMENTED",
    permission: "域包目录与 manifest 为仓内已提交记录（E1 结构级）；本视图只读回，不安装、不生成、不判定设计质量",
    reason: "读回路由已落地：页面列出 design-lab/domain-packs 下真实存在的目录，并逐包给出仓内校验器自己的判定与原因。仍未闭合的是能力验收本身——仍有目录声明 workflow/domain-pack/v1 而被 Spec V2 校验器拒绝，具体数量与目录名由路由给出，不在 UI 侧写死。",
    nextAction: "把仍处 v1 的域包补齐到 Spec V2 十要素，并按 E2+ 做宿主与设计质量验收；UI 读回无需再改。"
  },
  {
    capabilityId: "host-adapter-live",
    domain: "创作工具（宿主实时状态）",
    source: "IA 槽位 #/tools",
    owner: "Host/Tool Adapter 层",
    route: "GET /api/projects/{id}/tasks（已有）+ 宿主探测路由（缺）",
    contractRef: "src/design_lab/native_assets.py Bundles；宿主 adapter 合同",
    implementationState: "BLOCKED",
    permission: "宿主（Illustrator/Photoshop 等）需以官方插件/CLI/MCP 形态接入；UI 只读回，不触发实操",
    reason: "后端尚无宿主在线探测路由；任务台账可读回，但宿主是否在线/可执行只能 UNKNOWN。",
    nextAction: "在 adapter 层增加宿主探测读回路由（官方接入后），UI 替换 UNKNOWN 占位。"
  },
  {
    capabilityId: "mcp-diagnostics",
    domain: "MCP 诊断",
    source: "任务包 2026-09-30（新增）",
    owner: "MCP 工具层",
    route: "GET /api/mcp/…（缺）",
    contractRef: "无现有 MCP 后端路由",
    implementationState: "BLOCKED",
    permission: "需本机 MCP 运行时 + 服务路由",
    reason: "当前后端不暴露 MCP 状态；不安装、不假报可用。",
    nextAction: "后端提供 MCP 读回路由后 UI 接入；在此之前 UI 只标注 BLOCKED。"
  },
  {
    capabilityId: "collaboration",
    domain: "团队协作",
    source: "IA 槽位 #/collaboration",
    owner: "（超出当前范围）",
    route: "无（单用户模型）",
    contractRef: "AGENTS.md：本地单用户服务，无协作路由",
    implementationState: "PLANNED",
    permission: "需要多用户/权限模型先立项",
    reason: "本地单用户模型；协作是后续独立立项，不做假入口。",
    nextAction: "立项协作模型后再评估路由与页面。"
  }
];
function capabilityCard(c) {
  return el(
    "div",
    { class: "panel capability-card", dataset: { capability: c.capabilityId } },
    el(
      "div",
      {},
      el("h3", {}, c.domain),
      el(
        "div",
        { class: "status-stack" },
        // style.css establishes `.tag.neutral` for exactly this: a non-verdict must not
        // borrow the weight of a verdict. PLANNED says "no answer yet", so it gets the
        // outline pill the dashboard blueprint cards already use -- and IMPLEMENTED,
        // which this call site would otherwise have painted the same `info` blue, is a
        // real verdict and gets the affirmative one.
        el(
          "span",
          { class: "tag " + (c.implementationState === "BLOCKED" ? "warn" : c.implementationState === "IMPLEMENTED" ? "ok" : "neutral") },
          en(c.implementationState)
        )
      )
    ),
    el("p", { class: "muted" }, c.reason),
    el(
      "details",
      { class: "advanced" },
      el("summary", {}, "接入明细"),
      el(
        "div",
        { class: "advanced-body" },
        el("p", { class: "view-hint" }, `状态来源：${c.source}`),
        el("p", { class: "view-hint" }, `所需条件：${c.permission}`),
        el("p", { class: "view-hint" }, `工程落点：${c.route}（${c.contractRef}）`),
        el("p", { class: "view-hint" }, `下一动作：${c.nextAction}`)
      )
    )
  );
}
function buildVersionRing(versions) {
  if (versions.length <= 1) return null;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "version-ring");
  svg.setAttribute("viewBox", "0 0 120 120");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `方向版本环：${versions.length} 个版本`);
  const cx = 60, cy = 60, r = 46;
  const orbit = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  orbit.setAttribute("class", "version-ring-orbit");
  orbit.setAttribute("cx", String(cx));
  orbit.setAttribute("cy", String(cy));
  orbit.setAttribute("r", String(r));
  orbit.setAttribute("fill", "none");
  svg.append(orbit);
  versions.forEach((v, i) => {
    const n = Math.max(versions.length, 1);
    const angle = i / n * Math.PI * 2 - Math.PI / 2;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    const node = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    node.setAttribute("class", "version-ring-node" + (v.chosen ? " is-chosen" : ""));
    node.setAttribute("cx", x.toFixed(2));
    node.setAttribute("cy", y.toFixed(2));
    node.setAttribute("r", v.chosen ? "6" : "4");
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `v${v.version}` + (v.chosen ? "（选定）" : "") + (v.superseded_by ? " · 已被取代" : "");
    node.append(title);
    svg.append(node);
  });
  return svg;
}
function sharedInputRows(response, limit = 4) {
  const entries = Object.entries(response.shared_inputs).slice(0, limit);
  if (!entries.length) return [emptyLi(response, "尚无外置输入", "服务未返回 shared_inputs")];
  return entries.map(([name, input]) => el(
    "li",
    { class: "list-item" },
    el("div", {}, el("strong", {}, name), el("small", {}, input.path)),
    el("span", {
      class: input.status === "MISSING" ? "tag bad" : input.status === "DECLARED_NOT_PROBED" ? "tag warn" : "tag ok"
    }, en(input.status))
  ));
}
function kpiCard(value, label, note, trend) {
  const unread = !token && value === "0";
  const shown = unread ? "—" : value;
  const isText = !/^\d[\d,]*(?:\.\d+)?$/.test(shown);
  const children = [
    el("strong", { dataset: { count: shown }, class: isText ? "is-text" : null }, shown),
    el("small", {}, label)
  ];
  const trendText = unread ? "未读回：未连接本机设计服务" : note;
  if (trendText) children.push(el("div", { class: "trend" }, trendText));
  return el("div", { class: "panel kpi" }, ...children);
}
function animateKpiCount(el2) {
  const raw = el2.dataset.count;
  if (raw === void 0) return;
  if (!/^\d+(\.\d+)?$/.test(raw)) return;
  const target = parseFloat(raw);
  if (Number.isNaN(target)) return;
  if (typeof performance === "undefined" || typeof requestAnimationFrame !== "function") return;
  if (globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const suffix = el2.dataset.suffix ?? "";
  const decimals = raw.includes(".") ? raw.split(".")[1].length : 0;
  const duration = 850;
  const start = performance.now();
  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    el2.textContent = (target * eased).toFixed(decimals) + suffix;
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
function stateMachineStepper() {
  const stages = ["brief", "research", "designing", "review", "qa", "approved", "delivered", "archived"];
  const ol = el("ol", { class: "state-machine", "aria-label": "设计域状态机（契约可视化，不代表项目进度）" });
  for (const stage of stages) ol.append(el("li", { class: "state-machine-step", dataset: { state: stage } }, en(stage)));
  return ol;
}
const FAILED_STATES = /* @__PURE__ */ new Set(["FAILED", "TIMED_OUT", "CANCELLED"]);
const HUMAN_STATES = /* @__PURE__ */ new Set(["OUTCOME_UNKNOWN", "CANCEL_REQUESTED", "RECONCILING"]);
const IN_FLIGHT_STATES = /* @__PURE__ */ new Set(["PENDING", "RUNNING"]);
function taskTriage(state) {
  if (FAILED_STATES.has(state)) return "failed";
  if (HUMAN_STATES.has(state)) return "needs_human";
  if (IN_FLIGHT_STATES.has(state)) return "in_flight";
  if (state === "RECEIPTED") return "done";
  return "unknown";
}
const RECENT_KEY = "design-lab.recent-projects";
const RECENT_MAX = 8;
function recentProjectIds() {
  try {
    const raw = globalThis.localStorage?.getItem(RECENT_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v) => typeof v === "string").slice(0, RECENT_MAX) : [];
  } catch {
    return [];
  }
}
function rememberProject(id) {
  if (!id) return;
  try {
    const next = [id, ...recentProjectIds().filter((v) => v !== id)].slice(0, RECENT_MAX);
    globalThis.localStorage?.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
  }
}
const PLAN_FILTER_KEY = "design-lab.assistant-plan-filters";
function readPlanFilters() {
  const fallback = { text: "", outputType: "all", state: "all" };
  try {
    const raw = globalThis.localStorage?.getItem(PLAN_FILTER_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return fallback;
    const row = parsed;
    return {
      text: typeof row.text === "string" ? row.text.slice(0, 200) : "",
      outputType: typeof row.output_type === "string" ? row.output_type.slice(0, 40) : "all",
      state: typeof row.state === "string" ? row.state.slice(0, 20) : "all"
    };
  } catch {
    return fallback;
  }
}
function writePlanFilters(seed) {
  try {
    globalThis.localStorage?.setItem(PLAN_FILTER_KEY, JSON.stringify(
      { text: seed.text, output_type: seed.outputType, state: seed.state }
    ));
  } catch {
  }
}
async function renderDashboard(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回服务状态…"));
  const [health, projects2, systems, environment] = await Promise.all([
    apiOrEmpty("/health", OFFLINE.health),
    apiOrEmpty("/projects", OFFLINE.projects),
    apiOrEmpty("/design-systems", OFFLINE.designSystems),
    apiOrEmpty("/environment", OFFLINE.environment)
  ]);
  const probeIds = projects2.projects.slice(0, 6).map((p) => p.id);
  const probes = await Promise.all(probeIds.map(async (pid) => {
    const taskResult = { res: null, err: null };
    const bundleResult = { res: null, err: null };
    try {
      taskResult.res = await api(`/projects/${pid}/tasks`);
    } catch (e) {
      taskResult.err = e;
    }
    try {
      bundleResult.res = await api(`/projects/${pid}/bundles`);
    } catch (e) {
      bundleResult.err = e;
    }
    return { pid, taskResult, bundleResult };
  }));
  const readable = probes.filter((p) => p.taskResult.res !== null).length;
  const triageRows = probes.flatMap((p) => (p.taskResult.res?.tasks ?? []).map((t) => {
    const byAttempt = taskTriage(t.attempt.state);
    return {
      project: projects2.projects.find((x) => x.id === p.pid)?.name ?? p.pid,
      kind: t.kind,
      state: t.state,
      attempt: t.attempt.state,
      bucket: byAttempt !== "unknown" ? byAttempt : taskTriage(t.state),
      pid: p.pid
    };
  }));
  const bundlesReadable = probes.filter((p) => p.bundleResult.res !== null).length;
  const activeProductionRows = triageRows.filter((r) => r.bucket === "in_flight");
  const allBundles = probes.flatMap(
    (p) => (p.bundleResult.res?.bundles ?? []).map((b) => ({
      ...b,
      project: projects2.projects.find((x) => x.id === p.pid)?.name ?? p.pid,
      pid: p.pid
    }))
  );
  const bundleHeading = !probes.length ? "交付包（台账无项目可读）" : bundlesReadable === probes.length ? `交付包（${allBundles.length}）` : `交付包（未读回 ${probes.length - bundlesReadable}/${probes.length} 项目）`;
  const sysCount = systems.design_systems.length;
  const projCount = projects2.projects.length;
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "仪表盘"),
      el("p", {}, "项目、品牌、预检与交付已可读回；研究、设计领域、协作尚未开放（见能力登记表）。")
    ),
    el(
      "div",
      { class: "page-actions" },
      el("button", {
        type: "button",
        class: "primary-btn",
        onclick: () => {
          window.location.hash = "";
        }
      }, "+ 新建项目")
    )
  );
  const grid = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(projCount), "项目", "服务端项目台账读回，非统计猜测"),
    kpiCard(String(sysCount), "设计系统", "资源登记的设计系统总数 · 服务端目录读回"),
    kpiCard(health.status, "服务状态", `版本 ${health.version} · 作用域 ${health.scope}`),
    kpiCard(health.version, "服务版本", "服务自检读回")
  );
  for (const v of grid.querySelectorAll("strong[data-count]")) {
    const text = v.textContent;
    if (text !== null && /^\d+$/.test(text)) v.dataset.count = text;
  }
  const systemsList = el(
    "ul",
    { class: "items-chips", "data-view-item": "brand" },
    ...systems.design_systems.map((system) => el(
      "li",
      {},
      `${system.name} · ${system.title} · v${system.version} · 证据 ${system.evidence_level}`
    ))
  );
  const recent = [...projects2.projects].sort((a, b) => {
    const rank = recentProjectIds();
    const ra = rank.indexOf(a.id);
    const rb = rank.indexOf(b.id);
    return (ra < 0 ? Number.MAX_SAFE_INTEGER : ra) - (rb < 0 ? Number.MAX_SAFE_INTEGER : rb);
  }).slice(0, 6);
  const recentIds = recentProjectIds();
  const recentPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "最近项目"),
    el(
      "ul",
      { class: "list" },
      ...recent.length ? recent.map((p) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, p.name),
          el("small", {}, p.id)
        ),
        el("span", { class: "tag info" }, recentIds.includes(p.id) ? "最近打开" : "已登记")
      )) : [emptyLi(projects2, "尚无项目", "在工作台新建项目后读回此处")]
    ),
    el("p", { class: "view-hint" }, recentIds.length ? "按本机最近打开的项目排序（仅保存项目 id 于本机，不上传）。" : "本机尚未记录打开过的项目，暂按服务返回顺序显示。")
  );
  const trendPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "设计质量趋势 · 未读回"),
    el("p", { class: "view-hint" }, "无质量读回路由（见能力登记表 quality / Human Jury）；不以演示序列充当评分。")
  );
  const researchCard = CAPABILITY_REGISTRY.find((c) => c.capabilityId === "research-insights");
  const deliveryCard = CAPABILITY_REGISTRY.find((c) => c.capabilityId === "design-domain-model");
  const modulePanels = el(
    "div",
    { class: "three-col spaced-top" },
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "Research"),
      el("div", { class: "muted" }, "研究洞察模块：真实读回待接入，未接入前显式 UNKNOWN。")
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "Brand"),
      el("div", { class: "muted" }, `品牌系统：目录登记 ${sysCount} 个设计系统（服务端目录读回，全局目录而非本项目状态）。`)
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "Delivery"),
      el("div", { class: "muted" }, "交付中心：按任务读回，未打包不宣称交付完成。")
    )
  );
  const blueprintCards = el(
    "div",
    { class: "three-col spaced-top" },
    ...researchCard ? [capabilityCard(researchCard)] : [],
    ...deliveryCard ? [capabilityCard(deliveryCard)] : [],
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "协作"),
      el(
        "div",
        { class: "status-stack" },
        el("span", { class: "tag neutral" }, en("PLANNED")),
        el("small", {}, "本地单用户模型，无协作路由")
      ),
      el("p", { class: "view-hint" }, "协作是后续独立立项；不建假入口，标签保持 feature-gated。")
    )
  );
  const triagePanel = (bucket, title, emptyText) => {
    const rows = triageRows.filter((r) => r.bucket === bucket);
    const body = readable === 0 ? el("ul", { class: "list" }, el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "未读回"),
        el("small", {}, "服务不可达或未连接；此处不显示 0，避免把「没读到」说成「没有」。")
      )
    )) : el(
      "ul",
      { class: "list" },
      ...rows.length ? rows.map((r) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `${r.project} · ${r.kind}`),
          el("small", {}, `attempt.state=${r.attempt} · job.state=${r.state}`)
        ),
        el("span", { class: bucket === "failed" ? "tag bad" : "tag warn" }, r.attempt)
      )) : [el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, emptyText),
          el("small", {}, `已读回 ${readable}/${probeIds.length} 个项目的任务`)
        )
      )]
    );
    return el("div", { class: "panel" }, el("h3", {}, readable === 0 ? title : `${title}（${rows.length}）`), body);
  };
  const continueId = recentProjectIds()[0];
  const continueProj = continueId ? projects2.projects.find((p) => p.id === continueId) : void 0;
  const continuePanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "继续项目"),
    el("ul", { class: "list" }, continueProj ? el(
      "li",
      { class: "list-item" },
      el("div", {}, el("strong", {}, continueProj.name), el("small", {}, `本机最近打开 · ${continueProj.id}`)),
      el(
        "div",
        { class: "actions" },
        el("button", {
          type: "button",
          class: "primary-btn",
          id: "pd-continue",
          onclick: () => {
            window.location.hash = `#/projects/${encodeURIComponent(continueProj.id)}`;
          }
        }, "继续")
      )
    ) : el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "尚无「继续项目」"),
        el("small", {}, "在本机打开过某个项目后，这里会显示最近打开的那一个。")
      )
    ))
  );
  target.replaceChildren(
    pageHead,
    grid,
    el("div", { class: "two-col spaced-top" }, recentPanel, trendPanel),
    modulePanels,
    // Pack 01_RESEARCH_AND_PRODUCT §101: the home page should offer 「继续项目」. It is
    // derived from the SAME local recency record the 最近项目 panel uses (project ids only,
    // kept on this machine, never uploaded), and it is honest when there is nothing to
    // continue rather than pointing at an arbitrary project.
    continuePanel,
    el(
      "div",
      { class: "two-col spaced-top" },
      triagePanel("needs_human", "待审（需人工处理）", "无待审任务"),
      triagePanel("failed", "失败", "无失败任务")
    ),
    ...shapeNoticeRows(environment, health, projects2, systems)
  ), // 2026-09-30 — 活跃生产 + 最近交付 + Host/Capability 状态 + Quick Launch。
  // 全部来自真实读回：活跃生产 = in_flight triage；最近交付 = /bundles 读回；
  // Host 状态 = /environment shared_inputs + 能力登记表（诚实 UNKNOWN 占位，
  // 不做假探测）；Quick Launch = 跳转各视图的一行直达。
  el(
    "div",
    { class: "two-col spaced-top" },
    el(
      "div",
      { class: "panel" },
      el("h3", {}, `活跃生产（${activeProductionRows.length}）`),
      el(
        "ul",
        { class: "list" },
        ...activeProductionRows.length ? activeProductionRows.map((r) => el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, `${r.project} · ${r.kind}`),
            el("small", {}, `job.state=${r.state} · attempt=${r.attempt}`)
          ),
          // PENDING has not started (job_store requires PENDING -> RUNNING
          // before adapter dispatch), so the pill carries the real state
          // instead of claiming 运行中 for both.
          el("span", { class: "tag warn" }, r.attempt)
        )) : [el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, readable === 0 ? "未读回" : "无运行中任务"),
            el("small", {}, readable === 0 ? "服务不可达或未连接；此处不显示 0，避免把「没读到」说成「没有」。" : "运行中任务为 PENDING / RUNNING 状态（服务侧作业状态词表）。")
          )
        )]
      ),
      el(
        "div",
        { class: "panel" },
        el("h3", {}, bundleHeading),
        el(
          "ul",
          { class: "list" },
          ...allBundles.length ? allBundles.slice(0, 8).map((b) => el(
            "li",
            { class: "list-item" },
            el(
              "div",
              {},
              el("strong", {}, `${b.project} · 交付包 v${b.version_no}`),
              el("small", {}, `${b.id} · ${b.byte_size} 字节 · ${b.rights}`)
            ),
            el(
              "span",
              { class: b.rights === "NOT_REVIEWED" ? "tag warn" : "tag info" },
              b.rights === "NOT_REVIEWED" ? "权利未审查" : b.rights
            )
          )) : [emptyLi(projects2, "尚无交付包", "任务完成并打包后，交付会在此读回。")]
        )
      )
    ),
    el(
      "div",
      { class: "panel spaced-top" },
      el("h3", {}, "Host / Capability 状态"),
      el(
        "div",
        { class: "three-col" },
        el(
          "div",
          { class: "panel" },
          el("h3", {}, "宿主读回"),
          el(
            "ul",
            { class: "list" },
            ...TOOL_ADAPTERS.map((a) => el(
              "li",
              { class: "list-item" },
              el(
                "div",
                {},
                el("strong", {}, a.name),
                el("small", {}, a.path)
              ),
              el("span", { class: "tag neutral" }, en("UNKNOWN"))
            ))
          ),
          el("p", { class: "view-hint" }, "宿主在线状态尚未有服务路由；此处 UNKNOWN，不假报可用。")
        ),
        el(
          "div",
          { class: "panel" },
          el("h3", {}, "共享输入"),
          el("ul", { class: "list" }, ...sharedInputRows(environment)),
          el("p", { class: "view-hint" }, "服务端环境读回；写权限与状态由服务裁定。")
        ),
        el(
          "div",
          { class: "panel" },
          el("h3", {}, "未来能力"),
          el(
            "ul",
            { class: "list" },
            ...CAPABILITY_REGISTRY.slice(0, 4).map((c) => el(
              "li",
              { class: "list-item" },
              el(
                "div",
                {},
                el("strong", {}, c.domain),
                el("small", {}, c.contractRef)
              ),
              el(
                "span",
                { class: c.implementationState === "BLOCKED" ? "tag warn" : "tag info" },
                c.implementationState
              )
            ))
          )
        )
      ),
      el(
        "div",
        { class: "panel quick-launch spaced-top" },
        el("h3", {}, "Quick Launch"),
        el(
          "ul",
          { class: "list" },
          el(
            "li",
            { class: "list-item" },
            el("div", {}, el("strong", {}, "新建项目"), el("small", {}, "进入工作台创建项目")),
            el(
              "div",
              { class: "actions" },
              el("button", {
                type: "button",
                class: "ghost-btn",
                onclick: () => {
                  window.location.hash = "";
                }
              }, "工作台")
            )
          ),
          el(
            "li",
            { class: "list-item" },
            el("div", {}, el("strong", {}, "项目列表"), el("small", {}, "全部项目一览")),
            el(
              "div",
              { class: "actions" },
              el("button", {
                type: "button",
                class: "ghost-btn",
                onclick: () => {
                  window.location.hash = "#/projects";
                }
              }, "项目")
            )
          ),
          el(
            "li",
            { class: "list-item" },
            el("div", {}, el("strong", {}, "创作工具"), el("small", {}, "宿主任务读回")),
            el(
              "div",
              { class: "actions" },
              el("button", {
                type: "button",
                class: "ghost-btn",
                onclick: () => {
                  window.location.hash = "#/tools";
                }
              }, "创作工具")
            )
          ),
          el(
            "li",
            { class: "list-item" },
            el("div", {}, el("strong", {}, "预检 / QA"), el("small", {}, "任务资源预检")),
            el(
              "div",
              { class: "actions" },
              el("button", {
                type: "button",
                class: "ghost-btn",
                onclick: () => {
                  window.location.hash = "#/preflight";
                }
              }, "预检")
            )
          )
        )
      )
    ),
    el(
      "p",
      { class: "view-hint" },
      `待审 / 失败按各项目任务的实际执行轮次状态判定（服务侧词表：TERMINAL={RECEIPTED, FAILED, TIMED_OUT, CANCELLED}）。OUTCOME_UNKNOWN 是「结果未知」，计入待审而不计入失败。本轮最多读回 ${probeIds.length} 个项目的任务。`
    ),
    el("p", { class: "eyebrow" }, "设计系统登记"),
    systemsList,
    el("p", { class: "eyebrow" }, "设计域状态机（UI 参考稿 B10/B07 · 非服务状态，未读回）"),
    blueprintCards,
    stateMachineStepper()
  );
  target.querySelectorAll("strong[data-count]").forEach((k) => animateKpiCount(k));
}
const BRAND_MODULES = ["Logo", "Color", "Typography", "Icon", "Graphic Language", "Templates", "Applications", "Assets"];
async function renderBrandSystems(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回设计系统…"));
  const systems = await apiOrEmpty("/design-systems", OFFLINE.designSystems);
  const sysCount = systems.design_systems.length;
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "品牌系统"),
      el("p", {}, "延续锁定的高级、发光、动感产品表达。模块为视觉占位；资产与版本由服务端目录读回。")
    ),
    el("div", { class: "page-actions" })
  );
  const kpis = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(sysCount), "设计系统", "资源登记总数 · 服务端目录读回"),
    // A frontend constant counted into a KPI is a number the service never read
    // back, however honest the caption. It reads as unmeasured until there is a
    // brand-module store behind it.
    kpiCard("—", "VI 模块", "无服务端读回 · 下方为设计参考模块名,非资产统计"),
    kpiCard("—", "活跃绑定", "绑定在工作台 DESIGN LAYER 执行")
  );
  const moduleGrid = el(
    "div",
    { class: "three-col" },
    ...BRAND_MODULES.map((name) => el(
      "div",
      { class: "panel", dataset: { module: name } },
      el("h3", {}, name),
      el("p", { class: "muted" }, "视觉占位 · 资产与版本由服务端目录读回"),
      el("span", { class: "tag info" }, "VI 模块")
    ))
  );
  const systemsList = el(
    "div",
    { class: "panel" },
    el("h3", {}, `设计系统登记（${sysCount}）`),
    el(
      "ul",
      { class: "list" },
      ...systems.design_systems.length ? systems.design_systems.map((system) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `${system.name} · ${system.title}`),
          el("small", {}, `v${system.version} · 证据 ${system.evidence_level}`)
        ),
        el("span", { class: "tag info" }, system.version)
      )) : [
        emptyLi(systems, "尚无登记设计系统", "在工作台 DESIGN LAYER 绑定后读回此处")
      ]
    )
  );
  target.replaceChildren(
    pageHead,
    kpis,
    moduleGrid,
    systemsList,
    el("p", { class: "view-hint" }, "绑定到方向的操作在工作台「05 / DESIGN LAYER」页执行；本页只读回，不修改。"),
    ...shapeNoticeRows(systems)
  );
}
const JURY_CRITERIA = [
  { criterion_id: "brief-fit", weight: 0.25 },
  { criterion_id: "composition", weight: 0.25 },
  { criterion_id: "typography", weight: 0.2 },
  { criterion_id: "brand-system", weight: 0.15 },
  { criterion_id: "production", weight: 0.15 }
];
function juryCriteriaWith(assessments) {
  return JURY_CRITERIA.map((axis, index) => ({
    criterion_id: axis.criterion_id,
    weight: axis.weight,
    note: assessments[index]?.note ?? "",
    score: assessments[index]?.score ?? 0
  }));
}
const JURY_UNREADABLE = {
  schemaVersion: "design-lab/jury-readback/v1",
  records: [],
  verdict_count: 0,
  proposal_count: 0,
  current_verdicts: {},
  reviewable_versions: [],
  human_acceptance: "UNKNOWN"
};
function acceptanceFraction(data) {
  const accepted = data.accepted_versions;
  const total = data.reviewable_active_versions;
  if (typeof accepted !== "number" || typeof total !== "number") return "未读回";
  return `${accepted}/${total}`;
}
async function renderJuryReview(host) {
  host.replaceChildren(el("p", { class: "view-loading" }, "正在读回评审记录…"));
  const projects2 = await apiOrEmpty("/projects", OFFLINE.projects);
  const projectShape = shapeNotice(projects2);
  if (projectShape) {
    host.replaceChildren(el(
      "p",
      { class: "error" },
      `评审项目清单未读回：${projectShape}`
    ));
    return;
  }
  if (!projects2.projects.length) {
    host.replaceChildren(el(
      "p",
      { class: "view-hint" },
      "本机尚无项目：评审记录按项目保存，这里不能替某个项目宣称已验收。"
    ));
    return;
  }
  const picker = el("select", { class: "input", id: "jury-project" });
  for (const p of projects2.projects) picker.append(new Option(p.name, p.id));
  const load = async () => {
    const id = picker.value || projects2.projects[0].id;
    const data = await apiOrEmpty(`/projects/${id}/jury`, JURY_UNREADABLE);
    const shape = shapeNotice(data);
    body.replaceChildren(juryReadbackPanel(id, data, load, shape));
  };
  const body = el("div", { class: "jury-body" });
  picker.onchange = () => {
    void load().catch((error) => setStatus(errMsg(error), true));
  };
  host.replaceChildren(el("label", { class: "muted" }, "评审项目", picker), body);
  await load();
}
function juryReadbackPanel(projectId, data, reload, unread) {
  if (unread) {
    return el("div", {}, el(
      "p",
      { class: "error" },
      `评审读回不完整：${unread}。缺失字段不会被当作空集合或已验收。`
    ));
  }
  if (data.error) {
    return el(
      "p",
      { class: "error" },
      `评审未读回：${data.error}。未读回不等于无裁决，也不等于已验收。`
    );
  }
  const verdicts = Object.entries(data.current_verdicts ?? {});
  const list = el("ul", { class: "list" }, ...verdicts.length ? verdicts.map(([subject, record]) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, String(record["verdict"] ?? "未记录判定")),
      el("div", { class: "value-mono" }, subject),
      el("div", { class: "muted" }, String((record["juror"] ?? {}).attestation ?? "无评审依据"))
    )
  )) : [emptyLi(
    data,
    "尚无人签署的裁决",
    "Agent 建议不计入验收，人工签署是唯一改变此处的途径。"
  )]);
  const summary = el(
    "p",
    { class: "view-hint" },
    `已签署 ${data.verdict_count ?? 0} · Agent 建议 ${data.proposal_count ?? 0} · 人工验收 ` + (data.human_acceptance === "ACCEPTED" ? "已接受" : "未接受") + `（当前版本 ${acceptanceFraction(data)}）`
  );
  return el(
    "div",
    {},
    summary,
    list,
    juryVerdictForm(projectId, data.reviewable_versions ?? [], reload)
  );
}
const ACCEPTANCE_TAGS = { ACCEPTED: "ok", NOT_ACCEPTED: "warn" };
function evidenceJuryColumn(data) {
  const heading = el("h3", {}, "人工评审裁决 · Human Jury");
  const unread = shapeNotice(data) || disconnectedNotice(data);
  if (unread) {
    return el(
      "div",
      { class: "panel" },
      heading,
      el(
        "p",
        { class: "error" },
        `${unread}；裁决未读回。未读回不等于无裁决，也不等于已验收。`
      )
    );
  }
  const verdicts = Object.entries(data.current_verdicts ?? {});
  const list = el("ul", { class: "list" }, ...verdicts.length ? verdicts.map(([subject, record]) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, String(record["verdict"] ?? "未记录判定")),
      // subject_ref and the artifact digest are long identifiers: their own row in
      // .value-mono, never inside the nowrap .tag pill.
      el("div", { class: "value-mono" }, subject),
      el("div", { class: "muted" }, String((record["juror"] ?? {}).attestation ?? "无评审依据"))
    ),
    record["kind"] ? el("span", { class: "tag info" }, en(String(record["kind"]))) : ""
  )) : [emptyLi(
    data,
    "尚无人签署的裁决",
    "裁决需在预检 / QA 页由人签署后在此读回；Agent 建议不计入验收。"
  )]);
  const acceptance = typeof data.human_acceptance === "string" ? data.human_acceptance : "";
  const verdictCount = typeof data.verdict_count === "number" ? String(data.verdict_count) : "未读回";
  const proposalCount = typeof data.proposal_count === "number" ? String(data.proposal_count) : "未读回";
  return el(
    "div",
    { class: "panel" },
    heading,
    el(
      "p",
      { class: "view-hint" },
      `已签署 ${verdictCount} · Agent 建议 ${proposalCount} · 当前版本已接受 ${acceptanceFraction(data)}`
    ),
    el(
      "p",
      {},
      acceptance ? el(
        "span",
        { class: "tag " + (ACCEPTANCE_TAGS[acceptance] ?? "neutral") },
        en(acceptance)
      ) : el("span", { class: "tag neutral" }, "人工验收状态未读回"),
      el(
        "span",
        { class: "muted" },
        " · 人工验收是按项目当前版本算的，一条裁决不会替整个项目出证。"
      )
    ),
    list,
    el(
      "p",
      { class: "view-hint" },
      "本页只读回裁决，不签署、不改写：签署是 Human Gate，在预检 / QA 页执行。"
    )
  );
}
function juryVerdictForm(projectId, versions, reload) {
  const versionSelect = el("select", { class: "input", id: "jury-version" });
  versionSelect.append(new Option("选择被评审的版本", ""));
  for (const v of versions) {
    versionSelect.append(new Option(
      `${v.subject_ref} · ${v.artifact_sha256.slice(0, 12)}…`,
      v.subject_ref
    ));
  }
  const juror = el("input", {
    class: "input",
    id: "jury-juror",
    type: "text",
    placeholder: "评审人 id",
    autocomplete: "off"
  });
  const attestation = el("textarea", {
    class: "input",
    id: "jury-attestation",
    placeholder: "你在什么条件下看了这份产物（放大比例、屏幕、与参考的对比）"
  });
  const approve = el("input", {
    type: "radio",
    name: "jury-verdict",
    id: "jury-approve",
    value: "APPROVE"
  });
  const reject = el("input", {
    type: "radio",
    name: "jury-verdict",
    id: "jury-reject",
    value: "REJECT"
  });
  const evidence = el("textarea", {
    class: "input",
    id: "jury-evidence",
    placeholder: "拒绝时必填，一行一条依据"
  });
  const scores = JURY_CRITERIA.map((axis) => el("input", {
    class: "input",
    type: "number",
    id: `jury-score-${axis.criterion_id}`,
    min: "0",
    max: "5",
    step: "0.1",
    "aria-label": `${axis.criterion_id} 评分`
  }));
  const notes = JURY_CRITERIA.map((axis) => el("input", {
    class: "input",
    type: "text",
    id: `jury-note-${axis.criterion_id}`,
    placeholder: `${axis.criterion_id} 的评审说明`
  }));
  const outcome = el("p", { class: "view-hint", id: "jury-outcome" }, "");
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "jury-submit" },
    "签署裁决"
  );
  submit.onclick = () => {
    void (async () => {
      const chosen = versionSelect.value;
      const digest = versions.find((v) => v.subject_ref === chosen)?.artifact_sha256 ?? "";
      const verdict = approve.checked ? "APPROVE" : reject.checked ? "REJECT" : "";
      if (!chosen || !digest) {
        outcome.textContent = "未签署：必须先选择被评审的版本，裁决不能指向凭记忆写出的摘要。";
        return;
      }
      if (!verdict) {
        outcome.textContent = "未签署：不接受任何默认判定。";
        return;
      }
      const invalid = scores.findIndex((node) => node.value === "" || Number(node.value) < 0 || Number(node.value) > 5);
      if (invalid >= 0) {
        outcome.textContent = `未签署：${JURY_CRITERIA[invalid].criterion_id} 分值缺失或超出 0-5。`;
        return;
      }
      if (verdict === "REJECT" && !evidence.value.trim()) {
        outcome.textContent = "未签署：拒绝必须写明依据，否则无法复核或申诉。";
        return;
      }
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/jury/verdict`, {
          schemaVersion: "design-lab/assurance-jury-record/v2",
          kind: "JURY_VERDICT",
          jury_record_id: "jury-" + Math.random().toString(16).slice(2, 34),
          subject_ref: chosen,
          artifact_sha256: digest,
          juror: {
            juror_id: juror.value.trim(),
            kind: "HUMAN",
            members: [],
            attestation: attestation.value.trim()
          },
          criteria: juryCriteriaWith(scores.map((node, index) => ({
            score: Number(node.value),
            note: notes[index].value.trim()
          }))),
          verdict,
          decided_at: (/* @__PURE__ */ new Date()).toISOString().replace(/\.\d{3}Z$/, "Z"),
          supersedes: null,
          evidence_refs: evidence.value.split("\n").map((line) => line.trim()).filter(Boolean)
        });
        await reload();
        outcome.textContent = "已签署；下方列表为服务端读回。";
      } catch (error) {
        outcome.textContent = `未签署：${errMsg(error)}`;
      } finally {
        submit.disabled = false;
      }
    })();
  };
  return el(
    "details",
    { class: "advanced" },
    el("summary", {}, "签署人工裁决（写入项目状态，之后不可修改）"),
    el(
      "div",
      { class: "advanced-body" },
      versions.length ? el("p", { class: "view-hint" }, "版本与其摘要由服务端读回，不由人手写。") : el(
        "p",
        { class: "view-hint" },
        "该项目当前没有 ACTIVE 版本可评审；生产发布后此处才会出现候选。"
      ),
      el("label", {}, "被评审版本", versionSelect),
      el("label", {}, "评审人", juror),
      el("label", {}, "评审依据", attestation),
      el(
        "div",
        {},
        approve,
        el("label", { for: "jury-approve" }, "接受"),
        " ",
        reject,
        el("label", { for: "jury-reject" }, "拒绝")
      ),
      el("label", {}, "拒绝依据（拒绝时必填）", evidence),
      ...JURY_CRITERIA.flatMap((axis, index) => [
        el("label", {}, `${axis.criterion_id} · 分值 0-5（权重 ${axis.weight}）`, scores[index]),
        el("label", {}, `${axis.criterion_id} · 说明`, notes[index])
      ]),
      submit,
      outcome
    )
  );
}
const RIGHTS_UNREADABLE = {
  schemaVersion: "design-lab/rights-readback/v1",
  decisions: [],
  current_decisions: {},
  unapproved_scopes: [],
  ever_filed_scopes: [],
  scope_conflicts: [],
  name_checked_only: [],
  does_not_prove: []
};
const RIGHTS_CLEARANCE_TAGS = { CLEARED: "ok", NOT_REVIEWED: "warn" };
const RIGHTS_DECISION_TAGS = {
  DENIED: "bad",
  BLOCKED_BY_LICENSE: "bad",
  PENDING_REVIEW: "warn"
};
const RIGHTS_DECISION_SCHEMA_VERSION = "design-lab/rights-decision/v1";
function rightsCount(value) {
  return typeof value === "number" ? String(value) : "未读回";
}
function clearanceFraction(data) {
  if (typeof data.approved_scope_count !== "number" || typeof data.filed_scope_count !== "number")
    return "未读回";
  return `${data.approved_scope_count}/${data.filed_scope_count}`;
}
function unapprovedScopeSet(data) {
  return Array.isArray(data.unapproved_scopes) ? new Set(data.unapproved_scopes.map((row) => String(row?.use_scope ?? ""))) : null;
}
function rightsDecisionTagClass(scope, record, unapproved) {
  if (unapproved === null) return "neutral";
  if (!unapproved.has(scope)) return "ok";
  return RIGHTS_DECISION_TAGS[String(record?.decision ?? "")] ?? "warn";
}
function clearanceExplanation(data, clearance) {
  if (!clearance) return " · 服务端没有给出清算词，本页不替它补一个；未读回不等于未清算。";
  const filed = data.filed_scope_count;
  const outstanding = data.unapproved_scopes;
  if (typeof filed !== "number" || !Array.isArray(outstanding))
    return " · 分母未读回，所以这一行只转述清算词本身，不推断它站在多少个范围上。";
  if (filed === 0)
    return " · 该项目没有任何使用范围被提交过：这道门没有被问过，不是有人在等答复。 PENDING_REVIEW 只能由人提交产生，服务与页面都不会替没人问过的范围生成它。";
  if (outstanding.length)
    return ` · 已提交但未计入清算的范围：${outstanding.map((row) => `${row.use_scope}（${row.decision}）`).join("、")}。 这一行说的是"读起来未清算"，不是"正在等待审查"。`;
  return ' · 已提交的范围全部处于批准状态；清算只覆盖这些范围，见下方"本读回不证明"。';
}
function rightsScopeRows(data, emptyHint) {
  const scopes = Object.entries(data.current_decisions ?? {});
  const unapproved = unapprovedScopeSet(data);
  return el("ul", { class: "list" }, ...scopes.length ? scopes.map(([scope, record]) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, scope),
      // A decision id and a license reference are long identifiers: their own
      // .value-mono row, never inside the nowrap .tag pill (UI-AUDIT-20261006).
      el(
        "div",
        { class: "value-mono" },
        `决定 ${String(record?.decision_id ?? "未读回")}` + (record?.license_ref ? ` · 许可 ${String(record.license_ref)}` : "")
      ),
      el(
        "div",
        { class: "muted" },
        `决定人 ${String(record?.decided_by ?? "未读回")}` + (record?.decided_at ? ` · ${String(record.decided_at)}` : " · 决定时间未读回") + (record?.territory ? ` · 地域 ${String(record.territory)}` : "")
      ),
      record?.note ? el("div", { class: "view-hint" }, String(record.note)) : ""
    ),
    el("span", {
      class: "tag " + rightsDecisionTagClass(scope, record, unapproved)
    }, record?.decision ? en(String(record.decision)) : "决定词未读回")
  )) : [emptyLi(data, "尚无人签署的权利决定", emptyHint)]);
}
function rightsFacts(data) {
  const clearance = typeof data.rights_clearance === "string" ? data.rights_clearance : "";
  const states = data.decision_states && typeof data.decision_states === "object" ? Object.entries(data.decision_states) : [];
  const everCount = Array.isArray(data.ever_filed_scopes) ? data.ever_filed_scopes.length : null;
  const standingCount = Object.keys(data.current_decisions ?? {}).length;
  const nodes = [
    el(
      "p",
      { class: "view-hint" },
      `当前批准 ${clearanceFraction(data)} · 决定总数 ${rightsCount(data.decision_count)} · 曾提交过的范围 ${everCount === null ? "未读回" : String(everCount)} 个`
    ),
    el(
      "p",
      {},
      el(
        "span",
        { class: "tag " + (RIGHTS_CLEARANCE_TAGS[clearance] ?? "neutral") },
        clearance ? en(clearance) : "权利清算状态未读回"
      ),
      el("span", { class: "muted" }, clearanceExplanation(data, clearance))
    )
  ];
  if (everCount !== null && everCount > standingCount) {
    nodes.push(el(
      "p",
      { class: "view-hint" },
      `${everCount - standingCount} 个范围已不再出现在现行集合中（被后来的决定取代），清算只按现行集合计算。`
    ));
  }
  nodes.push(el(
    "p",
    { class: "muted" },
    states.length ? `现行决定按状态：${states.map(([word, count]) => `${word} ${count}`).join(" · ")}` : "状态计数未读回：响应没有给出 decision_states，本页不自行清点。"
  ));
  if (data.scope_conflicts.length) {
    nodes.push(el(
      "p",
      { class: "error" },
      `范围冲突 ${data.scope_conflicts.length} 项：` + data.scope_conflicts.map((row) => `${row.use_scope}（${(row.decision_ids ?? []).join("、")}）`).join("；") + '。同一范围带着多条未被取代的现行决定，这些范围的"当前权利立场"是不确定的；服务端取最新一条只是为了给出读回，不是替人裁决。'
    ));
  }
  if (data.name_checked_only.length) {
    nodes.push(el(
      "p",
      { class: "view-hint" },
      `仅按名字核查的范围 ${data.name_checked_only.length} 个：${data.name_checked_only.join("、")}。合同关闭属性，HTTP 提交带不进声明的 actor kind，所以这些行只证明署名不自称自动化，不证明是一只手敲的字。`
    ));
  }
  nodes.push(el(
    "div",
    { class: "rights-does-not-prove" },
    el(
      "p",
      { class: "muted" },
      `本读回不证明（由服务端自己列出，${data.does_not_prove.length} 条）：`
    ),
    ...data.does_not_prove.length ? data.does_not_prove.map((line) => el("p", { class: "view-hint" }, String(line))) : [el(
      "p",
      { class: "error" },
      "未读回：响应没有给出 does_not_prove，本页不替服务端省略它自己声明的限制。"
    )]
  ));
  return nodes;
}
const EVIDENCE_PROJECTION_UNREADABLE = {
  receipts: [],
  reasonCounts: { integrity: {}, currency: {} },
  taskCounts: {}
};
const PROJECTION_RECEIPT_LIMIT = 12;
function projectionStateWord(receipt) {
  if (!receipt.verified) return "NOT VERIFIED";
  return receipt.current ? "VERIFIED CURRENT" : "VERIFIED NOT CURRENT";
}
function projectionCount(value) {
  return typeof value === "number" ? String(value) : "—";
}
function projectionReasonList(group, noneText) {
  const entries = Object.entries(group ?? {}).sort((a, b) => a[0].localeCompare(b[0]));
  if (!entries.length) return el("p", { class: "view-hint" }, noneText);
  return el("ul", { class: "list" }, ...entries.map(([token2, count]) => el(
    "li",
    { class: "list-item" },
    el("div", {}, en(token2), el("small", {}, "该理由命中的字节声明数")),
    el("span", { class: "tag warn" }, String(count))
  )));
}
function projectionReasonLine(label, reasons) {
  if (!reasons.length) return el("small", {}, `${label}：无`);
  return el(
    "small",
    {},
    label + "：",
    ...reasons.slice(0, 3).flatMap((reason, index) => index === 0 ? [en(reason)] : [" · ", en(reason)]),
    ...reasons.length > 3 ? [el("span", {}, ` 等 ${reasons.length} 项`)] : []
  );
}
function projectionReceiptRows(receipts) {
  const shown = receipts.slice(0, PROJECTION_RECEIPT_LIMIT);
  const rest = receipts.length - shown.length;
  return el(
    "ul",
    { class: "list" },
    ...shown.map((receipt) => el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, receipt.id),
        el(
          "small",
          { class: "value-mono" },
          `subject ${receipt.subjectSha.slice(0, 12)} · ${receipt.kind}`
        ),
        projectionReasonLine("完整性理由", receipt.integrityReasons),
        projectionReasonLine("时效理由", receipt.currencyReasons)
      ),
      el(
        "span",
        { class: receipt.verified ? receipt.current ? "tag ok" : "tag info" : "tag bad" },
        en(projectionStateWord(receipt))
      )
    )),
    ...rest > 0 ? [el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, `其余 ${rest} 条未逐条列出`),
        el("small", {}, "上方计数覆盖全部记录；此处只是不再展开，不是没有这些记录。")
      )
    )] : []
  );
}
function evidenceProjectionPanel(data, unread) {
  const refusal = data.error ? `服务端在响应里给出了拒绝码 ${String(data.error)}。` : "";
  if (unread) {
    return el(
      "p",
      { class: "error" },
      `${refusal}${unread}；证据链状态未读回。未读回不等于已验证，也不等于没有问题。`
    );
  }
  if (data.error) {
    return el(
      "p",
      { class: "error" },
      `证据链状态未读回：${String(data.error)}。服务端拒绝时没有给出任何计数，本页不会替它补一个，也不会把拒绝解释成"没有证据问题"。`
    );
  }
  const totals = data.totals;
  const receipts = Array.isArray(data.receipts) ? data.receipts : [];
  if (!totals || typeof totals.records !== "number") {
    return el(
      "p",
      { class: "error" },
      "证据链状态未读回：响应没有给出 totals.records。缺少计数不得被当作 0 条记录。"
    );
  }
  if (!Array.isArray(data.receipts)) {
    return el(
      "p",
      { class: "error" },
      "证据链状态未读回：响应没有给出 receipts 集合，无法逐条判断，也不会显示任何计数。"
    );
  }
  return el(
    "div",
    {},
    el(
      "div",
      { class: "kpi-grid" },
      kpiCard(projectionCount(totals.records), "条收据", "config/task-ledger-r3.json"),
      kpiCard(projectionCount(totals.verified), "字节可复现", "在其绑定提交上重算"),
      kpiCard(projectionCount(totals.unverified), "不可复现", "含未通过 outcome 的行"),
      kpiCard(projectionCount(totals.current), "仍适用当前检出", "verified 的子集")
    ),
    el("h4", {}, "完整性理由分布（为何这些字节不再在其声称的来源处）"),
    projectionReasonList(
      data.reasonCounts?.integrity,
      "没有完整性理由：本次读回没有发现无法复现的字节声明。"
    ),
    el("h4", {}, "时效理由分布（为何完整的收据不再描述当前检出的字节）"),
    projectionReasonList(
      data.reasonCounts?.currency,
      "没有时效理由：所有完整收据引用的文件都与当前检出一致。"
    ),
    el("h4", {}, "逐条收据"),
    receipts.length ? projectionReceiptRows(receipts) : el("p", { class: "view-hint" }, "账本没有任何收据；这是读回来的空账本，不是读回失败。"),
    el(
      "p",
      { class: "view-hint" },
      `判定对象为当前检出 ${data.subjectSha ? data.subjectSha.slice(0, 12) : "（响应未给出）"}，来源 ${data.ledger ?? "（响应未给出）"}。该读回对当前检出重新计算，不读取 reports/current/（生成物绑定它写下时所在的提交）。"仍适用当前检出"是"字节可复现"的子集：完整的收据若引用的文件已移动，它仍是诚实的历史，但不是今天这份代码的证据。`
    )
  );
}
async function runEvidenceProjection(host) {
  host.replaceChildren(el(
    "p",
    { class: "view-loading" },
    "正在对当前检出重算证据链完整性（逐条复算字节声明，约一秒）…"
  ));
  try {
    const data = await apiOrEmpty(
      "/evidence-projection",
      EVIDENCE_PROJECTION_UNREADABLE
    );
    host.replaceChildren(evidenceProjectionPanel(data, shapeNotice(data)));
  } catch (error) {
    const envelope = error.serviceEnvelope;
    const code = typeof envelope?.["error"] === "string" ? envelope["error"] : errMsg(error);
    host.replaceChildren(el(
      "p",
      { class: "error" },
      `证据链状态未读回：${String(code)}。服务端在拒绝时没有给出任何计数或收据列表，本页不会把一次拒绝显示成"没有证据问题"。`
    ));
  }
}
function evidenceProjectionPanelBox() {
  const out = el(
    "div",
    { class: "evidence-projection-outcome", id: "evidence-projection-outcome" },
    el(
      "p",
      { class: "view-hint" },
      "尚未读回证据链完整性：这一判定要对当前检出逐条复算，不在页面构建时自动执行，也不读取任何生成物。未读回不等于已验证。"
    )
  );
  const run = el(
    "button",
    { type: "button", class: "ghost-btn", id: "evidence-projection-run" },
    "读回证据链完整性"
  );
  run.onclick = () => {
    void runEvidenceProjection(out);
  };
  return el(
    "div",
    { class: "panel" },
    el("h3", {}, "证据链完整性 · Human EVIDENCE"),
    run,
    out,
    el(
      "p",
      { class: "view-hint" },
      "来源 GET /api/evidence-projection（src/design_lab/governance/evidence_readback.py 依 design-lab/schemas/evidence-projection.schema.json 校验自身后才应答）。本页只读回，不修改账本：账本行由验证运行时写入，投影状态由这条读回呈现。"
    )
  );
}
function evidenceRightsColumn(data, unread) {
  const heading = el("h3", {}, "权利决定读回 · Human RIGHTS");
  if (unread) {
    return el(
      "div",
      { class: "panel" },
      heading,
      el(
        "p",
        { class: "error" },
        `${unread}；权利决定未读回。未读回不等于没有决定，也不等于已清算。`
      )
    );
  }
  if (data.error) {
    return el(
      "div",
      { class: "panel" },
      heading,
      el(
        "p",
        { class: "error" },
        `权利未读回：${String(data.error)}。未读回不等于没有决定，也不等于已清算。`
      )
    );
  }
  return el(
    "div",
    { class: "panel" },
    heading,
    ...rightsFacts(data),
    rightsScopeRows(data, "权利决定需在预检 / QA 页由人提交后在此读回；没有被提交过的范围不会出现在这里，也不会带任何默认状态。"),
    el(
      "p",
      { class: "view-hint" },
      "本页只读回决定与清算，不提交、不改写：提交是 Human Gate，在预检 / QA 页执行。权利门不代替质量、制作与发布门。"
    )
  );
}
function rightsReadbackPanel(projectId, data, reload, unread, outcome) {
  if (unread) {
    return el("div", {}, el(
      "p",
      { class: "error" },
      `权利读回不完整：${unread}。缺失字段不会被当作空集合或已清算。`
    ));
  }
  if (data.error) {
    return el(
      "p",
      { class: "error" },
      `权利未读回：${String(data.error)}。未读回不等于无决定，也不等于已清算。`
    );
  }
  return el(
    "div",
    {},
    ...rightsFacts(data),
    rightsScopeRows(data, "在下方提交一条决定后在此读回；未被提交过的范围没有默认状态。"),
    rightsDecisionForm(projectId, data, reload, outcome)
  );
}
function rightsDecisionForm(projectId, data, reload, outcome) {
  const vocabulary = Array.isArray(data.decision_vocabulary) ? data.decision_vocabulary : [];
  const scope = el("input", {
    class: "input",
    id: "rights-use-scope",
    type: "text",
    placeholder: "使用范围，例如 font-brandon-grotesk / client-photo-01",
    autocomplete: "off"
  });
  const signer = el("input", {
    class: "input",
    id: "rights-decided-by",
    type: "text",
    placeholder: "决定人（人的名字；自称 agent / model / system 的署名会被服务端拒绝）",
    autocomplete: "off"
  });
  const territory = el("input", {
    class: "input",
    id: "rights-territory",
    type: "text",
    placeholder: "可选：地域，例如 worldwide / cn-only"
  });
  const licenseRef = el("input", {
    class: "input",
    id: "rights-license-ref",
    type: "text",
    placeholder: "可选：许可文本的引用，例如 LICENSE-FILE:OFL.txt"
  });
  const note = el("textarea", {
    class: "input",
    id: "rights-note",
    placeholder: "可选：依据哪份文本、在什么范围内作出的判断"
  });
  const decisionInputs = vocabulary.map((word) => el("input", {
    type: "radio",
    name: "rights-decision",
    id: `rights-decision-${word}`,
    value: word
  }));
  const supersedes = el("select", { class: "input", id: "rights-supersedes" });
  const supersedeScopes = /* @__PURE__ */ new Map();
  supersedes.append(new Option("不替代：这是一条新的决定", ""));
  for (const [useScope, record] of Object.entries(data.current_decisions ?? {})) {
    const previous = typeof record?.decision_id === "string" ? record.decision_id : "";
    if (!previous) continue;
    supersedeScopes.set(previous, useScope);
    supersedes.append(new Option(`${useScope} · ${previous}`, previous));
  }
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "rights-submit" },
    "提交权利决定"
  );
  if (!vocabulary.length) submit.disabled = true;
  let decisionId = "";
  let lastFingerprint = "";
  submit.onclick = () => {
    void (async () => {
      const useScope = scope.value.trim();
      const chosen = decisionInputs.find((node) => node.checked);
      const actor = signer.value.trim();
      if (!vocabulary.length) {
        outcome.textContent = "未提交：决定词表未读回（响应没有给出 decision_vocabulary），页面不替合同发明一个状态词。";
        return;
      }
      if (!useScope) {
        outcome.textContent = "未提交：必须先写明使用范围；一条决定要落在一个范围上，否则读回时没人知道它管什么。";
        return;
      }
      if (!chosen) {
        outcome.textContent = "未提交：没有选中任何决定词；权利门不接受页面替你猜的默认状态。";
        return;
      }
      if (!actor) {
        outcome.textContent = "未提交：决定人必须写明。权利门不由发起请求的人默认签署，服务端也会按名字拒绝自称自动化的署名。";
        return;
      }
      const previousId = supersedes.value;
      const previousScope = supersedeScopes.get(previousId) ?? "";
      if (previousId && previousScope && previousScope !== useScope) {
        outcome.textContent = `未提交：${previousId} 决定的是 ${previousScope}，与 ${useScope} 不是同一个使用范围；替代只能落在同一范围上，本页不发送注定被拒的请求。`;
        return;
      }
      const body = {
        schemaVersion: RIGHTS_DECISION_SCHEMA_VERSION,
        use_scope: useScope,
        decision: chosen.value,
        decided_by: actor,
        // The page stamps the moment of signing from the browser clock and the service
        // validates its RFC3339 shape; the human name is what the gate records, not this.
        decided_at: (/* @__PURE__ */ new Date()).toISOString().replace(/\.\d{3}Z$/, "Z"),
        territory: territory.value.trim() || null,
        license_ref: licenseRef.value.trim() || null,
        note: note.value.trim() || null
      };
      const fingerprint = JSON.stringify(body);
      if (fingerprint !== lastFingerprint) {
        decisionId = "rights-" + Math.random().toString(16).slice(2, 34);
        lastFingerprint = fingerprint;
      }
      const payload = { decision_id: decisionId, ...body };
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/rights` + (previousId ? `?supersedes=${encodeURIComponent(previousId)}` : ""), payload);
        await reload();
        outcome.textContent = "已提交一条权利决定；上方读回来自服务端，不是本页记住的输入。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        const code = typeof envelope?.error === "string" ? envelope.error : errMsg(error);
        const detail = typeof envelope?.detail === "string" ? envelope.detail : "";
        outcome.textContent = `未提交：${code}${detail ? ` —— ${detail}` : ""}。服务端没有写入任何决定；上方读回仍是提交之前的状态，不是这次的结论。`;
      } finally {
        submit.disabled = false;
      }
    })();
  };
  return el(
    "details",
    { class: "advanced" },
    el("summary", {}, "提交权利决定（写入项目状态，之后不可修改，只能由新决定取代）"),
    el(
      "div",
      { class: "advanced-body" },
      el(
        "p",
        { class: "view-hint" },
        vocabulary.length ? `可用决定词由服务端合同给出：${vocabulary.join(" / ")}。` : "决定词表未读回：响应没有给出 decision_vocabulary，本表单不可提交。"
      ),
      el(
        "p",
        { class: "view-hint" },
        "一条决定只覆盖一个使用范围；PENDING_REVIEW 只有人选它才会出现，页面与服务端都不会替没人问过的范围生成它。一次点击提交一条。"
      ),
      el("label", {}, "使用范围", scope),
      el("div", {}, ...vocabulary.flatMap((word, index) => [
        decisionInputs[index],
        el("label", { for: `rights-decision-${word}` }, en(word))
      ])),
      el("label", {}, "决定人", signer),
      el("label", {}, "地域（可选）", territory),
      el("label", {}, "许可引用（可选）", licenseRef),
      el("label", {}, "说明（可选）", note),
      el("label", {}, "取代哪条现行决定（只列读回中出现过的）", supersedes),
      submit
    )
  );
}
async function renderRightsReview(host) {
  host.replaceChildren(el("p", { class: "view-loading" }, "正在读回权利决定…"));
  const projects2 = await apiOrEmpty("/projects", OFFLINE.projects);
  const projectShape = shapeNotice(projects2);
  if (projectShape) {
    host.replaceChildren(el(
      "p",
      { class: "error" },
      `权利项目清单未读回：${projectShape}`
    ));
    return;
  }
  if (!projects2.projects.length) {
    const offline = disconnectedNotice(projects2);
    host.replaceChildren(el(
      "p",
      { class: offline ? "error" : "view-hint" },
      offline ? `${offline}，项目台账未读回，因此不能断言无项目，也不能替某个项目提交权利决定。` : "本机尚无项目：权利决定按项目保存，这里不能替不存在的项目宣称已清算。"
    ));
    return;
  }
  const picker = el("select", { class: "input", id: "rights-project" });
  for (const p of projects2.projects) picker.append(new Option(p.name, p.id));
  const outcome = el("p", { class: "view-hint", id: "rights-review-outcome" }, "");
  const body = el("div", { class: "rights-body" });
  const load = async () => {
    const id = picker.value || projects2.projects[0].id;
    const data = await apiOrEmpty(`/projects/${id}/rights`, RIGHTS_UNREADABLE);
    const shape = shapeNotice(data);
    body.replaceChildren(rightsReadbackPanel(id, data, load, shape, outcome));
  };
  picker.onchange = () => {
    void load().catch((error) => setStatus(errMsg(error), true));
  };
  host.replaceChildren(el("label", { class: "muted" }, "权利项目", picker), outcome, body);
  await load();
}
const RESEARCH_UNREADABLE = {
  schemaVersion: "design-lab/research-readback/v1",
  findings: [],
  current_findings: {},
  confidence_counts: {},
  does_not_prove: [],
  actor_kinds: {},
  unattributed_findings: []
};
function researchNumber(data, key) {
  const value = data[key];
  return typeof value === "number" ? String(value) : "未读回";
}
function researchFacts(data) {
  const verdict = data.research_verdict;
  const tagClass = verdict === null || verdict === void 0 ? "warn" : "info";
  const tags = Object.entries(data.confidence_counts ?? {});
  return el(
    "div",
    { class: "panel research-facts" },
    el("h3", {}, "研究结论读回"),
    el(
      "p",
      { class: "view-hint" },
      `共 ${researchNumber(data, "finding_count")} 条 · 现行 ${researchNumber(data, "current_finding_count")} 条 · 已被取代 ${researchNumber(data, "superseded_finding_count")} 条 · 有来源 ${researchNumber(data, "sourced_finding_count")} 条 · 无来源 ${researchNumber(data, "unsourced_finding_count")} 条 · 来源引用合计 ${researchNumber(data, "source_ref_total")} 个`
    ),
    el(
      "p",
      { class: "muted" },
      `来源字段名取自响应（${data.source_ref_field ?? "未读回"}），置信度计数来自服务端逐词表给出（含 0），标注数 ${researchNumber(data, "stated_confidence_count")}；未署名 ${researchNumber(data, "unattributed_findings")} 条。`
    ),
    tags.length ? el("div", {}, ...tags.flatMap(([word, count]) => [
      el(
        "span",
        { class: "tag " + (count ? "info" : "neutral") },
        en(word)
      ),
      el("span", { class: "muted" }, String(count))
    ])) : el("p", { class: "view-hint" }, "置信度计数未读回：响应没有给出 confidence_counts，本页不代替服务发明分类。"),
    el(
      "span",
      { class: "tag " + tagClass },
      verdict === null || verdict === void 0 ? "无完成判定词" : en(String(verdict))
    ),
    el(
      "p",
      { class: "view-hint" },
      data.research_verdict_note ?? "判定说明未读回：响应没有给出 research_verdict_note。"
    ),
    el(
      "p",
      { class: "muted" },
      `本面不证明设计质量（proves_design_quality=${String(data.proves_design_quality ?? "未读回")}），也不是知识导出（is_knowledge_export=${String(data.is_knowledge_export ?? "未读回")}）。`
    ),
    ...data.undeclared_disclaimer ? [el("p", { class: "view-hint" }, `未声明免责：${data.undeclared_disclaimer}`)] : [],
    el(
      "ul",
      { class: "list" },
      ...(data.does_not_prove ?? []).map((line) => el(
        "li",
        { class: "list-item" },
        el("span", {}, en(line))
      ))
    ),
    ...data.does_not_prove?.length ? [] : [el(
      "p",
      { class: "view-hint" },
      "本读回未给出 does_not_prove，因此无法说明这些数字不覆盖什么。"
    )]
  );
}
function researchFindingRows(data) {
  const current = data.current_findings ?? {};
  const findings = data.findings ?? [];
  if (!findings.length) {
    return el(
      "ul",
      { class: "list" },
      emptyLi(
        data,
        "本项目尚无已持久化的研究结论",
        "记录一条带来源的结论后在此读回；未读回不等于本项目没有结论。"
      )
    );
  }
  return el(
    "ul",
    { class: "list" },
    ...findings.map((record) => {
      const id = typeof record.finding_id === "string" ? record.finding_id : "未读回";
      const superseded = !Object.prototype.hasOwnProperty.call(current, id);
      const sources = Array.isArray(record.sourceRefs) ? record.sourceRefs : [];
      return el(
        "li",
        { class: "list-item" },
        el("span", {}, record.claim ?? "结论正文未读回"),
        el("span", { class: "value-mono" }, id),
        el(
          "span",
          { class: "tag " + (superseded ? "neutral" : "info") },
          superseded ? "已被取代" : "现行"
        ),
        el(
          "span",
          { class: "tag " + (record.confidence ? "info" : "warn") },
          record.confidence ? en(record.confidence) : "未标注置信度"
        ),
        el(
          "span",
          { class: "muted" },
          sources.length ? `来源 ${sources.join(" · ")}` : "来源未读回"
        )
      );
    })
  );
}
function researchDecisionForm(projectId, data, reload, outcome) {
  const vocabulary = Array.isArray(data.confidence_vocabulary) ? data.confidence_vocabulary : [];
  const claim = el("textarea", {
    class: "input",
    id: "research-claim",
    maxlength: "4000",
    "aria-label": "研究结论正文"
  });
  const sources = el("input", {
    class: "input",
    id: "research-sources",
    maxlength: "2000",
    placeholder: "interview-07, bench-figma-2026-05",
    "aria-label": "支撑这条结论的来源引用，用逗号或空格分隔，至少一个"
  });
  const confidence = el("select", { class: "input", id: "research-confidence" });
  confidence.append(new Option("不标注（响应里就不会有这个字段）", ""));
  for (const word of vocabulary) confidence.append(new Option(word, word));
  const notRule = el("input", { type: "checkbox", id: "research-not-design-rule" });
  const supersedes = el("select", { class: "input", id: "research-supersedes" });
  supersedes.append(new Option("不替代：这是一条新的结论", ""));
  for (const id of Object.keys(data.current_findings ?? {})) {
    supersedes.append(new Option(id, id));
  }
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "research-submit" },
    "记录一条研究结论"
  );
  let findingId = "";
  let lastFingerprint = "";
  submit.onclick = () => {
    void (async () => {
      const text = claim.value.trim();
      const refs = sources.value.split(/[,\n\s]+/).map((part) => part.trim()).filter(Boolean);
      if (!text) {
        outcome.textContent = "未提交：结论正文为空。页面不发送一条没有主张的记录。";
        return;
      }
      if (!refs.length) {
        outcome.textContent = "未提交：没有任何来源引用。一条没有来源的结论是猜测，服务端会拒绝（RESEARCH_SOURCE_REQUIRED），本页不替你补一个来源。";
        return;
      }
      const body = {
        claim: text,
        sourceRefs: refs
      };
      if (confidence.value) body.confidence = confidence.value;
      if (notRule.checked) body.notDesignRule = true;
      const fingerprint = JSON.stringify(body);
      if (fingerprint !== lastFingerprint) {
        findingId = "rf-" + Math.random().toString(16).slice(2, 34);
        lastFingerprint = fingerprint;
      }
      const previous = supersedes.value;
      const payload = { ...body, finding_id: findingId };
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/research` + (previous ? `?supersedes=${encodeURIComponent(previous)}` : ""), payload);
        await reload();
        outcome.textContent = "已记录一条研究结论；上方读回来自服务端，不是本页记住的输入。这条结论不等于设计质量判定，也不等于知识导出。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        outcome.textContent = `未记录：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "") + "。服务端未写入任何结论。";
      } finally {
        submit.disabled = false;
      }
    })().catch((error) => setStatus(errMsg(error), true));
  };
  return el(
    "div",
    { class: "panel research-form" },
    el("h3", {}, "记录一条研究结论"),
    el(
      "p",
      { class: "view-hint" },
      "一条结论必须带至少一个来源引用；置信度只有你选了才会出现在记录里，页面不默认一个。这里写入的是工作输入，不是 Human Gate 裁决，也不会提升任何验收轴。"
    ),
    el("label", {}, "结论正文", claim),
    el("label", {}, "来源引用（至少一个）", sources),
    el("label", {}, "置信度（可选）", confidence),
    el("label", {}, "标注这不是一条设计规则（可选）", notRule),
    el("label", {}, "取代哪条现行结论（只列读回中出现过的）", supersedes),
    submit
  );
}
async function renderResearch(host) {
  host.replaceChildren(el("p", { class: "view-loading" }, "正在读回研究结论…"));
  const projects2 = await apiOrEmpty("/projects", OFFLINE.projects);
  const projectShape = shapeNotice(projects2);
  if (projectShape) {
    host.replaceChildren(el("p", { class: "error" }, `研究项目清单未读回：${projectShape}`));
    return;
  }
  if (!projects2.projects.length) {
    const offline = disconnectedNotice(projects2);
    host.replaceChildren(el(
      "p",
      { class: offline ? "error" : "view-hint" },
      offline ? `${offline}，项目台账未读回，因此不能断言无项目，也不能替某个项目记录结论。` : "本机尚无项目：研究结论按项目保存，这里不能替不存在的项目建立结论。"
    ));
    return;
  }
  const picker = el("select", { class: "input", id: "research-project" });
  for (const p of projects2.projects) picker.append(new Option(p.name, p.id));
  const outcome = el("p", { class: "view-hint", id: "research-review-outcome" }, "");
  const body = el("div", { class: "research-body" });
  const load = async () => {
    const id = picker.value || projects2.projects[0].id;
    const data = await apiOrEmpty(
      `/projects/${id}/research`,
      RESEARCH_UNREADABLE
    );
    const shape = shapeNotice(data);
    body.replaceChildren(
      shape ? el("p", { class: "error" }, `研究读回形状异常：${shape}`) : researchFacts(data),
      researchFindingRows(data),
      researchDecisionForm(id, data, load, outcome)
    );
  };
  picker.onchange = () => {
    void load().catch((error) => setStatus(errMsg(error), true));
  };
  host.replaceChildren(
    el(
      "div",
      { class: "page-head" },
      el(
        "div",
        {},
        el("h2", {}, "研究洞察"),
        el("p", {}, "按项目读回已持久化的研究结论与其来源覆盖；写入是工作输入，不是验收判定。")
      )
    ),
    el("label", { class: "muted" }, "研究项目", picker),
    outcome,
    body
  );
  await load();
}
async function renderResearchView(target) {
  const findings = el("div", { id: "research-findings" });
  const library = el("div", { id: "capability-library" });
  target.replaceChildren(findings, library);
  await renderResearch(findings);
  await renderCapabilityLibrary(library);
}
async function renderPreflight(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在准备预检…"));
  const known = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H020";
  const input = el("input", {
    id: "preflight-task-input",
    class: "input preflight-input",
    // The example used to live in the placeholder, where a placeholder cannot wrap:
    // at 1280 the field clipped it after the comma, so the format was visible and the
    // only concrete example was not. It moved into the result panel's first message.
    placeholder: "<TASKPACK>::<TASK_KEY>",
    maxlength: "200",
    "aria-label": "任务资源预检 ID，格式为任务包 ID::任务键"
  });
  const runBtn = el("button", { type: "button", class: "primary-btn", id: "preflight-run" }, "运行预检");
  const result = el(
    "div",
    { class: "panel preflight-result" },
    // Constructed empty, this rendered as a large blank bordered box, which reads as
    // a broken panel rather than as a result area waiting for a run.
    el(
      "p",
      { class: "view-hint" },
      "尚未运行预检。填写任务全 ID（形如 " + known + "），点「运行预检」后在此读回判定与资源清单。"
    )
  );
  const kpiGrid = el(
    "div",
    { class: "kpi-grid" },
    kpiCard("—", "登记资源", "运行预检后读回"),
    kpiCard("—", "阻塞资源", "运行预检后读回"),
    kpiCard("—", "判定", "READY / BLOCKED"),
    kpiCard("—", "机器范围", "运行预检后读回")
  );
  const setKpi = (index, value) => {
    const strong = kpiGrid.querySelectorAll(".kpi strong")[index];
    if (strong) strong.textContent = value;
  };
  const resetKpis = () => {
    for (let i = 0; i < 4; i += 1) setKpi(i, "—");
  };
  const runPreflight = async () => {
    const taskId = input.value.trim();
    if (!taskId) {
      resetKpis();
      result.replaceChildren(el("p", { class: "view-hint" }, "请先填写要预检的任务全 ID（<TASKPACK>::<TASK_KEY>）。"));
      return;
    }
    resetKpis();
    result.replaceChildren(el("p", { class: "view-loading" }, `正在读回 ${taskId} 的资源判定…`));
    try {
      const data = await api(`/task-preflight?task=${encodeURIComponent(taskId)}`);
      const blocked = data.blocked_resources.length;
      const noData = data.resources.length === 0;
      setKpi(0, String(data.resources.length));
      setKpi(1, String(blocked));
      setKpi(2, noData ? "—" : data.verdict);
      setKpi(3, data.machine_scope);
      result.replaceChildren(
        el(
          "span",
          { class: "tag " + (blocked ? "bad" : noData ? "warn" : "ok") },
          noData ? "无可判定资源" : data.verdict
        ),
        el(
          "span",
          { class: "muted" },
          `登记 ${data.registry_state} · 机器 ${data.machine_scope} · 权限 ${data.permissions.meaning}`
        ),
        noData ? el("p", { class: "view-hint" }, `该任务未解析到任何资源（登记状态 ${data.registry_state}）；没有可比对的资源，不给出 READY 判定。`) : blocked ? el("p", { class: "view-hint" }, `阻塞资源 ${blocked} 项：${data.blocked_resources.join(" · ")}。此预检只读回，不安装、不裁许可、不遍历外部根。`) : el("p", { class: "view-hint" }, "无阻塞资源。此为只读预检判定，不等同质量或 rights 验收。"),
        el(
          "div",
          {
            class: "table-wrap",
            tabindex: "0",
            role: "region",
            "aria-label": "预检资源表（可横向滚动）"
          },
          el(
            "table",
            { class: "table" },
            el("thead", {}, el("tr", {}, el("th", {}, "资源"), el("th", {}, "状态"), el("th", {}, "说明"))),
            el("tbody", {}, ...data.resources.map((row) => el(
              "tr",
              {},
              el("td", {}, row.ref),
              el("td", {}, el("span", { class: "tag info" }, row.state)),
              el("td", {}, row.meaning)
            )))
          )
        )
      );
    } catch (error) {
      resetKpis();
      result.replaceChildren(el("p", { class: "error" }, `预检未确认：${errMsg(error)}。服务端拒绝时未写入任何判定。`));
    }
  };
  runBtn.onclick = () => {
    void runPreflight().catch((error) => setStatus(errMsg(error), true));
  };
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "预检 / QA"),
      el("p", {}, "与 CLI doctor 同一读回源：只探测与报告，从不安装、从不接受许可、从不遍历外部根。")
    ),
    el(
      "div",
      { class: "page-actions" },
      runBtn
    )
  );
  const juryHost = el("div", { id: "jury-review" });
  const rightsHost = el("div", { id: "rights-review" });
  target.replaceChildren(
    pageHead,
    kpiGrid,
    el(
      "div",
      { class: "toolbar" },
      el("label", { class: "muted" }, "任务全 ID", input)
    ),
    result,
    el(
      "section",
      { class: "panel" },
      el("h3", {}, "设计评审 · Human Jury"),
      el(
        "p",
        { class: "view-hint" },
        "与上方资源预检是两件事：这里读回的是人工签署的裁决，绑定到具体版本摘要。"
      ),
      juryHost
    ),
    el(
      "section",
      { class: "panel" },
      el("h3", {}, "权利决定 · Human RIGHTS"),
      el(
        "p",
        { class: "view-hint" },
        "与上方资源预检、人工评审都是不同的门：这里读回并提交的是一条使用范围上的许可立场。提交是 Human Gate，只在本页由人执行；证据系统只读回。"
      ),
      rightsHost
    )
  );
  await renderJuryReview(juryHost);
  await renderRightsReview(rightsHost);
}
function valueRow(label, value, long, tagClass = "info") {
  return long ? el(
    "li",
    { class: "list-item value-row" },
    el("span", {}, label),
    el("span", { class: "value-mono" }, value)
  ) : el(
    "li",
    { class: "list-item" },
    el("span", {}, label),
    el("span", { class: "tag " + tagClass }, value)
  );
}
function axisValueText(value) {
  if (value === null || value === void 0) return "该记录无此字段";
  if (Array.isArray(value)) return value.length ? value.join("、") : "未分类";
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? entries.map(([k, v]) => `${k}：${String(v)}`).join(" · ") : "未分类";
  }
  return String(value);
}
function capabilityDetail(c) {
  const axes = Object.entries(c.axes ?? {});
  return el(
    "details",
    { class: "capability-detail" },
    el("summary", {}, "能力详情 · 七轴、资格依据与许可前置"),
    el(
      "ul",
      { class: "list" },
      ...axes.map(([axis, value]) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, en(axis)),
          el("small", {}, axisValueText(value))
        )
      )),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "资格判定"),
          el("small", {}, c.qualified === null ? c.qualificationReason ?? "未判定" : `已判定为 ${String(c.qualified)}；证据 ${(c.qualificationEvidence ?? []).join("、") || "未列出"}`)
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "许可与权利"),
          el("small", {}, `${c.license ?? "无许可记录"}${c.licenseUrl ? ` · ${c.licenseUrl}` : ""}${c.rightsNotes ? ` · ${c.rightsNotes}` : ""}；许可分布不等于使用权，未审的素材不得进入正式交付。`)
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "证据级"),
          el("small", {}, c.evidenceLevel ? `${en(c.evidenceLevel)} · 证据级只说明观察强度，不等于设计质量或宿主可运行` : "未记录证据级")
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "反例与不适用"),
          el("small", {}, '仓内尚无按能力记录的失败样本或反例；没有记录就说没有记录，不把空白读成"没有已知问题"。')
        )
      )
    ),
    el("button", { type: "button", class: "primary-btn", disabled: "" }, "使用此能力"),
    el(
      "p",
      { class: "view-hint" },
      "此按钮当前禁用：把能力落成目标生成包属于 DL-UI-U05 / DL-FINAL-T10，接通之前它不该看起来可用。"
    )
  );
}
async function renderCapabilityLibrary(target, opts = {}) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回能力目录…"));
  const data = await apiOrEmpty("/capabilities", OFFLINE.capabilities);
  const rows = data.capabilities;
  const filter = el("input", {
    class: "input capability-filter",
    type: "search",
    id: "capability-filter",
    placeholder: "按 ID / 许可 / 域 / 处置 / 修订状态过滤",
    "aria-label": "能力目录过滤"
  });
  const shown = el("span", { class: "muted", id: "capability-shown" }, "");
  const body = el("tbody", {});
  const FACETS = [
    { field: "license", label: "许可" },
    { field: "disposition", label: "处置" },
    { field: "presence", label: "存在状态" },
    { field: "evidenceLevel", label: "证据级" }
  ];
  const ANY = "__any__";
  const NONE = "__none__";
  const facetPicks = FACETS.map((facet) => {
    const values = Array.from(new Set(rows.map((c) => c[facet.field]))).sort((a, b) => (a ?? "￿").localeCompare(b ?? "￿"));
    const select = el(
      "select",
      { class: "input", "aria-label": `按${facet.label}过滤` },
      el("option", { value: ANY }, `全部${facet.label}（${values.length} 个取值）`),
      ...values.map((v) => el("option", { value: v ?? NONE }, v ?? "无记录"))
    );
    return { field: facet.field, label: facet.label, select };
  });
  const axisFilled = (c, axis) => {
    const v = c.axes?.[axis];
    return Array.isArray(v) ? v.length > 0 : v !== void 0 && v !== null;
  };
  const TYPE_TAB_NOTE = '这一类与相邻两类都按 artifactTypes 轴分组，而本批读回里该轴没有任何取值，所以三类目前给的是同一个空集——不是三种各自量出来的"没有"。等人工分类补上取值后，各 tab 的归属由该轴自己的值决定，这里不替它猜词表。（三类的谓词是同一个，所以三个数字必然相等；这不是三种各自的读数。）';
  const ASSET_TABS = [
    { label: "全部资产", basis: "本批读回的全部记录", members: () => true, note: "" },
    {
      label: "可调用能力",
      basis: "qualified",
      // `qualified` is a verdict, and its domain is true / false / null ("未判定"). `!== null`
      // counted a record the service had explicitly judged NOT callable, so the one tab whose
      // whole purpose is "what can I actually call" listed the refusals beside the passes.
      // Only the affirmative value belongs here; `false` and `null` are two different refusals
      // and neither of them is availability.
      members: (c) => c.qualified === true,
      note: "这一类按资格判定字段计数，不按 kind：kind 说的是记录类型，可调用性说的是资格。只有 qualified === true 才算可调用；false（已判不合格）与 null（未判定）都不在这一类里，两者也不互相冒充。"
    },
    {
      label: "规范与方法",
      basis: "artifactTypes",
      members: (c) => axisFilled(c, "artifactTypes"),
      note: TYPE_TAB_NOTE
    },
    {
      label: "案例与参考",
      basis: "artifactTypes",
      members: (c) => axisFilled(c, "artifactTypes"),
      note: TYPE_TAB_NOTE
    },
    {
      label: "模板与配方",
      basis: "artifactTypes",
      members: (c) => axisFilled(c, "artifactTypes"),
      note: TYPE_TAB_NOTE
    }
  ];
  let tabPick = 0;
  const tabsBox = el("div", {
    class: "asset-tabs",
    role: "tablist",
    "aria-label": "资产类型"
  });
  const unreadReadback = () => Boolean(disconnectedNotice(data)) || shapeFieldMissing(data, "capabilities");
  const axisPopulated = (axis) => rows.some((c) => axisFilled(c, axis));
  const tabBadge = (t, n) => {
    if (unreadReadback()) return "未读回";
    if (t.basis === "artifactTypes" && !axisPopulated(t.basis)) return "未分类";
    return String(n);
  };
  const active = el("div", {
    class: "capability-active",
    id: "capability-active",
    "aria-label": "已选检索条件"
  });
  const chip = (label, value, remove) => el(
    "span",
    { class: "capability-chip" },
    el("span", { class: "capability-chip-text" }, `${label}：${value}`),
    el("button", {
      type: "button",
      class: "capability-chip-x",
      "aria-label": `移除条件 ${label} ${value}`,
      title: `移除 ${label}：${value}`,
      onclick: () => {
        remove();
        render();
      }
    }, "×")
  );
  const clearSearchOnly = () => {
    filter.value = "";
    for (const f of facetPicks) f.select.value = ANY;
  };
  const domainCondition = hashCondition(window.location.hash, "domain");
  const domainHit = (c) => domainCondition !== null && declaredDomains(c).includes(domainCondition);
  const renderActive = () => {
    const picked = [];
    const needleNow = (filter.value || "").trim();
    if (needleNow) {
      picked.push(chip("关键词", needleNow, () => {
        filter.value = "";
      }));
    }
    for (const f of facetPicks) {
      const v = f.select.value;
      if (v === ANY || v === "") continue;
      picked.push(chip(f.label, v === NONE ? "无记录" : v, () => {
        f.select.value = ANY;
      }));
    }
    if (domainCondition !== null) {
      picked.push(chip(
        "声明领域",
        domainCondition,
        () => {
          window.location.hash = capabilityHashForDomain(null);
        }
      ));
    }
    if (!picked.length) {
      active.replaceChildren(el(
        "span",
        { class: "muted" },
        "没有检索条件：下面显示的是这一批读回的全部记录。"
      ));
      return;
    }
    const matched = rows.filter(domainHit).length;
    const unclassified = rows.filter(domainsUnclassified).length;
    const domainNote = domainCondition === null ? [] : [
      el(
        "span",
        { class: "muted", id: "capability-domain-note" },
        `按声明领域过滤：本批读回 ${rows.length} 条里 ${matched} 条在 axes.domains 声明了 “${domainCondition}”，${rows.length - matched} 条没有（其中 ${unclassified} 条自己记着 domains 轴未分类；未分类不等于不属于）。`
      )
    ];
    active.replaceChildren(
      el("span", { class: "muted" }, `已选 ${picked.length} 项条件`),
      ...picked,
      el("button", {
        type: "button",
        class: "secondary",
        id: "capability-clear",
        onclick: () => {
          clearSearchOnly();
          render();
        }
      }, "清除检索条件"),
      ...domainNote
    );
  };
  const render = () => {
    const needle = (filter.value || "").trim().toLowerCase();
    const faceted = rows.filter((c) => (needle ? [
      c.id,
      c.license,
      c.domain,
      c.disposition,
      c.presence,
      c.revisionState,
      c.sourceType,
      c.evidenceLevel,
      c.upstreamOwner
    ].join(" ").toLowerCase().includes(needle) : true) && (domainCondition === null || domainHit(c)) && facetPicks.every((f) => {
      const want = f.select.value;
      if (want === ANY || want === "") return true;
      if (want === NONE) return c[f.field] === null || c[f.field] === void 0;
      return c[f.field] === want;
    }));
    const tab = ASSET_TABS[tabPick];
    const keep = faceted.filter(tab.members);
    tabsBox.replaceChildren(...ASSET_TABS.map((t, i) => el(
      "button",
      {
        type: "button",
        role: "tab",
        id: `asset-tab-${i}`,
        class: "asset-tab" + (i === tabPick ? " on" : ""),
        "aria-selected": i === tabPick ? "true" : "false",
        onclick: () => {
          tabPick = i;
          render();
        }
      },
      el("span", {}, t.label),
      el("small", {}, tabBadge(t, faceted.filter(t.members).length))
    )));
    const byId2 = /* @__PURE__ */ new Map();
    for (const c of keep) if (!byId2.has(c.id)) byId2.set(c.id, c);
    const unique = Array.from(byId2.values());
    const duplicates = keep.length - unique.length;
    body.replaceChildren(...unique.map((c) => el(
      "tr",
      {},
      el(
        "td",
        {},
        el("strong", {}, c.id),
        el("div", { class: "muted" }, `${c.kind} · ${c.sourceType ?? "未分类"}`),
        // The withdrawal instruction is part of the record, not an afterthought: the
        // plan asks for upgrade/withdraw with source references, and this is the
        // recorded path for exactly this candidate.
        c.removalPath ? el(
          "details",
          { class: "capability-withdraw" },
          el("summary", {}, "撤回路径"),
          el("p", { class: "mono" }, c.removalPath)
        ) : "",
        // DL-UI-U03: 详情随记录一起读回，不另开一页去猜。
        capabilityDetail(c),
        // R2 §5: 完整详情要有自己的地址，才谈得上"被重新找到"。行内展开是速览，
        // 这个按钮把地址换成本条记录的稳定 ID。
        el(
          "button",
          {
            type: "button",
            class: "secondary capability-open",
            "aria-label": `查看 ${c.id} 的完整详情`,
            onclick: () => {
              window.location.hash = capabilityDetailHash(c.id);
            }
          },
          "查看详情"
        )
      ),
      el("td", {}, c.license ?? "（无记录）"),
      el("td", {}, c.disposition ?? "—"),
      el("td", {}, c.presence ?? "—"),
      el("td", {}, el("span", {
        // A revision recovered by exact repository-path join is the only green here;
        // unresolved and not-verified are warnings, never blanks.
        class: "tag " + (c.revisionState === "VERIFIED" ? "ok" : "warn")
      }, en(c.revisionState)), c.revision ? el("div", { class: "mono" }, c.revision) : ""),
      el("td", {}, c.qualified === null ? el("span", { class: "tag neutral" }, "未判定") : el("span", { class: "tag info" }, String(c.qualified))),
      el("td", {}, c.evidenceLevel ? el(
        "span",
        { class: "tag " + (c.evidenceLevel === "E0" ? "warn" : "info") },
        en(c.evidenceLevel)
      ) : el("span", { class: "tag neutral" }, "未记录")),
      // Popularity is shown with its observation stamp and an explicit not-a-score
      // marker, per the taxonomy policy `popularityIsNotQuality`.
      el("td", {}, c.popularity ? el(
        "span",
        { class: "muted" },
        `★ ${c.popularity.stargazerCount ?? "—"} · fork ${c.popularity.forkCount ?? "—"} · ${c.popularity.observedAt?.slice(0, 10) ?? "未记时间"} · 非质量分`
      ) : el("span", { class: "muted" }, "未观测"))
    )));
    if (!unique.length) {
      const headline = unreadReadback() ? `${tab.label}：未读回` : `${tab.label}：本批读回里这一类没有命中记录`;
      const why = unreadReadback() ? "这一批没有读回能力记录（未连接，或响应没有给出 capabilities），所以这里既不是 0 条，也不是这一类没有资产。" : faceted.length === 0 ? `当前关键词与筛选组合下没有候选记录，所以这里说的是检索条件，不是这一类资产的有无。` : `${tab.label} 按 ${tab.basis} 计数；在其余条件剩下的 ${faceted.length} 条候选里，这个字段没有给出任何命中的记录。`;
      body.append(el(
        "tr",
        { class: "asset-empty" },
        el(
          "td",
          { colspan: String(TABLE_COLUMNS.length) },
          el("strong", {}, headline),
          el("p", { class: "view-hint" }, why),
          tab.note ? el("p", { class: "view-hint" }, tab.note) : ""
        )
      ));
    }
    shown.textContent = `显示 ${unique.length} / ${rows.length} 条` + (duplicates ? `（本组合下按 ID 去掉 ${duplicates} 条重复）` : "（按 ID 去重）");
    renderActive();
  };
  filter.oninput = () => {
    render();
  };
  for (const facet of facetPicks) facet.select.onchange = () => {
    render();
  };
  const TABLE_COLUMNS = [
    "能力",
    "许可",
    "处置",
    "存在状态",
    "修订",
    "资格判定",
    "证据级",
    "热度（非质量分）"
  ];
  const researchCard = CAPABILITY_REGISTRY.find((c) => c.capabilityId === "research-insights");
  target.replaceChildren(
    el(
      "div",
      { class: "page-head" },
      el(
        "div",
        {},
        el("h2", {}, "能力目录"),
        // The payload carries `unmeasuredMeans` for machines; the reader gets the same
        // rule in the page's own language, with the English state words left untranslated.
        el("p", {}, "只读回仓内已维护的能力记录：来源锁、修订账与模型雷达。空白不等于 0：未经宿主运行与人工验收的项标为 未判定，未取回修订的项标为 NOT_VERIFIED 或 UNRESOLVED；本视图不安装、不取证、不代签许可。")
      ),
      el("div", { class: "page-actions" }, shown)
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, `能力记录（${data.counts.total}）`),
      el(
        "p",
        { class: "view-hint" },
        `许可分布 ${Object.entries(data.counts.byLicense).map(([k, v]) => `${k} ${v}`).join(" · ")}；修订 ${Object.entries(data.counts.byRevisionState).map(([k, v]) => `${k} ${v}`).join(" · ")}；资格判定 ${data.counts.qualificationVerdicts}（合格 ${data.counts.qualifiedTrue} / 不合格 ${data.counts.qualifiedFalse} / 未裁定 ${data.counts.qualificationNotAdjudicated}）。本视图不安装、不取证、不代签许可。`
      ),
      tabsBox,
      el(
        "div",
        { class: "project-picker capability-facets" },
        el("label", { class: "capability-filter" }, "关键词", filter),
        ...facetPicks.map((f) => el(
          "label",
          { class: "capability-filter" },
          f.label,
          f.select
        ))
      ),
      active,
      el(
        "div",
        {
          class: "table-wrap",
          tabindex: "0",
          role: "region",
          "aria-label": "能力目录表（可横向滚动）"
        },
        el(
          "table",
          { class: "table" },
          el("thead", {}, el(
            "tr",
            {},
            ...TABLE_COLUMNS.map((h) => el("th", {}, h))
          )),
          body
        )
      )
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "分类轴现状"),
      el(
        "p",
        { class: "view-hint" },
        `已连接候选分类 ${data.classification?.joined ?? 0} / ${data.counts.total} 条。` + (data.classification?.unclassifiedAxes?.length ? `以下轴在候选分类账中全部为空，界面不代填：${data.classification.unclassifiedAxes.join("、")}。` : "所有已声明分类轴均有值。") + ` ${data.classification?.note ?? ""}`
      ),
      el(
        "p",
        { class: "view-hint" },
        "热度取自 GitHub 观测并带观测时间；策略明确 popularityIsNotQuality，因此它不参与排序或判定。"
      )
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "研究结论"),
      el("p", { class: "view-hint" }, "研究结论已改为读本项目的持久化路由，在本页上方读回；这里保留登记表卡片本身，不再声称缺少路由。"),
      researchCard ? capabilityCard(researchCard) : el("p", { class: "view-hint" }, "（登记表无此项）")
    ),
    capabilityDrawer(rows, opts.openId ?? null),
    ...shapeNoticeRows(data)
  );
  render();
  if (opts.openId && typeof document !== "undefined" && typeof document.getElementById === "function") {
    const panel = document.getElementById("capability-drawer");
    if (panel && typeof panel.focus === "function") panel.focus();
  }
}
function capabilityDrawer(rows, openId) {
  if (!openId) return el("div", { class: "cap-drawer-slot", hidden: "" });
  const found = rows.find((c) => c.id === openId) ?? null;
  if (!found) {
    return el(
      "section",
      {
        class: "cap-drawer",
        id: "capability-drawer",
        tabindex: "-1",
        "aria-labelledby": "cap-drawer-title"
      },
      el("h3", { id: "cap-drawer-title" }, "详情地址指向的记录不在本批读回里"),
      stateBlock({
        kind: "unknown",
        title: "未找到该记录",
        weight: "neutral",
        producer: `#/capabilities/${openId} 不在本批 GET /api/capabilities 的 ${rows.length} 条读回里；地址本身合法，但记录身份以读回为准。`,
        next: "返回能力目录重选一条；不要按 ID 猜测这条能力的资格、许可或证据级。"
      }),
      el(
        "div",
        { class: "uif-row" },
        el("button", {
          type: "button",
          class: "secondary",
          onclick: () => {
            window.location.hash = "#/capabilities";
          }
        }, "返回能力目录")
      )
    );
  }
  const row = (label, value) => el(
    "div",
    { class: "cap-drawer-row" },
    el("span", { class: "muted" }, label),
    typeof value === "string" ? el("span", {}, value) : value
  );
  const panel = el(
    "section",
    {
      class: "cap-drawer",
      id: "capability-drawer",
      tabindex: "-1",
      "aria-labelledby": "cap-drawer-title"
    },
    el(
      "div",
      { class: "cap-drawer-head" },
      el("h3", { id: "cap-drawer-title" }, found.id),
      el("button", {
        type: "button",
        class: "secondary",
        id: "capability-drawer-close",
        onclick: () => {
          window.location.hash = "#/capabilities";
        }
      }, "返回能力目录")
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      `稳定 ID ${found.id} · 类型 ${found.kind} · 来源 ${found.sourceType ?? "未分类"}。这一面板与列表行读的是同一份记录，不是第二份台账；地址可以贴给别人，但对方看到的仍是那一批读回的内容。`
    ),
    row("领域", found.domain ? el("span", {}, found.domain) : el("span", { class: "tag neutral" }, "未分类")),
    row("资产类型", found.kind),
    row("能力范围 / 资格判定", found.qualified === null ? el("span", { class: "tag neutral" }, "未判定") : el("span", { class: "tag info" }, String(found.qualified))),
    el("p", { class: "uif-spec-note" }, found.qualificationReason ?? "资格依据：本条记录自带判定，无需补充理由。"),
    row("许可", found.license ?? "（无记录）"),
    row("处置 / 存在状态", `${found.disposition ?? "—"} · ${found.presence ?? "—"}`),
    row("修订", el(
      "span",
      {},
      el(
        "span",
        { class: "tag " + (found.revisionState === "VERIFIED" ? "ok" : "warn") },
        en(found.revisionState)
      ),
      found.revision ? el("span", { class: "mono" }, ` ${found.revision}`) : ""
    )),
    row("证据级", found.evidenceLevel ? el(
      "span",
      { class: "tag " + (found.evidenceLevel === "E0" ? "warn" : "info") },
      en(found.evidenceLevel)
    ) : el("span", { class: "tag neutral" }, "未记录")),
    row("热度（非质量分）", found.popularity ? `★ ${found.popularity.stargazerCount ?? "—"} · fork ${found.popularity.forkCount ?? "—"} · ${found.popularity.observedAt?.slice(0, 10) ?? "未记时间"}` : "未观测"),
    found.removalPath ? row("撤回路径", el("span", { class: "mono" }, found.removalPath)) : "",
    el("h4", {}, "分类轴"),
    el(
      "p",
      { class: "uif-spec-note" },
      '轴值来自候选分类账；为空的轴显示"未分类"而不是 0，也不由界面代填——填它是人工分类判断，属 DL-FINAL-T06 的验收内容。'
    ),
    el("ul", { class: "cap-drawer-axes" }, ...Object.entries(found.axes ?? {}).map(([axis, v]) => el("li", {}, `${axis} · ${axisValueText(v)}`))),
    el(
      "div",
      { class: "uif-row" },
      el("button", { type: "button", class: "primary-btn", disabled: "" }, "用于本次制作"),
      el(
        "span",
        { class: "theme-toggle-note" },
        "禁用：把这条 ID 与 revision 带进制作上下文属 DL-UI-U04/U05，接通前它不该看起来可点。"
      )
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      "本面板不宣称执行资格：分析、目标包生成、真实执行、原生工程交付与真人评审是不同结论，这里只读回记录里已有的字段。"
    )
  );
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") window.location.hash = "#/capabilities";
  });
  return panel;
}
const DOMAIN_TONE = {
  // VALIDATES is the only green, and it is green about structure. NOT_CHECKED is
  // deliberately warn rather than bad: no verdict was produced, which is not a failure.
  VALIDATES: "ok",
  INVALID: "bad",
  UNREADABLE: "bad",
  NOT_CHECKED: "warn"
};
const DOMAIN_UNREAD = "未读回";
const DOMAIN_UNDECLARED = "未声明";
function domainRead(value) {
  return value ? value : DOMAIN_UNREAD;
}
function domainDeclared(value) {
  return value === void 0 ? DOMAIN_UNREAD : value ?? DOMAIN_UNDECLARED;
}
function domainDependencies(values) {
  if (values === void 0) return DOMAIN_UNREAD;
  if (values === null) return DOMAIN_UNDECLARED;
  return values.length ? values.join(" / ") : "声明为空（无依赖）";
}
function domainVerdict(value) {
  return value === void 0 ? DOMAIN_UNREAD : en(value);
}
function domainTone(value) {
  return value === void 0 ? "warn" : DOMAIN_TONE[value] ?? "warn";
}
function domainPackRow(pack) {
  const go = domainDetailHash(pack.packId);
  const verdict = el(
    "span",
    { class: "tag " + domainTone(pack.validation) },
    domainVerdict(pack.validation)
  );
  return el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, pack.displayName ?? domainRead(pack.directory)),
      el("small", {}, `目录 ${domainRead(pack.directory)} · pack_id ${domainDeclared(pack.packId)} · 版本 ${domainDeclared(pack.version)} · 领域 ${domainDeclared(pack.domain)} · 清单 schema ${domainDeclared(pack.manifestSchemaVersion)} · 依赖 ${domainDependencies(pack.dependencies)}`)
    ),
    verdict,
    go ? el("button", {
      type: "button",
      class: "secondary",
      onclick: () => {
        window.location.hash = go;
      }
    }, "查看详情") : el("span", { class: "muted" }, "无独立地址：清单未声明 pack_id")
  );
}
function domainJoinRow(found, join) {
  if (join === null) {
    return el("span", { class: "muted" }, "列表页不读能力目录；只有打开某个域包的地址才做这次读回。");
  }
  if (join.state === "NOT_READ") {
    return el(
      "span",
      {},
      el("span", { class: "tag warn" }, "未读回"),
      ` ${join.why}。没有读到能力目录，就既不能说有几个关联，也不能说没有关联。`
    );
  }
  if (!found.domain) {
    return el(
      "span",
      {},
      el("span", { class: "tag neutral" }, "无关联键"),
      ` 该域包没有声明领域（pack_id 为 ${domainDeclared(found.packId)} 的清单里 domain 字段缺失），所以没有可查的关联键。这既不是"有 ${join.matched} 条"，也不是"该领域没有能力"。`
    );
  }
  if (join.matched > 0) {
    return el(
      "span",
      {},
      el("span", { class: "tag ok" }, `已接线 ${join.matched} 条`),
      ` 能力目录 ${join.records} 条读回里有 ${join.matched} 条在 axes.domains 声明 ${domainRead(found.domain)}；跳转只做地址切换。`
    );
  }
  if (join.records === 0) {
    return el(
      "span",
      {},
      el("span", { class: "tag warn" }, "目录为空"),
      ' 能力目录这次读回 0 条记录：这是目录本身为空，不能读成"该领域没有能力"。'
    );
  }
  if (join.unclassified >= join.records) {
    return el(
      "span",
      {},
      el("span", { class: "tag neutral" }, "还没有分类"),
      ` 能力目录 ${join.records} 条读回里，声明该领域的有 0 条；而 ${join.unclassified}/${join.records} 条的 domains 轴都在服务自己的未分类轴清单里 —— 这是"分类还没做"，不是"该领域没有能力"。补分类属 DL-FINAL-T06，不由界面猜测。`
    );
  }
  return el(
    "span",
    {},
    el("span", { class: "tag neutral" }, "无已接线关联"),
    ` 能力目录 ${join.records} 条里有 ${join.records - join.unclassified} 条已给出 domains 分类，其中声明 ${domainRead(found.domain)} 的为 0 条 —— 这是"没有已接线关联"，仍不等于"该领域没有能力"：能力目录只覆盖已登记的来源与模型。`
  );
}
function domainDrawer(packs, openId, join = null) {
  if (!openId) return el("div", { class: "cap-drawer-slot", hidden: "" });
  const found = packs.find((pack) => pack.packId === openId) ?? null;
  const row = (label, value) => el(
    "div",
    { class: "cap-drawer-row" },
    el("span", { class: "muted" }, label),
    typeof value === "string" ? el("span", {}, value) : value
  );
  if (!found) {
    return el(
      "section",
      {
        class: "cap-drawer",
        id: "domain-drawer",
        tabindex: "-1",
        "aria-labelledby": "domain-drawer-title"
      },
      el("h3", { id: "domain-drawer-title" }, "详情地址指向的域包不在本批读回里"),
      stateBlock({
        kind: "unknown",
        title: "未找到该域包",
        weight: "neutral",
        producer: `#/domains/${openId} 不在本批 GET /api/domains 的 ${packs.length} 个域包目录读回里；地址本身合法，但域包身份以读回为准。`,
        next: "返回域包登记重选一条；不要按 pack_id 猜测它的判定、版本或依赖。"
      }),
      el(
        "div",
        { class: "uif-row" },
        el("button", {
          type: "button",
          class: "secondary",
          onclick: () => {
            window.location.hash = "#/domains";
          }
        }, "返回域包登记")
      )
    );
  }
  const facts = [
    row("目录", el("span", { class: "mono" }, domainRead(found.directory))),
    row("pack_id", el("span", { class: "mono" }, domainDeclared(found.packId))),
    row("声明领域", domainDeclared(found.domain)),
    row("版本", domainDeclared(found.version)),
    row("清单 schema", el(
      "span",
      { class: "mono" },
      domainDeclared(found.manifestSchemaVersion)
    )),
    row("依赖", domainDependencies(found.dependencies)),
    row("结构判定", el(
      "span",
      { class: "tag " + domainTone(found.validation) },
      domainVerdict(found.validation)
    )),
    row("判定原因", found.validationErrors.length ? el("span", {}, found.validationErrors.join(" ｜ ") + (found.validationErrors.length < (found.validationErrorCount ?? 0) ? `（校验器共 ${found.validationErrorCount} 条，此处每条只取首行）` : "")) : found.validation === "VALIDATES" ? "校验器未给出问题条目（结构级 E1，不是领域能力验收）" : "校验器未给出逐条原因"),
    row("服务备注", found.note ?? "（服务未给备注）"),
    row("能力关联", domainJoinRow(found, join)),
    el(
      "div",
      { class: "cap-drawer-row" },
      el(
        "button",
        {
          type: "button",
          class: "secondary",
          id: "domain-view-capabilities",
          // The condition the tooltip promises travels with the jump. Before this the hash was a
          // bare `#/capabilities`, so the button said "filter by the declared domain" and then
          // showed the unfiltered library -- the one thing a reader could not check from here.
          onclick: () => {
            window.location.hash = capabilityHashForDomain(found.domain);
          },
          disabled: join && join.matched > 0 ? void 0 : "",
          title: join === null ? "列表页不读能力目录；打开某个域包的地址才会做第二次读回。" : join.state === "NOT_READ" ? `没读到能力目录：${join.why}。既不能说有几个关联，也不能说没有。` : join.matched > 0 ? `只做地址跳转，并把“声明领域 = ${found.domain}”带过去：能力目录按 axes.domains 过滤，不启动宿主、不改变资格。` : "没有可跳转的关联：该领域的分类还没接线（原因见上一行）。"
        },
        "按该领域查看能力"
      ),
      el(
        "span",
        { class: "muted" },
        "这一行的每个数字都来自本路由第二次读回 ",
        el("span", { class: "mono" }, domainRead("GET /api/capabilities")),
        "；关联键只用能力记录自己声明的 ",
        el("span", { class: "mono" }, domainRead("axes.domains")),
        "，不拿 capability.domain 的字符串巧合当关联。"
      )
    )
  ];
  const panel = el(
    "section",
    {
      class: "cap-drawer",
      id: "domain-drawer",
      tabindex: "-1",
      "aria-labelledby": "domain-drawer-title"
    },
    el(
      "div",
      { class: "cap-drawer-head" },
      el(
        "h3",
        { id: "domain-drawer-title" },
        found.displayName ?? domainRead(found.directory)
      ),
      el("button", {
        type: "button",
        class: "secondary",
        id: "domain-drawer-close",
        onclick: () => {
          window.location.hash = "#/domains";
        }
      }, "返回域包登记")
    ),
    ...facts,
    el(
      "p",
      { class: "view-hint" },
      "这里的每一项都来自 GET /api/domains 对这一个目录的读回；判定词来自仓内校验器 ",
      el("span", { class: "mono" }, domainRead("design-lab/scripts/verify_domain_pack_v2.py")),
      "。",
      en("VALIDATES"),
      " 只说明结构合规。"
    )
  );
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") window.location.hash = "#/domains";
  });
  return panel;
}
async function renderAutomationConnectors(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回自动化连接器登记…"));
  const answer = await apiOrEmpty(
    "/automation-connectors",
    OFFLINE.automationConnectors
  );
  const notice = shapeNotice(answer);
  const rows = answer.connectors ?? [];
  const counts = answer.counts;
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "自动化连接器"),
      el(
        "p",
        { class: "muted" },
        answer.meaning,
        "两个来源分别标记为 ",
        el("span", { class: "value-mono" }, `注册表 ${answer.registry_state}`),
        " 与 ",
        el("span", { class: "value-mono" }, `投递包 ${answer.pack_state}`),
        "。",
        answer.unprobedMeans
      )
    ),
    el("div", { class: "page-actions" })
  );
  const kpis = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(rows.length), "已登记连接器", "本项目注册表与投递包登记的条数"),
    kpiCard(String(counts.probed_by_design_lab), "本项目已探测", "为零就是说从未探测过，不是探测失败"),
    kpiCard(String(counts.enabled), "已启用", "owner 2026-10-28 未授权启用任何一个"),
    kpiCard(
      String(counts.native_tool_calls_executed),
      "原生工具调用",
      "本轮为零；包里逐条 nativeToolCalled:false"
    )
  );
  const table = el("ul", { class: "list" }, ...rows.map((row) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, row.id),
      el("small", {}, [
        row.transport ?? "传输未声明",
        row.design_lab_state,
        row.design_lab_enabled ? "已启用" : "未启用",
        row.activation === "NOT_ACTIVATED_BY_OWNER" ? "owner 明确不启用" : "未申请启用",
        row.handshaked_in_pack_evidence ? `包内证据：握手过，列得 ${row.tools_listed_in_pack_evidence ?? 0} 条工具` : "包内证据：未握手",
        row.same_named_project_adapters.length ? `同名既有注册行 ${row.same_named_project_adapters.length} 条（仅同名，未判定同一上游）` : "本项目此前没有同名注册行",
        `权利 ${row.rights}`
      ].join(" · "))
    ),
    el(
      "div",
      { class: "actions" },
      el(
        "span",
        { class: `tag ${row.design_lab_enabled ? "info" : "warn"}` },
        row.design_lab_enabled ? "已启用" : "未启用"
      )
    )
  )));
  const closed = el(
    "section",
    { class: "panel" },
    el("p", { class: "eyebrow" }, "NOT ACTIVATED"),
    el("h3", {}, "留在关闭位的"),
    el(
      "ul",
      { class: "items-stack" },
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "windows 桌面 UI 自动化"),
          el("small", {}, "受控 UI 自动化这一档本轮不启用；启用需要 owner 另给明确授权。")
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "真启动宿主软件 / 调用任何工具"),
          el("small", {}, "逐次的 Human Gate 决定；这一屏不提供该动作。")
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "包内 21 个真实公司名品牌模板"),
          el("small", {}, "商标与许可归属仍待 Rights gate，本轮只逐字节登记。")
        )
      )
    ),
    el(
      "p",
      { class: "view-hint" },
      `惰性隔离的第三方指令体（SKILL.md 等）读数：${answer.inert_instruction_blobs ?? "未读回"}；`,
      " 它们不进入本项目的指令面、prompt、工具发现或能力计数。"
    )
  );
  const claims = el(
    "section",
    { class: "panel" },
    el("p", { class: "eyebrow" }, "这一屏没有说的事"),
    el("ul", { class: "items-stack" }, ...(answer.claims_not_made ?? []).map((line) => el(
      "li",
      { class: "list-item" },
      el("div", {}, el("small", {}, line))
    ))),
    el(
      "p",
      { class: "view-hint" },
      "证据等级上限：",
      answer.evidence_ceiling || "未读回，因此本页不下等级结论。"
    )
  );
  target.replaceChildren(
    pageHead,
    kpis,
    ...notice ? [el("p", { class: "error", role: "alert" }, `未读回：${notice}`)] : [],
    table,
    closed,
    claims
  );
}
async function renderDomains(target, opts = {}) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回域包…"));
  const data = await apiOrEmpty("/domains", OFFLINE.domains);
  const packs = data.packs.map((pack) => ({
    ...pack,
    validationErrors: Array.isArray(pack.validationErrors) ? pack.validationErrors : []
  }));
  const tallies = data.counts.byValidation;
  const findings = packs.filter((pack) => pack.validation !== "VALIDATES");
  const judged = (state) => packs.filter((pack) => pack.validation === state).length;
  const truncated = findings.filter((pack) => pack.validationErrors.length < (pack.validationErrorCount ?? pack.validationErrors.length));
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "设计领域"),
      el(
        "p",
        { class: "muted" },
        "域包清单、身份与判定全部来自 ",
        el("span", { class: "mono" }, domainRead(data.root)),
        " 的服务端读回；判定由仓内校验器 ",
        el("span", { class: "mono" }, domainRead(data.checker.path)),
        " 逐包给出。",
        en("VALIDATES"),
        " 只表示结构（E1）合规：不是宿主运行、不是设计验收、也不是该领域能力已被认定。未声明与未读回是两件事，分开写。"
      )
    ),
    el("div", { class: "page-actions" })
  );
  const kpis = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(packs.length), "域包目录", `${domainRead(data.root)} 读回`),
    kpiCard(String(judged("VALIDATES")), "结构校验通过", "校验器判定，E1 结构级"),
    kpiCard(String(judged("INVALID")), "校验不通过", "下方逐项列出校验器原因"),
    kpiCard(
      String(packs.length - judged("VALIDATES")),
      "未通过 / 无判定",
      "校验不通过、清单读不到或未产生判定，逐项见下方"
    )
  );
  const unavailable = [];
  if (data.rootState !== "PRESENT") {
    unavailable.push(`域包根 ${domainRead(data.root)} 的状态是 ${domainRead(data.rootState)}，没有目录被列出`);
  }
  if (data.checker.state !== "LOADED") {
    unavailable.push(`校验器 ${domainRead(data.checker.path)} 未能载入${data.checker.note ? `（${data.checker.note}）` : ""}，因此没有任何域包获得判定`);
  }
  const banner = unavailable.length ? [el("p", { class: "error" }, "未读回判定基础：" + unavailable.join("；") + "。")] : [];
  const entries = Object.entries(tallies);
  const tallyLine = el(
    "p",
    { class: "view-hint" },
    entries.length ? `判定分布（路由统计）：${entries.map(([state, count]) => `${state} ${count}`).join(" · ")}` : disconnectedNotice(data) ? `判定分布未读回：${disconnectedNotice(data)}` : "判定分布为空：本次读回没有给出判定计数，逐包状态见上方列表"
  );
  const packList = el(
    "div",
    { class: "panel" },
    el("h3", {}, `域包登记（${packs.length}）`),
    el(
      "ul",
      { class: "list" },
      ...packs.length ? packs.map(domainPackRow) : [emptyLi(
        data,
        shapeFieldMissing(data, "packs") ? "未读回" : "尚无域包目录",
        shapeFieldMissing(data, "packs") ? "响应没有给出 packs，所以这一屏不是服务端答出来的空台账" : `${domainRead(data.root)} 下没有可读回的域包目录`
      )]
    ),
    tallyLine
  );
  const findingPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, `结构校验发现（${findings.length}）`),
    ...findings.length ? findings.map((pack) => el(
      "p",
      { class: "view-hint" },
      el("span", { class: "mono" }, domainRead(pack.directory)),
      " · ",
      domainVerdict(pack.validation),
      `：${pack.validationErrors.length ? pack.validationErrors.join(" ｜ ") : "（校验器未给出逐条原因）"}`,
      pack.validationErrors.length < (pack.validationErrorCount ?? 0) ? `（校验器共 ${pack.validationErrorCount} 条，此处每条只取首行）` : "",
      pack.note ? ` 备注：${pack.note}` : ""
    )) : [el(
      "p",
      { class: "view-hint" },
      data.checker.state === "LOADED" && data.rootState === "PRESENT" ? "本次读回的每个域包目录都通过结构校验；这不构成领域能力验收。" : "没有可报告的发现，因为判定基础本身未读回（见上方告警）。"
    )]
  );
  let join = null;
  if (opts.openId) {
    const caps = await apiOrEmpty("/capabilities", OFFLINE.capabilities);
    const unread = disconnectedNotice(caps) || shapeNotice(caps);
    const rows = Array.isArray(caps.capabilities) ? caps.capabilities : [];
    const slug = packs.find((pack) => pack.packId === opts.openId)?.domain ?? null;
    const unclassified = domainsUnclassified;
    join = unread ? { state: "NOT_READ", records: 0, matched: 0, unclassified: 0, why: unread } : {
      state: "READ",
      records: rows.length,
      matched: slug ? rows.filter((row) => declaredDomains(row).includes(slug)).length : 0,
      unclassified: rows.filter(unclassified).length,
      why: ""
    };
  }
  target.replaceChildren(
    pageHead,
    kpis,
    ...banner,
    domainDrawer(packs, opts.openId ?? null, join),
    packList,
    findingPanel,
    el(
      "p",
      { class: "view-hint" },
      `${domainRead(data.meaning)} ${domainRead(data.unmeasuredMeans)}` + (truncated.length ? `（其中 ${truncated.length} 项的校验原因按每条首行截断）` : "") + " 本页不安装、不生成、不改写域包，也不判定设计质量。"
    ),
    ...shapeNoticeRows(data)
  );
}
async function renderSettings(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回运行环境…"));
  const [env, catalog, knowledge] = await Promise.all([
    apiOrEmpty("/environment", OFFLINE.environment),
    apiOrEmpty("/models", OFFLINE.models),
    apiOrEmpty(
      "/knowledge-entries/search?limit=1",
      OFFLINE.knowledgeLibrary
    )
  ]);
  const catalogOffline = disconnectedNotice(catalog);
  const knowledgeOffline = disconnectedNotice(knowledge);
  const rows = [
    { label: "环境状态", value: env.status, long: false },
    { label: "诊断契约", value: env.schemaVersion, long: true },
    { label: "项目根", value: env.project_root, long: true },
    { label: "项目本地根", value: env.project_local_root, long: true },
    { label: "写入痕迹", value: `写入 ${env.write_trace} · 迁移 ${env.migration}`, long: false },
    { label: "代理配置", value: `${env.agent_profile.status} · ${env.agent_profile.writable ? "可写" : "不可写"}`, long: false }
  ];
  const writablePill = (writable) => el(
    "span",
    { class: "tag " + (writable ? "warn" : "info") },
    writable ? "声明可写（未探测）" : "只读"
  );
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "系统设置"),
      el("p", {}, "这一页只收四件事：模型服务、目标工具档案、导入更新、备份与诊断。设置只读回服务端诊断，不修改任何配置；没有读回的项不用默认值代替。")
    ),
    el("div", { class: "page-actions" })
  );
  const modelsPanel = el(
    "section",
    { class: "panel", id: "settings-models" },
    el("h3", {}, "模型服务"),
    ...catalogOffline ? [el("p", { class: "error" }, `${catalogOffline}；模型候选、端点与资格计数都未读回。`)] : [
      el(
        "ul",
        { class: "list" },
        valueRow("目录契约", catalog.schemaVersion, true),
        valueRow("观测时间", catalog.observed_at ?? "未记录", false),
        valueRow(
          "候选 / 可调用端点",
          `${catalog.counts.models} / ${catalog.counts.endpoints}`,
          false
        ),
        valueRow("合格本地模型", String(catalog.counts.qualified_local), false),
        valueRow("默认启用", String(catalog.counts.default_enabled_true), false),
        valueRow(
          "选择传输",
          `${catalog.selection.transport} · executed=${String(catalog.selection.executed)}`,
          true
        )
      ),
      el(
        "p",
        { class: "view-hint" },
        '选择按项目记录，记下的只是"谁在什么时候选了哪个"；它不代表加载、推理或发送。默认 fail-closed 与"用户能选"是两件事：选了也不改变合格状态。'
      )
    ],
    el(
      "div",
      { class: "kb-actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/models";
        }
      }, "打开模型选择")
    )
  );
  const targetProfilesPanel = el(
    "section",
    { class: "panel", id: "settings-target-profiles" },
    el("h3", {}, "目标工具档案"),
    // 2026-10-24 DL-KB-09/10：这一节此前写着"本服务没有档案路由，也没有可读回的档案行"。那句话
    // 当时是真的，现在不是：/api/target-profile-axes、/api/target-profiles（读与写）、
    // /api/target-profiles/{id} 与 …/validate 五条路由已经上线，屏上也真的在读它们。留着旧句
    // 会让下一会话错误地不信任远端已经存在的能力，所以改成按读回说话。
    el(
      "p",
      { class: "view-hint" },
      '目标工具档案（软件 × 模型 × 接入方式 × 任务模式）由本服务的档案路由读回，在「目标组合」那一屏逐项显示官方支持与本项目未测试。档案里的字段按出处分级，"本项目实测"这一项本轮恒为空：没有任何外部产品或模型被运行过。'
    ),
    el(
      "div",
      { class: "kb-actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/target-profiles";
        }
      }, "打开目标组合"),
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/tools";
        }
      }, "创作工具现状"),
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/models";
        }
      }, "模型候选")
    )
  );
  const importPanel = el(
    "section",
    { class: "panel", id: "settings-import" },
    el("h3", {}, "导入更新"),
    el(
      "p",
      { class: "view-hint" },
      "知识条目的新增、修订、导入与「导入新版本并替代」都在知识与提示词库：导入只写本机服务、不抓取来源，旧版本保留不覆盖。"
    ),
    el(
      "p",
      { class: "view-hint" },
      '本服务没有联网更新或安装包通道；这一页不提供"检查更新"按钮，也不宣称有新版本。'
    ),
    el(
      "div",
      { class: "kb-actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/knowledge";
        }
      }, "打开知识与提示词库")
    )
  );
  const indexLine = knowledgeOffline ? el("p", { class: "error" }, `${knowledgeOffline}；检索索引状态未读回。`) : el(
    "p",
    {},
    `知识条目 ${knowledge.index.rows} 条 · 派生索引 ${knowledge.index.indexed} 行` + (knowledge.index.rebuilt_at ? ` · 上次重建 ${knowledge.index.rebuilt_at}` : "") + (knowledge.index.indexed === knowledge.index.rows ? "" : "（不完整，可在库内重建）")
  );
  const backupPanel = el(
    "section",
    { class: "panel", id: "settings-backup" },
    // 面板标题与首行不能再同名（此前两处都叫"环境状态"，读起来像重复）；标题说明这是
    // 哪一类信息，行内才是值。
    el("h3", {}, "备份与诊断"),
    el(
      "ul",
      { class: "list" },
      ...rows.map((r) => valueRow(
        r.label,
        r.value,
        r.long,
        r.label === "代理配置" ? "warn" : "info"
      ))
    ),
    indexLine,
    el(
      "p",
      { class: "view-hint" },
      '本服务没有备份路由：备份是文件系统操作，这一页不伪造"备份"按钮。写入以追加方式保存，诊断读数来自本次实时读回。'
    )
  );
  target.replaceChildren(
    pageHead,
    el("div", { class: "two-col" }, modelsPanel, targetProfilesPanel),
    el("div", { class: "two-col" }, importPanel, backupPanel),
    el(
      "details",
      { class: "advanced" },
      el("summary", {}, "服务端路径诊断（默认收起）"),
      el(
        "div",
        { class: "advanced-body" },
        el(
          "div",
          { class: "three-col" },
          el(
            "div",
            { class: "panel" },
            el("h3", {}, "项目根（服务声明可写，未探测）"),
            el(
              "ul",
              { class: "list" },
              ...Object.keys(env.roots).length ? Object.entries(env.roots).map(([name, root]) => el(
                "li",
                { class: "list-item" },
                el("div", {}, el("strong", {}, name), el("small", {}, root.path)),
                writablePill(root.writable)
              )) : [emptyLi(env, "尚无根登记", "服务未返回 roots")]
            )
          ),
          el(
            "div",
            { class: "panel" },
            el("h3", {}, "外置输入（只读 · DECLARED_NOT_PROBED）"),
            el(
              "ul",
              { class: "list" },
              ...Object.keys(env.shared_inputs).length ? Object.entries(env.shared_inputs).map(([name, input]) => el(
                "li",
                { class: "list-item" },
                el("div", {}, el("strong", {}, name), el("small", {}, input.path)),
                el("span", { class: "tag info" }, input.status)
              )) : [emptyLi(env, "尚无外置输入", "服务未返回 shared_inputs")]
            )
          )
        )
      )
    ),
    el("p", { class: "view-hint" }, "代理配置私有状态不可写：PRIVATE_NOT_INSPECTED · 不可写。本服务不读取、不打印任何凭据。"),
    ...shapeNoticeRows(env, catalog, knowledge)
  );
}
const KB_STRATEGY_MEANING = {
  BROWSE: "没有检索词，按写入时间从新到旧浏览",
  TRIGRAM: "全部检索词都由 FTS5 trigram 索引回答",
  SHORT_FALLBACK: "检索词短于 3 个字符，trigram 索引答不了，由子串回退命中",
  MIXED: "部分检索词由索引回答；索引答空或过短的词走子串回退"
};
const KB_FIELD_LABELS = {
  title: "标题",
  summary: "摘要",
  body: "正文",
  domain_tags: "领域标签",
  task_tags: "任务标签",
  target_tools: "目标工具"
};
function showCopyFallback(text, note) {
  const area = el("textarea", {
    class: "input as-copy-fallback",
    rows: "6",
    readonly: "readonly"
  });
  area.value = text;
  note.replaceChildren(el(
    "span",
    {},
    "浏览器没有允许写入剪贴板：文本已在下方展开并选中，按 Ctrl+C 复制。这只是复制，不是选用。"
  ), area);
  area.focus();
  area.select();
}
function kbTypeLabel(vocabulary, value) {
  return vocabulary.find((option) => option.value === value)?.label ?? value;
}
function kbTagList(raw) {
  return raw.split(/[,，、;；]/).map((value) => value.trim()).filter(Boolean);
}
function kbSourceRows(source) {
  return [
    valueRow("来源 ID", source.sourceId, true),
    valueRow("来源版本", source.version, false),
    valueRow("出处", source.origin, true),
    valueRow("作者", source.author, true),
    valueRow(
      "许可",
      source.license,
      false,
      source.license === "UNKNOWN" ? "neutral" : "info"
    ),
    valueRow(
      "许可状态",
      source.licenseStatus,
      false,
      source.licenseStatus === "reviewed" ? "ok" : source.licenseStatus === "reference-only" ? "warn" : "neutral"
    ),
    valueRow("允许用途", source.allowedUsage, true),
    valueRow("引用范围", source.citationScope, true),
    valueRow("观测时间", source.observedAt, false),
    valueRow("来源内容哈希", source.contentHash, true),
    valueRow(
      "核验状态",
      source.verification,
      false,
      source.verification === "UNVERIFIED" ? "warn" : "neutral"
    )
  ];
}
function kbEntryBlocks(doc, vocabulary) {
  return [
    el(
      "div",
      { class: "kb-badges kb-badges-start" },
      el("span", { class: "tag info" }, kbTypeLabel(vocabulary, doc.entry_type)),
      el(
        "span",
        { class: "tag " + (doc.recommended ? "ok" : "neutral") },
        doc.recommended ? "推荐版本" : "非推荐版本"
      ),
      el("span", { class: "tag neutral" }, `r${doc.revision}`)
    ),
    el("p", { class: "kb-body" }, doc.body),
    el(
      "ul",
      { class: "list" },
      valueRow("摘要", doc.summary, true),
      valueRow("适用场景", doc.applicability, true),
      valueRow("边界与反例", doc.limits, true),
      valueRow("领域标签", doc.domain_tags.join("、"), true),
      valueRow("任务标签", doc.task_tags.join("、"), true),
      valueRow("适用目标", doc.target_tools.join("、"), true),
      valueRow(
        "关联能力",
        doc.related_capability_ids.length ? doc.related_capability_ids.join("、") : "（无）",
        true
      ),
      valueRow("内容哈希", doc.content_sha256, true),
      valueRow("写入时间 / 记录人", `${doc.created_at} · ${doc.created_by}`, true),
      valueRow("取代", doc.supersedes ?? "（无）", true)
    )
  ];
}
const KB_JUDGEMENT_KIND_LABELS = {
  RECOMMENDATION: "推荐版本",
  SOURCE_STATE: "来源状态"
};
const KB_SOURCE_STATE_LABELS = { ACTIVE: "仍然有效", INVALID: "已失效" };
const REFERENCE_KIND_LABELS = {
  ASSET: "素材",
  BRIEF: "需求 Brief",
  DIRECTION: "方向",
  PROMPT_RESULT: "提示词结果",
  KNOWLEDGE: "知识条目"
};
function kbJudgementSentence(item) {
  if (!item) return "";
  const who = `${item.recorded_by} 于 ${item.recorded_at}`;
  if (item.kind === "RECOMMENDATION") return `推荐 r${item.revision} —— ${who}记下，理由：${item.reason}`;
  return `${KB_SOURCE_STATE_LABELS[item.value ?? ""] ?? en(item.value ?? "")}${item.replaced_by ? `，替代条目 ${item.replaced_by}` : ""} —— ${who}记下，理由：${item.reason}`;
}
function kbJudgementList(judgements) {
  return el("ul", { class: "list" }, ...judgements.map((item) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, KB_JUDGEMENT_KIND_LABELS[item.kind] ?? en(item.kind)),
      el("small", {}, kbJudgementSentence(item))
    ),
    el("span", { class: "tag neutral" }, item.judgement_id)
  )));
}
function kbJudgementPanel(detail, judge) {
  const basis = detail.recommendation_basis === "recorded-judgement" ? `当前推荐 r${detail.recommended_revision} 来自一次后来记下的判断，不是写入时的标记。` : detail.recommendation_basis === "written-flag" ? `当前推荐 r${detail.recommended_revision} 是写入那个版本时一起记下的标记；之后没有人改过。` : "当前没有推荐版本：没有人写下推荐，服务也不会自动排一个。";
  const source = detail.source_state ? `来源状态：${kbJudgementSentence(detail.source_state)}` : "来源状态没有人说过——「没有人说过」不等于「来源没问题」。";
  const revision = el(
    "select",
    {
      id: "kb-judge-revision",
      class: "input",
      "aria-label": "要推荐哪一个已存下的修订"
    },
    ...detail.revisions.map((row) => el(
      "option",
      { value: String(row.revision) },
      `r${row.revision} · ${row.title}${row.readable ? "" : " · JSON 不可读"}`
    ))
  );
  const preferred = detail.recommended_revision ?? detail.latest_revision;
  if (preferred !== null) revision.value = String(preferred);
  const reason = el("input", {
    id: "kb-judge-reason",
    class: "input",
    maxlength: "300",
    placeholder: "为什么改推荐这一版（必填）",
    "aria-label": "改推荐理由"
  });
  const decider = el("input", {
    id: "kb-judge-name",
    class: "input",
    maxlength: "80",
    placeholder: "记录人姓名（必填）",
    "aria-label": "推荐判断的记录人"
  });
  const recommendNotice = el("div", { role: "status", "aria-live": "polite" });
  const recommendSubmit = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "kb-judge-submit"
  }, "记录推荐判断");
  recommendSubmit.onclick = () => {
    if (!reason.value.trim()) {
      recommendNotice.replaceChildren(el(
        "p",
        { class: "error" },
        "判断必须写出理由：没有理由的排序，服务会直接拒绝。"
      ));
      return;
    }
    if (!decider.value.trim()) {
      recommendNotice.replaceChildren(el(
        "p",
        { class: "error" },
        "必须填上记录人：验收只接受具名真人，这一页不会替你铸造一个名字。"
      ));
      return;
    }
    recommendSubmit.disabled = true;
    recommendNotice.replaceChildren(el("p", { class: "view-loading" }, "正在记录…"));
    void (async () => {
      try {
        await judge({
          kind: "RECOMMENDATION",
          revision: Number(revision.value),
          value: null,
          replaced_by: null,
          reason: reason.value.trim(),
          recorded_by: decider.value.trim(),
          recorded_by_kind: "HUMAN"
        });
        recommendNotice.replaceChildren(el("p", {}, "已记下，正在按服务的答案读回这条判断。"));
      } catch (error) {
        recommendNotice.replaceChildren(el("p", { class: "error" }, `记录或读回失败：${errMsg(error)}`));
        recommendSubmit.disabled = false;
      }
    })();
  };
  const stateValue = el(
    "select",
    {
      id: "kb-source-value",
      class: "input",
      "aria-label": "来源现在的状态"
    },
    el("option", { value: "ACTIVE" }, KB_SOURCE_STATE_LABELS.ACTIVE),
    el("option", { value: "INVALID" }, KB_SOURCE_STATE_LABELS.INVALID)
  );
  const replacement = el("input", {
    id: "kb-source-replacement",
    class: "input",
    placeholder: "kentry-…（标记失效时必填：用哪一条替代）",
    "aria-label": "替代条目编号"
  });
  const sourceReason = el("input", {
    id: "kb-source-reason",
    class: "input",
    maxlength: "300",
    placeholder: "为什么这样判定（必填）",
    "aria-label": "来源判定理由"
  });
  const sourceDecider = el("input", {
    id: "kb-source-name",
    class: "input",
    maxlength: "80",
    placeholder: "记录人姓名（必填）",
    "aria-label": "来源判断的记录人"
  });
  const sourceNotice = el("div", { role: "status", "aria-live": "polite" });
  const sourceSubmit = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "kb-source-submit"
  }, "记录来源判断");
  sourceSubmit.onclick = () => {
    const invalid = stateValue.value === "INVALID";
    if (invalid && !replacement.value.trim()) {
      sourceNotice.replaceChildren(el(
        "p",
        { class: "error" },
        "标记失效必须写出替代条目的编号：一个打不开的替代不是替代，服务会拒绝。"
      ));
      return;
    }
    if (!sourceReason.value.trim() || !sourceDecider.value.trim()) {
      sourceNotice.replaceChildren(el(
        "p",
        { class: "error" },
        "理由与记录人都必填：这条判断只接受具名真人写明为什么。"
      ));
      return;
    }
    sourceSubmit.disabled = true;
    sourceNotice.replaceChildren(el("p", { class: "view-loading" }, "正在记录…"));
    void (async () => {
      try {
        await judge({
          kind: "SOURCE_STATE",
          revision: null,
          value: stateValue.value,
          replaced_by: invalid ? replacement.value.trim() : null,
          reason: sourceReason.value.trim(),
          recorded_by: sourceDecider.value.trim(),
          recorded_by_kind: "HUMAN"
        });
        sourceNotice.replaceChildren(el("p", {}, "已记下，正在按服务的答案读回这条判断。"));
      } catch (error) {
        sourceNotice.replaceChildren(el("p", { class: "error" }, `记录或读回失败：${errMsg(error)}`));
        sourceSubmit.disabled = false;
      }
    })();
  };
  return el(
    "div",
    { class: "kb-judgements" },
    el("h4", {}, "判断与来源状态（真人记录，不改写任何版本）"),
    el(
      "p",
      { class: "view-hint" },
      `${basis} ${source} 修订行是只追加的，所以「把推荐退回旧版本」只能靠这样一条记录表达：写下判断不会新增修订，也不会改动任何已存字节。`
    ),
    ...detail.judgements.length ? [kbJudgementList(detail.judgements)] : [el(
      "p",
      { class: "muted" },
      "还没有人记下判断：下面两个表单是这条判断的第一次记录。"
    )],
    el(
      "div",
      { class: "kb-judge-grid" },
      el(
        "div",
        {},
        fieldRow("推荐哪一个已存版本", revision, "kb-judge-revision"),
        fieldRow("理由", reason, "kb-judge-reason"),
        fieldRow("记录人", decider, "kb-judge-name"),
        el("div", { class: "kb-actions" }, recommendSubmit),
        recommendNotice
      ),
      el(
        "div",
        {},
        fieldRow("来源状态", stateValue, "kb-source-value"),
        fieldRow("替代条目（仅失效时必填）", replacement, "kb-source-replacement"),
        fieldRow("理由", sourceReason, "kb-source-reason"),
        fieldRow("记录人", sourceDecider, "kb-source-name"),
        el("div", { class: "kb-actions" }, sourceSubmit),
        sourceNotice
      )
    )
  );
}
function kbDetailPanel(detail, vocabulary, actions) {
  const current = detail.current;
  const sameRevision = detail.recommended_revision !== null && detail.recommended_revision === detail.latest_revision;
  const headBadges = [
    el(
      "span",
      { class: "tag " + (detail.status === "ACTIVE" ? "ok" : "neutral") },
      en(detail.status)
    ),
    sameRevision ? el("span", { class: "tag ok" }, `最新 r${detail.latest_revision} · 推荐版本`) : el("span", { class: "tag info" }, `最新 r${detail.latest_revision ?? "？"}`)
  ];
  if (detail.recommended_revision === null) {
    headBadges.push(el("span", { class: "tag neutral" }, "无推荐版本"));
  } else if (!sameRevision) {
    headBadges.push(el("span", { class: "tag warn" }, `推荐 r${detail.recommended_revision}`));
  }
  const children = [
    el(
      "div",
      { class: "kb-detail-head" },
      el(
        "div",
        {},
        el("h3", {}, current ? current.title : `条目 ${detail.knowledge_entry_id}`),
        el("p", { class: "value-mono" }, detail.knowledge_entry_id)
      ),
      el("div", { class: "kb-badges" }, ...headBadges)
    )
  ];
  if (detail.superseded_by) {
    children.push(el(
      "p",
      { class: "view-hint" },
      "这条条目已被取代，取代它的是 ",
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => actions.open(detail.superseded_by)
      }, detail.superseded_by)
    ));
  }
  if (!current) {
    children.push(el(
      "p",
      { class: "error" },
      `最新版本的 JSON 无法解析（不可读版本 ${detail.unreadable_count} 个）：本次读回不展示正文，也不猜测它的内容。`
    ));
  } else {
    children.push(...kbEntryBlocks(current, vocabulary));
    children.push(el("h4", {}, "来源与许可"));
    children.push(el("ul", { class: "list" }, ...kbSourceRows(current.source)));
    const copyNote = el("p", { class: "view-hint", role: "status", id: "kb-copy-status" });
    const copyButton = el(
      "button",
      { type: "button", class: "ghost-btn", id: "kb-copy-body" },
      "复制正文"
    );
    copyButton.onclick = () => {
      const text = current.body;
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          copyNote.textContent = `已复制正文 ${text.length} 个字符：这只是复制到剪贴板，没有发送任何东西，也没有改动条目。`;
        }, () => showCopyFallback(text, copyNote));
        return;
      }
      showCopyFallback(text, copyNote);
    };
    children.push(el(
      "div",
      { class: "kb-actions" },
      el("button", {
        type: "button",
        class: "primary-btn",
        onclick: () => actions.revise(current)
      }, "修订为新版本"),
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => actions.importReplace(current)
      }, "导入新版本并替代"),
      copyButton
    ), copyNote);
  }
  if (detail.recommended && detail.recommended_revision !== detail.latest_revision) {
    children.push(el(
      "h4",
      {},
      `推荐版本 r${detail.recommended_revision}（不是最新 r${detail.latest_revision}）`
    ));
    children.push(el(
      "p",
      { class: "view-hint" },
      detail.recommendation_basis === "recorded-judgement" ? "这个推荐版本是后来有人记下的判断，不是写入时的标记，也不是自动排序；下面是那个版本的正文。" : "推荐版本是写入时记录下来的判断，不是自动排序；下面是那个版本的正文。"
    ));
    children.push(...kbEntryBlocks(detail.recommended, vocabulary));
  }
  children.push(kbJudgementPanel(detail, actions.judge));
  children.push(el("h4", {}, "修订历史（旧版本保留，不覆盖）"));
  children.push(el("ul", { class: "list" }, ...detail.revisions.map((revision) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, `r${revision.revision} · ${revision.title}`),
      el(
        "small",
        {},
        `${revision.created_at} · ${revision.created_by}` + (revision.readable ? "" : " · JSON 不可读")
      ),
      el("small", { class: "value-mono" }, revision.content_sha256)
    ),
    el(
      "div",
      { class: "kb-badges" },
      el(
        "span",
        { class: "tag " + (revision.recommended ? "ok" : "neutral") },
        revision.recommended ? "推荐" : "记录"
      )
    )
  ))));
  if (detail.unreadable_count) {
    children.push(el(
      "p",
      { class: "error" },
      `另有 ${detail.unreadable_count} 个版本行无法解析；它们仍计入历史，不会被隐藏。`
    ));
  }
  if (detail.does_not_say.length) {
    children.push(el("h4", {}, "服务声明它没有说的话"));
    children.push(el("ul", { class: "list" }, ...detail.does_not_say.map((line) => el("li", { class: "list-item" }, line))));
  }
  return el("section", { class: "panel kb-detail-panel" }, ...children);
}
function knowledgeEntryFields(prefix, vocabulary, licenseStates, initial) {
  const entryType = el(
    "select",
    { id: `${prefix}-entry-type`, class: "input" },
    ...vocabulary.length ? vocabulary.map((option) => el("option", { value: option.value }, option.label)) : [el("option", { value: "" }, "类型清单未读回")]
  );
  const title = el("input", {
    id: `${prefix}-title`,
    class: "input",
    maxlength: "160",
    placeholder: "例如：分镜拆解三步法"
  });
  const summary = el("input", {
    id: `${prefix}-summary`,
    class: "input",
    maxlength: "300",
    placeholder: "一句话说明它能解决什么问题"
  });
  const body = el("textarea", {
    id: `${prefix}-body`,
    class: "input",
    rows: "6",
    placeholder: "方法、步骤、提示词或配方正文"
  });
  const applicability = el("input", {
    id: `${prefix}-applicability`,
    class: "input",
    maxlength: "400",
    placeholder: "什么时候适用；留空则服务写 UNKNOWN"
  });
  const limits = el("input", {
    id: `${prefix}-limits`,
    class: "input",
    maxlength: "400",
    placeholder: "边界、反例与失败条件；留空则服务写 UNKNOWN"
  });
  const domainTags = el("input", {
    id: `${prefix}-domains`,
    class: "input",
    placeholder: "例如：film、brand"
  });
  const taskTags = el("input", {
    id: `${prefix}-tasks`,
    class: "input",
    placeholder: "例如：storyboard、naming"
  });
  const targetTools = el("input", {
    id: `${prefix}-targets`,
    class: "input",
    placeholder: "例如：photoshop、figma"
  });
  const related = el("input", {
    id: `${prefix}-related`,
    class: "input",
    placeholder: "capability id，逗号分隔（可选）"
  });
  const sourceId = el("input", {
    id: `${prefix}-source-id`,
    class: "input",
    maxlength: "200",
    placeholder: "例如：internal-style-guide"
  });
  const sourceVersion = el("input", {
    id: `${prefix}-source-version`,
    class: "input",
    maxlength: "120",
    placeholder: "例如：2026-10"
  });
  const sourceOrigin = el("input", {
    id: `${prefix}-source-origin`,
    class: "input",
    maxlength: "400",
    placeholder: "路径或 URL（服务不会去抓取）"
  });
  const sourceAuthor = el("input", {
    id: `${prefix}-source-author`,
    class: "input",
    maxlength: "200",
    placeholder: "原作者或机构"
  });
  const license = el("input", {
    id: `${prefix}-license`,
    class: "input",
    maxlength: "120",
    placeholder: "例如：CC-BY-4.0；留空则 UNKNOWN"
  });
  const licenseStatus = el(
    "select",
    { id: `${prefix}-license-status`, class: "input" },
    ...licenseStates.length ? licenseStates.map((state) => el("option", { value: state }, state)) : [el("option", { value: "" }, "许可状态清单未读回")]
  );
  if (!initial && licenseStates.includes("unknown")) licenseStatus.value = "unknown";
  const allowedUsage = el("input", {
    id: `${prefix}-allowed-usage`,
    class: "input",
    maxlength: "400",
    placeholder: "允许的用途范围"
  });
  const citationScope = el("input", {
    id: `${prefix}-citation-scope`,
    class: "input",
    maxlength: "400",
    placeholder: "引用范围（内部 / 署名 / 不可转引）"
  });
  const author = el("input", {
    id: `${prefix}-author`,
    class: "input",
    maxlength: "120",
    placeholder: "你的名字或代号（必填，服务不持有身份）"
  });
  const recommended = el("input", { type: "checkbox", id: `${prefix}-recommended` });
  const setIf = (input, value) => {
    if (value && value !== "UNKNOWN") input.value = value;
  };
  if (initial) {
    title.value = initial.title;
    summary.value = initial.summary;
    body.value = initial.body;
    setIf(applicability, initial.applicability);
    setIf(limits, initial.limits);
    setIf(domainTags, initial.domain_tags.join("、"));
    setIf(taskTags, initial.task_tags.join("、"));
    setIf(targetTools, initial.target_tools.join("、"));
    setIf(related, initial.related_capability_ids.join("、"));
    setIf(sourceId, initial.source.sourceId);
    setIf(sourceVersion, initial.source.version);
    setIf(sourceOrigin, initial.source.origin);
    setIf(sourceAuthor, initial.source.author);
    setIf(license, initial.source.license);
    setIf(allowedUsage, initial.source.allowedUsage);
    setIf(citationScope, initial.source.citationScope);
    if (vocabulary.some((option) => option.value === initial.entry_type))
      entryType.value = initial.entry_type;
    if (licenseStates.includes(initial.source.licenseStatus))
      licenseStatus.value = initial.source.licenseStatus;
    recommended.checked = initial.recommended;
  } else {
    recommended.checked = true;
  }
  const element = el(
    "div",
    { class: "two-col kb-form-fields" },
    fieldRow("类型", entryType, `${prefix}-entry-type`),
    fieldRow("标题（必填）", title, `${prefix}-title`),
    fieldRow("一句话用途（必填）", summary, `${prefix}-summary`),
    fieldRow("适用目标（逗号分隔）", targetTools, `${prefix}-targets`),
    fieldRow("领域标签（逗号分隔）", domainTags, `${prefix}-domains`),
    fieldRow("任务标签（逗号分隔）", taskTags, `${prefix}-tasks`),
    el(
      "div",
      { class: "kb-span" },
      fieldRow("正文（必填）", body, `${prefix}-body`)
    ),
    el(
      "div",
      { class: "kb-span" },
      fieldRow("适用场景（可选）", applicability, `${prefix}-applicability`)
    ),
    el(
      "div",
      { class: "kb-span" },
      fieldRow("边界与反例（可选）", limits, `${prefix}-limits`)
    ),
    fieldRow("来源 ID", sourceId, `${prefix}-source-id`),
    fieldRow("来源版本", sourceVersion, `${prefix}-source-version`),
    fieldRow("出处（路径或 URL）", sourceOrigin, `${prefix}-source-origin`),
    fieldRow("来源作者", sourceAuthor, `${prefix}-source-author`),
    fieldRow("许可", license, `${prefix}-license`),
    fieldRow("许可状态", licenseStatus, `${prefix}-license-status`),
    fieldRow("允许用途", allowedUsage, `${prefix}-allowed-usage`),
    fieldRow("引用范围", citationScope, `${prefix}-citation-scope`),
    el(
      "div",
      { class: "kb-span" },
      fieldRow("关联能力 ID（逗号分隔，可选）", related, `${prefix}-related`)
    ),
    el(
      "div",
      { class: "kb-span" },
      fieldRow("记录人（必填）", author, `${prefix}-author`)
    ),
    fieldRow("标记为推荐版本", recommended, `${prefix}-recommended`)
  );
  return {
    entryType,
    title,
    summary,
    body,
    applicability,
    limits,
    domainTags,
    taskTags,
    targetTools,
    related,
    sourceId,
    sourceVersion,
    sourceOrigin,
    sourceAuthor,
    license,
    licenseStatus,
    allowedUsage,
    citationScope,
    author,
    recommended,
    element
  };
}
function knowledgeFormPanel(kind, vocabulary, licenseStates, initial, replaceId, onWritten, onCancel) {
  const prefix = kind === "create" ? "kb-new" : kind === "revise" ? "kb-revise" : "kb-import";
  const fields = knowledgeEntryFields(prefix, vocabulary, licenseStates, initial);
  const supersedes = el("input", {
    id: `${prefix}-supersedes`,
    class: "input",
    placeholder: "kentry-…（可选：这条导入替代哪一条）"
  });
  if (replaceId) supersedes.value = replaceId;
  const notice = el("div", { role: "status", "aria-live": "polite" });
  const submit = el(
    "button",
    { type: "button", class: "primary-btn" },
    kind === "revise" ? `提交 r${(initial?.revision ?? 0) + 1}` : kind === "import" ? "导入并读回" : "写入并读回"
  );
  const cancel = el("button", {
    type: "button",
    class: "ghost-btn",
    id: `${prefix}-cancel`,
    onclick: onCancel
  }, "取消");
  const heading = kind === "create" ? "新增条目" : kind === "revise" ? `修订 r${initial?.revision ?? "？"} → r${(initial?.revision ?? 0) + 1}` : "从文件导入";
  const caption = kind === "create" ? "编号由服务生成（kentry-…）；写入后立即读回。来源核验状态永远是 UNVERIFIED——保存不等于核验。" : kind === "revise" ? "旧版本保留，当前版本是最大修订号；提交会带上读到的 expected_revision，冲突时服务拒绝而不是覆盖。" : "同一来源 ID + 版本的同内容再导入返回 DUPLICATE（不写）；不同版本并存，结果里会列出 related_entries。导入不抓取来源。";
  const collect = () => {
    const source = {};
    const fromInput = (key, input) => {
      const value = input.value.trim();
      if (value) source[key] = value;
    };
    fromInput("sourceId", fields.sourceId);
    fromInput("version", fields.sourceVersion);
    fromInput("origin", fields.sourceOrigin);
    fromInput("author", fields.sourceAuthor);
    fromInput("license", fields.license);
    fromInput("allowedUsage", fields.allowedUsage);
    fromInput("citationScope", fields.citationScope);
    if (fields.licenseStatus.value) source.licenseStatus = fields.licenseStatus.value;
    return {
      entry_type: fields.entryType.value,
      title: fields.title.value.trim(),
      summary: fields.summary.value.trim(),
      body: fields.body.value.trim(),
      // Both keys always go on the wire. The create route demands the exact key set, and the store
      // is what turns an empty string into the literal UNKNOWN -- dropping the key here used to make
      // "left 适用场景 blank" fail with a bare INVALID_PROJECT_FIELDS the reader cannot act on
      // (found by the browser walk on 2026-10-24; the DOM harness never caught it because its
      // fixture typed both boxes).
      applicability: fields.applicability.value.trim(),
      limits: fields.limits.value.trim(),
      domain_tags: kbTagList(fields.domainTags.value),
      task_tags: kbTagList(fields.taskTags.value),
      target_tools: kbTagList(fields.targetTools.value),
      related_capability_ids: kbTagList(fields.related.value),
      recommended: fields.recommended.checked,
      source
    };
  };
  const refusalLines = [];
  const clearRefusals = () => {
    refusalLines.splice(0).forEach(({ line, control }) => {
      control.removeAttribute("aria-describedby");
      line.remove();
    });
  };
  const fieldRefusals = () => {
    const problems = [];
    const blank = (input) => !input.value.trim();
    if (!fields.entryType.value)
      problems.push({
        control: fields.entryType,
        label: "类型",
        message: "类型清单未读回（未连接本机服务）：先连接服务，类型选项才会从服务端读回。"
      });
    if (blank(fields.title))
      problems.push({
        control: fields.title,
        label: "标题",
        message: "标题为空：服务把空标题写成 UNKNOWN，这条检索不到，也没法在列表里认出它。"
      });
    if (blank(fields.summary))
      problems.push({
        control: fields.summary,
        label: "一句话用途",
        message: "一句话用途为空：服务把空摘要写成 UNKNOWN，列表里只剩标题。"
      });
    if (blank(fields.body))
      problems.push({
        control: fields.body,
        label: "正文",
        message: "正文为空：方法、步骤或提示词本体还没有内容，服务不会存一条空条目。"
      });
    if (blank(fields.author))
      problems.push({
        control: fields.author,
        label: "记录人",
        message: "记录人为空：服务不持有身份，页面不会替你铸造一个，之后也没人能被找到。" + (kind === "import" ? "导入同样要署名——导入人就是这条的记录人。" : "")
      });
    if (kind === "import" && blank(fields.sourceId))
      problems.push({
        control: fields.sourceId,
        label: "来源 ID",
        message: '来源 ID 为空：重复导入无法和"新版本"区分，服务会直接拒绝这条写入。'
      });
    if (kind === "import" && blank(fields.sourceVersion))
      problems.push({
        control: fields.sourceVersion,
        label: "来源版本",
        message: "来源版本为空：没有版本 pin，同内容的第二次导入无法判定为 DUPLICATE。"
      });
    return problems;
  };
  const paintRefusals = (problems) => {
    clearRefusals();
    problems.forEach((problem) => {
      const line = el("p", { class: "error" });
      if (problem.control.id) {
        line.id = `${problem.control.id}-refusal`;
        line.setAttribute("data-for", problem.control.id);
        problem.control.setAttribute("aria-describedby", line.id);
      }
      line.textContent = problem.message;
      const row = problem.control.closest(".field-row");
      (row ?? problem.control.parentNode ?? problem.control).append(line);
      refusalLines.push({ line, control: problem.control });
    });
    notice.replaceChildren(el(
      "p",
      { class: "error" },
      `${problems.length} 处拦住了这次写入：${problems.map((p) => p.label).join("、")}。每条说明写在它拦住的输入框下面。`
    ));
    problems[0]?.control.focus();
  };
  submit.onclick = () => {
    const problems = fieldRefusals();
    if (problems.length) {
      paintRefusals(problems);
      return;
    }
    clearRefusals();
    submit.disabled = true;
    notice.replaceChildren(el("p", { class: "view-loading" }, "正在写入…"));
    void (async () => {
      try {
        if (kind === "import") {
          const body = collect();
          body.imported_by = fields.author.value.trim();
          body.supersedes = supersedes.value.trim() || null;
          const response = await api("/knowledge-entries/import", body);
          notice.replaceChildren(
            el(
              "p",
              {},
              "导入结果 ",
              el(
                "span",
                { class: "tag " + (response.outcome === "DUPLICATE" ? "warn" : "ok") },
                en(response.outcome)
              ),
              ` · ${response.knowledge_entry_id} · r${response.revision}`
            ),
            el("p", { class: "value-mono" }, en(response.explanation)),
            ...response.related_entries.length ? [el("p", { class: "muted" }, `同源其它版本：${response.related_entries.join("、")}`)] : []
          );
          onWritten(response.knowledge_entry_id);
        } else if (kind === "revise" && initial) {
          const body = collect();
          body.created_by = fields.author.value.trim();
          body.expected_revision = initial.revision;
          const response = await api(
            `/knowledge-entries/${initial.knowledge_entry_id}/revisions`,
            body
          );
          notice.replaceChildren(
            el("p", {}, `已写入 r${response.revision} · ${response.entry.knowledge_entry_id}`),
            el("p", { class: "value-mono" }, response.entry.content_sha256),
            el("p", { class: "muted" }, "旧版本仍在修订历史里；写入不等于核验，也不会导出。")
          );
          onWritten(response.entry.knowledge_entry_id);
        } else {
          const body = collect();
          body.created_by = fields.author.value.trim();
          body.supersedes = null;
          const response = await api("/knowledge-entries", body);
          notice.replaceChildren(
            el("p", {}, `已写入 r${response.revision} · ${response.entry.knowledge_entry_id}`),
            el("p", { class: "value-mono" }, response.entry.content_sha256),
            el("p", { class: "muted" }, "已按服务返回的编号读回；保存不等于核验，也不会导出。")
          );
          onWritten(response.entry.knowledge_entry_id);
        }
      } catch (error) {
        notice.replaceChildren(el("p", { class: "error" }, `写入失败：${errMsg(error)}`));
      } finally {
        submit.disabled = false;
      }
    })();
  };
  return el(
    "section",
    { class: "panel kb-form" },
    el(
      "div",
      { class: "kb-detail-head" },
      el("h3", {}, heading),
      el("span", { class: "tag neutral" }, "真实写入")
    ),
    el("p", { class: "view-hint" }, caption),
    fields.element,
    ...kind === "import" ? [fieldRow("替代哪一条（可选）", supersedes, `${prefix}-supersedes`)] : [],
    el("div", { class: "kb-actions" }, submit, cancel),
    notice
  );
}
async function renderKnowledgeLibrary(target) {
  const query = el("input", {
    id: "kb-query",
    class: "input kb-search",
    type: "search",
    placeholder: "搜索标题、摘要、正文、标签或目标工具（中文短词也可以）",
    "aria-label": "知识检索词"
  });
  const type = el("select", { id: "kb-type", class: "input", "aria-label": "按条目类型筛选" });
  type.append(el("option", { value: "" }, "全部类型"));
  const domain = el("input", {
    id: "kb-domain",
    class: "input",
    placeholder: "领域标签（精确匹配）",
    "aria-label": "按领域标签筛选"
  });
  const task = el("input", {
    id: "kb-task",
    class: "input",
    placeholder: "任务标签（精确匹配）",
    "aria-label": "按任务标签筛选"
  });
  const targetTool = el("input", {
    id: "kb-target",
    class: "input",
    placeholder: "目标工具（精确匹配）",
    "aria-label": "按目标工具筛选"
  });
  const searchButton = el("button", { type: "submit", class: "primary-btn", id: "kb-search" }, "搜索");
  const clearButton = el("button", { type: "button", class: "ghost-btn", id: "kb-clear" }, "清空条件");
  const newButton = el("button", { type: "button", class: "ghost-btn", id: "kb-new" }, "新增条目");
  const importButton = el("button", { type: "button", class: "ghost-btn", id: "kb-import" }, "导入条目");
  const rebuildButton = el("button", { type: "button", class: "ghost-btn", id: "kb-rebuild" }, "重建检索索引");
  const meta = el("div", { class: "kb-meta", role: "status", "aria-live": "polite" });
  meta.replaceChildren(el("p", { class: "view-loading" }, "正在检索…"));
  const results = el("ul", { class: "list", id: "kb-results" });
  const moreHost = el("div", { class: "kb-actions", id: "kb-more" });
  const listPanel = el(
    "section",
    { class: "panel" },
    el("h3", {}, "检索结果"),
    results,
    moreHost
  );
  const detailNote = el("div", { id: "kb-detail-outside" });
  const detailContent = el(
    "div",
    { id: "kb-detail-content" },
    el(
      "section",
      { class: "panel" },
      el("h3", {}, "条目详情"),
      el(
        "p",
        { class: "muted" },
        "从左侧选择一条条目：正文、来源、许可、内容哈希、修订历史与推荐版本都在这里。"
      )
    )
  );
  const detailHost = el("div", { id: "kb-detail" }, detailNote, detailContent);
  const formHost = el("div", { id: "kb-form" });
  const notes = el("div", { id: "kb-notes" });
  let vocabulary = [];
  let licenseStates = [];
  let shown = 0;
  let selectedId = "";
  let visibleIds = /* @__PURE__ */ new Set();
  let pendingNotice = "";
  let committed = false;
  const searchForm = el("form", { class: "toolbar", onsubmit: (event) => {
    event.preventDefault();
    void runSearch(0);
  } }, query, type, domain, task, targetTool, searchButton, clearButton);
  const readFilters = () => {
    const params = new URLSearchParams();
    if (query.value.trim()) params.set("q", query.value.trim());
    if (type.value) params.set("type", type.value);
    if (domain.value.trim()) params.set("domain", domain.value.trim());
    if (task.value.trim()) params.set("task", task.value.trim());
    if (targetTool.value.trim()) params.set("target", targetTool.value.trim());
    return params;
  };
  const load = async (offset) => {
    const params = readFilters();
    params.set("offset", String(offset));
    params.set("limit", "50");
    try {
      const answer = await apiOrEmpty(
        `/knowledge-entries/search?${params.toString()}`,
        OFFLINE.knowledgeLibrary
      );
      pendingNotice = shapeNotice(answer);
      return answer;
    } catch (error) {
      if (!committed) throw error;
      results.replaceChildren();
      moreHost.replaceChildren();
      notes.replaceChildren();
      meta.replaceChildren(el(
        "p",
        { class: "error" },
        `检索失败：${errMsg(error)}（列表已清空，避免把上一次的答案留在这里）`
      ));
      return null;
    }
  };
  function setDetailOutside(outside) {
    detailNote.replaceChildren(...outside ? [el(
      "p",
      { class: "view-hint" },
      "右侧是上次选中的条目，不在本次检索结果里——它不是这次检索的命中。"
    )] : []);
  }
  function renderDetail(detail) {
    detailContent.replaceChildren(kbDetailPanel(detail, vocabulary, {
      open: (id) => {
        void openDetail(id);
      },
      revise: (doc) => openForm("revise", doc, null),
      importReplace: (doc) => openForm("import", doc, doc.knowledge_entry_id),
      // The judgement route answers the entry's own readback, and the honest confirmation is that
      // readback re-rendered -- list badges included -- not a sentence this page wrote about a
      // POST it hopes succeeded.
      judge: async (body) => {
        await api(
          `/knowledge-entries/${detail.knowledge_entry_id}/judgements`,
          body
        );
        await runSearch(0);
        await openDetail(detail.knowledge_entry_id);
      }
    }));
  }
  async function openDetail(id) {
    detailContent.replaceChildren(el("p", { class: "view-loading" }, "正在读回条目…"));
    try {
      const detail = await api(`/knowledge-entries/${id}`);
      selectedId = id;
      renderDetail(detail);
      setDetailOutside(!visibleIds.has(id));
    } catch (error) {
      detailContent.replaceChildren(el("p", { class: "error" }, `条目读回失败：${errMsg(error)}`));
    }
  }
  function openForm(kind, doc, replaceId) {
    formHost.replaceChildren(knowledgeFormPanel(
      kind,
      vocabulary,
      licenseStates,
      doc,
      replaceId,
      (entryId) => {
        void runSearch(0, entryId);
      },
      () => {
        formHost.replaceChildren();
      }
    ));
    formHost.scrollIntoView({ block: "start" });
  }
  const rowFor = (row, showMatch) => {
    const targets = row.target_tools.length ? row.target_tools.join("、") : "UNKNOWN";
    const why = showMatch && row.matched_fields.length ? `命中：${row.matched_fields.map((field) => KB_FIELD_LABELS[field] ?? field).join("、")}（检索词 ${row.matched_terms.join("、")}）` : "";
    const recommendedIsLatest = row.recommended_is_latest && row.recommended_revision !== null;
    const badges = [
      recommendedIsLatest ? el("span", { class: "tag info" }, `最新 r${row.revision} · 推荐版本`) : el("span", { class: "tag info" }, `r${row.revision}`),
      el(
        "span",
        { class: "tag " + (row.status === "ACTIVE" ? "ok" : "neutral") },
        en(row.status)
      )
    ];
    if (row.recommended_revision === null) {
      badges.push(el("span", { class: "tag neutral" }, "无推荐版本"));
    } else if (!recommendedIsLatest) {
      badges.push(el(
        "span",
        { class: "tag warn" },
        `推荐 r${row.recommended_revision} · 非最新`
      ));
    }
    return el(
      "li",
      { class: "list-item kb-row" },
      el(
        "div",
        { class: "kb-row-main" },
        el(
          "button",
          {
            type: "button",
            class: "kb-open",
            onclick: () => {
              void openDetail(row.knowledge_entry_id);
            }
          },
          el("strong", {}, row.title)
        ),
        el("small", {}, row.summary),
        el("small", {}, `适用：${targets}`),
        ...why ? [el("small", { class: "muted" }, why)] : []
      ),
      el("div", { class: "kb-badges" }, ...badges)
    );
  };
  const renderAnswer = (data, append) => {
    committed = true;
    if (data.entryTypes.length) {
      vocabulary = data.entryTypes;
      if (type.options.length !== vocabulary.length + 1) {
        const selected = type.value;
        type.replaceChildren(
          el("option", { value: "" }, "全部类型"),
          ...vocabulary.map((option) => el("option", { value: option.value }, option.label))
        );
        type.value = vocabulary.some((option) => option.value === selected) ? selected : "";
      }
    }
    if (data.licenseStates.length) licenseStates = data.licenseStates;
    const offline = disconnectedNotice(data);
    const activeFilters = [
      data.filters.type,
      data.filters.domain,
      data.filters.task,
      data.filters.target
    ].filter(Boolean);
    if (offline) {
      meta.replaceChildren(
        el("p", { class: "muted" }, offline),
        el(
          "p",
          { class: "muted" },
          "检索策略、索引状态与条目数都未读回：这一页不会用 0 或 BROWSE 代替没有问到的读数。"
        )
      );
    } else {
      const strategy = KB_STRATEGY_MEANING[data.strategy];
      const indexNote = data.index.indexed === data.index.rows ? `索引 ${data.index.indexed}/${data.index.rows}` : `索引 ${data.index.indexed}/${data.index.rows}（不完整，可重建）`;
      meta.replaceChildren(
        el(
          "p",
          {},
          `共 ${data.total} 条`,
          data.query ? ` · 检索词「${data.query}」` : " · 浏览模式",
          activeFilters.length ? ` · 筛选 ${activeFilters.join("、")}` : "",
          " · 策略 ",
          en(data.strategy),
          strategy ? `：${strategy}` : "：本页没有这个策略的解释文案",
          ` · ${indexNote}`
        ),
        ...data.index.indexed !== data.index.rows ? [el(
          "p",
          { class: "error" },
          "派生索引与条目数不一致：这次答案可能不完整；重建索引后重搜。"
        )] : [],
        ...pendingNotice ? [el("p", { class: "error" }, pendingNotice)] : []
      );
    }
    const showMatch = Boolean(data.query);
    if (!append) {
      results.replaceChildren();
      shown = 0;
      visibleIds = new Set(data.entries.map((row) => row.knowledge_entry_id));
    } else {
      for (const row of data.entries) visibleIds.add(row.knowledge_entry_id);
    }
    setDetailOutside(Boolean(selectedId) && !visibleIds.has(selectedId));
    if (!data.entries.length) {
      const condition = Boolean(data.query) || activeFilters.length > 0;
      results.append(el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, offline ? "未读回" : condition ? "没有符合条件的结果" : "当前没有条目"),
          el("small", {}, offline || data.explanation || '服务没有给出解释；本页不会推荐"相近"的条目来填空。')
        )
      ));
      moreHost.replaceChildren();
      notes.replaceChildren();
      return;
    }
    const rows = data.entries.map((row) => rowFor(row, showMatch));
    if (append) results.append(...rows);
    else results.replaceChildren(...rows);
    shown += data.entries.length;
    moreHost.replaceChildren(...data.next_offset === null ? [] : [el("button", {
      type: "button",
      class: "ghost-btn",
      onclick: () => {
        void runSearch(data.next_offset);
      }
    }, `加载更多（已显示 ${shown} / 共 ${data.total}）`)]);
    if (!offline && data.does_not_say.length) {
      notes.replaceChildren(el(
        "p",
        { class: "view-hint" },
        `服务声明：${data.does_not_say.join("；")}`
      ));
    } else {
      notes.replaceChildren();
    }
  };
  async function runSearch(offset, focusId) {
    const data = await load(offset);
    if (!data) return;
    renderAnswer(data, offset > 0);
    if (focusId) await openDetail(focusId);
  }
  clearButton.onclick = () => {
    query.value = "";
    type.value = "";
    domain.value = "";
    task.value = "";
    targetTool.value = "";
    void runSearch(0);
  };
  newButton.onclick = () => openForm("create", null, null);
  importButton.onclick = () => openForm("import", null, null);
  rebuildButton.onclick = () => {
    rebuildButton.disabled = true;
    void (async () => {
      try {
        const response = await api(
          "/knowledge-entries/index-rebuild",
          {}
        );
        const receipt = el(
          "p",
          { class: "view-hint" },
          `索引已重建：${response.indexed} 条 · ${response.rebuilt_at}。重建只动派生索引，不改任何条目。`
        );
        await runSearch(0);
        meta.append(receipt);
      } catch (error) {
        meta.replaceChildren(el("p", { class: "error" }, `重建失败：${errMsg(error)}`));
      } finally {
        rebuildButton.disabled = false;
      }
    })();
  };
  target.replaceChildren(
    el(
      "div",
      { class: "page-head kb-head" },
      el(
        "div",
        {},
        el("h2", {}, "知识与提示词库"),
        el("p", {}, "搜索是这一页的主入口：查规范、方法、提示词、模型指南、配方与案例；列表是检索的答案，不是全表导出。新增、修订与导入都写入本机服务并立刻读回。")
      ),
      el("div", { class: "page-actions" }, newButton, importButton, rebuildButton)
    ),
    searchForm,
    el(
      "p",
      { class: "view-hint" },
      "领域 / 任务 / 目标工具是标签的精确匹配筛选。检索只匹配标题、摘要、正文与这三类标签，不做近义词扩写，也不调用模型。"
    ),
    meta,
    formHost,
    el("div", { class: "split kb-split" }, listPanel, detailHost),
    notes
  );
  const initial = await load(0);
  if (initial) renderAnswer(initial, false);
}
const ASSIST_UNKNOWN = "UNKNOWN";
const ASSIST_UNUSED = "UNUSED";
function formatByteSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const text = unit === 0 ? String(Math.round(value)) : value.toFixed(value >= 10 ? 0 : 1);
  return `${text} ${units[unit]}`;
}
function assistanceWords(value) {
  return value.split(/[、,，\n]/).map((part) => part.trim()).filter(Boolean);
}
function assistanceSteps(text) {
  const rows = [];
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const parts = line.split("|").map((part) => part.trim());
    const step = parts[0] ?? "";
    if (!step) return null;
    rows.push({
      step,
      tool: parts[1] || null,
      job_id: parts[2] || null,
      operation_id: parts[3] || null
    });
  }
  return rows;
}
function assistanceRefusal(error) {
  const envelope = error?.serviceEnvelope;
  const code = envelope?.error;
  const detail = envelope?.detail;
  if (typeof code !== "string") return errMsg(error);
  return typeof detail === "string" && detail ? `${code}：${detail}` : code;
}
async function renderDesignAssistant(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读取输出类型与工作区…"));
  const objective = el("textarea", {
    id: "as-objective",
    class: "input",
    rows: "4",
    placeholder: "例如：为秋季新品做一张克制的主视觉海报，给标题留出大面积空白。"
  });
  const objectiveCount = el("span", { class: "as-count", id: "as-objective-count" }, "0 字");
  const objectiveClear = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "as-objective-clear"
  }, "清空");
  const objectiveMeta = el(
    "div",
    { class: "as-field-meta" },
    objectiveClear,
    objectiveCount,
    el("span", { class: "as-hint" }, "Shift+Return 换行")
  );
  const syncObjectiveMeta = () => {
    objectiveCount.textContent = `${objective.value.length} 字`;
  };
  objective.addEventListener("input", syncObjectiveMeta);
  objectiveClear.addEventListener("click", () => {
    objective.value = "";
    syncObjectiveMeta();
    objective.focus();
  });
  const outputType = el("div", {
    class: "as-chips",
    id: "as-output-type",
    role: "radiogroup",
    "aria-label": "输出类型",
    tabindex: "-1"
  });
  const chosenOutputType = () => outputType.querySelector("input:checked")?.value ?? "";
  const chooseOutputType = (value) => {
    for (const chip of Array.from(outputType.querySelectorAll("input"))) {
      chip.checked = chip.value === value;
    }
  };
  const workspace = el("select", { id: "as-workspace", class: "input" });
  const workspaceName = el("input", {
    id: "as-workspace-name",
    class: "input",
    maxlength: "160",
    placeholder: "工作区名称（留空则取需求前 20 字）"
  });
  const workspaceNameRow = el(
    "label",
    { class: "field-row as-new-workspace" },
    el("span", {}, "新工作区名称"),
    workspaceName
  );
  const author = el("input", {
    id: "as-author",
    class: "input",
    maxlength: "120",
    placeholder: "你的名字或代号（必填）"
  });
  const assetSelect = el("select", { id: "as-reference-select", class: "input" });
  const addReference = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "as-reference-add"
  }, "添加参考");
  const referenceList = el("ul", { class: "list as-refs", id: "as-references" });
  const referenceCount = el(
    "span",
    { class: "as-count", id: "as-reference-count" },
    "已关联 0 项参考"
  );
  const submit = el(
    "button",
    { type: "submit", class: "primary-btn", id: "as-submit" },
    "整理方案"
  );
  const cancelEdit = el("button", {
    type: "button",
    class: "ghost-btn as-hidden",
    id: "as-cancel-edit"
  }, "取消修订");
  const formError = el("p", { class: "error", id: "as-form-error", role: "alert" });
  const formStatus = el("p", { class: "view-hint", id: "as-form-status", role: "status" });
  function showFieldRefusal(control, message) {
    formError.textContent = message;
    if (control.id) formError.setAttribute("data-for", control.id);
    const row = control.closest(".field-row") ?? control;
    const slot = row.closest(".as-row") ?? row;
    slot.parentNode?.insertBefore(formError, slot.nextSibling);
    control.focus();
  }
  function clearFieldRefusal() {
    formError.replaceChildren();
    formError.removeAttribute("data-for");
    formStatus.parentNode?.insertBefore(formError, formStatus);
  }
  const creative = el("textarea", {
    id: "as-creative",
    class: "input",
    rows: "4",
    placeholder: "一段中性的创意说明；留空则方案只有目标（保存成功，但未提供创意）。"
  });
  const brand = el("input", {
    id: "as-brand",
    class: "input",
    placeholder: "例如：只用两种油墨（用、或逗号分隔）"
  });
  const role = el("input", {
    id: "as-role",
    class: "input",
    placeholder: "例如：面向采购负责人（用、或逗号分隔）"
  });
  const lens = el("input", {
    id: "as-lens",
    class: "input",
    placeholder: "镜头或视角要求（可留空）"
  });
  const sound = el("input", {
    id: "as-sound",
    class: "input",
    placeholder: "声音或配乐要求（可留空）"
  });
  const gaps = el("input", {
    id: "as-gaps",
    class: "input",
    placeholder: "待补充内容（可留空）"
  });
  const limits = el("input", {
    id: "as-limits",
    class: "input",
    placeholder: "这次不做什么（可留空）"
  });
  const stepText = el("textarea", {
    id: "as-steps",
    class: "input",
    rows: "3",
    placeholder: "每行一条：步骤 | 工具 | 作业编号 | 操作编号\n后三项可留空；服务会写 UNKNOWN / UNUSED，不自造编号。"
  });
  const shotHost = el("div", { class: "as-shot-rows", id: "as-shot-rows" });
  const addShot = el(
    "button",
    { type: "button", class: "ghost-btn", id: "as-add-shot" },
    "加一行镜头"
  );
  const shotHint = el(
    "p",
    { class: "view-hint", id: "as-shot-hint" },
    "每行一个镜头：时长（秒，可留空）、这一镜头要完成什么（必填）、镜头运动、声音、参考角色。序号按行顺序生成。留空的整行不写入。"
  );
  const shotRows = [];
  function addShotRow(seed) {
    const duration = el("input", {
      class: "input",
      type: "number",
      min: "0",
      step: "0.1",
      maxlength: "8",
      placeholder: "例如 4（留空=未定）"
    });
    const purpose = el("input", {
      class: "input",
      maxlength: "500",
      placeholder: "这一镜头要完成什么"
    });
    const camera = el("input", { class: "input", maxlength: "200", placeholder: "镜头运动（可留空）" });
    const soundNote = el("input", { class: "input", maxlength: "200", placeholder: "声音（可留空）" });
    const role2 = el("input", { class: "input", maxlength: "100", placeholder: "参考角色（可留空）" });
    const remove = el("button", { type: "button", class: "ghost-btn" }, "去掉");
    const row = { duration, purpose, camera, soundNote, role: role2, remove };
    if (seed) {
      duration.value = seed.duration ?? "";
      purpose.value = seed.purpose ?? "";
      camera.value = seed.camera ?? "";
      soundNote.value = seed.soundNote ?? "";
      role2.value = seed.role ?? "";
    }
    remove.onclick = () => {
      const at = shotRows.indexOf(row);
      if (at >= 0) shotRows.splice(at, 1);
      paintShotRows();
    };
    shotRows.push(row);
    paintShotRows();
    purpose.focus();
  }
  function paintShotRows() {
    shotHost.replaceChildren(...shotRows.map((row, position) => el(
      "div",
      { class: "field-grid as-shot-row" },
      el(
        "label",
        { class: "field-row" },
        el("span", {}, `序号 ${position + 1}`),
        el("input", {
          class: "input",
          value: String(position + 1),
          readonly: "readonly",
          "aria-label": `第 ${position + 1} 行的序号`
        })
      ),
      el("label", { class: "field-row" }, el("span", {}, "时长秒"), row.duration),
      el("label", { class: "field-row" }, el("span", {}, "要完成什么"), row.purpose),
      el("label", { class: "field-row" }, el("span", {}, "镜头运动"), row.camera),
      el("label", { class: "field-row" }, el("span", {}, "声音"), row.soundNote),
      el("label", { class: "field-row" }, el("span", {}, "参考角色"), row.role),
      row.remove
    )));
  }
  function clearShotRows() {
    shotRows.splice(0, shotRows.length);
    paintShotRows();
  }
  const shotCell = (value) => value === null || value === ASSIST_UNKNOWN || value === ASSIST_UNUSED ? "" : value;
  function fillShotRows(rows) {
    clearShotRows();
    for (const row of rows) {
      addShotRow({
        duration: row.duration_s === null ? "" : String(row.duration_s),
        purpose: row.purpose,
        camera: shotCell(row.camera),
        soundNote: shotCell(row.sound),
        role: shotCell(row.reference_role)
      });
    }
    objective.focus();
  }
  function shotTable() {
    const rows = [];
    for (let position = 0; position < shotRows.length; position += 1) {
      const row = shotRows[position];
      const purpose = row.purpose.value.trim();
      const duration = row.duration.value.trim();
      const camera = row.camera.value.trim();
      const soundNote = row.soundNote.value.trim();
      const role2 = row.role.value.trim();
      if (!purpose && !duration && !camera && !soundNote && !role2) continue;
      if (!purpose) {
        return { rows: [], problem: `第 ${position + 1} 行没有写「要完成什么」：一行分镜至少要说要拍什么，否则导出的表格里那一行没人能核对。` };
      }
      let seconds = null;
      if (duration) {
        const parsed = Number(duration);
        if (!Number.isFinite(parsed) || parsed < 0) {
          return { rows: [], problem: `第 ${position + 1} 行的时长「${duration}」不是一个不小于 0 的秒数：留空表示未定，页面不替你猜一个数。` };
        }
        seconds = parsed;
      }
      rows.push({
        index: position + 1,
        duration_s: seconds,
        purpose,
        camera: camera || null,
        sound: soundNote || null,
        reference_role: role2 || null
      });
    }
    return { rows, problem: "" };
  }
  addShot.onclick = () => addShotRow();
  const more = el(
    "details",
    { class: "advanced", id: "as-advanced" },
    el("summary", {}, "更多设置（设计建议、约束与外部步骤）"),
    el(
      "div",
      { class: "advanced-body as-more" },
      el("label", { class: "field-row" }, el("span", {}, "设计建议"), creative),
      el("label", { class: "field-row" }, el("span", {}, "品牌约束"), brand),
      el("label", { class: "field-row" }, el("span", {}, "角色约束"), role),
      el("label", { class: "field-row" }, el("span", {}, "镜头 / 视角"), lens),
      el("label", { class: "field-row" }, el("span", {}, "声音"), sound),
      el(
        "div",
        { class: "field-row" },
        el("span", {}, "镜头表（分镜）"),
        addShot
      ),
      shotHint,
      shotHost,
      el("label", { class: "field-row" }, el("span", {}, "待补充内容"), gaps),
      el("label", { class: "field-row" }, el("span", {}, "边界（不做什么）"), limits),
      el("label", { class: "field-row" }, el("span", {}, "外部步骤"), stepText)
    )
  );
  const form = el(
    "form",
    { class: "panel as-form", id: "as-form" },
    el("h3", {}, "你想完成什么设计？"),
    el(
      "p",
      { class: "view-hint" },
      "写下目标就能保存一条方案。保存的是方案本身，不是一次模型运行；工具与模型不在这里选，稍后在工具交接里补。"
    ),
    el("label", { class: "field-row" }, el("span", {}, "需求"), objective),
    objectiveMeta,
    el(
      "div",
      { class: "as-row" },
      el("label", { class: "field-row" }, el("span", {}, "工作区"), workspace),
      workspaceNameRow
    ),
    el(
      "label",
      { class: "field-row" },
      el("span", {}, "参考附件"),
      el("div", { class: "as-row" }, assetSelect, addReference, referenceCount)
    ),
    referenceList,
    el(
      "div",
      { class: "as-row" },
      // A <label> cannot wrap a group of labelled chips (label inside label), and the group
      // carries its own accessible name, so this row is a plain .field-row container.
      el("div", { class: "field-row" }, el("span", {}, "输出类型"), outputType),
      el("label", { class: "field-row" }, el("span", {}, "记录人"), author)
    ),
    more,
    formError,
    formStatus,
    el("div", { class: "as-actions" }, submit, cancelEdit)
  );
  const filterSeed = readPlanFilters();
  let filterDriftNotice = "";
  const planSearch = el("input", {
    id: "as-plan-search",
    class: "input",
    type: "search",
    maxlength: "200",
    value: filterSeed.text,
    placeholder: "按目标文字找回方案（在这一次读回的结果里筛）"
  });
  const planTypeFilter = el("select", {
    id: "as-plan-filter-type",
    class: "input",
    "aria-label": "按输出类型筛选方案"
  });
  const stateFilters = [
    { value: "all", label: "全部状态", keep: () => true },
    { value: "provided", label: "已提供创意", keep: (row) => row.provided },
    { value: "open", label: "还没写创意", keep: (row) => !row.provided },
    { value: "chosen", label: "已被具名选用", keep: (row) => row.chosen_revision !== null }
  ];
  const planStateFilter = el(
    "select",
    {
      id: "as-plan-filter-state",
      class: "input",
      "aria-label": "按方案状态筛选"
    },
    ...stateFilters.map((item) => el("option", { value: item.value }, item.label))
  );
  if (!stateFilters.some((item) => item.value === filterSeed.state)) {
    planStateFilter.value = "all";
  } else {
    planStateFilter.value = filterSeed.state;
  }
  const keepFilters = () => {
    filterDriftNotice = "";
    writePlanFilters({
      text: planSearch.value,
      outputType: planTypeFilter.value,
      state: planStateFilter.value
    });
  };
  planSearch.addEventListener("input", () => {
    keepFilters();
    renderPlans();
  });
  planTypeFilter.addEventListener("change", () => {
    keepFilters();
    renderPlans();
  });
  planStateFilter.addEventListener("change", () => {
    keepFilters();
    renderPlans();
  });
  const planList = el("ul", { class: "list", id: "as-list" });
  const listMeta = el("p", { class: "view-hint", id: "as-list-meta" });
  const listPanel = el(
    "section",
    { class: "panel" },
    el("h3", {}, "最近的方案"),
    el(
      "div",
      { class: "as-row" },
      el("label", { class: "field-row" }, el("span", {}, "找回"), planSearch),
      el("label", { class: "field-row" }, el("span", {}, "类型"), planTypeFilter),
      el("label", { class: "field-row" }, el("span", {}, "状态"), planStateFilter)
    ),
    listMeta,
    planList
  );
  const meta = el("div", { class: "as-meta", id: "as-meta", role: "status" });
  const detailHost = el("div", { id: "as-detail" });
  let outputTypes = [];
  let materials = [];
  let workspaces = [];
  let selected = "";
  let references = [];
  let knowledgeChoices = [];
  let projectChoices = [];
  let assets = [];
  let plans = [];
  let planAnswer = OFFLINE.assistancePlans;
  let editing = null;
  let duplicateFrom = "";
  let busy2 = false;
  let vocabularyNotice = "";
  let workspaceNotice = "";
  let plansNotice = "";
  let assetsNotice = "";
  let knowledgeNotice = "";
  let projectNotice = "";
  async function loadVocabulary() {
    const answer = await apiOrEmpty(
      "/assistance-plan-output-types",
      OFFLINE.assistanceOutputTypes
    );
    vocabularyNotice = shapeNotice(answer);
    return answer;
  }
  async function loadWorkspaces() {
    const answer = await apiOrEmpty("/projects", OFFLINE.projects);
    workspaceNotice = shapeNotice(answer);
    return answer;
  }
  async function loadPlans(projectId) {
    const answer = await apiOrEmpty(
      `/projects/${projectId}/assistance-plans?limit=20`,
      OFFLINE.assistancePlans
    );
    plansNotice = shapeNotice(answer);
    return answer;
  }
  async function loadAssets(projectId) {
    const answer = await apiOrEmpty(
      `/projects/${projectId}/assets`,
      OFFLINE.assets
    );
    assetsNotice = shapeNotice(answer);
    return answer;
  }
  async function loadKnowledgeChoices() {
    const answer = await apiOrEmpty(
      "/knowledge-entries/search?limit=200",
      OFFLINE.knowledgeLibrary
    );
    knowledgeNotice = shapeNotice(answer);
    knowledgeChoices = (answer.entries ?? []).map((entry) => ({
      id: entry.knowledge_entry_id,
      title: entry.title
    }));
    fillAssets();
    renderReferences();
  }
  async function loadProjectChoices(projectId) {
    const [briefs, directions, results] = await Promise.all([
      apiOrEmpty(`/projects/${projectId}/briefs`, OFFLINE.briefs),
      apiOrEmpty(`/projects/${projectId}/directions`, OFFLINE.directions),
      apiOrEmpty(
        `/projects/${projectId}/prompt-results`,
        OFFLINE.promptResults
      )
    ]);
    const latestResult = /* @__PURE__ */ new Map();
    for (const row of results.results ?? []) {
      if (!row.result_id) continue;
      const seen = latestResult.get(row.result_id);
      if (!seen || (row.revision ?? 0) > (seen.revision ?? 0)) latestResult.set(row.result_id, row);
    }
    projectChoices = [
      ...(briefs.briefs ?? []).map((brief) => ({
        kind: "BRIEF",
        id: brief.brief_id,
        label: `${brief.title} · r${brief.version}`
      })),
      ...(directions.directions ?? []).map((direction) => ({
        kind: "DIRECTION",
        id: direction.direction_id,
        label: `${direction.title} · r${direction.version}`
      })),
      ...[...latestResult].map(([id, row]) => ({
        kind: "PROMPT_RESULT",
        id,
        label: `${row.kind === "reversal" ? "反推" : "生成"} · r${row.revision}`
      }))
    ];
    const truncated = [
      briefs.next_cursor ? "需求 Brief" : "",
      directions.next_cursor ? "方向" : ""
    ].filter(Boolean).join("、");
    projectNotice = [
      shapeNotice(briefs),
      shapeNotice(directions),
      shapeNotice(results),
      truncated ? `这一页之后还有更早的${truncated}没有读到` : ""
    ].filter(Boolean).join("；");
    fillAssets();
    renderReferences();
  }
  const labelOf = (value) => outputTypes.find((option) => option.value === value)?.label ?? value;
  const notices = () => [
    vocabularyNotice,
    workspaceNotice,
    plansNotice,
    assetsNotice,
    projectNotice,
    knowledgeNotice
  ].filter(Boolean).join("；");
  function fillWorkspaces() {
    workspace.replaceChildren(
      el("option", { value: "" }, "＋ 新建轻量工作区"),
      ...workspaces.map((project2) => el("option", { value: project2.id }, project2.name))
    );
    workspace.value = selected;
    workspaceNameRow.classList.toggle("as-hidden", selected !== "");
  }
  function referenceGroup(kind, label, options, emptyText) {
    return el(
      "optgroup",
      { label },
      ...options.length ? options.map((option) => el("option", { value: `${kind}:${option.id}` }, option.text)) : [el("option", { value: "" }, emptyText)]
    );
  }
  const ofKind = (kind) => projectChoices.filter((choice) => choice.kind === kind);
  function fillAssets() {
    const groups = [
      referenceGroup(
        "ASSET",
        "本工作区素材",
        assets.map((asset) => ({
          // Every word here is a field the route served. There is no name to show: the stored
          // filename is a publish-time constant (`image_assets.py:144` writes reference.png or
          // reference.jpg; native_tasks.py:172 writes native.<ext>), never the name the designer
          // gave the file, so printing it would look like a caption while saying nothing.
          // The short id tail is what distinguishes two same-size images from each other.
          id: asset.id,
          text: `${asset.media_type} · ${asset.width}×${asset.height} · ${formatByteSize(asset.byte_size)} · ${asset.id.slice(0, 12)}…`
        })),
        assetsNotice || "这个工作区还没有素材"
      ),
      referenceGroup(
        "BRIEF",
        "本工作区的需求 Brief",
        ofKind("BRIEF").map((choice) => ({ id: choice.id, text: `${choice.label} · ${choice.id}` })),
        projectNotice || "这个工作区还没有需求 Brief"
      ),
      referenceGroup(
        "DIRECTION",
        "本工作区的方向",
        ofKind("DIRECTION").map((choice) => ({
          id: choice.id,
          text: `${choice.label} · ${choice.id}`
        })),
        projectNotice || "这个工作区还没有方向"
      ),
      referenceGroup(
        "PROMPT_RESULT",
        "本工作区的提示词结果",
        ofKind("PROMPT_RESULT").map((choice) => ({
          id: choice.id,
          text: `${choice.label} · ${choice.id}`
        })),
        projectNotice || "这个工作区还没有提示词结果"
      ),
      referenceGroup(
        "KNOWLEDGE",
        "知识与提示词库",
        knowledgeChoices.map((entry) => ({ id: entry.id, text: `${entry.title} · ${entry.id}` })),
        knowledgeNotice || "库里还没有条目"
      )
    ];
    const offered = assets.length + projectChoices.length + knowledgeChoices.length;
    assetSelect.replaceChildren(
      el("option", { value: "" }, offered ? "选择参考（素材、需求、方向、提示词结果或知识条目）" : [assetsNotice, projectNotice, knowledgeNotice].filter(Boolean).join("；") || "这一页没有可引用的材料"),
      ...groups
    );
    addReference.disabled = offered === 0;
  }
  function renderReferences() {
    const known = /* @__PURE__ */ new Set([
      ...assets.map((asset) => `ASSET:${asset.id}`),
      ...projectChoices.map((choice) => `${choice.kind}:${choice.id}`),
      ...knowledgeChoices.map((entry) => `KNOWLEDGE:${entry.id}`)
    ]);
    const kindLabel = (kind) => REFERENCE_KIND_LABELS[kind] ?? kind;
    const assetById = new Map(assets.map((asset) => [asset.id, asset]));
    const choiceById = new Map(projectChoices.map((choice) => [`${choice.kind}:${choice.id}`, choice]));
    const knowledgeById = new Map(knowledgeChoices.map((entry) => [entry.id, entry]));
    const captionOf = (kind, id) => {
      if (kind === "ASSET") {
        const asset = assetById.get(id);
        return asset ? `${asset.media_type} · ${asset.width}×${asset.height} · ${formatByteSize(asset.byte_size)}` : "";
      }
      if (kind === "KNOWLEDGE") return knowledgeById.get(id)?.title ?? "";
      return choiceById.get(`${kind}:${id}`)?.label ?? "";
    };
    syncObjectiveMeta();
    referenceCount.textContent = `已关联 ${references.length} 项参考`;
    referenceList.replaceChildren(...references.length ? references.map((reference) => el(
      "li",
      { class: "list-item as-ref" },
      el("span", { class: "tag neutral" }, kindLabel(reference.kind)),
      ...captionOf(reference.kind, reference.id) ? [el("span", { class: "as-ref-caption" }, captionOf(reference.kind, reference.id))] : [],
      el("span", { class: "value-mono" }, reference.id),
      el(
        "span",
        { class: "tag " + (known.has(`${reference.kind}:${reference.id}`) ? "neutral" : "warn") },
        known.has(`${reference.kind}:${reference.id}`) ? "已选参考" : "不在当前清单（保留方案里原有的引用）"
      ),
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          references = references.filter((entry) => entry.id !== reference.id || entry.kind !== reference.kind);
          renderReferences();
        }
      }, "移除")
    )) : [el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "未添加参考"),
        el("small", {}, "参考只登记链接与当时的版本；服务不会因此分析图片。")
      )
    )]);
  }
  function fillPlanTypeFilter() {
    const values = outputTypes.map((row) => row.value);
    const wanted = values.includes(filterSeed.outputType) ? filterSeed.outputType : "all";
    if (filterSeed.outputType !== "all" && wanted === "all") {
      filterDriftNotice = `上一次选的输出类型「${filterSeed.outputType}」已不在这一版词表里，筛选回到「全部类型」。`;
    }
    planTypeFilter.replaceChildren(
      el("option", { value: "all" }, "全部类型"),
      ...outputTypes.map((row) => el("option", { value: row.value }, row.label))
    );
    planTypeFilter.value = wanted;
  }
  function renderPlans() {
    if (!selected) {
      listMeta.textContent = "还没有工作区：保存第一条方案时会新建一个轻量工作区。";
      planList.replaceChildren();
      return;
    }
    if (plansNotice) {
      listMeta.textContent = plansNotice;
      planList.replaceChildren(el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "未读回"),
          el("small", {}, `${plansNotice}，因此不能说这个工作区没有方案。`)
        )
      ));
      return;
    }
    const scope = `这个工作区共 ${planAnswer.total} 条，这一页读到 ${plans.length} 条` + (planAnswer.next_offset === null ? "" : "，还有更早的没有读到");
    const needle = planSearch.value.trim().toLowerCase();
    const typeWanted = planTypeFilter.value;
    const stateFilter = stateFilters.find((item) => item.value === planStateFilter.value) ?? stateFilters[0];
    const filtering = needle !== "" || typeWanted !== "all" || stateFilter.value !== "all";
    const visible = filtering ? plans.filter((row) => (needle === "" || row.objective.toLowerCase().includes(needle)) && (typeWanted === "all" || row.output_type === typeWanted) && stateFilter.keep(row)) : plans;
    listMeta.textContent = filterDriftNotice + (filtering ? `${scope}；按当前条件显示 ${visible.length} 条。筛选只在这 ${plans.length} 条里做，不是全库搜索。` : `${scope}（这一页最多 ${planAnswer.limit} 条）。`);
    if (!plans.length) {
      planList.replaceChildren(emptyLi(
        planAnswer,
        "尚无方案",
        "在上方写下需求并保存第一条；保存后会在这里读回。"
      ));
      return;
    }
    if (!visible.length) {
      planList.replaceChildren(el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "这一页里没有匹配的"),
          el("small", {}, `${plans.length} 条已读回的方案里，没有同时满足「${needle || "文字"}」、类型「${typeWanted === "all" ? "全部" : labelOf(typeWanted)}」与状态「${stateFilter.label}」的。清空条件即可看回全部。`)
        )
      ));
      return;
    }
    planList.replaceChildren(...visible.map((row) => {
      const badges = [el("span", { class: "tag info" }, `r${row.revision}`)];
      badges.push(row.provided ? el("span", { class: "tag ok" }, "方案已提供") : el("span", { class: "tag warn" }, "尚未提供创意"));
      badges.push(row.chosen_revision === null ? el("span", { class: "tag neutral" }, "尚无用户选用") : el("span", { class: "tag ok" }, `用户选用 r${row.chosen_revision}`));
      return el(
        "li",
        { class: "list-item as-plan-row" },
        el(
          "button",
          {
            type: "button",
            class: "as-plan-open",
            onclick: () => {
              void openPlan(row.plan_id);
            }
          },
          el("strong", {}, row.objective),
          el("small", {}, `${labelOf(row.output_type)} · ${row.created_by} · ${row.created_at}`)
        ),
        el("div", { class: "as-badges" }, ...badges)
      );
    }));
  }
  async function refreshPlans() {
    if (!selected) {
      plans = [];
      planAnswer = OFFLINE.assistancePlans;
      plansNotice = "";
      renderPlans();
      return;
    }
    const answer = await loadPlans(selected);
    plans = answer.plans;
    planAnswer = answer;
    renderPlans();
  }
  async function refreshReferenceSources() {
    if (!selected) {
      assets = [];
      assetsNotice = "";
      projectChoices = [];
      projectNotice = "";
      fillAssets();
      renderReferences();
      return;
    }
    const answer = await loadAssets(selected);
    assets = answer.assets;
    await loadProjectChoices(selected);
  }
  function referenceRow(status) {
    const stateLabel = status.state === "CURRENT" ? "当前" : status.state === "CHANGED" ? "已变化" : "找不到";
    const stateClass = status.state === "CURRENT" ? "ok" : status.state === "CHANGED" ? "warn" : "bad";
    const analysisLabel = status.analysis === "ANALYZED" ? "已分析" : status.analysis === "LINKED_ONLY" ? "仅登记链接" : "不适用";
    return el(
      "li",
      { class: "list-item value-row" },
      el(
        "div",
        { class: "as-ref-head" },
        el("span", { class: "tag info" }, status.kind),
        el("span", { class: "tag " + stateClass }, stateLabel),
        el(
          "span",
          { class: "tag " + (status.analysis === "ANALYZED" ? "ok" : "neutral") },
          analysisLabel
        )
      ),
      el("span", { class: "value-mono" }, status.id),
      el(
        "small",
        {},
        `登记 r${status.recorded_revision} · 现为 ` + (status.current_revision === null ? "找不到" : `r${status.current_revision}`)
      )
    );
  }
  function stepRow(step) {
    const label = (value) => {
      if (value === ASSIST_UNKNOWN) return el("span", { class: "tag neutral" }, "未登记");
      if (value === ASSIST_UNUSED) return el("span", { class: "tag neutral" }, "未使用 ", en(ASSIST_UNUSED));
      return value;
    };
    return el(
      "li",
      { class: "list-item value-row" },
      el("span", {}, step.step),
      el("small", {}, "工具："),
      el("span", {}, label(step.tool)),
      el("small", {}, "作业编号："),
      el("span", {}, label(step.job_id)),
      el("small", {}, "操作编号："),
      el("span", {}, label(step.operation_id))
    );
  }
  async function readMaterial(answer, note, format) {
    if (!format) {
      note.textContent = "没有选中材料格式：页面不知道该把哪一种交给浏览器。";
      return null;
    }
    note.textContent = "正在从服务读取这份材料…";
    try {
      return await api(
        `/projects/${answer.project_id}/assistance-plans/${answer.plan_id}/export?format=${encodeURIComponent(format)}`
      );
    } catch (problem) {
      note.textContent = `材料没有读到：${assistanceRefusal(problem)}。这一句说的是这份材料，方案本身没有因此变动。`;
      return null;
    }
  }
  function materialReply(file, done) {
    return `${done} ${file.format_label}（r${file.revision} · ${file.body_bytes} 字节 · ${file.body_sha256}）。这只是把材料交出去，不是选用，也不是发送。${file.not_executed}`;
  }
  async function copyMaterial(answer, note, format) {
    const file = await readMaterial(answer, note, format);
    if (!file) return;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(file.body).then(
        () => {
          note.textContent = materialReply(file, "已复制");
        },
        () => showCopyFallback(file.body, note)
      );
      return;
    }
    showCopyFallback(file.body, note);
  }
  async function downloadMaterial(answer, note, format) {
    const file = await readMaterial(answer, note, format);
    if (!file) return;
    const blob = new Blob([file.body], { type: file.content_type + ";charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = el("a", { href: url, download: file.filename });
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1e3);
    note.textContent = materialReply(file, "已下载");
  }
  function renderDetail(answer) {
    const doc = answer.current;
    if (!doc) {
      detailHost.replaceChildren(el(
        "p",
        { class: "error" },
        "这个方案的最新修订无法解析：页面不展示正文，也不猜测它的内容。"
      ));
      return;
    }
    const states = answer.states;
    const choice = answer.choice;
    const chosenElsewhere = choice.chosen && !choice.is_latest;
    const chips = el(
      "div",
      { class: "as-states", id: "as-states" },
      el(
        "span",
        {
          class: "tag " + (states.saved ? "ok" : "neutral"),
          id: "as-saved",
          dataset: { state: String(states.saved) }
        },
        states.saved ? "已保存" : "尚未保存"
      ),
      el(
        "span",
        {
          class: "tag " + (states.provided ? "ok" : "warn"),
          id: "as-provided",
          dataset: { state: String(states.provided) }
        },
        states.provided ? "方案已提供" : "尚未提供创意"
      ),
      el(
        "span",
        {
          class: "tag " + (states.chosen ? "ok" : "neutral"),
          id: "as-chosen",
          dataset: { state: String(states.chosen) }
        },
        states.chosen ? `用户选用 · r${choice.revision}` : "尚无用户选用"
      ),
      el(
        "span",
        {
          class: "tag " + (states.externally_verified ? "ok" : "warn"),
          id: "as-external",
          dataset: { state: String(states.externally_verified) }
        },
        states.externally_verified ? "外部已验证" : "外部未验证"
      )
    );
    const note = el("p", { class: "view-hint as-copy-note", id: "as-copy-note" });
    const actions = el("div", { class: "as-actions", id: "as-actions" });
    const materialSelect = el(
      "select",
      {
        id: "as-material",
        class: "input",
        "aria-label": "要带走的材料格式"
      },
      ...materials.length ? materials.map((row) => el("option", { value: row.value }, row.label)) : [el("option", { value: "" }, "材料格式未读回")]
    );
    const copyButton = el("button", {
      type: "button",
      class: "ghost-btn",
      id: "as-copy",
      onclick: () => {
        void copyMaterial(answer, note, materialSelect.value);
      }
    }, "复制材料");
    const downloadButton = el(
      "button",
      {
        type: "button",
        class: "ghost-btn",
        id: "as-download",
        onclick: () => {
          void downloadMaterial(answer, note, materialSelect.value);
        }
      },
      "下载材料"
    );
    const duplicateButton = el("button", {
      type: "button",
      class: "ghost-btn",
      id: "as-duplicate",
      onclick: () => {
        void startDuplicating(answer);
      }
    }, "复制一份");
    copyButton.disabled = materials.length === 0;
    downloadButton.disabled = materials.length === 0;
    if (!materials.length) {
      note.textContent = "材料格式没有从服务读回：这两种动作都要按服务给出的格式表走，页面不替你抄一份格式表，所以现在按不动。";
    }
    let primary;
    if (!states.provided) {
      primary = el("button", {
        type: "button",
        class: "primary-btn",
        id: "as-supply",
        onclick: () => {
          void startEditing(answer, true);
        }
      }, "补充创意");
    } else if (!states.chosen || chosenElsewhere) {
      primary = el(
        "button",
        {
          type: "button",
          class: "primary-btn",
          id: "as-choose",
          onclick: () => openChooseForm(answer, actions, note)
        },
        chosenElsewhere ? `设为选用 r${answer.latest_revision}` : "设为选用"
      );
    } else {
      primary = el("button", {
        type: "button",
        class: "primary-btn",
        id: "as-revise",
        onclick: () => {
          void startEditing(answer, false);
        }
      }, "修订方案");
    }
    const reviseGhost = states.provided && !(primary.id === "as-revise") ? el("button", {
      type: "button",
      class: "ghost-btn",
      id: "as-revise",
      onclick: () => {
        void startEditing(answer, false);
      }
    }, "修订方案") : null;
    actions.replaceChildren(
      primary,
      ...reviseGhost ? [reviseGhost] : [],
      materialSelect,
      copyButton,
      downloadButton,
      duplicateButton
    );
    const sections = [
      el(
        "div",
        { class: "as-detail-head" },
        el(
          "div",
          {},
          el("h3", {}, doc.objective),
          el(
            "p",
            { class: "muted" },
            `${labelOf(doc.output_type)} · 最新 r${answer.latest_revision} · 记录人 ${doc.created_by} · ${doc.created_at}`
          )
        ),
        chips
      )
    ];
    if (chosenElsewhere) {
      sections.push(el(
        "p",
        { class: "error" },
        `选用记录在 r${choice.revision}，最新已是 r${answer.latest_revision}：选用的不是最新修订，两者都如实保留。`
      ));
    }
    if (choice.chosen && choice.actor) {
      sections.push(el(
        "p",
        { class: "view-hint", id: "as-choice" },
        `选用人 ${choice.actor} · ${choice.chosen_at ?? "时间未读回"}` + (choice.is_latest ? "" : `（选用的是 r${choice.revision}，不是最新修订）`)
      ));
    }
    sections.push(el("h4", {}, "目标与方向"));
    sections.push(el("p", { class: "as-body" }, doc.objective));
    sections.push(el(
      "ul",
      { class: "list" },
      valueRow("输出类型", labelOf(doc.output_type), false),
      valueRow("品牌约束", doc.brand_constraints.join("、") || "未登记", true),
      valueRow("角色约束", doc.role_constraints.join("、") || "未登记", true),
      valueRow("镜头 / 视角", doc.lens === ASSIST_UNKNOWN ? "未登记" : doc.lens, true),
      valueRow("声音", doc.sound === ASSIST_UNKNOWN ? "未登记" : doc.sound, true),
      valueRow("边界", doc.limits.join("、") || "未登记", true)
    ));
    sections.push(el("h4", {}, "设计建议"));
    sections.push(el(
      "p",
      { class: states.provided ? "as-body" : "view-hint" },
      states.provided ? doc.neutral_creative : "尚未提供创意：这条方案已经保存，只是还没有写到创意。用「补充创意」补上。"
    ));
    sections.push(el("h4", {}, "脚本与分镜"));
    const storedShots = doc.shots ?? [];
    if (storedShots.length) {
      sections.push(el(
        "ul",
        { class: "list as-shot-list", id: "as-shots" },
        ...storedShots.map((shot) => el(
          "li",
          { class: "list-item value-row" },
          el("span", {}, `镜头 ${shot.index}`),
          el("small", {}, shot.duration_s === null ? "时长未定" : `时长 ${shot.duration_s} 秒`),
          el("span", {}, shot.purpose),
          el("small", {}, "镜头运动："),
          el("span", {}, shotCell(shot.camera) || "未登记"),
          el("small", {}, "声音："),
          el("span", {}, shotCell(shot.sound) || "未登记"),
          el("small", {}, "参考角色："),
          el("span", {}, shotCell(shot.reference_role) || "未登记")
        ))
      ));
      sections.push(el(
        "p",
        { class: "view-hint" },
        `镜头表读到 ${storedShots.length} 行：分镜 CSV、markdown 与纯文本里的镜头段都来自这一张表，页面不另写一份。`
      ));
    } else if (!states.provided) {
      sections.push(el(
        "p",
        { class: "view-hint" },
        "尚未提供创意，因此还没有可读的脚本；这条方案也没有登记镜头行。"
      ));
    } else {
      sections.push(el("p", { class: "as-body" }, doc.neutral_creative));
      sections.push(el(
        "p",
        { class: "view-hint" },
        "这条方案没有登记镜头行，所以脚本就是上面这段正文。要一张能在拍摄现场核对的分镜表，在「更多设置」里逐行写镜头，保存后这里会读回来；没有镜头行时分镜 CSV 会被服务按名字拒绝，页面不画一张空表冒充分镜。"
      ));
    }
    sections.push(el("h4", {}, "工具交接材料"));
    sections.push(doc.external_steps.length ? el("ul", { class: "list" }, ...doc.external_steps.map(stepRow)) : el("p", { class: "view-hint" }, "本方案没有登记外部步骤。"));
    sections.push(el(
      "p",
      { class: "view-hint" },
      "服务不派发也不核验这些步骤；编号是登记值，不是执行证据。"
    ));
    const referenceSummary = `当前 ${answer.reference_status.length} 条参考 · 已分析 ${answer.analysis_summary.analyzed} · 仅登记链接 ${answer.analysis_summary.linked_only}`;
    sections.push(el(
      "details",
      { class: "advanced", id: "as-basis" },
      el("summary", {}, `参考与依据（${referenceSummary}）`),
      el(
        "div",
        { class: "advanced-body" },
        el("ul", { class: "list" }, ...answer.reference_status.length ? answer.reference_status.map(referenceRow) : [el("li", { class: "list-item" }, "这条方案没有登记参考。")]),
        el(
          "p",
          { class: "view-hint" },
          "参考按写入时的版本与摘要固定；「已变化」表示对象后来前进了，「仅登记链接」表示没有那次摘要的反推证据。"
        )
      )
    ));
    const tools = doc.external_steps.map((step) => step.tool).filter((tool) => tool !== ASSIST_UNKNOWN && tool !== ASSIST_UNUSED);
    sections.push(el(
      "details",
      { class: "advanced", id: "as-tools" },
      el("summary", {}, "适用工具"),
      el(
        "div",
        { class: "advanced-body" },
        tools.length ? el("p", {}, `方案登记的工具：${tools.join("、")}。工具组合可以稍后再选。`) : el("p", { class: "view-hint" }, "还没有登记工具；这不妨碍保存与复制方案。")
      )
    ));
    sections.push(el(
      "details",
      { class: "advanced", id: "as-gaps" },
      el("summary", {}, `待补充内容（${doc.known_gaps.length}）`),
      el(
        "div",
        { class: "advanced-body" },
        doc.known_gaps.length ? el("ul", { class: "list" }, ...doc.known_gaps.map((gap) => el("li", { class: "list-item" }, gap))) : el("p", { class: "view-hint" }, "服务没有记录待补充项。")
      )
    ));
    const revisionRow = (revision) => el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, `r${revision.revision}`),
        el("small", {}, `${revision.created_by} · ${revision.created_at}` + (revision.readable ? "" : " · JSON 不可读")),
        el("small", { class: "value-mono" }, revision.content_sha256)
      ),
      el(
        "span",
        { class: "tag " + (revision.revision === answer.latest_revision ? "info" : "neutral") },
        revision.revision === answer.latest_revision ? "最新" : "旧版本"
      )
    );
    sections.push(el(
      "details",
      { class: "advanced", id: "as-revisions" },
      el("summary", {}, `修订历史（${answer.revisions.length}）`),
      el(
        "div",
        { class: "advanced-body" },
        el("ul", { class: "list" }, ...answer.revisions.map(revisionRow))
      )
    ));
    if (answer.does_not_say.length) {
      sections.push(el(
        "details",
        { class: "advanced", id: "as-claims" },
        el("summary", {}, "服务声明它没有说的话"),
        el(
          "div",
          { class: "advanced-body" },
          el("ul", { class: "list" }, ...answer.does_not_say.map((line) => el("li", { class: "list-item" }, line)))
        )
      ));
    }
    sections.push(comparePanel(answer), feedbackPanel(answer), actions, note);
    detailHost.replaceChildren(el(
      "section",
      { class: "panel as-detail", id: "as-plan" },
      ...sections
    ));
  }
  function feedbackPanel(answer) {
    let verdictWords = [];
    let wordsRead = false;
    let justRecorded = null;
    const outcome = el(
      "select",
      { id: "as-fb-outcome", class: "input" },
      el("option", { value: "" }, "暂不记录")
    );
    const target2 = el("input", {
      id: "as-fb-target",
      class: "input",
      maxlength: "200",
      placeholder: "拿去的入口（例如 elevenlabs--web-app--music）"
    });
    const actor = el("input", {
      id: "as-fb-actor",
      class: "input",
      maxlength: "200",
      placeholder: "记录人姓名（必填：这是一条具名的人的陈述）"
    });
    const noteArea = el("textarea", {
      id: "as-fb-note",
      class: "input",
      rows: "2",
      placeholder: "发生了什么（可选）：哪里可用、哪里不行、要带哪个限制走"
    });
    const sourceRef = el("input", {
      id: "as-fb-source",
      class: "input",
      maxlength: "200",
      placeholder: "外部编号（可留空：留空记为 UNUSED，页面不代铸）"
    });
    const model = el("input", {
      id: "as-fb-model",
      class: "input",
      maxlength: "200",
      placeholder: "当时用的模型/版本（可留空：留空记为未说明，不推断）"
    });
    const timecodes = el("input", {
      id: "as-fb-timecodes",
      class: "input",
      maxlength: "400",
      placeholder: "问题时间码，逗号分隔（例如 00:03-00:05）"
    });
    const dimensionHost = el("div", { class: "as-fb-dimensions", id: "as-fb-dimensions" });
    const addButton = el("button", {
      type: "button",
      class: "ghost-btn",
      id: "as-fb-add-dimension"
    }, "加一条维度");
    addButton.disabled = true;
    const dimensionRows = [];
    function addDimensionRow() {
      const name = el("input", {
        class: "input",
        maxlength: "120",
        placeholder: "维度（例如 画幅 / 时长 / 品牌色）"
      });
      const verdict = el(
        "select",
        { class: "input" },
        ...verdictWords.map((word) => el("option", { value: word.value }, word.label))
      );
      const note = el("input", {
        class: "input",
        maxlength: "1000",
        placeholder: "这一维度上的具体情况（可选）"
      });
      dimensionRows.push({ name, verdict, note });
      dimensionHost.append(el(
        "div",
        { class: "field-grid as-fb-dimension" },
        el("label", { class: "field-row" }, el("span", {}, "维度"), name),
        el("label", { class: "field-row" }, el("span", {}, "结论"), verdict),
        el("label", { class: "field-row" }, el("span", {}, "情况"), note)
      ));
    }
    const save = el(
      "button",
      { type: "button", class: "ghost-btn", id: "as-fb-save" },
      "记录这次外部使用"
    );
    save.disabled = true;
    const status = el("p", { class: "view-hint", id: "as-fb-status", role: "status" });
    const error = el("p", { class: "error", id: "as-fb-error", role: "alert" });
    const history = el("ul", { class: "list", id: "as-fb-history" });
    const planId = answer.plan_id;
    const revision = answer.latest_revision;
    function fillWords(words, select, keepDefault) {
      const previous = select.value;
      const defaultOption = [el("option", { value: "" }, "暂不记录")];
      select.replaceChildren(
        ...defaultOption,
        ...words.map((word) => el("option", { value: word.value }, word.label))
      );
      if (previous && words.some((word) => word.value === previous)) select.value = previous;
    }
    function tallyOf(list, value) {
      const count = list.outcome_histogram[value];
      return typeof count === "number" ? String(count) : "未说明";
    }
    function paint(records, problem) {
      error.textContent = problem ?? "";
      const confirmed = justRecorded;
      justRecorded = null;
      const say = (line) => {
        status.textContent = (confirmed ?? "") + line;
      };
      if (!records) {
        history.replaceChildren();
        say(wordsRead ? "未读回：这一次没有从服务读到这条方案的反馈历史。" : "未读回：结果词随反馈历史一起从服务读到，读到之前这个面板不能写 —— 页面不替你手抄状态词。");
        return;
      }
      verdictWords = records.dimension_verdict_words;
      fillWords(records.outcome_words, outcome);
      if (!wordsRead) {
        wordsRead = true;
        save.disabled = false;
        addButton.disabled = false;
      }
      if (!records.total) {
        history.replaceChildren();
        say("尚无记录 —— 不记录是正常状态，页面不替你补一条 UNKNOWN。");
        return;
      }
      history.replaceChildren(...records.records.map((row) => el(
        "li",
        { class: "list-item", id: `as-fb-row-${row.feedback_no}` },
        `${row.outcome_label}（r${row.revision}） · ${row.target_key} · ${row.actor} · ${row.recorded_at} · 外部编号 ${row.source_ref}` + (row.note ? ` —— ${row.note}` : "")
      )));
      say(`已读回 ${records.total} 条自愿记录：` + records.outcome_words.map((word) => `${word.label} ${tallyOf(records, word.value)}`).join(" / ") + "。这些记录不把「外部未验证」改成已验证。");
    }
    async function readBack() {
      if (!selected) {
        paint(null, "还没有工作区：这条记录要落到哪个工作区说不清，所以不写。");
        return;
      }
      try {
        paint(await api(
          `/projects/${selected}/assistance-plans/${planId}/feedback`
        ), null);
      } catch (problem) {
        paint(null, `反馈历史读回失败：${assistanceRefusal(problem)}`);
      }
    }
    save.onclick = () => {
      const workspace2 = selected;
      if (!workspace2 || busy2) return;
      if (!outcome.value) {
        error.textContent = "没有选择结果：不记录就不写入，页面不会替你补一个 UNKNOWN。";
        return;
      }
      if (!actor.value.trim()) {
        error.textContent = "记录人姓名必填：一条外部使用反馈是人的陈述，得说得出是谁说的。";
        actor.focus();
        return;
      }
      if (!target2.value.trim()) {
        error.textContent = "要写清拿去哪个入口，否则这条经验回到方案里也对不上号。";
        target2.focus();
        return;
      }
      busy2 = true;
      save.disabled = true;
      void (async () => {
        try {
          const written = await api(
            `/projects/${workspace2}/assistance-plans/${planId}/feedback`,
            {
              outcome: outcome.value,
              target_key: target2.value.trim(),
              target_model: model.value.trim() || null,
              dimensions: dimensionRows.map((row) => ({
                name: row.name.value.trim(),
                verdict: row.verdict.value,
                note: row.note.value.trim() || null
              })).filter((row) => row.name),
              issue_timecodes: timecodes.value.split(/[,\n]/).map((s) => s.trim()).filter((s) => s),
              actor: actor.value.trim(),
              note: noteArea.value.trim() || null,
              source_ref: sourceRef.value.trim() || null,
              revision
            }
          );
          error.textContent = "";
          justRecorded = `已记录：${written.feedback.outcome_label}（外部编号 ${written.feedback.source_ref}）。这是你的陈述：系统没有核验外部运行，方案的「外部未验证」保持不变。`;
          await readBack();
        } catch (problem) {
          error.textContent = `记录失败：${assistanceRefusal(problem)}。你的输入还在。`;
        } finally {
          busy2 = false;
          save.disabled = false;
        }
      })();
    };
    addButton.onclick = addDimensionRow;
    void readBack();
    return el(
      "section",
      { class: "panel as-feedback", id: "as-feedback" },
      el("h3", {}, "外部使用反馈（自愿）"),
      el(
        "p",
        { class: "view-hint" },
        "把材料拿去外部工具之后发生了什么，由你决定记不记。这条记录与「已保存／已提供／已选用／外部未验证」四个状态分开：记一条「可用」不会让系统核验通过，也不改变材料准备状态。"
      ),
      el(
        "div",
        { class: "field-grid" },
        el("label", { class: "field-row" }, el("span", {}, "结果"), outcome),
        el("label", { class: "field-row" }, el("span", {}, "拿去的入口"), target2),
        el("label", { class: "field-row" }, el("span", {}, "记录人"), actor),
        el("label", { class: "field-row" }, el("span", {}, "外部编号"), sourceRef)
      ),
      el("label", { class: "field-row" }, el("span", {}, "当时模型/版本"), model),
      el("label", { class: "field-row" }, el("span", {}, "问题时间码"), timecodes),
      el(
        "div",
        { class: "field-row" },
        el("span", {}, "逐维度结论"),
        addButton
      ),
      dimensionHost,
      el("label", { class: "field-row" }, el("span", {}, "发生了什么"), noteArea),
      save,
      status,
      error,
      el("p", { class: "view-hint", id: "as-fb-history-label" }, "已记录的历史"),
      history
    );
  }
  function comparePanel(answer) {
    const readable = answer.revisions.filter((row) => row.readable);
    const revisionOptions = () => readable.map((row) => el(
      "option",
      { value: String(row.revision) },
      `r${row.revision} · ${row.created_by} · ${row.created_at}`
    ));
    const from = el("select", {
      id: "as-compare-from",
      class: "input",
      "aria-label": "对比的较早修订"
    }, ...revisionOptions());
    const to = el("select", {
      id: "as-compare-to",
      class: "input",
      "aria-label": "对比的较晚修订"
    }, ...revisionOptions());
    if (readable.length >= 2) {
      to.value = String(readable[readable.length - 1].revision);
    }
    const run = el(
      "button",
      { type: "button", class: "ghost-btn", id: "as-compare-run" },
      "对比这两个修订"
    );
    const status = el("p", { class: "view-hint", id: "as-compare-status", role: "status" });
    const body = el("div", { id: "as-compare-body" });
    const fields = [
      { label: "目标", read: (doc) => doc.objective },
      { label: "输出类型", read: (doc) => labelOf(doc.output_type) },
      { label: "设计建议", read: (doc) => doc.neutral_creative },
      { label: "品牌约束", read: (doc) => doc.brand_constraints.join("、") || "未登记" },
      { label: "角色约束", read: (doc) => doc.role_constraints.join("、") || "未登记" },
      { label: "镜头 / 视角", read: (doc) => doc.lens },
      { label: "声音", read: (doc) => doc.sound },
      { label: "镜头表", read: (doc) => (doc.shots ?? []).map((shot) => `${shot.index} · ${shot.duration_s === null ? "时长未定" : `${shot.duration_s} 秒`} · ${shot.purpose}`).join(" / ") || "没有镜头行" },
      { label: "边界", read: (doc) => doc.limits.join("、") || "未登记" },
      { label: "待补充", read: (doc) => doc.known_gaps.join("、") || "未登记" },
      { label: "外部步骤", read: (doc) => doc.external_steps.map((step) => `${step.step} | ${step.tool} | ${step.job_id} | ${step.operation_id}`).join(" / ") || "没有登记" },
      { label: "参考", read: (doc) => doc.references.map((reference) => `${reference.kind} ${reference.id} r${reference.revision}`).join(" / ") || "没有登记" }
    ];
    async function compare() {
      const left = Number(from.value);
      const right = Number(to.value);
      if (!readable.length) {
        status.textContent = "这条方案没有可读的修订：正文解析不了，页面不猜内容。";
        body.replaceChildren();
        return;
      }
      if (left === right) {
        status.textContent = "两个下拉选的是同一个修订：对比需要两份不同的正文。";
        body.replaceChildren();
        return;
      }
      status.textContent = "正在读回这两个修订…";
      try {
        const read = (revision) => api(
          `/projects/${answer.project_id}/assistance-plans/${answer.plan_id}/revisions/${revision}`
        );
        const [older, newer] = await Promise.all([read(left), read(right)]);
        const rows = fields.map((field) => {
          const before = field.read(older.document);
          const after = field.read(newer.document);
          return el(
            "li",
            { class: "list-item value-row" },
            el("span", {}, field.label),
            el(
              "span",
              { class: "tag " + (before === after ? "neutral" : "info") },
              before === after ? "相同" : "不同"
            ),
            el("small", {}, `r${older.revision}：`),
            el("span", {}, before),
            el("small", {}, `r${newer.revision}：`),
            el("span", {}, after)
          );
        });
        body.replaceChildren(el("ul", { class: "list" }, ...rows));
        status.textContent = `对比的是 r${older.revision}（${older.content_sha256}）与 r${newer.revision}（${newer.content_sha256}）：两份正文各来自一次按修订读取，选用状态` + (older.is_chosen === newer.is_chosen ? `两边一致（${older.is_chosen ? "已选用" : "未选用"}）` : "在两边不同") + "。";
      } catch (problem) {
        body.replaceChildren();
        status.textContent = `对比读回失败：${assistanceRefusal(problem)}。没有读到正文就不比较，页面不拿一个版本冒充另一个。`;
      }
    }
    run.onclick = () => {
      void compare();
    };
    if (!readable.length) {
      run.disabled = true;
      status.textContent = "这条方案没有可读的修订，对比按不动：正文解析不了，页面不猜内容。";
    }
    return el(
      "details",
      { class: "advanced", id: "as-compare" },
      el("summary", {}, `修订对比（读到 ${readable.length} 个可读版本）`),
      el(
        "div",
        { class: "advanced-body" },
        el(
          "div",
          { class: "as-row" },
          el("label", { class: "field-row" }, el("span", {}, "较早"), from),
          el("label", { class: "field-row" }, el("span", {}, "较晚"), to)
        ),
        el("div", { class: "as-row" }, run),
        el(
          "p",
          { class: "view-hint" },
          "两份正文都从「按修订读取」的接口读回：新版本从来不覆盖旧版本，这里比较的就是服务里真实存下的两条记录。"
        ),
        status,
        body
      )
    );
  }
  function openChooseForm(answer, actions, note) {
    const name = el("input", {
      id: "as-choose-name",
      class: "input",
      maxlength: "200",
      placeholder: "选用人姓名（必填；这是一条具名人工记录）"
    });
    const error = el("p", { class: "error", role: "alert" });
    const confirm = el("button", {
      type: "submit",
      class: "primary-btn",
      id: "as-choose-submit"
    }, "确认选用");
    const cancel = el("button", {
      type: "button",
      class: "ghost-btn",
      id: "as-choose-cancel"
    }, "取消");
    const chooseForm = el(
      "form",
      { class: "as-choose", id: "as-choose-form" },
      el("label", { class: "field-row" }, el("span", {}, "以谁的名义选用"), name),
      el(
        "p",
        { class: "view-hint" },
        `将记录：${answer.latest_revision} 这一次修订被具名的人选用。它不是评分，也不是系统推荐；复制文本不需要这一步。`
      ),
      error,
      el("div", { class: "as-actions" }, confirm, cancel)
    );
    chooseForm.onsubmit = (event) => {
      event.preventDefault();
      const actor = name.value.trim();
      if (!actor) {
        error.textContent = "请填写选用人姓名：只有具名的人可以选用，代理不能替人选用。";
        name.focus();
        return;
      }
      confirm.disabled = true;
      void (async () => {
        try {
          const chosen = await api(
            `/projects/${selected}/assistance-plans/${answer.plan_id}/choose`,
            { actor, actor_kind: "human", revision: answer.latest_revision }
          );
          note.textContent = `已记录：${actor} 选用 r${answer.latest_revision}。`;
          renderDetail(chosen);
          await refreshPlans();
        } catch (failure) {
          error.textContent = `选用失败：${assistanceRefusal(failure)}`;
          confirm.disabled = false;
        }
      })();
    };
    cancel.onclick = () => {
      actions.replaceChildren();
      renderDetail(answer);
    };
    actions.replaceChildren(chooseForm);
    name.focus();
  }
  function endEditing() {
    editing = null;
    duplicateFrom = "";
    submit.textContent = "整理方案";
    cancelEdit.classList.add("as-hidden");
  }
  const DRAFT_PREFIX = "design-lab.plan-draft";
  const DRAFT_TTL_MS = 24 * 60 * 60 * 1e3;
  const DRAFT_MAX_CHARS = 12e3;
  const draftSlot = () => editing ? `revise:${editing.planId}:r${editing.expectedRevision}` : duplicateFrom ? `duplicate:${duplicateFrom}` : `new:${selected}`;
  const draftValues = () => ({
    objective: objective.value,
    creative: creative.value,
    brand: brand.value,
    role: role.value,
    lens: lens.value,
    sound: sound.value,
    gaps: gaps.value,
    limits: limits.value,
    steps: stepText.value,
    author: author.value
  });
  const draftShots = () => shotRows.map((row) => ({
    duration: row.duration.value,
    purpose: row.purpose.value,
    camera: row.camera.value,
    soundNote: row.soundNote.value,
    role: row.role.value
  }));
  const hasDraftText = (fields, shots) => Object.values(fields).some((value) => value.trim() !== "") || shots.some((row) => Object.values(row).some((value) => value.trim() !== ""));
  const writeDraft = () => {
    const slot = draftSlot();
    const fields = draftValues();
    const shots = draftShots();
    if (!hasDraftText(fields, shots)) return;
    try {
      const payload = JSON.stringify({ slot, savedAt: Date.now(), fields, shots });
      if (payload.length > DRAFT_MAX_CHARS) return;
      globalThis.localStorage?.setItem(`${DRAFT_PREFIX}:${slot}`, payload);
    } catch {
    }
  };
  const clearDraft = (slot) => {
    try {
      globalThis.localStorage?.removeItem(`${DRAFT_PREFIX}:${slot}`);
    } catch {
    }
  };
  const offerDraft = () => {
    const slot = draftSlot();
    let saved = null;
    try {
      const raw = globalThis.localStorage?.getItem(`${DRAFT_PREFIX}:${slot}`);
      if (!raw || raw.length > DRAFT_MAX_CHARS) return;
      saved = JSON.parse(raw);
    } catch {
      return;
    }
    if (!saved || saved.slot !== slot || typeof saved.savedAt !== "number" || Date.now() - saved.savedAt > DRAFT_TTL_MS) return;
    const fields = saved.fields;
    const restored = {
      ...draftValues(),
      ...Object.fromEntries(Object.entries(fields ?? {}).filter(([, value]) => typeof value === "string"))
    };
    const rawShots = Array.isArray(saved.shots) ? saved.shots : [];
    const shots = rawShots.filter((row) => row && typeof row === "object" && typeof row.purpose === "string" && typeof row.duration === "string" && typeof row.camera === "string" && typeof row.soundNote === "string" && typeof row.role === "string");
    if (!hasDraftText(restored, shots)) return;
    for (const [key, value] of Object.entries(restored)) {
      const node = {
        objective,
        creative,
        brand,
        role,
        lens,
        sound,
        gaps,
        limits,
        steps: stepText,
        author
      }[key];
      node.value = value;
    }
    if (shots.length) {
      clearShotRows();
      for (const row of shots) addShotRow(row);
      objective.focus();
    }
    formStatus.textContent = `这台机器上有一份未完成的编辑（${new Date(saved.savedAt).toLocaleString()}），已经放回表单：它只在本机，超过 24 小时就不再拿回来，保存成功后会清掉。输出类型按这条方案原本的类型与服务读回的词表，参考与附件不在草稿里，需要重新挑。`;
  };
  let draftTimer = null;
  const scheduleDraft = () => {
    if (draftTimer) clearTimeout(draftTimer);
    draftTimer = setTimeout(writeDraft, 400);
  };
  const cancelDraftWrite = (slot) => {
    if (draftTimer) clearTimeout(draftTimer);
    draftTimer = null;
    clearDraft(slot);
  };
  form.addEventListener("input", scheduleDraft);
  form.addEventListener("change", scheduleDraft);
  async function openFormFor(doc, submitLabel, statusLine, focusTarget) {
    if (!workspaces.some((project2) => project2.id === doc.project_id)) {
      workspaces = (await loadWorkspaces()).projects;
    }
    selected = doc.project_id;
    fillWorkspaces();
    objective.value = doc.objective;
    chooseOutputType(doc.output_type);
    creative.value = doc.neutral_creative === ASSIST_UNKNOWN ? "" : doc.neutral_creative;
    brand.value = doc.brand_constraints.join("、");
    role.value = doc.role_constraints.join("、");
    lens.value = doc.lens === ASSIST_UNKNOWN ? "" : doc.lens;
    sound.value = doc.sound === ASSIST_UNKNOWN ? "" : doc.sound;
    gaps.value = doc.known_gaps.join("、");
    limits.value = doc.limits.join("、");
    stepText.value = doc.external_steps.map((step) => [
      step.step,
      step.tool === ASSIST_UNKNOWN ? "" : step.tool,
      step.job_id === ASSIST_UNUSED ? "" : step.job_id,
      step.operation_id === ASSIST_UNUSED ? "" : step.operation_id
    ].join(" | ")).join("\n");
    fillShotRows(doc.shots ?? []);
    references = doc.references.map((reference) => ({
      kind: reference.kind,
      id: reference.id
    }));
    await refreshReferenceSources();
    await refreshPlans();
    submit.textContent = submitLabel;
    cancelEdit.classList.remove("as-hidden");
    more.open = true;
    formStatus.textContent = statusLine;
    clearFieldRefusal();
    offerDraft();
    form.scrollIntoView({ block: "start" });
    focusTarget.focus();
  }
  async function startEditing(answer, focusCreative) {
    const doc = answer.current;
    if (!doc) return;
    editing = { planId: answer.plan_id, expectedRevision: answer.latest_revision };
    duplicateFrom = "";
    await openFormFor(
      doc,
      "保存为新修订",
      `正在修订 r${answer.latest_revision}：保存会追加一条新修订，旧版本保留。`,
      focusCreative ? creative : objective
    );
  }
  async function startDuplicating(answer) {
    const doc = answer.current;
    if (!doc) return;
    editing = null;
    duplicateFrom = answer.plan_id;
    await openFormFor(
      doc,
      "另存为新方案",
      `以上内容取自 ${answer.plan_id} 的 r${doc.revision}：保存会新建一条方案（编号由服务铸造），这一条与它的修订历史都不变。参考与附件只带 id，保存时由服务重新核对，对不上会被点名拒绝。`,
      objective
    );
  }
  async function openPlan(planId) {
    if (!selected) return;
    detailHost.replaceChildren(el("p", { class: "view-loading" }, "正在读回方案…"));
    try {
      const answer = await api(
        `/projects/${selected}/assistance-plans/${planId}`
      );
      renderDetail(answer);
      document.getElementById("as-plan")?.scrollIntoView({ block: "start" });
    } catch (error) {
      detailHost.replaceChildren(
        el("p", { class: "error" }, `方案读回失败：${assistanceRefusal(error)}`),
        el("button", {
          type: "button",
          class: "ghost-btn",
          onclick: () => {
            void openPlan(planId);
          }
        }, "重新读回")
      );
    }
  }
  async function afterWrite(planId, message) {
    formStatus.textContent = message;
    await openPlan(planId);
    await refreshPlans();
  }
  async function submitPlan() {
    if (busy2) return;
    clearFieldRefusal();
    formStatus.replaceChildren();
    const text = objective.value.trim();
    if (!text) {
      showFieldRefusal(
        objective,
        "请先写下要完成的设计目标：保存的是一条方案记录，不是一次运行。"
      );
      return;
    }
    if (!author.value.trim()) {
      showFieldRefusal(author, "记录人不能为空：方案要写明是谁写的。");
      return;
    }
    if (!chosenOutputType()) {
      showFieldRefusal(
        outputType,
        "输出类型未读回，暂时无法保存；这个选择来自服务，页面不手抄一份词表。"
      );
      return;
    }
    const stepRows = assistanceSteps(stepText.value);
    if (stepRows === null) {
      showFieldRefusal(
        stepText,
        "外部步骤每行都要有步骤名称：格式是「步骤 | 工具 | 作业编号 | 操作编号」，后三项可留空。"
      );
      return;
    }
    const shots = shotTable();
    if (shots.problem) {
      more.open = true;
      showFieldRefusal(shotHost, shots.problem);
      return;
    }
    busy2 = true;
    submit.disabled = true;
    const draftWasFor = draftSlot();
    try {
      if (!selected) {
        const name = workspaceName.value.trim() || text.slice(0, 20);
        const created = await api("/projects", { name });
        selected = created.project.id;
        workspaces = (await loadWorkspaces()).projects;
        fillWorkspaces();
      }
      const body = {
        objective: text,
        output_type: chosenOutputType(),
        neutral_creative: creative.value.trim() || null,
        brand_constraints: assistanceWords(brand.value),
        role_constraints: assistanceWords(role.value),
        lens: lens.value.trim() || null,
        sound: sound.value.trim() || null,
        references: references.map((reference) => ({
          kind: reference.kind,
          id: reference.id
        })),
        external_steps: stepRows,
        known_gaps: assistanceWords(gaps.value),
        limits: assistanceWords(limits.value),
        shots: shots.rows,
        created_by: author.value.trim()
      };
      if (editing) {
        const saved = await api(
          `/projects/${selected}/assistance-plans/${editing.planId}/revisions`,
          { ...body, expected_revision: editing.expectedRevision }
        );
        const planId = saved.plan.plan_id;
        cancelDraftWrite(draftWasFor);
        endEditing();
        objective.value = "";
        creative.value = "";
        references = [];
        stepText.value = "";
        clearShotRows();
        renderReferences();
        await afterWrite(planId, `已保存为 r${saved.revision}：旧修订保留，新修订成为最新。`);
      } else {
        const copiedFrom = duplicateFrom;
        const saved = await api(
          `/projects/${selected}/assistance-plans`,
          body
        );
        cancelDraftWrite(draftWasFor);
        objective.value = "";
        creative.value = "";
        references = [];
        stepText.value = "";
        clearShotRows();
        renderReferences();
        endEditing();
        await afterWrite(
          saved.plan.plan_id,
          (copiedFrom ? `已复制为新的方案 ${saved.plan.plan_id}：内容取自 ${copiedFrom}，那一条与它的修订历史都没有变化。` : "已保存 ") + `r${saved.revision}。` + (saved.plan.neutral_creative === ASSIST_UNKNOWN ? "这条方案还没有创意，四态里「方案已提供」会保持为否。" : "")
        );
      }
      await refreshReferenceSources();
    } catch (error) {
      const envelope = error?.serviceEnvelope;
      if (editing && envelope?.error === "ASSISTANCE_PLAN_REVISION_CONFLICT") {
        clearFieldRefusal();
        formError.replaceChildren(
          el("span", {}, `保存失败：${assistanceRefusal(error)}。这次写入按 r${editing.expectedRevision} 准备，服务里的方案已经前进；你的输入还在，读回最新后可以再保存。`),
          el("button", {
            type: "button",
            class: "ghost-btn",
            id: "as-reload-latest",
            onclick: () => {
              void (async () => {
                const planId = editing?.planId;
                if (!planId) return;
                const answer = await api(
                  `/projects/${selected}/assistance-plans/${planId}`
                );
                renderDetail(answer);
                await startEditing(answer, false);
              })();
            }
          }, "读回最新并保留我的输入")
        );
      } else {
        const refusal = assistanceRefusal(error);
        clearFieldRefusal();
        formError.textContent = `保存失败：${refusal}${refusal.endsWith("。") ? "" : "。"}你的输入还在这个表单里，改动没有离开它。`;
      }
    } finally {
      busy2 = false;
      submit.disabled = outputTypes.length === 0;
    }
  }
  form.onsubmit = (event) => {
    event.preventDefault();
    void submitPlan();
  };
  cancelEdit.onclick = () => {
    const copiedFrom = duplicateFrom;
    const planBeingRevised = editing?.planId ?? "";
    endEditing();
    formStatus.textContent = copiedFrom ? `已取消复制：${copiedFrom} 与它的内容都没有任何变化，也没有新方案被写入。` : `已取消修订${planBeingRevised ? "：" + planBeingRevised : ""}；服务里的方案没有变化。`;
    clearFieldRefusal();
  };
  addReference.onclick = () => {
    const chosen = assetSelect.value;
    const separator = chosen.indexOf(":");
    if (separator < 1) return;
    const reference = { kind: chosen.slice(0, separator), id: chosen.slice(separator + 1) };
    if (references.some((entry) => entry.kind === reference.kind && entry.id === reference.id))
      return;
    references = [...references, reference];
    renderReferences();
  };
  workspace.onchange = () => {
    selected = workspace.value;
    workspaceNameRow.classList.toggle("as-hidden", selected !== "");
    references = [];
    void (async () => {
      try {
        await refreshReferenceSources();
        await refreshPlans();
      } catch (error) {
        showFieldRefusal(workspace, `工作区读数失败：${assistanceRefusal(error)}`);
      }
    })();
  };
  const types = await loadVocabulary();
  outputTypes = types.output_types;
  materials = types.export_formats ?? [];
  fillPlanTypeFilter();
  outputType.replaceChildren(
    ...outputTypes.length ? outputTypes.map((option) => el(
      "label",
      { class: "as-chip" },
      el("input", { type: "radio", name: "as-output-type", value: option.value }),
      el("span", {}, option.label)
    )) : [el("span", { class: "as-chips-empty" }, "输出类型未读回")]
  );
  submit.disabled = outputTypes.length === 0;
  const listing = await loadWorkspaces();
  workspaces = listing.projects;
  selected = workspaces.length ? workspaces[workspaces.length - 1].id : "";
  fillWorkspaces();
  fillAssets();
  renderReferences();
  void (async () => {
    try {
      await loadKnowledgeChoices();
    } catch (error) {
      knowledgeNotice = `库未读回：${assistanceRefusal(error)}`;
      fillAssets();
      renderReferences();
    }
  })();
  renderPlans();
  offerDraft();
  if (selected) {
    await refreshReferenceSources();
    await refreshPlans();
  } else {
    assetsNotice = "";
  }
  const notice = notices();
  meta.replaceChildren(
    ...notice ? [el("p", { class: "error" }, notice)] : [],
    el(
      "p",
      { class: "view-hint" },
      "四态由服务读回：已保存、方案已提供、用户选用、外部未验证。「已保存」不等于「已生成」；「外部未验证」不是警告，是服务不派发也不核验外部步骤。"
    )
  );
  target.replaceChildren(
    el(
      "div",
      { class: "page-head as-head" },
      el(
        "div",
        {},
        el("h2", {}, "设计辅助"),
        el("p", {}, "写下一个目标，保存为一条可读的方案：先有需求、参考附件与输出类型，工具与模型稍后再选。页面不做聊天气泡流、节点画布或多 Agent 控制台。")
      )
    ),
    el("div", { class: "split as-split" }, form, listPanel),
    detailHost,
    meta
  );
}
const TP_PICK_ORDER = ["software", "agent", "entry", "model", "task_mode"];
const TP_ADVANTAGE_FIELDS = ["input_modality", "reference_roles", "output_form", "prompt_style"];
const TP_LIMIT_FIELDS = ["negative_input", "known_conflicts", "asset_limits", "ranges"];
const TP_OFFICIAL_PROVENANCE = ["OFFICIAL_DOC", "OPEN_SOURCE_IMPL"];
const TP_SUPPORT_TAG = {
  DOCUMENTED_CLAIM: "info",
  CONDITIONAL: "warn",
  UNREACHED: "bad",
  USER_DRAFT: "neutral"
};
const TP_SUPPORT_NOTE = {
  DOCUMENTED_CLAIM: "官方页面写到了这一项，但本项目没有跑过",
  CONDITIONAL: "官方页面自述尚未交付，或只在另一个入口成立",
  UNREACHED: "本轮没有取回任何官方字节，全部字段保持未知",
  USER_DRAFT: "某个人在这里登记了意向，没有对外部目标的证据"
};
const TP_VERDICT_TAG = {
  DOCUMENTED_SUPPORT: "info",
  DOCUMENTED_NOT_SUPPORT: "bad",
  UNKNOWN: "neutral",
  NOT_APPLICABLE: "warn"
};
const TP_DEFAULT_ASK = {
  modality: "一段文本加一张参考图",
  reference_role: "这张参考图承担 style",
  asset_count: "3 张参考图",
  asset_format: "PNG",
  duration: "8 秒",
  aspect: "9:16",
  resolution: "1080x1920",
  negative_input: "一段负向提示",
  parameter: "seed"
};
const TP_DEFAULT_DIMENSIONS = ["modality", "reference_role", "negative_input", "parameter"];
function tpFieldText(field) {
  if (!field) return "这一项没有读回来";
  if (field.value !== null && field.value !== void 0) return field.value;
  return field.reason ?? "没有值，也没有说明为什么没有值（这是档案的缺陷，不是一种支持声明）";
}
function tpSupportBadge(state) {
  return el("span", {
    class: "tag " + (TP_SUPPORT_TAG[state] ?? "neutral"),
    dataset: { support: state }
  }, en(state));
}
function tpRefusal(error) {
  const envelope = error?.serviceEnvelope;
  const code = envelope?.error;
  const detail = envelope?.detail;
  if (typeof code !== "string") return errMsg(error);
  return typeof detail === "string" && detail ? `${code}：${detail}` : code;
}
async function renderTargetProfiles(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回目标档案词表与档案清单…"));
  const axesRead = await apiOrEmpty(
    "/target-profile-axes",
    OFFLINE.targetProfileAxes
  );
  const listRead = await apiOrEmpty(
    "/target-profiles?limit=100",
    OFFLINE.targetProfiles
  );
  let axesNotice = shapeNotice(axesRead);
  let listNotice = shapeNotice(listRead);
  let axesOffline = disconnectedNotice(axesRead);
  let listOffline = disconnectedNotice(listRead);
  const axes = axesRead;
  let profiles = listRead.profiles;
  const axisLabel = new Map(axes.axes.map((option) => [option.key, option.label]));
  const fieldLabel = new Map(axes.capability_fields.map((option) => [option.key, option.label]));
  const provenanceLabel = new Map(
    axes.provenance_kinds.map((option) => [option.key, option.label])
  );
  const measuredFields = axesOffline || typeof axes.measured_fields !== "number" ? null : axes.measured_fields;
  const histogramCount = (kind) => {
    if (listOffline) return null;
    const value = listRead.provenance_histogram?.[kind];
    return typeof value === "number" ? value : null;
  };
  const numberOr = (value) => value === null ? "未读回" : String(value);
  const chosen = {};
  for (const key of TP_PICK_ORDER) chosen[key] = "";
  let planOnly = false;
  let resolved = null;
  let answer = null;
  let stale = false;
  let busy2 = false;
  const askedInputs = /* @__PURE__ */ new Map();
  const software = el("select", { id: "tp-software", class: "input" });
  const agent = el("select", { id: "tp-agent", class: "input" });
  const entry = el("select", { id: "tp-entry", class: "input" });
  const model = el("select", { id: "tp-model", class: "input" });
  const taskMode = el("select", { id: "tp-task-mode", class: "input" });
  const pickers = {
    software,
    agent,
    entry,
    model,
    task_mode: taskMode
  };
  const planOnlyBox = el("input", { type: "checkbox", id: "tp-plan-only" });
  const actor = el("input", {
    id: "tp-actor",
    class: "input",
    maxlength: "200",
    placeholder: "你的名字或代号（登记草稿目标时必填，页面不代人签名）"
  });
  const sourceRef = el("input", {
    id: "tp-source-ref",
    class: "input",
    maxlength: "200",
    placeholder: "外部作业编号：自己填写；留空就是不使用，服务写 UNUSED"
  });
  const combination = el("p", { class: "view-hint tp-name", id: "tp-combination", role: "status" });
  const limits = el("p", { class: "view-hint tp-name", id: "tp-limits" });
  const creative = el("textarea", {
    id: "tp-creative",
    class: "input",
    rows: "4",
    placeholder: "一段中性的创意说明。它不跟着目标重写：02:68「更换模型时保留故事、品牌、镜头目的与素材角色」。"
  });
  const brand = el("input", {
    id: "tp-brand",
    class: "input",
    placeholder: "品牌约束（用、或逗号分隔），切换目标后仍在原位"
  });
  const verifyState = el("div", { class: "view-hint", id: "tp-verify-state", role: "status" });
  const verdictHost = el("div", { id: "tp-verdicts" });
  const validate = el(
    "button",
    { type: "button", class: "primary-btn", id: "tp-validate" },
    "按这个目标重新校验"
  );
  const verifyError = el("p", { class: "error", id: "tp-verify-error", role: "alert" });
  const officialHead = el("div", { class: "kb-meta", id: "tp-official-head" });
  const officialList = el("ul", { class: "list", id: "tp-official-list" });
  const untestedHead = el("div", { class: "kb-meta", id: "tp-untested-head" });
  const untestedList = el("ul", { class: "list", id: "tp-untested-list" });
  const officialPanel = el(
    "section",
    {
      class: "panel",
      id: "tp-official",
      dataset: { column: "official" }
    },
    el("h3", {}, "官方支持"),
    officialHead,
    officialList
  );
  const untestedPanel = el(
    "section",
    {
      class: "panel",
      id: "tp-untested",
      dataset: { column: "untested" }
    },
    el("h3", {}, "本项目未测试"),
    untestedHead,
    untestedList
  );
  const routeNote = el("p", { class: "view-hint", id: "tp-route-note" });
  const routeHost = el("div", { class: "grid-stack", id: "tp-routes" });
  const fieldHost = el("div", { class: "grid-stack", id: "tp-more-fields" });
  const dimensionHost = el("div", { class: "grid-stack", id: "tp-dimensions" });
  const draftOut = el("p", { class: "tp-line", id: "tp-draft-out", role: "status" });
  const draftSave = el(
    "button",
    { type: "button", class: "ghost-btn", id: "tp-draft-save" },
    "把当前组合登记为草稿目标"
  );
  const meta = el("div", { class: "kb-meta", id: "tp-meta", role: "status" });
  function poolBefore(axisIndex) {
    if (axisIndex > 0 && !chosen.software) return [];
    let pool = profiles;
    for (let i = 0; i < axisIndex; i += 1) {
      const key = TP_PICK_ORDER[i];
      if (!chosen[key]) break;
      pool = pool.filter((profile) => profile.axes[key] === chosen[key]);
    }
    return pool;
  }
  function optionValues(axisIndex, key) {
    const seen = [];
    for (const profile of poolBefore(axisIndex)) {
      const value = profile.axes[key];
      if (typeof value === "string" && value && !seen.includes(value)) seen.push(value);
    }
    return seen.sort();
  }
  function fillPicker(key, axisIndex, emptyLabel) {
    const select = pickers[key];
    const pool = poolBefore(axisIndex);
    const values = optionValues(axisIndex, key);
    if (chosen[key] && !values.includes(chosen[key])) chosen[key] = "";
    select.replaceChildren(
      el("option", { value: "" }, emptyLabel),
      ...values.map((value) => el(
        "option",
        { value },
        `${value} · 这个入口下 ${pool.filter((profile) => profile.axes[key] === value).length} 份档案`
      ))
    );
    select.value = chosen[key];
  }
  function fillPickers() {
    const catalogued = profiles.map((profile) => profile.axes.software ?? "");
    const values = [...new Set([...axes.software, ...catalogued].filter((value) => value))].sort();
    software.replaceChildren(
      el("option", { value: "" }, "暂不指定（未知目标，不是一次可运行的选择）"),
      ...values.map((value) => el(
        "option",
        { value },
        catalogued.includes(value) ? value : `${value} · 服务词表里有，档案还没覆盖`
      ))
    );
    software.value = chosen.software;
    const pending = chosen.software ? "" : "（先选软件或 Agent）";
    fillPicker("agent", 1, `未声明 Agent：档案没填这一轴，不等于没有 Agent${pending}`);
    fillPicker("entry", 2, `接入方式未指定${pending}`);
    fillPicker("model", 3, `模型未指定${pending}`);
    fillPicker("task_mode", 4, `任务模式未指定${pending}`);
  }
  function resolveTarget() {
    const pool = poolBefore(TP_PICK_ORDER.length);
    resolved = pool.length === 1 ? pool[0] : null;
  }
  function combinationText() {
    if (!chosen.software) {
      return "当前组合：暂不指定目标。这不是一个可运行的目标，只是一个还没指定的规划状态" + (planOnly ? " ｜ 已勾选仅规划" : "");
    }
    if (resolved) {
      const parts2 = TP_PICK_ORDER.map((key) => `${axisLabel.get(key) ?? key}：${resolved?.axes[key] ?? "未声明"}`);
      return `${parts2.join(" · ")} —— 唯一对应档案 ${resolved.profile_key}（${resolved.origin === "SEEDED" ? "配置内种子" : "某人登记的草稿"}）` + (planOnly ? " ｜ 仅规划" : "");
    }
    const parts = TP_PICK_ORDER.map((key) => `${axisLabel.get(key) ?? key}：${chosen[key] || "未选"}`);
    return `${parts.join(" · ")} —— 当前组合对应 ${poolBefore(TP_PICK_ORDER.length).length} 份档案，还没唯一到一个目标` + (planOnly ? " ｜ 仅规划" : "");
  }
  function limitsText() {
    if (!chosen.software) {
      return `「暂不指定」的限制：这一屏不推荐路线、不校验参数，也不会运行任何东西。服务在清单应答里写着 executable=${String(listRead.executable)}；"没有指定目标" 与 "目标已经可以跑" 是两件事。`;
    }
    if (!resolved) {
      return `还没唯一到一个目标：可以读档案，但不能校验一个不存在的组合。服务的可执行常量是 executable=${String(listRead.executable)}。`;
    }
    if (planOnly) {
      return `「仅规划」的限制：这个组合只作为规划材料留着。02:66 说用户仍能保留仅规划的未验证路线，但系统不能标它已可执行；本轮对这份档案读到的 executable=${String(resolved.executable)}，没有一次外部调用。`;
    }
    return `两条始终成立的限制：左栏「官方支持」只是别人的页面或实现里写了什么，右栏「本项目未测试」才是我们自己的状态（实测字段 ${numberOr(measuredFields)} 项）；并且本轮不运行任何外部产品或模型（读到的 executable=${String(resolved.executable)}）。`;
  }
  function fieldRow2(labelText, field) {
    const state = field?.state ?? "UNKNOWN";
    const tag = state === "DOCUMENTED" ? "info" : state === "NOT_DOCUMENTED" ? "warn" : "bad";
    const provenance = field?.provenance ?? "";
    return el(
      "li",
      { class: "list-item value-row" },
      el(
        "div",
        { class: "kb-badges kb-badges-start" },
        el("strong", { class: "tp-name" }, labelText),
        el("span", { class: "tag " + tag }, en(state)),
        el(
          "span",
          { class: "tag neutral" },
          provenanceLabel.get(provenance) ?? "出处不在服务词表里"
        )
      ),
      el("small", { class: "tp-name" }, tpFieldText(field)),
      ...field?.source ? [el(
        "small",
        { class: "value-mono" },
        `${field.source}${field.observed_at ? ` · 读到日 ${field.observed_at}` : ""}`
      )] : []
    );
  }
  function rowsFor(keys, fields) {
    return keys.map((key) => fieldRow2(fieldLabel.get(key) ?? key, fields[key]));
  }
  function measuredFieldCount(fields) {
    return Object.keys(fields).filter((key) => fields[key].provenance === "PROJECT_MEASURED").length;
  }
  function renderTruthColumns() {
    const subject = resolved;
    const fields = subject?.fields ?? {};
    const keys = Object.keys(fields);
    const officialKeys = keys.filter(
      (key) => TP_OFFICIAL_PROVENANCE.includes(fields[key].provenance)
    );
    const untestedKeys = keys.filter((key) => !officialKeys.includes(key));
    officialHead.replaceChildren(
      el("p", {}, subject ? `这份档案里出处属于官方文档或开源实现的字段：${officialKeys.length} 项` : listOffline ? `${listOffline}：本批有几份档案、各出处多少项，都是没问到的数，不写成 0。` : `还没唯一到一个目标。本批 ${profiles.length} 份档案合计：官方文档出处 ${numberOr(histogramCount("OFFICIAL_DOC"))} 项、开源实现证据 ${numberOr(histogramCount("OPEN_SOURCE_IMPL"))} 项（读自清单应答的 provenance_histogram，不是页面自己数的）`),
      el("p", {}, '这一栏只说"别人的页面或实现里写着什么"。它不等于本项目验证过——验证过的东西在右栏，右栏现在是空的。')
    );
    officialList.replaceChildren(...subject && officialKeys.length ? rowsFor(officialKeys, fields) : [emptyLi(
      listRead,
      "尚无官方出处字段",
      subject ? "这份档案的每个字段都不是官方文档或开源实现的出处。" : "唯一到一个目标之后，这里逐项列出它的官方出处字段。"
    )]);
    untestedHead.replaceChildren(
      el(
        "p",
        {
          id: "tp-measured-count",
          // 全批的实测字段数读服务的 axes.measured_fields；这一份档案自己的数现数，不写死。
          dataset: {
            all: numberOr(measuredFields),
            profile: subject ? String(measuredFieldCount(fields)) : ""
          }
        },
        subject ? `本项目实测字段数（这份档案）：${measuredFieldCount(fields)}` : `本项目实测字段数（全部档案合计，读自 axes.measured_fields）：${numberOr(measuredFields)}`
      ),
      el("p", {}, `出处直方图里的本项目实测（PROJECT_MEASURED）：${numberOr(histogramCount("PROJECT_MEASURED"))} 项`),
      el("p", {}, axes.measured_note || '未读回服务关于"这一列为什么是这个数"的说明。'),
      el(
        "div",
        { class: "grid-stack", id: "tp-support-histogram" },
        ...Object.entries(listRead.support_histogram ?? {}).length ? Object.entries(listRead.support_histogram ?? {}).map(([state, count]) => el(
          "p",
          { class: "tp-line" },
          tpSupportBadge(state),
          ` ${TP_SUPPORT_NOTE[state] ?? "这一档不在服务的 support_states 词表里，按原词显示"}：${count} 份档案`
        )) : [el(
          "p",
          { class: "tp-line", id: "tp-support-histogram-empty" },
          `支持状态直方图${listOffline ? `：${listOffline}` : "未读回：应答里没有这个映射"}`
        )]
      )
    );
    untestedList.replaceChildren(
      ...subject ? rowsFor(untestedKeys.length ? untestedKeys : keys, fields) : profiles.map((profile) => el(
        "li",
        { class: "list-item value-row" },
        el(
          "div",
          { class: "kb-badges kb-badges-start" },
          el("strong", { class: "tp-name" }, profile.axes.software ?? profile.profile_key),
          tpSupportBadge(profile.support_state)
        ),
        el(
          "small",
          { class: "tp-name" },
          `${TP_SUPPORT_NOTE[profile.support_state] ?? "按原词显示"}；档案 ${profile.profile_key} 里本项目实测 0 项`
        )
      )),
      ...(subject?.reach_attempts ?? []).length ? [el(
        "li",
        { class: "list-item value-row", id: "tp-reach-attempts" },
        el("strong", { class: "tp-name" }, "取回尝试（档案正文登记的每一次）"),
        ...(subject?.reach_attempts ?? []).map((attempt) => el(
          "small",
          { class: "value-mono" },
          attempt
        ))
      )] : [],
      ...subject?.conditional_reason ? [el(
        "li",
        { class: "list-item value-row", id: "tp-conditional-reason" },
        el("strong", { class: "tp-name" }, "条件成立的原因（档案正文原句）"),
        el("small", { class: "tp-name" }, subject.conditional_reason)
      )] : []
    );
  }
  function routePool() {
    if (!chosen.software) return [];
    return poolBefore(1);
  }
  function renderRoutes() {
    const pool = routePool();
    if (!pool.length) {
      routeHost.replaceChildren(el(
        "p",
        { class: "tp-line", id: "tp-routes-empty" },
        chosen.software ? '这个软件下没有可读回的档案：不推荐任何路线，也不把"没有档案"写成"不支持"。' : '暂不指定目标：这一屏不给路线。"没指定"不是一条通用路线，也不是一次可运行的选择。'
      ));
      routeNote.textContent = "上面那句是状态说明，不是一条候选。";
      return;
    }
    const documented = pool.filter((profile) => profile.support_state === "DOCUMENTED_CLAIM");
    const ordered = (documented.length ? documented : pool).slice().sort((a, b) => a.profile_key.localeCompare(b.profile_key));
    const picked = ordered.slice(0, 2);
    routeHost.replaceChildren(...picked.map((profile, index) => el(
      "article",
      {
        class: "row-card grid-stack",
        id: `tp-route-${index + 1}`,
        dataset: { profile: profile.profile_key, support: profile.support_state }
      },
      el(
        "h4",
        { class: "tp-name" },
        `${profile.axes.software ?? "软件未声明"} · ${profile.axes.entry ?? "接入方式未声明"} · ${profile.axes.task_mode ?? "任务模式未声明"}`
      ),
      el(
        "div",
        { class: "kb-badges kb-badges-start" },
        tpSupportBadge(profile.support_state),
        el("span", { class: "tag neutral" }, "并列候选，不排名"),
        ...planOnly ? [el("span", { class: "tag warn" }, "仅规划")] : []
      ),
      el(
        "div",
        { class: "grid-stack", id: `tp-route-${index + 1}-advantage` },
        el("p", { class: "tp-line" }, el("strong", {}, "优势（档案正文原句）")),
        ...TP_ADVANTAGE_FIELDS.map((key) => el(
          "p",
          { class: "tp-line" },
          `${fieldLabel.get(key) ?? key}：${tpFieldText(profile.fields[key])}`
        ))
      ),
      el(
        "div",
        { class: "grid-stack", id: `tp-route-${index + 1}-limit` },
        el("p", { class: "tp-line" }, el("strong", {}, "限制（档案正文原句）")),
        ...TP_LIMIT_FIELDS.map((key) => el(
          "p",
          { class: "tp-line" },
          `${fieldLabel.get(key) ?? key}：${tpFieldText(profile.fields[key])}`
        ))
      ),
      ...profile.conditional_reason ? [el("p", { class: "tp-line" }, `条件：${profile.conditional_reason}`)] : [],
      el(
        "p",
        { class: "view-hint" },
        "这两段只有档案里已有的句子，页面不加判断、不给分、不排名；「本项目实测 0 项」是本项目自己的状态，不是这份档案的缺点。"
      )
    )));
    routeNote.textContent = picked.length === pool.length ? `当前组合下共 ${pool.length} 条候选，全部列出（屏幕三的上限是两条）。` : `当前组合下还有 ${pool.length - picked.length} 条候选没有列出——这一屏最多两条，这不是把它们判成了次选。`;
  }
  function renderVerify() {
    const subject = resolved;
    verifyState.replaceChildren(el("p", { class: "tp-name" }, combinationText()));
    if (!subject) {
      validate.disabled = true;
      validate.textContent = "按这个目标重新校验";
      verdictHost.replaceChildren();
      return;
    }
    validate.disabled = busy2;
    validate.textContent = stale ? "按新目标重新校验" : "按这个目标重新校验";
    verifyState.append(el("p", {}, stale || !answer ? `目标已指向 ${subject.profile_key}：参数与参考角色需要重新校验。上面那两栏创意方向与品牌约束保留原位，不需要重填（06:20 验收 B2）。` : `目标 ${answer.profile_key} 已重新校验：${answer.verdicts.length} 条 verdict，每条都不授予可执行状态。`));
    if (answer && !stale) {
      const allFalse = answer.verdicts.every((verdict) => verdict.grants_execution === false);
      verdictHost.replaceChildren(el(
        "ul",
        {
          class: "list",
          id: "tp-verdict-list",
          // grants_execution 是服务在每条 verdict 里自带的字段；这里把"整批都为 false"写成一个
          // 可被几何闸读到的属性，而不是页面上的一句口号。
          dataset: { grantsExecution: String(allFalse), answerKey: answer.profile_key }
        },
        ...answer.verdicts.map((verdict) => el(
          "li",
          { class: "list-item value-row" },
          el(
            "div",
            { class: "kb-badges kb-badges-start" },
            el("strong", { class: "tp-name" }, `${verdict.dimension} ｜ 问的是：${verdict.asked}`),
            el("span", {
              class: "tag " + (TP_VERDICT_TAG[verdict.verdict] ?? "neutral"),
              dataset: { verdict: verdict.verdict }
            }, en(verdict.verdict)),
            el(
              "span",
              { class: "tag bad", dataset: { grants: String(verdict.grants_execution) } },
              en("grants_execution=false")
            )
          ),
          el("small", { class: "tp-name" }, `依据字段：${fieldLabel.get(verdict.field) ?? verdict.field} ｜ ${verdict.reason}`),
          ...verdict.source ? [el("small", { class: "value-mono" }, String(verdict.source))] : []
        )),
        el(
          "li",
          { class: "list-item value-row", id: "tp-execution-note" },
          el("strong", { class: "tp-name" }, "这次校验说了什么、没说什么"),
          el("small", { class: "tp-name" }, answer.execution_note),
          el(
            "small",
            { class: "tp-name" },
            "读到的 executable=",
            String(answer.executable),
            " · 这份档案的支持状态：",
            en(answer.support_state)
          ),
          el("small", { class: "tp-name" }, `退路（档案正文）：${tpFieldText(answer.fallback)}`)
        )
      ));
      return;
    }
    verdictHost.replaceChildren();
  }
  async function runValidate() {
    const subject = resolved;
    if (!subject) return;
    busy2 = true;
    validate.disabled = true;
    verifyError.textContent = "";
    const dimensions = {};
    for (const box of Array.from(dimensionHost.querySelectorAll(
      "input[type=checkbox]"
    ))) {
      if (!box.checked) continue;
      const asked = askedInputs.get(box.value);
      dimensions[box.value] = asked ? asked.value : box.value;
    }
    if (!Object.keys(dimensions).length) {
      verifyError.textContent = "先在「更多设置」里勾出要问的维度，再校验。";
      busy2 = false;
      renderVerify();
      return;
    }
    try {
      answer = await api(
        `/target-profiles/${subject.profile_id}/validate`,
        { dimensions }
      );
      stale = false;
    } catch (error) {
      answer = null;
      stale = true;
      verifyError.textContent = `校验没有回来：${errMsg(error)}`;
    } finally {
      busy2 = false;
    }
    renderVerify();
    renderMeta();
  }
  async function loadDetail(profile) {
    askedInputs.clear();
    if (!profile) {
      fieldHost.replaceChildren(el(
        "p",
        { class: "tp-line" },
        "还没唯一到一个目标：单份档案的完整字段读回要先有一个 profile_id。"
      ));
      return;
    }
    fieldHost.replaceChildren(el("p", { class: "view-loading" }, "正在读回这份档案的专业参数…"));
    let document2;
    try {
      document2 = await api(`/target-profiles/${profile.profile_id}`);
    } catch (error) {
      fieldHost.replaceChildren(el(
        "p",
        { class: "error" },
        `单份档案读回失败：${errMsg(error)}`
      ));
      return;
    }
    const reasons = Object.entries(document2.axis_reasons);
    const keys = axes.capability_fields.length ? axes.capability_fields.map((option) => option.key) : Object.keys(document2.fields);
    fieldHost.replaceChildren(
      el(
        "h4",
        { class: "tp-name" },
        `档案 ${document2.profile_key} 的专业参数（02:64 那 13 项，逐项带出处与读到日）`
      ),
      el("p", { class: "view-hint", id: "tp-axis-reasons" }, reasons.length ? reasons.map(([key, reason]) => `${axisLabel.get(key) ?? key}：${reason}`).join(" ｜ ") : "七个身份轴都填了值，没有需要解释的空轴。"),
      el("ul", { class: "list" }, ...keys.map((key) => fieldRow2(
        fieldLabel.get(key) ?? key,
        document2.fields[key]
      )))
    );
  }
  function renderDimensions() {
    dimensionHost.replaceChildren(
      el("h4", { class: "tp-name" }, "要校验的维度（服务给的 validate_dimensions，不新增维度）")
    );
    if (!axes.validate_dimensions.length) {
      dimensionHost.append(el(
        "p",
        { class: "error" },
        `校验维度词表未读回${axesOffline ? `：${axesOffline}` : "；离线时不显示手抄维度"}`
      ));
      return;
    }
    for (const dimension of axes.validate_dimensions) {
      const box = el("input", { type: "checkbox", id: `tp-dim-${dimension}`, value: dimension });
      if (TP_DEFAULT_DIMENSIONS.includes(dimension)) box.checked = true;
      const asked = el("input", {
        class: "input",
        id: `tp-ask-${dimension}`,
        "aria-label": `要问「${dimension}」的具体输入`,
        value: TP_DEFAULT_ASK[dimension] ?? dimension
      });
      askedInputs.set(dimension, asked);
      dimensionHost.append(el(
        "div",
        { class: "tp-dimension" },
        el(
          "label",
          { class: "tp-dimension-name", for: `tp-dim-${dimension}` },
          box,
          el("span", {}, en(dimension))
        ),
        asked
      ));
    }
  }
  async function saveDraft() {
    draftOut.textContent = "";
    if (!actor.value.trim()) {
      draftOut.textContent = "草稿目标要具名记录人：这一栏不代人签名。";
      actor.focus();
      return;
    }
    const subject = resolved ?? poolBefore(TP_PICK_ORDER.length)[0] ?? null;
    if (!chosen.software || !subject) {
      draftOut.textContent = "没有可登记的组合：先选一个软件；想保持「暂不指定」就别写草稿。";
      return;
    }
    const entryKind = subject.axes.entry ?? "UNSTATED";
    if (!axes.entry_kinds.includes(entryKind)) {
      draftOut.textContent = `入口 ${entryKind} 不在服务的 entry_kinds 词表里，不提交。`;
      return;
    }
    busy2 = true;
    draftSave.disabled = true;
    try {
      const written = await api("/target-profiles", {
        software: subject.axes.software ?? "",
        agent: subject.axes.agent ?? null,
        model: subject.axes.model ?? null,
        provider: subject.axes.provider ?? null,
        version: subject.axes.version ?? null,
        entry: entryKind,
        task_mode: subject.axes.task_mode ?? "",
        actor: actor.value.trim(),
        // 编号仍由人填写；留空发空串，服务把它写成字面 UNUSED，页面不代铸一个标识当来源证据。
        source_ref: sourceRef.value.trim(),
        fields: {}
      });
      draftOut.textContent = `已存为草稿 ${written.profile.profile_id}（r${written.revision}，support_state=${written.profile.support_state}，外部编号=${written.profile.source_ref ?? "UNUSED"}）。服务同时声明：${written.claims_not_made.join("；")}。`;
      const refreshed = await apiOrEmpty(
        "/target-profiles?limit=100",
        OFFLINE.targetProfiles
      );
      listNotice = shapeNotice(refreshed);
      listOffline = disconnectedNotice(refreshed);
      listRead.profiles = refreshed.profiles;
      listRead.total = refreshed.total;
      listRead.support_histogram = refreshed.support_histogram;
      listRead.provenance_histogram = refreshed.provenance_histogram;
      profiles = listRead.profiles;
      fillPickers();
      resolveTarget();
      renderAll();
      meta.dataset.reread = "done";
    } catch (error) {
      draftOut.textContent = `草稿没有写入：${tpRefusal(error)}`;
    } finally {
      busy2 = false;
      draftSave.disabled = false;
    }
  }
  function renderMeta() {
    const notes = [axesNotice, listNotice, axesOffline, listOffline].filter(Boolean);
    meta.replaceChildren(
      ...notes.length ? [el("p", { class: "error" }, notes.join("；"))] : [],
      el(
        "p",
        { class: "tp-line" },
        `清单应答：total=${listRead.total} · 本页 ${profiles.length} 条 · offset=${listRead.offset} · limit=${listRead.limit}`
      ),
      el(
        "p",
        { class: "tp-line" },
        "这一面读的是目标档案路由：词表、清单、单份档案、草稿写入与校验各一条。它不运行任何东西，也不替外部产品或模型声明已测试。"
      )
    );
  }
  function renderAll() {
    combination.textContent = combinationText();
    combination.dataset.mode = !chosen.software ? "unspecified" : !resolved ? "partial" : planOnly ? "plan-only" : "target";
    limits.textContent = limitsText();
    renderTruthColumns();
    renderRoutes();
    renderVerify();
    renderMeta();
  }
  function onPickChanged(key, value) {
    chosen[key] = value;
    for (const later of TP_PICK_ORDER.slice(TP_PICK_ORDER.indexOf(key) + 1)) chosen[later] = "";
    const before = resolved?.profile_id ?? "";
    fillPickers();
    resolveTarget();
    if ((resolved?.profile_id ?? "") !== before) {
      stale = true;
      answer = null;
      verifyError.textContent = "";
      void loadDetail(resolved);
    }
    renderAll();
  }
  for (const key of TP_PICK_ORDER) {
    pickers[key].addEventListener("change", () => onPickChanged(key, pickers[key].value));
  }
  planOnlyBox.addEventListener("change", () => {
    planOnly = planOnlyBox.checked;
    renderAll();
  });
  validate.addEventListener("click", () => {
    void runValidate();
  });
  draftSave.addEventListener("click", () => {
    void saveDraft();
  });
  fillPickers();
  resolveTarget();
  renderDimensions();
  await loadDetail(resolved);
  renderAll();
  target.replaceChildren(
    el(
      "div",
      { class: "page-head" },
      el(
        "div",
        {},
        el("h2", {}, "目标组合选择面板"),
        el("p", {}, "先选软件与 Agent，再只看这个入口真的被记过的模型、接入方式与任务模式。官方写了什么、本项目测过什么，是两栏，不是一个分数。")
      )
    ),
    el(
      "div",
      { class: "split kb-split" },
      el(
        "section",
        { class: "panel" },
        el("h3", {}, "第一步：软件 / Agent"),
        el(
          "p",
          { class: "view-hint" },
          "顺序来自屏幕三那句「用户先选软件/Agent，再看到该入口可用的模型/模式」。「暂不指定」与「仅规划」是这一屏上的两个显式状态，不是一次可运行的选择。"
        ),
        el(
          "div",
          { class: "tp-row" },
          el(
            "label",
            { class: "field-row" },
            el("span", {}, axisLabel.get("software") ?? "软件"),
            software
          ),
          el(
            "label",
            { class: "field-row" },
            el("span", {}, axisLabel.get("agent") ?? "Agent"),
            agent
          )
        ),
        el("h3", {}, "第二步：这个入口可用的接入方式 / 模型 / 任务模式"),
        el(
          "div",
          { class: "tp-row" },
          el(
            "label",
            { class: "field-row" },
            el("span", {}, axisLabel.get("entry") ?? "入口"),
            entry
          ),
          el(
            "label",
            { class: "field-row" },
            el("span", {}, axisLabel.get("model") ?? "模型"),
            model
          ),
          el(
            "label",
            { class: "field-row" },
            el("span", {}, axisLabel.get("task_mode") ?? "任务模式"),
            taskMode
          )
        ),
        el(
          "label",
          { class: "tp-plan" },
          planOnlyBox,
          el("span", {}, "仅规划：这个组合只作为规划材料保留，不标为可执行")
        ),
        combination,
        limits,
        // 08:9（屏幕一）那句「方案助手模型是另一种配置，不混进同一菜单」在这一屏照样成立：
        // 这里选的是外部制作目标（软件 × 模型 × 接入方式 × 任务模式），助手模型在 #/models 与
        // #/assistant 那一屏配置，两个菜单不合并成一个。
        el(
          "p",
          { class: "view-hint" },
          '这里的模型是"外部制作目标"，不是方案助手模型：助手模型在「模型选择」那一屏配置，两个菜单不合并（这条规则出自 08 line 9，不是屏幕三那一句）。'
        )
      ),
      el(
        "section",
        { class: "panel" },
        el("h3", {}, "创意方向与品牌约束（切换目标后仍在原位）"),
        el(
          "p",
          { class: "view-hint" },
          "06:20 验收 B2「切换目标模型，原创意和品牌约束保留，参数及参考角色重新校验」；02:68 也说更换模型时保留故事、品牌、镜头目的与素材角色，不把旧参数原样搬到新模型。这两栏是本屏的规划文本，不写进服务，也不冒充一条已保存的方案。"
        ),
        el("label", { class: "field-row" }, el("span", {}, "创意方向"), creative),
        el("label", { class: "field-row" }, el("span", {}, "品牌约束"), brand),
        el("h3", {}, "参数与参考角色的重新校验"),
        verifyState,
        verdictHost,
        el("div", { class: "as-actions" }, validate),
        verifyError
      )
    ),
    el("div", { class: "two-col kb-split" }, officialPanel, untestedPanel),
    el(
      "section",
      { class: "panel" },
      el("h3", {}, "推荐路线（最多两条，并列，不排名）"),
      routeNote,
      routeHost
    ),
    el(
      "details",
      { class: "advanced" },
      el("summary", {}, "更多设置（专业参数、校验维度与草稿目标）"),
      el(
        "div",
        { class: "advanced-body as-more" },
        fieldHost,
        dimensionHost,
        el("h4", { class: "tp-name" }, "把当前组合登记为草稿目标"),
        el(
          "p",
          { class: "view-hint" },
          '草稿写进服务的 target_profile_draft，支持状态由存储侧固定成 USER_DRAFT：页面不能把一个人的猜测写成官方支持，也写不进"本项目实测"。'
        ),
        el(
          "div",
          { class: "tp-row" },
          el("label", { class: "field-row" }, el("span", {}, "记录人"), actor),
          el(
            "label",
            { class: "field-row" },
            el("span", {}, "外部作业编号（可留空＝不使用）"),
            sourceRef
          )
        ),
        el("div", { class: "kb-actions" }, draftSave),
        draftOut
      )
    ),
    meta
  );
}
async function projectPickerPanel(target, title, body, preamble, caption = "只读回服务端台账；本页不提交、不修改。") {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回项目台账…"));
  const data = await apiOrEmpty("/projects", OFFLINE.projects);
  const unread = shapeNotice(data);
  const offline = disconnectedNotice(data);
  if (!data.projects.length) {
    target.replaceChildren(
      el(
        "div",
        { class: "page-head" },
        el(
          "div",
          {},
          el("h2", {}, title),
          el("p", {}, caption)
        )
      ),
      ...preamble ? [preamble] : [],
      el(
        "p",
        { class: unread || offline ? "error" : "view-hint" },
        unread ? `${unread}，因此无法判断台账是否为空` : offline ? `${offline}，台账未读回，不能断言为空` : "尚无项目。先在工作台新建项目，再读回此视图。"
      )
    );
    return;
  }
  const sole = data.projects.length === 1 ? data.projects[0] : null;
  const select = el("select", { class: "project-select", id: `${title.replace(/\s+/g, "-")}-project` });
  if (!sole) select.append(el("option", { value: "" }, `选择项目（共 ${data.projects.length} 个）`));
  for (const p of data.projects) select.append(el("option", { value: p.id }, p.name));
  const content = el("div", { class: "route-view-body" });
  target.replaceChildren(
    el(
      "div",
      { class: "page-head" },
      el(
        "div",
        {},
        el("h2", {}, title),
        el("p", {}, caption)
      )
    ),
    ...preamble ? [preamble] : [],
    el("label", { class: "project-picker" }, "项目", select),
    content,
    ...shapeNoticeRows(data)
  );
  const load = async () => {
    const id = select.value;
    if (!id) {
      content.replaceChildren(el(
        "div",
        { class: "empty" },
        el("div", { class: "icon", "aria-hidden": "true" }, "—"),
        el("p", {}, `未选择项目，${title}没有可读回的记录`),
        el("small", {}, "在上方「项目」中选择项目后，本页从服务端台账只读回；未读回不显示数字。")
      ));
      return;
    }
    content.replaceChildren(el("p", { class: "view-loading" }, "正在读回该项目…"));
    try {
      content.replaceChildren(await body(id));
    } catch (error) {
      content.replaceChildren(el("p", { class: "error" }, `读回失败：${errMsg(error)}`));
    }
  };
  select.onchange = () => {
    void load();
  };
  await load();
}
async function renderProjects(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回项目台账…"));
  const data = await apiOrEmpty("/projects", OFFLINE.projects);
  const n = data.projects.length;
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "项目"),
      el("p", {}, "支持筛选、编辑与本地持久化。数据来自服务端台账；新建 / 选择项目在工作台执行，本页只读回。")
    ),
    el(
      "div",
      { class: "page-actions" },
      el("button", {
        type: "button",
        class: "primary-btn",
        onclick: () => {
          window.location.hash = "";
        }
      }, "+ 新建项目")
    )
  );
  const kpis = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(n), "项目", "服务端台账读回"),
    kpiCard("—", "进行中", "状态需在工作台查看"),
    kpiCard("—", "已完成", "状态需在工作台查看")
  );
  const list = el(
    "div",
    {
      class: "table-wrap",
      tabindex: "0",
      role: "region",
      "aria-label": "项目台账表（可横向滚动）"
    },
    el(
      "table",
      { class: "table" },
      el("thead", {}, el(
        "tr",
        {},
        el("th", { scope: "col" }, "项目"),
        el("th", { scope: "col" }, "ID"),
        el("th", { scope: "col" }, "状态"),
        el("th", { scope: "col" }, "操作")
      )),
      el(
        "tbody",
        {},
        ...data.projects.length ? data.projects.map((p) => el(
          "tr",
          {},
          el("th", { scope: "row" }, expandableTitle(p.name)),
          el("td", {}, p.id),
          // The roll-up now also carries objects/waiting/last_activity_at, but there is still no
          // status field: a project record cannot say 进行中/已完成, so this column stays the
          // read-back fact it was. The same page already refuses to guess one in its KPIs.
          el("td", {}, el("span", { class: "tag neutral" }, "未读回")),
          el("td", {}, el("button", {
            type: "button",
            class: "ghost-btn",
            // B07 `/projects/:id` — reached from a row, never a nav item
            // (ROUTE_VIEWS has 22 entries and the browser E2E asserts that nav item
            // count; a parameterized detail route must not be added to the table.)
            onclick: () => {
              window.location.hash = projectDetailHash(p.id);
            }
          }, "打开"))
        )) : [el("tr", {}, emptyTd(data, "尚无项目", "在工作台新建项目后出现。", 4))]
      )
    )
  );
  target.replaceChildren(
    pageHead,
    kpis,
    el("div", { class: "panel" }, el("h3", {}, `项目（${n}）`), list),
    ...shapeNoticeRows(data)
  );
}
const TOOL_ADAPTERS = [
  { name: "Illustrator / AI", kind: "illustrator", state: "declared", path: "宿主驱动" },
  { name: "Photoshop / PSD", kind: "photoshop", state: "declared", path: "宿主驱动" }
];
async function renderCreativeTools(target) {
  await projectPickerPanel(target, "创作工具", async (id) => {
    const tasks2 = await apiOrEmpty(`/projects/${id}/tasks`, OFFLINE.tasks);
    const env = await apiOrEmpty("/environment", OFFLINE.environment);
    const mcpCard = CAPABILITY_REGISTRY.find((c) => c.capabilityId === "mcp-diagnostics");
    const hostCard = CAPABILITY_REGISTRY.find((c) => c.capabilityId === "host-adapter-live");
    const hostStatus = el(
      "div",
      { class: "panel" },
      el("h3", {}, "宿主 / Capability 状态"),
      el(
        "div",
        { class: "three-col" },
        el(
          "div",
          { class: "panel" },
          el("h3", {}, "宿主读回"),
          el(
            "ul",
            { class: "list" },
            ...TOOL_ADAPTERS.map((a) => el(
              "li",
              { class: "list-item" },
              el(
                "div",
                {},
                el("strong", {}, a.name),
                el("small", {}, a.path)
              ),
              el("span", { class: "tag neutral" }, en("UNKNOWN"))
            ))
          ),
          el("p", { class: "view-hint" }, "宿主在线状态尚未有服务路由；此处 UNKNOWN，不假报可用。")
        ),
        el(
          "div",
          { class: "panel" },
          el("h3", {}, "共享输入"),
          el("ul", { class: "list" }, ...sharedInputRows(env)),
          el("p", { class: "view-hint" }, "服务端环境读回。")
        ),
        hostCard ? capabilityCard(hostCard) : el("div", { class: "panel" }),
        mcpCard ? capabilityCard(mcpCard) : el("div", { class: "panel" })
      )
    );
    const adapterGrid = el(
      "div",
      { class: "card-flow" },
      ...TOOL_ADAPTERS.map(
        (a) => el(
          "div",
          { class: "panel" },
          el("h3", {}, a.name),
          el(
            "div",
            { class: "status-stack" },
            el("span", { class: "tag info" }, a.state),
            // Neutral, not ok: the fact here is that an adapter entry exists in
            // integrations/adapter-registry.json. Nothing probed the host, and the panel
            // above this one says so ("UNKNOWN，不假报可用"). A green pill on the same
            // page contradicted it.
            el("span", { class: "tag neutral" }, "登记于 adapter-registry")
          )
        ),
        el("p", { class: "view-hint" }, "连接方式 / 权限 / 可执行能力由宿主与 service 裁定；本页只读回，不触发实操。")
      )
    );
    const rows = tasks2.tasks.length ? tasks2.tasks.map((t) => el(
      "tr",
      {},
      el("td", {}, t.kind),
      el("td", {}, t.state),
      el("td", {}, t.attempt.state)
    )) : [el("tr", {}, emptyTd(tasks2, "尚无宿主任务", "创作任务由 Illustrator / Photoshop 在工作台高级区提交。", 3))];
    return el(
      "div",
      {},
      hostStatus,
      adapterGrid,
      el("p", { class: "view-hint" }, "宿主任务只读回服务端任务台账。提交 / 运行 / 取消由宿主（Illustrator / Photoshop）在工作台执行；本页不触发实操。"),
      el(
        "div",
        { class: "panel" },
        el("h3", {}, `任务（${tasks2.tasks.length}）`),
        el(
          "div",
          {
            class: "table-wrap",
            tabindex: "0",
            role: "region",
            "aria-label": "设计领域任务表（可横向滚动）"
          },
          el(
            "table",
            { class: "table" },
            el("thead", {}, el("tr", {}, el("th", {}, "类型"), el("th", {}, "状态"), el("th", {}, "尝试"))),
            el("tbody", {}, ...rows)
          )
        )
      ),
      ...shapeNoticeRows(env, tasks2)
    );
  });
}
const DELIVERABLE_FORMATS = [
  { format: "PSD", producedBy: "native.psd" },
  { format: "AI", producedBy: "native.ai" },
  { format: "PNG", producedBy: "preview.png" },
  { format: "SVG", producedBy: "preview.svg" },
  { format: "Archive", producedBy: "delivery.zip" },
  { format: "PDF", producedBy: null },
  { format: "Video", producedBy: null },
  { format: "3D", producedBy: null }
];
const PREFLIGHT_PROFILES = ["print", "digital", "video"];
const OUTCOME_TAGS = {
  PASS: "ok",
  WARNING: "warn",
  FAIL: "bad",
  NOT_MEASURED: "warn",
  NOT_APPLICABLE: "neutral"
};
function artifactPreflightPanel(bundleId, data) {
  const tagClass = data.verdict === "PASS" ? "ok" : data.verdict === "WARN" || data.verdict === "INCOMPLETE" ? "warn" : data.verdict === "BLOCKED" ? "bad" : "neutral";
  const unmeasured = data.counts["NOT_MEASURED"] ?? 0;
  return el(
    "div",
    { class: "bundle-preflight-readback" },
    el(
      "p",
      {},
      el("span", { class: "tag " + tagClass }, en(data.verdict)),
      el(
        "span",
        { class: "muted" },
        `profile ${en(data.profile)} · 判据版本 ${String(data.profileSchema)} · 未量 ${unmeasured} 项 / 共 ${data.findings.length} 项`
      )
    ),
    // The rule that keeps INCOMPLETE honest is the service's sentence, not the page's.
    el("p", { class: "view-hint" }, data.meaning),
    el(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "产物预检结果表（可横向滚动）"
      },
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          el("th", {}, "检查项"),
          el("th", {}, "严重度"),
          el("th", {}, "结论"),
          el("th", {}, "读回与判据")
        )),
        el("tbody", {}, ...data.findings.map((finding) => el(
          "tr",
          {},
          el("td", {}, finding.id),
          el("td", {}, el("span", { class: "tag info" }, en(finding.severity))),
          el("td", {}, el("span", {
            class: "tag " + (OUTCOME_TAGS[finding.outcome] ?? "neutral")
          }, en(finding.outcome))),
          // Both strings travel: the reading and the criterion it was judged against.
          // A table of verdicts with no stated basis is what this module exists to stop.
          el(
            "td",
            {},
            finding.detail,
            el("div", { class: "value-mono" }, "判据：" + finding.criterion)
          )
        )))
      )
    )
  );
}
async function runArtifactPreflight(projectId, bundleId, profile, host) {
  host.replaceChildren(el(
    "p",
    { class: "view-loading" },
    `正在按 ${profile} profile 预检 ${bundleId}…`
  ));
  try {
    const data = await api(
      `/projects/${projectId}/bundles/${bundleId}/preflight?profile=${encodeURIComponent(profile)}`,
      {}
    );
    host.replaceChildren(artifactPreflightPanel(bundleId, data));
  } catch (error) {
    host.replaceChildren(el(
      "p",
      { class: "error" },
      `预检未确认：${errMsg(error)}。服务端拒绝时没有写入任何结论。`
    ));
  }
}
const ROLLBACK_STATE_TAGS = {
  RESOLVED: "ok",
  SOURCE_MISSING: "bad",
  OTHER_PROJECT: "bad",
  SOURCE_NOT_ACTIVE: "warn",
  REF_UNPARSED: "warn",
  ALL_RESOLVED: "info",
  PARTLY_UNRESOLVED: "warn",
  NONE_RESOLVED: "bad",
  NOTHING_TO_CHECK: "neutral",
  LEDGER_UNREADABLE: "warn"
};
const RECEIPT_AXIS_TAGS = { PASS: "ok", PARTIAL: "warn" };
function receiptIdentityRow(label, value) {
  return el(
    "tr",
    {},
    el("th", { scope: "row" }, label),
    el("td", {}, el("div", { class: "value-mono" }, value))
  );
}
function deliveryReceiptTableWrap(label, table) {
  return el("div", {
    class: "table-wrap",
    tabindex: "0",
    role: "region",
    "aria-label": label
  }, table);
}
function receiptLine(value, fallback, marked, mono) {
  const present = typeof value === "string" && value.length > 0;
  if (!present) return el("div", { class: "muted" }, fallback);
  const text = value;
  const body = marked ? en(text) : text;
  return el("div", mono ? { class: "value-mono" } : {}, body);
}
function rollbackLimits(readback) {
  const lines = Array.isArray(readback.does_not_prove) ? readback.does_not_prove : [];
  if (!lines.length) {
    return el(
      "p",
      { class: "view-hint" },
      "本读回未给出 does_not_prove，因此无法说明这些核对结论不覆盖什么。"
    );
  }
  return el("ul", { class: "list" }, ...lines.map((line) => el(
    "li",
    { class: "list-item" },
    el("span", {}, en(line))
  )));
}
function publishedWords(list) {
  return Array.isArray(list) ? list.filter((word) => typeof word === "string") : null;
}
function rollbackTagFor(word, list) {
  const published = publishedWords(list);
  if (published !== null && !published.includes(word)) return "bad";
  return ROLLBACK_STATE_TAGS[word] ?? "neutral";
}
function rollbackUnpublishedNote(word, list) {
  const published = publishedWords(list);
  return published !== null && !published.includes(word) ? "（不在响应公布的词表内）" : "";
}
function rollbackProofTable(readback) {
  const proofs = Array.isArray(readback.rollback_proofs) ? readback.rollback_proofs : [];
  const meaning = readback.state_meaning ?? {};
  return el(
    "div",
    {
      class: "table-wrap",
      tabindex: "0",
      role: "region",
      "aria-label": "回滚参照核对表（可横向滚动）"
    },
    el(
      "table",
      { class: "table" },
      el("thead", {}, el(
        "tr",
        {},
        el("th", {}, "交付物"),
        el("th", {}, "回滚参照"),
        el("th", {}, "核对"),
        el("th", {}, "依据")
      )),
      el("tbody", {}, ...proofs.map((proof) => {
        const state = typeof proof.state === "string" ? proof.state : "";
        const note = typeof meaning[state] === "string" ? meaning[state] : null;
        return el(
          "tr",
          {},
          el("td", {}, proof.deliverable_id ?? "未记录"),
          el("td", {}, receiptLine(proof.backup_ref, "文档未记录 backup_ref", false, true)),
          el(
            "td",
            {},
            el(
              "span",
              { class: "tag " + rollbackTagFor(state, readback.rollback_states) },
              state ? en(state) : "未读回",
              rollbackUnpublishedNote(state, readback.rollback_states)
            ),
            receiptLine(proof.version_no === null || proof.version_no === void 0 ? null : `版本 v${proof.version_no}`, "未解析出版本号", false, true)
          ),
          el(
            "td",
            {},
            receiptLine(proof.reason, "服务端未给出依据", true, false),
            receiptLine(note, "该状态的释义未随响应给出", true, false)
          )
        );
      }))
    )
  );
}
function rollbackNothingChecked(readback) {
  const state = typeof readback.rollback_state === "string" && readback.rollback_state.length ? readback.rollback_state : "";
  const cause = state === "LEDGER_UNREADABLE" ? "台账在本次读回中无法查询，所以没有任何一个引用被核对过；这不说明那些源版本已经不存在。" : '这份收据没有交付物条目可供核对，"没有可核对的东西"与"全部可兑现"不是同一件事。';
  return el(
    "p",
    { class: "view-hint" },
    "回滚核对未做（",
    state ? en(state) : "状态未读回",
    "）：",
    cause
  );
}
function rollbackProofRows(readback) {
  if (!Array.isArray(readback.rollback_proofs)) {
    return [el(
      "p",
      { class: "error" },
      "回滚参照未读回：响应没有给出 rollback_proofs，本页不替它宣布这些引用可兑现或不可兑现。"
    )];
  }
  if (!readback.rollback_proofs.length) return [rollbackNothingChecked(readback)];
  return [rollbackProofTable(readback)];
}
function deliveryReceiptPanel(readback) {
  const data = readback.receipt;
  if (!data || !Array.isArray(data.deliverables)) {
    return el(
      "p",
      { class: "error" },
      "收据形状未读回：文档没有给出 deliverables，本页不替它猜交付物数量。"
    );
  }
  const axis = typeof data.axes?.delivery === "string" ? data.axes.delivery : "";
  const aggregate = typeof readback.rollback_state === "string" ? readback.rollback_state : "";
  const identity = [
    receiptIdentityRow("文档版本", String(data.schemaVersion ?? "")),
    receiptIdentityRow("收据 id", String(data.receipt_id ?? "")),
    receiptIdentityRow("收据摘要", String(data.receipt_sha256 ?? "")),
    receiptIdentityRow("绑定任务", String(data.job_id ?? "")),
    receiptIdentityRow("记录时间", String(data.created_at ?? "文档未记录时间"))
  ];
  const entries = data.deliverables.map((entry) => el(
    "tr",
    {},
    el("td", {}, entry.deliverable_id),
    el("td", {}, String(entry.byte_size)),
    el("td", {}, entry.editable ? "可编辑源文件" : "预览（压平）"),
    // The readback columns are what the PARTIAL axis is about: a real delivery here
    // never re-opens its own artifact in the host, so this says 无 rather than passing.
    el("td", {}, entry.host_readback ? entry.readback_matches_artifact === false ? "有读回记录 · 与交付摘要不一致" : "有读回记录" : "无宿主读回记录"),
    el(
      "td",
      {},
      el("div", { class: "value-mono" }, String(entry.artifact_sha256)),
      el(
        "div",
        { class: "value-mono" },
        `回滚参照：${String(entry.rollback?.backup_ref ?? "文档未记录")}`
      )
    )
  ));
  const requirements = data.deliverables.flatMap((entry) => (entry.requirements ?? []).map((requirement) => el(
    "tr",
    {},
    el("td", {}, entry.deliverable_id),
    el("td", {}, requirement.req_id),
    // The status word is the document's own, never a paraphrase: a receipt that
    // records NOT_RUN for rights must not be painted 未通过 or 已验收.
    el("td", {}, el("span", { class: "tag info" }, en(String(requirement.status))))
  )));
  return el(
    "div",
    { class: "delivery-receipt-readback" },
    el(
      "p",
      {},
      el(
        "span",
        { class: "tag " + (RECEIPT_AXIS_TAGS[axis] ?? "neutral") },
        axis ? en(axis) : "轴值未读回"
      ),
      el(
        "span",
        {
          class: "tag " + rollbackTagFor(aggregate, readback.rollback_state_vocabulary)
        },
        aggregate ? en(aggregate) : "回滚汇总未读回",
        rollbackUnpublishedNote(aggregate, readback.rollback_state_vocabulary)
      ),
      el("span", { class: "muted" }, `交付收据 · ${data.deliverables.length} 个交付物`)
    ),
    deliveryReceiptTableWrap(
      "交付收据身份与时间表（可横向滚动）",
      el("table", { class: "table" }, el("tbody", {}, ...identity))
    ),
    deliveryReceiptTableWrap(
      "交付收据条目表（可横向滚动）",
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          el("th", {}, "交付物"),
          el("th", {}, "字节"),
          el("th", {}, "可编辑性"),
          el("th", {}, "宿主读回"),
          el("th", {}, "产物摘要 / 回滚参照")
        )),
        el("tbody", {}, ...entries)
      )
    ),
    deliveryReceiptTableWrap(
      "交付收据要求项表（可横向滚动）",
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          el("th", {}, "交付物"),
          el("th", {}, "要求项"),
          el("th", {}, "登记状态")
        )),
        el("tbody", {}, ...requirements)
      )
    ),
    ...rollbackProofRows(readback),
    el(
      "p",
      { class: "view-hint" },
      "收据读回的是交付时登记的事实：成员摘要、字节、可编辑性声明与逐项要求状态。要求项为 NOT_RUN / UNVERIFIED 说的是这些门当时没有跑，不是跑失败了；本页不把它读成 rights 或质量验收。"
    ),
    el(
      "p",
      { class: "view-hint" },
      "回滚核对只回答一件事：收据点名的那个不可变源版本，现在还在不在本项目的台账里。RESOLVED 不等于已经回滚过——收据自己把这条记录称为计划，本页不替它执行。"
    ),
    rollbackLimits(readback)
  );
}
function receiptRefusal(error) {
  const envelope = error.serviceEnvelope;
  const code = typeof envelope?.["error"] === "string" ? envelope["error"] : errMsg(error);
  if (code === "DELIVERY_RECEIPT_NOT_FOUND") {
    return "未读回交付收据（DELIVERY_RECEIPT_NOT_FOUND）：该 ACTIVE 版本没有已登记的收据文档。没有收据不等于交付失败，也不等于已验收；要出证需由交付流程写入。";
  }
  if (code === "DELIVERY_RECEIPT_UNVERIFIED") {
    return "拒绝出证（DELIVERY_RECEIPT_UNVERIFIED）：已登记的收据文档与它自己记录的摘要对不上，服务端没有读出它，本页也不会替它解释或补全。这不是请求写错，是这批字节不再被证明。";
  }
  return `收据未确认：${code}。服务端拒绝时没有写入任何结论。`;
}
async function runDeliveryReceipt(projectId, bundleId, versionId, host) {
  host.replaceChildren(el(
    "p",
    { class: "view-loading" },
    `正在读回 ${versionId} 的交付收据…`
  ));
  try {
    const data = await api(
      `/projects/${projectId}/bundles/${bundleId}/versions/${versionId}/receipt`
    );
    host.replaceChildren(deliveryReceiptPanel(data));
  } catch (error) {
    host.replaceChildren(el("p", { class: "error" }, receiptRefusal(error)));
  }
}
function evidenceDeliveryColumn(projectId, bundles) {
  const picker = el("select", { class: "input", id: "evidence-delivery-target" });
  const versions = /* @__PURE__ */ new Map();
  for (const bundle of bundles.bundles) versions.set(bundle.id, bundle.version_id);
  if (bundles.bundles.length) {
    for (const bundle of bundles.bundles) {
      picker.append(new Option(`v${bundle.version_no} · ${bundle.id}`, bundle.id));
    }
  } else {
    const [head, note] = emptyWording(
      bundles,
      "暂无交付包可读回",
      "交付发布后在此列出，预检与收据按包读回。"
    );
    picker.append(new Option(`${head} · ${note}`, ""));
  }
  const profilePicker = el(
    "select",
    { class: "input", id: "evidence-delivery-profile" },
    ...PREFLIGHT_PROFILES.map((name) => new Option(name, name))
  );
  const preflightOut = el(
    "div",
    {
      class: "bundle-preflight-outcome",
      id: "evidence-preflight-outcome"
    },
    el(
      "p",
      { class: "view-hint" },
      "尚未预检：预检只读取归档自带字节与随包清单，不修改交付包，也不代替 rights / 质量验收。"
    )
  );
  const receiptOut = el(
    "div",
    {
      class: "delivery-receipt-outcome",
      id: "evidence-receipt-outcome"
    },
    el(
      "p",
      { class: "view-hint" },
      "尚未读回交付收据：收据是交付时写下的文档，选中交付包后在此读回它说了什么、没说什么。"
    )
  );
  const preflightRun = el("button", {
    type: "button",
    class: "primary-btn",
    id: "evidence-preflight-run"
  }, "预检所选交付包");
  const receiptRun = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "evidence-receipt-run"
  }, "读回交付收据");
  preflightRun.disabled = bundles.bundles.length === 0;
  receiptRun.disabled = bundles.bundles.length === 0;
  preflightRun.onclick = () => {
    const bundleId = picker.value;
    if (!bundleId) {
      preflightOut.replaceChildren(el(
        "p",
        { class: "error" },
        "未预检：没有可选的交付登记，预检不能对一个凭记忆写出的 id 给出结论。"
      ));
      return;
    }
    void runArtifactPreflight(projectId, bundleId, profilePicker.value, preflightOut);
  };
  receiptRun.onclick = () => {
    const bundleId = picker.value;
    const versionId = versions.get(bundleId) ?? "";
    if (!bundleId || !versionId) {
      receiptOut.replaceChildren(el(
        "p",
        { class: "error" },
        "未读回收据：交付读回没有同时给出该包的 id 与版本 id，收据不能指向一个凭记忆写出的版本。"
      ));
      return;
    }
    void runDeliveryReceipt(projectId, bundleId, versionId, receiptOut);
  };
  return el(
    "div",
    { class: "panel" },
    el("h3", {}, "交付登记的读回 · 产物预检与交付收据"),
    el(
      "div",
      { class: "toolbar" },
      el("label", { class: "muted" }, "交付包", picker),
      el("label", { class: "muted" }, "profile", profilePicker),
      preflightRun,
      receiptRun
    ),
    el(
      "p",
      { class: "view-hint" },
      "两项都先选交付包：结论属于那一个版本。预检运行检查，收据读回交付时已登记的文档；两者都不修改交付包。"
    ),
    preflightOut,
    receiptOut
  );
}
async function renderDeliverables(target) {
  await projectPickerPanel(target, "交付中心", async (id) => {
    const [tasks2, bundles] = await Promise.all([
      apiOrEmpty(`/projects/${id}/tasks`, OFFLINE.tasks),
      apiOrEmpty(`/projects/${id}/bundles`, OFFLINE.bundles)
    ]);
    const bundleRows = bundles.bundles.length ? bundles.bundles.map((b) => el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, `交付包 · v${b.version_no}`),
        el("small", {}, `${b.id} · ${b.byte_size} 字节 · ${b.rights}`)
      ),
      el(
        "div",
        { class: "actions" },
        el("button", {
          type: "button",
          class: "ghost-btn",
          onclick: () => {
            window.location.hash = "#/projects/" + encodeURIComponent(id);
          }
        }, "在项目页下载"),
        el(
          "span",
          { class: b.rights === "NOT_REVIEWED" ? "tag warn" : "tag info" },
          b.rights === "NOT_REVIEWED" ? "权利未审查" : b.rights
        )
      )
    )) : [emptyLi(bundles, "尚无交付包", "任务完成并打包后，交付会在此读回。")];
    const bundleList = el(
      "ul",
      { class: "list" },
      ...bundleRows.filter((x) => x !== null)
    );
    const bundlePicker = el("select", { class: "input", id: "bundle-preflight-target" });
    if (bundles.bundles.length) {
      for (const b of bundles.bundles) {
        bundlePicker.append(new Option(`v${b.version_no} · ${b.id}`, b.id));
      }
    } else {
      const [head, note] = emptyWording(
        bundles,
        "暂无交付包可预检",
        "任务完成并打包后，交付会在此读回并可预检。"
      );
      bundlePicker.append(new Option(`${head} · ${note}`, ""));
    }
    const profilePicker = el(
      "select",
      { class: "input", id: "bundle-preflight-profile" },
      ...PREFLIGHT_PROFILES.map((name) => new Option(name, name))
    );
    const preflightOut = el(
      "div",
      {
        class: "bundle-preflight-outcome",
        id: "bundle-preflight-outcome"
      },
      el(
        "p",
        { class: "view-hint" },
        "尚未预检：预检只读取归档自带字节与随包清单，不修改交付包，也不代替 rights / 质量验收。"
      )
    );
    const preflightRun = el("button", {
      type: "button",
      class: "primary-btn",
      id: "bundle-preflight-run"
    }, "预检所选交付包");
    preflightRun.disabled = bundles.bundles.length === 0;
    preflightRun.onclick = () => {
      const bundleId = bundlePicker.value;
      if (!bundleId) {
        preflightOut.replaceChildren(el(
          "p",
          { class: "error" },
          "未预检：没有可选的交付登记，预检不能对一个凭记忆写出的 id 给出结论。"
        ));
        return;
      }
      void runArtifactPreflight(id, bundleId, profilePicker.value, preflightOut);
    };
    const bundlePanel = el(
      "div",
      { class: "panel" },
      el("h3", {}, `交付包（${bundles.bundles.length}）`),
      bundleList,
      el("p", { class: "view-hint" }, "交付包来自原生宿主导出；下载与 hash 核对在项目页执行（fail-closed）。"),
      el(
        "div",
        { class: "toolbar" },
        el("label", { class: "muted" }, "交付包", bundlePicker),
        el("label", { class: "muted" }, "profile", profilePicker),
        preflightRun
      ),
      preflightOut
    );
    const tasksRows = tasks2.tasks.length ? tasks2.tasks.map((t) => el(
      "tr",
      {},
      el("td", {}, t.kind),
      el("td", {}, t.state),
      el(
        "td",
        {},
        t.attempt.state,
        // RECEIPTED alone cannot tell an uncontested completion from one the operator
        // asked to stop and the host delivered anyway; the flags are what separate them.
        t.cancel.requested && !t.cancel.acknowledged ? el("span", { class: "tag warn" }, "取消未确认") : ""
      )
    )) : [el("tr", {}, emptyTd(tasks2, "尚无任务", "任务完成后交付包随读回导出。", 3))];
    const tasksPanel = el(
      "div",
      { class: "panel" },
      el("h3", {}, `交付候选任务（${tasks2.tasks.length}）`),
      el(
        "div",
        {
          class: "table-wrap",
          tabindex: "0",
          role: "region",
          "aria-label": "交付候选任务表（可横向滚动）"
        },
        el(
          "table",
          { class: "table" },
          el("thead", {}, el("tr", {}, el("th", {}, "类型"), el("th", {}, "状态"), el("th", {}, "尝试"))),
          el("tbody", {}, ...tasksRows.filter((x) => x !== null))
        )
      )
    );
    const manifestKpis = el(
      "div",
      { class: "kpi-grid" },
      kpiCard(String(tasks2.tasks.length), "交付候选", "读回任务台账 · 非已打包"),
      kpiCard(String(bundles.bundles.length), "交付包", "读回 /bundles · 可下载核对 hash"),
      kpiCard("—", "人工验收", "字体 / 链接 / rights / 质量")
    );
    for (const v of manifestKpis.querySelectorAll("strong[data-count]")) {
      const t = v.textContent;
      if (t !== null && /^\d+$/.test(t)) v.dataset.count = t;
    }
    const kindGrid = el(
      "div",
      { class: "three-col" },
      ...DELIVERABLE_FORMATS.map((f) => el(
        "div",
        { class: "panel" },
        el("h3", {}, f.format),
        f.producedBy ? el("span", { class: "tag ok" }, `可产出 · ${f.producedBy}`) : el("span", { class: "tag warn" }, "当前不产出 · 未接入")
      ))
    );
    return el(
      "div",
      {},
      manifestKpis,
      kindGrid,
      el("p", { class: "view-hint" }, "交付包按任务在下载时打包（字体 / 链接 / rights / 质量仍需人工验收）。本页只读回，不下载也不打包。"),
      bundlePanel,
      tasksPanel,
      ...shapeNoticeRows(bundles, tasks2)
    );
  });
}
async function renderEvidence(target) {
  await projectPickerPanel(target, "证据系统", async (id) => {
    const [layerResp, bundlesResp, juryResp, rightsResp] = await Promise.all([
      apiOrEmpty(`/projects/${id}/design-layer`, OFFLINE.designLayer),
      apiOrEmpty(`/projects/${id}/bundles`, OFFLINE.bundles),
      apiOrEmpty(`/projects/${id}/jury`, JURY_UNREADABLE),
      apiOrEmpty(`/projects/${id}/rights`, RIGHTS_UNREADABLE)
    ]);
    const juryUnread = shapeNotice(juryResp) || disconnectedNotice(juryResp);
    const rightsUnread = shapeNotice(rightsResp) || disconnectedNotice(rightsResp);
    const layer = layerResp.design_layer;
    const chosen = layer.chosen_direction ? `${layer.chosen_direction.title} · v${layer.chosen_direction.version}` : "（尚未选定方向）";
    const active = layer.active_binding ? `${layer.active_binding.design_system_name} · 绑定 ${layer.active_binding.direction_id}` : "（无活动绑定）";
    const bindingChain = el(
      "div",
      { class: "panel" },
      el("h3", {}, "证据绑定链"),
      el(
        "ul",
        { class: "list" },
        el(
          "li",
          { class: "list-item" },
          el("div", {}, el("strong", {}, "项目"), el("small", {}, id)),
          el("span", { class: "tag ok" }, "已读回")
        ),
        el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, `Brief（${layer.briefs.length} 版本）`),
            el("small", {}, layer.briefs.length ? layer.briefs.map((b) => `v${b.version}`).join(" → ") : "（无）")
          ),
          el(
            "span",
            { class: layer.briefs.length ? "tag ok" : "tag info" },
            layer.briefs.length ? "已读回" : "空"
          )
        ),
        el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, "选定方向"),
            el("small", {}, chosen)
          ),
          el(
            "span",
            { class: layer.chosen_direction ? "tag ok" : "tag warn" },
            layer.chosen_direction ? "已选定" : "未选定"
          )
        ),
        el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, `交付包（${bundlesResp.bundles.length}）`),
            el("small", {}, bundlesResp.bundles.length ? bundlesResp.bundles.map((b) => `v${b.version_no}`).join(" → ") : "（无）")
          ),
          el(
            "span",
            { class: bundlesResp.bundles.length ? "tag ok" : "tag info" },
            bundlesResp.bundles.length ? "已读回" : "空"
          )
        )
      ),
      el("p", { class: "view-hint" }, "绑定链只读回；方向选定与交付打包在项目页和工作台高级区执行。")
    );
    const kpis = el(
      "div",
      { class: "kpi-grid" },
      kpiCard(String(layer.briefs.length), "briefs", "设计简报版本"),
      kpiCard(String(layer.directions.length), "directions", "设计方向版本"),
      kpiCard(String(layer.design_systems.length), "设计系统", "登记系统"),
      kpiCard(String(bundlesResp.bundles.length), "交付包", "/bundles 读回"),
      kpiCard(
        juryUnread || typeof juryResp.verdict_count !== "number" ? "—" : String(juryResp.verdict_count),
        "人工裁决",
        juryUnread ? "裁决未读回" : "GET /jury 读回 · 仅人工签署"
      )
    );
    for (const v of kpis.querySelectorAll("strong[data-count]")) {
      const t = v.textContent;
      if (t !== null && /^\d+$/.test(t)) v.dataset.count = t;
    }
    const systems = el(
      "div",
      { class: "panel" },
      el("h3", {}, "设计系统登记"),
      el(
        "ul",
        { class: "list" },
        ...layer.design_systems.map((s) => el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, `${s.name} · ${s.title}`),
            el("small", {}, `v${s.version} · 证据 ${s.evidence_level}`)
          ),
          el("span", { class: "tag info" }, s.version)
        ))
      )
    );
    const done = el(
      "div",
      {},
      kpis,
      bindingChain,
      evidenceJuryColumn(juryResp),
      evidenceRightsColumn(rightsResp, rightsUnread),
      evidenceDeliveryColumn(id, bundlesResp),
      el(
        "div",
        { class: "panel" },
        el("h3", {}, "方向契约"),
        el(
          "div",
          {
            class: "table-wrap",
            tabindex: "0",
            role: "region",
            "aria-label": "设计层版本计数表"
          },
          el(
            "table",
            { class: "table" },
            el(
              "tbody",
              {},
              el("tr", {}, el("th", { scope: "row" }, "briefs"), el("td", {}, String(layer.briefs.length))),
              el("tr", {}, el("th", { scope: "row" }, "directions"), el("td", {}, String(layer.directions.length))),
              el("tr", {}, el("th", { scope: "row" }, "选定方向"), el("td", {}, chosen)),
              el("tr", {}, el("th", { scope: "row" }, "活动绑定"), el("td", {}, active))
            )
          )
        )
      ),
      systems,
      el("p", { class: "view-hint" }, "版本链（brief / direction 逐版本）在工作台点单条时读回；本页为只读证据视图，不修改 lineage。交付登记的两项读回（预检 / 收据）需要选中交付包后点击执行；证据链完整性由上方卡片对当前检出读回（GET /api/evidence-projection），但 E0–E5 的逐条证据记录仍无服务路由。"),
      ...shapeNoticeRows(layerResp, bundlesResp, juryResp, rightsResp)
    );
    return done;
  }, evidenceProjectionPanelBox());
}
const PROJECT_STAGES = [
  { key: "brief", label: "Brief", panelId: "#pd-brief-editor", state: "IMPLEMENTED" },
  { key: "references", label: "References", panelId: "#pd-reference-panel", state: "IMPLEMENTED" },
  {
    key: "research",
    label: "Research",
    panelId: "",
    state: "PLANNED",
    note: "研究洞察无后端路由（见能力登记表 research-insights）"
  },
  { key: "directions", label: "Directions", panelId: "#pd-direction-panel", state: "IMPLEMENTED" },
  { key: "design-system", label: "Design System", panelId: "#pd-design-system-panel", state: "IMPLEMENTED" },
  { key: "production", label: "Production", panelId: "#pd-tasks-panel", state: "IMPLEMENTED" },
  // Until 2026-10-13 no #pd-versions-panel was rendered: version readback lived in the brief /
  // direction panels and the Inspector ring, and a PLANNED node kept the stage honest, because an
  // IMPLEMENTED chip whose anchor does not exist is a button that silently does nothing
  // (buildStageNav only reveals `note` as a pointer-only title, so assistive tech and keyboard
  // users never saw it). The anchor exists now, so the chip is IMPLEMENTED.
  // DL-UI-U07: the Versions stage now has a real anchor. The panel reads the version chain a
  // route already returns; what it does *not* have is a revision editor, so the stage note says
  // so -- and the panel repeats it in visible text, because buildStageNav only exposes a note as
  // a pointer-only title (the same reason the sibling PLANNED nodes keep their boundary in prose).
  {
    key: "versions",
    label: "Versions",
    panelId: "#pd-versions-panel",
    state: "IMPLEMENTED",
    note: "版本链读回已实现（#pd-versions-panel）；局部改稿仍只有后端的 patch 路由，没有桌面编辑器"
  },
  // The only preflight with a route is /api/task-preflight — the repo's
  // task-resource doctor. Design quality, Jury and production preflight have no
  // route, so the stage name carries the boundary in visible text.
  {
    key: "review",
    label: "资源预检 + 人工评审",
    panelId: "#/preflight",
    state: "IMPLEMENTED",
    note: "任务包资源预检与 Human Jury 裁决均可读回；设计质量趋势与生产产物预检尚无入口"
  },
  {
    key: "handoff",
    label: "Handoff",
    panelId: "",
    state: "PLANNED",
    note: "交接清单模型未建（能力登记表）"
  },
  // #pd-deliveries is a bundle manifest (id/kind/size/sha256/rights). E0-E5
  // evidence records have no HTTP route, so this stage is not the Evidence gate.
  {
    key: "evidence",
    label: "Evidence",
    panelId: "#pd-deliveries",
    state: "PLANNED",
    note: "交付包清单与证据链完整性投影均可读回；E0–E5 逐条证据记录仍无路由"
  }
];
function buildStageNav(currentStageKey) {
  const nav = el("ol", { class: "stage-nav", "aria-label": "项目阶段导航" });
  for (const stage of PROJECT_STAGES) {
    const li = el("li", { class: "stage-nav-item", dataset: { stage: stage.key, state: stage.state } });
    const isCurrent = stage.key === currentStageKey;
    if (isCurrent) li.setAttribute("aria-current", "step");
    const btnAttrs = {
      type: "button",
      class: "stage-nav-btn" + (stage.state === "IMPLEMENTED" ? "" : " is-planned") + (isCurrent ? " is-current" : ""),
      onclick: () => {
        if (stage.panelId.startsWith("#/")) {
          window.location.hash = stage.panelId.slice(1);
        } else if (stage.panelId) {
          const target = document.querySelector(stage.panelId);
          if (target) {
            const reduce = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
            target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
            if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
            target.focus({ preventScroll: true });
          }
        }
      },
      title: stage.note ?? (stage.state === "IMPLEMENTED" ? "点击跳转到该阶段" : stage.note ?? "")
    };
    const tag = stage.state !== "IMPLEMENTED" ? el("span", { class: "tag " + (stage.state === "BLOCKED" ? "warn" : "neutral") }, en(stage.state)) : null;
    li.append(el(
      "button",
      btnAttrs,
      el("span", { class: "stage-nav-label" }, stage.label),
      ...tag ? [tag] : []
    ));
    nav.append(li);
  }
  return nav;
}
function buildInspectorPanel(id, layer) {
  const versionData = layer.directions.map((d) => ({
    version: d.version,
    chosen: d.chosen,
    superseded_by: d.superseded_by
  }));
  const ring = buildVersionRing(versionData);
  const chosen = layer.chosen_direction;
  const binding = layer.active_binding;
  const sysItems = layer.design_systems.length ? [el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, "设计系统"),
      el("small", {}, layer.design_systems.map((s) => s.name).join(", "))
    )
  )] : [];
  const body = el(
    "div",
    { class: "inspector-body" },
    ...ring ? [ring] : [],
    el("p", { class: "view-hint" }, `${layer.directions.length} 个方向版本` + (chosen ? ` · 选定：${chosen.title} v${chosen.version}` : " · 尚未选定方向")),
    el(
      "ul",
      { class: "list" },
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "活动绑定"),
          el("small", {}, binding ? `${binding.design_system_name} → ${binding.direction_id}` : "（无活动绑定）")
        )
      ),
      ...sysItems.filter((x) => x !== null)
    )
  );
  return el(
    "aside",
    { class: "inspector", id: "pd-inspector", "aria-label": "项目 Inspector" },
    el(
      "div",
      { class: "inspector-head" },
      el("h3", {}, "Inspector"),
      el("button", {
        type: "button",
        class: "ghost-btn inspector-toggle",
        "aria-expanded": "true",
        onclick: (e) => {
          const btn = e.currentTarget;
          const collapsed = btn.getAttribute("aria-expanded") === "false";
          btn.setAttribute("aria-expanded", String(!collapsed));
          btn.parentElement?.parentElement?.classList.toggle("is-collapsed", collapsed);
        }
      }, "收起")
    ),
    body
  );
}
function fieldRow(labelText, input, id) {
  const label = el("label", { class: "field-label", for: id }, labelText);
  return el("div", { class: "field-row" }, label, input);
}
function briefFieldRow(prefix) {
  const title = el("input", { id: `${prefix}-title`, class: "input", maxlength: "160", placeholder: "例如：秋季品牌视觉" });
  const goals = el("input", { id: `${prefix}-goals`, class: "input", maxlength: "400", placeholder: "现代, 温暖, 克制" });
  const constraints = el("input", { id: `${prefix}-constraints`, class: "input", maxlength: "400", placeholder: "例如：不改变 logo 拓扑" });
  const row = el(
    "div",
    { class: "row-card grid-stack" },
    fieldRow("简报标题（必填）", title, `${prefix}-title`),
    fieldRow("目标（逗号分隔，必填）", goals, `${prefix}-goals`),
    fieldRow("约束（可选）", constraints, `${prefix}-constraints`)
  );
  return { row, title, goals, constraints };
}
const TITLE_MAX = 18;
function expandableTitle(text, suffix = "") {
  const shown = `${text}${suffix}`;
  const wrap = el("span", { class: "title-cell" });
  if (shown.length <= TITLE_MAX) {
    wrap.append(el("strong", { class: "title-text" }, shown));
    return wrap;
  }
  const node = el("strong", { class: "title-text", title: shown }, `${shown.slice(0, TITLE_MAX)}…`);
  const btn = el("button", {
    type: "button",
    class: "ghost-btn title-expand",
    "aria-expanded": "false",
    onclick: () => {
      const expanded = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!expanded));
      node.textContent = expanded ? `${shown.slice(0, TITLE_MAX)}…` : shown;
      btn.textContent = expanded ? "全称" : "收起";
    }
  }, "全称");
  wrap.append(node, btn);
  return wrap;
}
function renderBriefEditor(id, layer, target) {
  const status = el("p", { class: "view-hint", id: "pd-brief-status", role: "status" }, "本页可真实创建并保存简报；保存成功后从服务端重新读回。");
  const stateChip = el("span", { class: "tag info", id: "pd-brief-state" }, "未修改");
  const setState = (kind) => {
    const chip = document.getElementById("pd-brief-state") || stateChip;
    const label = {
      idle: "未修改",
      dirty: "未保存（dirty）",
      saving: "保存中（saving）",
      saved: "已保存（saved）",
      conflict: "冲突（conflict·可恢复）",
      failed: "失败"
    };
    chip.className = kind === "saved" ? "tag ok" : kind === "conflict" ? "tag warn" : kind === "failed" ? "tag bad" : "tag info";
    chip.textContent = label[kind];
  };
  const draftKey = (form) => `design-lab.brief-draft:${id}:${form}`;
  const DRAFT_TTL_MS = 24 * 60 * 60 * 1e3;
  const DRAFT_MAX_CHARS = 2e3;
  const readDraft = (form) => {
    try {
      const raw = globalThis.localStorage?.getItem(draftKey(form));
      if (!raw || raw.length > DRAFT_MAX_CHARS) return null;
      const o = JSON.parse(raw);
      if (typeof o?.title !== "string" && typeof o?.goals !== "string") return null;
      if (typeof o.savedAt !== "number" || Date.now() - o.savedAt > DRAFT_TTL_MS) return null;
      return { title: String(o.title ?? ""), goals: String(o.goals ?? ""), constraints: String(o.constraints ?? "") };
    } catch {
      return null;
    }
  };
  const writeDraft = (form, v) => {
    try {
      const payload = JSON.stringify({ ...v, savedAt: Date.now() });
      if (payload.length > DRAFT_MAX_CHARS) return;
      globalThis.localStorage?.setItem(draftKey(form), payload);
    } catch {
    }
  };
  const clearDraft = (form) => {
    try {
      globalThis.localStorage?.removeItem(draftKey(form));
    } catch {
    }
  };
  const refresh2 = async () => {
    const live = document.getElementById("route-view");
    await renderProjectDetail(id, live || target);
  };
  const liveStatus = () => document.getElementById("pd-brief-status") || status;
  const clearInvalid = (...fields) => {
    for (const f of fields) f.removeAttribute("aria-invalid");
  };
  const fail = (error, focus) => {
    const node = liveStatus();
    node.className = "error";
    node.textContent = revisionHint(error);
    setState(errMsg(error) === "STALE_REVISION" ? "conflict" : "failed");
    if (focus) {
      focus.setAttribute("aria-invalid", "true");
      focus.focus();
    }
  };
  const ok = (message) => {
    const node = liveStatus();
    node.className = "view-hint";
    node.textContent = message;
  };
  const versions = /* @__PURE__ */ new Map();
  for (const row of layer.briefs) versions.set(row.brief_id, row.version);
  const create = briefFieldRow("pd-brief");
  const createBtn = el("button", { type: "button", class: "primary-btn", id: "pd-brief-create" }, "新建简报");
  let submittedCreate = { identity: "", key: "" };
  const createValues = () => ({ title: create.title.value, goals: create.goals.value, constraints: create.constraints.value });
  for (const f of [create.title, create.goals, create.constraints]) {
    f.addEventListener("input", () => {
      setState("dirty");
      writeDraft("create", createValues());
    });
  }
  createBtn.addEventListener("click", () => {
    void (async () => {
      setState("saving");
      status.className = "view-hint";
      status.textContent = "正在提交…";
      const title = create.title.value.trim();
      let goals;
      try {
        goals = splitList(create.goals.value, 300, "目标");
      } catch (error) {
        fail(error, create.goals);
        return;
      }
      clearInvalid(create.title, create.goals);
      if (!title) {
        fail(new Error("简报需要标题与至少一条目标"), create.title);
        return;
      }
      if (!goals.length) {
        fail(new Error("简报需要标题与至少一条目标"), create.goals);
        return;
      }
      const constraints = create.constraints.value.trim() || null;
      const identity = JSON.stringify({ id, title, goals, constraints });
      if (submittedCreate.identity !== identity) submittedCreate = { identity, key: uuid() };
      createBtn.disabled = true;
      try {
        await api(`/projects/${id}/briefs`, {
          title,
          goals,
          constraints,
          reference_asset_ids: [],
          idempotency_key: submittedCreate.key
        });
        clearDraft("create");
        await refresh2();
        ok(`简报已保存并读回：「${title}」。`);
        setState("saved");
      } catch (error) {
        fail(error);
      } finally {
        createBtn.disabled = false;
      }
    })();
  });
  const rev = briefFieldRow("pd-rev");
  const revHint = el(
    "p",
    { class: "view-hint", id: "pd-rev-target" },
    "在某一简报行点「新版本」以载入该版本内容；保存会新增版本，旧版本只保留为历史。"
  );
  const revBtn = el("button", { type: "button", class: "primary-btn", id: "pd-brief-revise" }, "保存新版本");
  let revTarget = null;
  const lineageBox = el("ul", { class: "list", id: "pd-brief-lineage" });
  const loadLineage = async (briefId) => {
    const data = await apiOrEmpty(`/projects/${id}/briefs/${briefId}/lineage`, {
      lineage: { brief_id: briefId, root_id: briefId, requested_id: briefId, live_id: null, versions: [] }
    });
    const rows = data.lineage.versions;
    const liveId = data.lineage.live_id;
    const notice = shapeNotice(data);
    lineageBox.replaceChildren(
      ...notice ? [el("li", { class: "error" }, notice)] : [],
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `版本链（${rows.length}）`),
          el("small", {}, `当前 ${liveId ? `版本 ${versions.get(liveId) ?? "?"}` : "—"}`)
        )
      ),
      ...rows.map((row) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `版本 ${row.version} · ${row.title}`),
          el("small", {}, `${row.goals.join(" / ")}${row.constraints ? ` · ${row.constraints}` : ""} · 参考 ${row.reference_asset_ids.length} · ${row.created_at}`)
        ),
        el("span", { class: row.brief_id === liveId ? "tag ok" : "tag warn" }, versionState(row.superseded_by, versions))
      ))
    );
  };
  const startRevision = (brief) => {
    void (async () => {
      revTarget = brief;
      rev.title.value = brief.title;
      rev.goals.value = brief.goals.join(", ");
      rev.constraints.value = brief.constraints ?? "";
      revHint.textContent = `正在修订「${brief.title}」版本 ${brief.version}；保存会新增一个版本，版本 ${brief.version} 只保留为历史。` + (brief.superseded_by === null ? "" : " 注意：该版本已被取代，服务端会以 STALE_REVISION 拒绝这次修订。");
      rev.title.focus();
      await loadLineage(brief.brief_id);
    })();
  };
  const revValues = () => ({ title: rev.title.value, goals: rev.goals.value, constraints: rev.constraints.value });
  for (const f of [rev.title, rev.goals, rev.constraints]) {
    f.addEventListener("input", () => {
      setState("dirty");
      writeDraft("rev", revValues());
    });
  }
  revBtn.addEventListener("click", () => {
    void (async () => {
      const source = revTarget;
      if (!source) {
        fail(new Error("请先在某一简报行点击「新版本」以载入要修订的内容"));
        return;
      }
      setState("saving");
      status.className = "view-hint";
      status.textContent = "正在提交修订…";
      const title = rev.title.value.trim();
      let goals;
      try {
        goals = splitList(rev.goals.value, 300, "目标");
      } catch (error) {
        fail(error, rev.goals);
        return;
      }
      clearInvalid(rev.title, rev.goals);
      if (!title) {
        fail(new Error("修订需要标题与至少一条目标"), rev.title);
        return;
      }
      if (!goals.length) {
        fail(new Error("修订需要标题与至少一条目标"), rev.goals);
        return;
      }
      const constraints = rev.constraints.value.trim() || null;
      revBtn.disabled = true;
      try {
        const data = await api(`/projects/${id}/briefs/${source.brief_id}/revisions`, {
          title,
          goals,
          constraints,
          // carry the source version's references: the route shell has no reference
          // picker yet (that is W04), and silently dropping them would lose data.
          reference_asset_ids: source.reference_asset_ids,
          idempotency_key: uuid()
        });
        clearDraft("rev");
        await refresh2();
        ok(`简报已保存为版本 ${data.brief.version}；版本 ${source.version} 只保留为历史，旧内容未被改写。`);
        setState("saved");
      } catch (error) {
        fail(error);
      } finally {
        revBtn.disabled = false;
      }
    })();
  });
  const briefRows = layer.briefs.length ? layer.briefs.map((brief) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      expandableTitle(brief.title, ` · v${brief.version}`),
      el("small", {}, `${brief.goals.join(" / ")}${brief.constraints ? ` · ${brief.constraints}` : ""} · 参考 ${brief.reference_asset_ids.length} · ${brief.created_at}`)
    ),
    el(
      "div",
      { class: "actions" },
      el("span", { class: brief.superseded_by === null ? "tag ok" : "tag warn" }, versionState(brief.superseded_by, versions)),
      el("button", { type: "button", class: "ghost-btn", onclick: () => startRevision(brief) }, "新版本")
    )
  )) : [emptyLi(layer, "尚无简报", "用下方表单创建该项目的第一份简报（真实写入，保存后读回）")];
  const restored = [];
  const createDraft = readDraft("create");
  if (createDraft) {
    create.title.value = createDraft.title;
    create.goals.value = createDraft.goals;
    create.constraints.value = createDraft.constraints;
    restored.push("新建简报");
  }
  const revDraft = readDraft("rev");
  if (revDraft) {
    rev.title.value = revDraft.title;
    rev.goals.value = revDraft.goals;
    rev.constraints.value = revDraft.constraints;
    restored.push("修订");
  }
  if (restored.length) setState("dirty");
  const draftNote = el("p", { class: "view-hint", id: "pd-brief-draft" }, restored.length ? `已恢复上次未保存的草稿：${restored.join("、")}。草稿仅保存在本机；保存成功或丢弃后即清除。` : "");
  const discardBtn = el("button", {
    type: "button",
    class: "ghost-btn",
    id: "pd-brief-discard",
    onclick: () => {
      clearDraft("create");
      clearDraft("rev");
      setState("idle");
      draftNote.textContent = "草稿已丢弃；表单内容未改动服务端任何状态。";
    }
  }, "丢弃草稿");
  const panel = el("div", { class: "panel", id: "pd-brief-editor" });
  panel.append(
    el("h3", {}, `简报（Brief）· ${layer.briefs.length} 个版本`),
    el("ul", { class: "list" }, ...briefRows),
    el(
      "div",
      { class: "row-card", style: "display:grid;gap:10px" },
      el("strong", {}, "新建简报"),
      create.row,
      el("div", { class: "actions" }, createBtn)
    ),
    el(
      "div",
      { class: "row-card", style: "display:grid;gap:10px" },
      el("strong", {}, "修订 / 新增版本"),
      revHint,
      rev.row,
      el("div", { class: "actions" }, revBtn)
    ),
    lineageBox,
    el("div", { class: "actions", id: "pd-brief-statebar" }, stateChip, discardBtn),
    draftNote,
    status
  );
  return panel;
}
function renderReferencePanel(id) {
  const heading = el("h3", { id: "pd-ref-heading" }, "参考素材");
  const list = el(
    "ul",
    { class: "list", id: "pd-ref-list" },
    el("li", { class: "list-item" }, el("div", {}, el("strong", {}, "正在读回…")))
  );
  const preview2 = el("img", { id: "pd-ref-preview", class: "ref-preview", alt: "参考素材预览" });
  preview2.hidden = true;
  const info2 = el(
    "p",
    { class: "view-hint", id: "pd-ref-info" },
    "点某一行的「预览」按需读取该资产；清单本身不预加载整图。"
  );
  const status = el("p", { class: "view-hint", id: "pd-ref-status", role: "status" }, "");
  const showError = (message) => {
    status.className = "error";
    status.textContent = message;
  };
  const showHint = (message) => {
    status.className = "view-hint";
    status.textContent = message;
  };
  const previewAsset = async (assetId) => {
    showHint(`正在读取 ${assetId} …`);
    try {
      const data = await api(`/projects/${id}/assets/${assetId}/content`);
      const a = data.asset;
      if (!["image/png", "image/jpeg"].includes(a.media_type)) throw new Error(`UNSUPPORTED_PREVIEW:${a.media_type}`);
      preview2.src = `data:${a.media_type};base64,${data.content_base64}`;
      preview2.hidden = false;
      info2.textContent = `${a.width} × ${a.height} · ${a.media_type} · rights: ${a.rights} · sha256 ${a.sha256.slice(0, 16)}…`;
      showHint(`已按需读回 ${assetId}。`);
    } catch (error) {
      preview2.hidden = true;
      preview2.removeAttribute("src");
      info2.textContent = "—";
      showError(`资产 ${assetId} 读取失败：${errMsg(error)}`);
    }
  };
  const assetRow = (a) => {
    const rights = a.rights === "NOT_REVIEWED" ? el("span", { class: "tag warn" }, "权利未审查") : el("span", { class: "tag info" }, a.rights);
    const headline = `${a.media_type} · ${a.width} × ${a.height} · ${formatByteSize(a.byte_size)}`;
    const provenance = [
      `版本记录 ${a.version_id.slice(0, 12)}…`,
      `sha256 ${a.sha256.replace(/^sha256:/, "").slice(0, 16)}…`,
      a.id
    ].join(" · ");
    return el(
      "li",
      { class: "list-item" },
      el("div", {}, el("strong", {}, headline), el("small", {}, provenance)),
      el(
        "div",
        { class: "actions" },
        rights,
        el("button", { type: "button", class: "ghost-btn", id: `pd-ref-preview-${a.id}`, onclick: () => {
          void previewAsset(a.id);
        } }, "预览")
      )
    );
  };
  const loadAssets = async () => {
    try {
      const data = await api(`/projects/${id}/assets`);
      const assets = data.assets;
      heading.textContent = `参考素材（${assets.length}）`;
      list.replaceChildren(
        ...assets.length ? assets.map(assetRow) : [el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, "尚无参考素材"),
            el("small", {}, "用下方批量导入，或在旧工作台导入；未知权利可研究，但会阻止生产认证。")
          )
        )]
      );
      showHint(assets.some((a) => a.rights === "NOT_REVIEWED") ? "清单已读回。存在「权利未审查」的素材：可继续研究，但在权利清除前不能作为生产认证依据（服务端 fail-closed）。" : "清单已读回；图片内容按需读取。");
      return true;
    } catch (error) {
      heading.textContent = "参考素材";
      list.replaceChildren(el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "未读回"),
          el("small", {}, "资产清单读取失败；此处不显示 0，避免把「没读到」说成「没有」。")
        )
      ));
      showError(`资产清单读取失败：${errMsg(error)}`);
      return false;
    }
  };
  void loadAssets();
  const fileInput = el("input", {
    type: "file",
    id: "pd-ref-files",
    class: "input",
    multiple: "multiple",
    accept: "image/png,image/jpeg"
  });
  const importBtn = el("button", { type: "button", class: "primary-btn", id: "pd-ref-import" }, "开始导入");
  const cancelBtn = el("button", { type: "button", class: "ghost-btn", id: "pd-ref-cancel" }, "取消");
  cancelBtn.disabled = true;
  const results = el("ul", { class: "list", id: "pd-ref-import-results" });
  const summary = el("p", { class: "view-hint", id: "pd-ref-import-summary" }, "尚未导入。");
  const selection = el("p", { class: "view-hint", id: "pd-ref-selection" }, "未选择文件。");
  let batchRunning = false;
  let cancelRequested = false;
  const renderResults = (rows, pending) => {
    results.replaceChildren(...rows.map((r) => el(
      "li",
      { class: "list-item" },
      el("div", {}, el("strong", {}, r.name), el("small", {}, r.detail)),
      el(
        "span",
        { class: r.status === "ok" ? "tag ok" : r.status === "cancelled" ? "tag warn" : "tag bad" },
        r.status === "ok" ? "已导入" : r.status === "cancelled" ? "已取消" : "失败"
      )
    )));
    const ok = rows.filter((r) => r.status === "ok").length;
    const failed = rows.filter((r) => r.status === "failed").length;
    const cancelled = rows.filter((r) => r.status === "cancelled").length;
    summary.className = "view-hint";
    summary.textContent = `导入 ${rows.length} 个：成功 ${ok} · 失败 ${failed} · 已取消 ${cancelled}` + (failed ? "（失败项按失败记；同一文件重试复用同一个键，不会变成第二份素材）" : "") + (pending ? ` · ${pending}` : "");
  };
  fileInput.addEventListener("change", () => {
    const n = fileInput.files ? fileInput.files.length : 0;
    selection.textContent = n ? `已选择 ${n} 个文件。` : "未选择文件。";
  });
  cancelBtn.addEventListener("click", () => {
    if (!batchRunning) return;
    cancelRequested = true;
    cancelBtn.disabled = true;
    selection.textContent = "已请求取消：正在上传的这个文件会完成，其余不再开始。";
  });
  importBtn.addEventListener("click", () => {
    void (async () => {
      if (batchRunning) return;
      const files = Array.from(fileInput.files ?? []);
      if (!files.length) {
        showError("请先选择要导入的图片（PNG / JPEG）。");
        return;
      }
      batchRunning = true;
      cancelRequested = false;
      importBtn.disabled = true;
      cancelBtn.disabled = false;
      const rows = [];
      for (const file of files) {
        if (cancelRequested) {
          rows.push({ name: file.name, status: "cancelled", detail: "取消后未开始" });
          continue;
        }
        if (!["image/png", "image/jpeg"].includes(file.type)) {
          rows.push({ name: file.name, status: "failed", detail: `不支持的媒体类型 ${file.type || "(空)"}：仅 PNG / JPEG` });
          renderResults(rows);
          continue;
        }
        if (file.size > 32 * 1024 * 1024) {
          rows.push({ name: file.name, status: "failed", detail: `超过 32 MiB（${Math.round(file.size / 1048576)} MiB）` });
          renderResults(rows);
          continue;
        }
        try {
          const bytes = new Uint8Array(await file.arrayBuffer());
          let binary = "";
          for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
          await api(
            `/projects/${id}/assets`,
            { content_base64: btoa(binary), idempotency_key: await sha256Hex(bytes) }
          );
          rows.push({ name: file.name, status: "ok", detail: `${Math.round(file.size / 1024)} KiB · 服务端已确认` });
        } catch (error) {
          rows.push({ name: file.name, status: "failed", detail: errMsg(error) });
        }
        renderResults(rows);
      }
      batchRunning = false;
      importBtn.disabled = false;
      cancelBtn.disabled = true;
      renderResults(rows, "正在从服务端重新读回清单…");
      const listRead = await loadAssets();
      renderResults(rows);
      const ok = rows.filter((r) => r.status === "ok").length;
      const cancelled = rows.filter((r) => r.status === "cancelled").length;
      if (cancelRequested) {
        showHint(`已取消：成功 ${ok}，已取消 ${cancelled}（取消后未开始的文件未写入服务端；正在上传的那个已按其真实结果记入）。`);
      } else if (ok === rows.length) {
        showHint(listRead ? `全部 ${ok} 个文件已导入并从服务端读回。` : `全部 ${ok} 个文件已导入；导入后的清单未读回，请稍后刷新。`);
      } else {
        showHint(`导入结束：成功 ${ok} / ${rows.length}；失败项按失败记，同一文件重试不会变成第二份素材；` + (listRead ? "清单已从服务端重新读回。" : "清单未读回，请稍后刷新。"));
      }
    })();
  });
  return el(
    "div",
    { class: "panel", id: "pd-reference-panel" },
    heading,
    list,
    el(
      "div",
      { class: "row-card grid-stack" },
      el("strong", {}, "预览（按需读取）"),
      preview2,
      info2
    ),
    el(
      "div",
      { class: "row-card grid-stack" },
      el("strong", {}, "批量导入（PNG / JPEG，单个 ≤ 32 MiB）"),
      fieldRow("选择要导入的图片", fileInput, "pd-ref-files"),
      selection,
      el("div", { class: "actions" }, importBtn, cancelBtn),
      results,
      summary
    ),
    status
  );
}
function renderDirectionPanel(id, layer, target) {
  const status = el("p", { class: "view-hint", id: "pd-dir-status", role: "status" }, "");
  const showError = (m) => {
    status.className = "error";
    status.textContent = m;
  };
  const showHint = (m) => {
    status.className = "view-hint";
    status.textContent = m;
  };
  const refresh2 = async () => {
    const live = document.getElementById("route-view");
    await renderProjectDetail(id, live || target);
  };
  const briefById = new Map(layer.briefs.map((b) => [b.brief_id, b]));
  const liveBriefs = layer.briefs.filter((b) => b.superseded_by === null);
  const chosen = layer.chosen_direction;
  const binding = layer.active_binding;
  const consistency = !chosen ? binding ? "不一致：存在活动绑定但没有选定方向" : "尚未选定方向" : binding ? binding.direction_id === chosen.direction_id ? `一致：选定方向与活动绑定同为一个（${chosen.title}）` : `不一致：选定方向「${chosen.title}」≠ 活动绑定所属方向 ${binding.direction_id}` : "方向已选定，但尚未绑定设计系统（属正常中间态，不宣称已一致到交付）";
  const directionRow = (d) => {
    const bound = briefById.get(d.brief_id);
    const stale = bound ? bound.superseded_by !== null : true;
    const mood = [d.color_mood ? `色感 ${d.color_mood}` : null, d.typography_mood ? `字感 ${d.typography_mood}` : null].filter(Boolean).join(" · ") || "（未填色感/字感）";
    const notes = d.style_notes && d.style_notes.length ? d.style_notes.join(" / ") : null;
    return el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        expandableTitle(d.title, ` · v${d.version}`),
        el("small", {}, `${mood}${notes ? ` · ${notes}` : ""} · ${d.direction_id}`),
        el("small", {}, d.actor ? `选定人：${d.actor}（${d.actor_kind ?? "未标注类型"}）` : "尚未有人选定"),
        ...stale ? [el("small", { class: "error" }, bound ? `绑定的简报版本 v${bound.version} 已被取代 → 该方向需重新审查（不自动失效，也不自动沿用）` : "绑定的简报已不在当前项目中 → 需重新审查")] : []
      ),
      el(
        "div",
        { class: "actions" },
        d.chosen ? el("span", { class: "tag ok" }, "已选定") : el("span", { class: "tag info" }, "候选"),
        ...d.chosen ? [] : [el("button", {
          type: "button",
          class: "ghost-btn",
          id: `pd-dir-choose-${d.direction_id}`,
          onclick: () => {
            void (async () => {
              showHint(`正在以人工身份选定「${d.title}」…`);
              try {
                await api(`/projects/${id}/directions/${d.direction_id}/choose`, {
                  actor: "workbench-user",
                  actor_kind: "human",
                  idempotency_key: uuid()
                });
                await refresh2();
              } catch (error) {
                showError(`方向选择未确认：${errMsg(error)}`);
              }
            })();
          }
        }, "选定（人工）")]
      )
    );
  };
  const briefSelect = el(
    "select",
    { id: "pd-dir-brief", class: "input" },
    ...liveBriefs.length ? liveBriefs.map((b) => el("option", { value: b.brief_id }, `${b.title} · v${b.version} · ${b.brief_id.slice(-8)}`)) : [el("option", { value: "" }, "（没有可用简报版本）")]
  );
  const title = el("input", { id: "pd-dir-title", class: "input", maxlength: "160", placeholder: "方向标题（必填）" });
  const colorMood = el("input", { id: "pd-dir-color", class: "input", maxlength: "120", placeholder: "色感（可选）" });
  const typeMood = el("input", { id: "pd-dir-type", class: "input", maxlength: "120", placeholder: "字感（可选）" });
  const createBtn = el("button", { type: "button", class: "primary-btn", id: "pd-dir-create" }, "新建方向候选");
  createBtn.addEventListener("click", () => {
    void (async () => {
      const briefId = briefSelect.value;
      const t = title.value.trim();
      if (!briefId) {
        showError("请先创建一份简报，再立方向。");
        return;
      }
      if (!t) {
        showError("方向需要标题。");
        title.setAttribute("aria-invalid", "true");
        title.focus();
        return;
      }
      title.removeAttribute("aria-invalid");
      createBtn.disabled = true;
      showHint("正在提交方向候选…");
      try {
        await api(`/projects/${id}/directions`, {
          brief_id: briefId,
          title: t,
          style_notes: null,
          color_mood: colorMood.value.trim() || null,
          typography_mood: typeMood.value.trim() || null,
          idempotency_key: uuid()
        });
        await refresh2();
        const node = document.getElementById("pd-dir-status");
        if (node) {
          node.className = "view-hint";
          node.textContent = `方向候选「${t}」已保存并读回；候选不会自动成为选定方向，必须由人选定。`;
        }
      } catch (error) {
        showError(`方向未确认：${errMsg(error)}`);
      } finally {
        createBtn.disabled = false;
      }
    })();
  });
  return el(
    "div",
    { class: "panel", id: "pd-direction-panel" },
    el("h3", {}, `方向（Direction）· ${layer.directions.length} 个候选`),
    el("p", { class: "view-hint", id: "pd-dir-consistency" }, `版本链 / 选定 / 绑定一致性：${consistency}`),
    el(
      "ul",
      { class: "list" },
      ...layer.directions.length ? [...layer.directions].map(directionRow) : [emptyLi(layer, "尚无方向候选", "先建立简报，再用下方表单立候选；选定必须由人执行。")]
    ),
    el(
      "div",
      { class: "row-card grid-stack" },
      el("strong", {}, "新建方向候选（绑定到某个简报版本）"),
      fieldRow("所属简报版本", briefSelect, "pd-dir-brief"),
      fieldRow("方向标题（必填）", title, "pd-dir-title"),
      fieldRow("色感（可选）", colorMood, "pd-dir-color"),
      fieldRow("字感（可选）", typeMood, "pd-dir-type"),
      el("div", { class: "actions" }, createBtn)
    ),
    status
  );
}
function renderDesignSystemPanel(id, layer, systems, target) {
  const status = el("p", { class: "view-hint", id: "pd-ds-status", role: "status" }, "");
  const showError = (m) => {
    status.className = "error";
    status.textContent = m;
  };
  const showHint = (m) => {
    status.className = "view-hint";
    status.textContent = m;
  };
  const refresh2 = async () => {
    const live = document.getElementById("route-view");
    await renderProjectDetail(id, live || target);
  };
  const chosen = layer.chosen_direction;
  const active = layer.active_binding;
  const select = el(
    "select",
    { id: "pd-ds-name", class: "input" },
    ...systems.design_systems.length ? systems.design_systems.map((s) => el("option", { value: s.name }, `${s.title} · v${s.version} · 证据 ${s.evidence_level}`)) : [el("option", { value: "" }, "（目录为空或未读回）")]
  );
  const bindBtn = el("button", { type: "button", class: "primary-btn", id: "pd-ds-bind" }, "绑定到已选定方向");
  bindBtn.disabled = !chosen || !systems.design_systems.length;
  const gate = el("p", { class: "view-hint", id: "pd-ds-gate" }, !chosen ? "绑定不可用：尚无人选定方向。请先在「方向」面板人工选定一个候选（AI 候选不会自动成为选定方向）。" : !systems.design_systems.length ? "绑定不可用：设计系统目录为空或未读回。" : `将绑定到已选定方向「${chosen.title}」（v${chosen.version}）。`);
  bindBtn.addEventListener("click", () => {
    void (async () => {
      const name = select.value;
      if (!chosen) {
        showError("请先人工选定一个方向，再绑定设计系统。");
        return;
      }
      if (!name) {
        showError("请选择要绑定的设计系统。");
        return;
      }
      bindBtn.disabled = true;
      showHint(`正在绑定 ${name} …`);
      try {
        await api(`/projects/${id}/directions/${chosen.direction_id}/bind`, {
          design_system_name: name,
          idempotency_key: uuid()
        });
        await refresh2();
        const node = document.getElementById("pd-ds-status");
        if (node) {
          node.className = "view-hint";
          node.textContent = `设计系统已绑定：${name}。设计契约已固定；制作与质量验收仍未执行。`;
        }
      } catch (error) {
        showError(`绑定未确认：${errMsg(error)}`);
        bindBtn.disabled = false;
      }
    })();
  });
  const consistent = !!(active && chosen && active.direction_id === chosen.direction_id);
  return el(
    "div",
    { class: "panel", id: "pd-design-system-panel" },
    el("h3", {}, `设计系统（DesignSystem）· 目录 ${systems.design_systems.length} 项 · 绑定 ${layer.bindings.length} 次`),
    el(
      "ul",
      { class: "list" },
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "活动绑定"),
          el("small", {}, active ? `${active.design_system_name} · 绑定于方向 ${active.direction_id} · v${active.version}` : "（无活动绑定）")
        ),
        el("span", { class: active ? "tag ok" : "tag info" }, active ? "已绑定" : "未绑定")
      ),
      ...active && chosen ? [el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "绑定与选定方向的一致性"),
          el("small", {}, consistent ? "一致：活动绑定所属方向就是人工选定的方向。" : `不一致：活动绑定属于 ${active.direction_id}，而人工选定的是 ${chosen.direction_id}。`)
        ),
        el("span", { class: consistent ? "tag ok" : "tag bad" }, consistent ? "一致" : "不一致")
      )] : []
    ),
    el(
      "div",
      { class: "row-card grid-stack" },
      el("strong", {}, "绑定设计系统（需先有人选定方向）"),
      gate,
      fieldRow("要绑定的设计系统", select, "pd-ds-name"),
      el("div", { class: "actions" }, bindBtn)
    ),
    el(
      "p",
      { class: "view-hint" },
      "Token 文档的写入与版本链在下方「设计系统 Token」面板执行（真实写入，读回持久化行）；版本 diff、发布与回滚尚无路由，本页不做假 diff。"
    ),
    status
  );
}
const TOKEN_SAMPLE_DOCUMENT = '{"color":{"$type":"color","brand":{"$value":"#2563EB"},"surface":{"$value":"{color.brand}"}},"scale":{"$type":"dimension","space":{"md":{"$value":"16px"}}}}';
function serviceErrorDetail(error) {
  const envelope = error?.serviceEnvelope;
  const detail = envelope?.detail;
  return Array.isArray(detail) ? detail.filter((line) => typeof line === "string") : [];
}
function tokenBaseline(documents, name) {
  return documents.find((row) => row.design_system_name === name) ?? null;
}
function renderTokenDocumentPanel(id, tokens, systems, target) {
  const documents = tokens.token_documents;
  const status = el("p", { class: "view-hint", id: "pd-token-status", role: "status" }, "");
  const showError = (message) => {
    status.className = "error";
    status.textContent = message;
  };
  const showHint = (message) => {
    status.className = "view-hint";
    status.textContent = message;
  };
  const refresh2 = async () => {
    const live = document.getElementById("route-view");
    await renderProjectDetail(id, live || target);
  };
  const select = el(
    "select",
    { id: "pd-token-name", class: "input" },
    ...systems.design_systems.length ? systems.design_systems.map((system) => el("option", {
      value: system.name
    }, `${system.title} · ${system.name} · 证据 ${system.evidence_level}`)) : [el("option", { value: "" }, "（目录为空或未读回）")]
  );
  const editor = el("textarea", {
    id: "pd-token-document",
    class: "input",
    rows: "10",
    spellcheck: "false",
    "aria-label": "DTCG Token 文档 JSON"
  });
  const gate = el("p", { class: "view-hint", id: "pd-token-gate" }, "");
  const fill = () => {
    const live = tokenBaseline(documents, select.value);
    editor.value = live ? JSON.stringify(live.document, null, 2) : TOKEN_SAMPLE_DOCUMENT;
    gate.textContent = !systems.design_systems.length ? "写入不可用：设计系统目录为空或未读回，服务端会以 UNKNOWN_DESIGN_SYSTEM 拒绝。" : live ? `将追加到 ${live.design_system_name} 的 v${live.version}（${live.token_count} 个 token）。本次提交基于 expected_version=${live.version}，服务端写入 v${live.version + 1}。` : `${select.value || "（未选择）"} 尚无 Token 文档；本次提交创建 v1。`;
  };
  fill();
  select.addEventListener("change", () => {
    fill();
  });
  const writeBtn = el("button", {
    type: "button",
    class: "primary-btn",
    id: "pd-token-write"
  }, documents.length ? "追加 Token 版本（真实写入）" : "提交 Token 文档（真实写入）");
  writeBtn.disabled = !systems.design_systems.length;
  writeBtn.addEventListener("click", () => {
    void (async () => {
      const name = select.value;
      if (!name) {
        showError("请先选择一个已登记的设计系统，再提交 Token 文档。");
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(editor.value);
      } catch (error) {
        showError(`Token 文档不是合法 JSON：${errMsg(error)}。本次未提交，服务端未写入任何内容。`);
        return;
      }
      const base = tokenBaseline(documents, name);
      const expectedVersion = base ? base.version : 0;
      writeBtn.disabled = true;
      showHint(`正在提交 ${name} 的 Token 文档（基于 v${expectedVersion}）…`);
      try {
        const result = await api(
          `/projects/${id}/design-system-tokens/${name}`,
          {
            document: parsed,
            expected_version: expectedVersion,
            actor: "workbench-user",
            actor_kind: "human",
            idempotency_key: uuid()
          }
        );
        await refresh2();
        const node = document.getElementById("pd-token-status");
        if (node) {
          node.className = "view-hint";
          node.textContent = `已写入并读回 v${result.token_document.version}（${result.token_document.token_count} 个 token · DTCG ${result.token_document.dtcg_schema_version}）。持久化与版本追加已验证；宿主 Token 工具、权利与质量验收仍未执行。`;
        }
      } catch (error) {
        const detail = serviceErrorDetail(error);
        const stale = errMsg(error) === "STALE_REVISION";
        showError(`Token 文档未被接受：${errMsg(error)}` + (detail.length ? `；字段：${detail.slice(0, 3).join(" | ")}` : "") + (stale ? `；${revisionHint(error)}` : "") + "；服务端未写入任何内容。");
        writeBtn.disabled = false;
      }
    })();
  });
  const rows = documents.length ? documents.map((doc) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, `${doc.design_system_name} · v${doc.version}`),
      el("small", {}, `${doc.token_count} 个 token · DTCG ${doc.dtcg_schema_version} · ${doc.spec_sha256.slice(0, 17)}…`),
      el("small", {}, `写回：${doc.actor || "未标注"} · ${doc.created_at}`)
    ),
    el(
      "span",
      { class: doc.actor_kind === "human" ? "tag ok" : "tag info" },
      doc.actor_kind ? en(doc.actor_kind) : "未标注身份"
    )
  )) : [emptyLi(
    tokens,
    "尚无 Token 文档",
    "用下方表单提交一份 DTCG Token 文档；写入后在此读回持久化行。"
  )];
  return el(
    "div",
    { class: "panel", id: "pd-token-panel" },
    el("h3", {}, `设计系统 Token（DTCG）· 当前文档 ${documents.length}`),
    el("ul", { class: "list" }, ...rows),
    el(
      "div",
      { class: "row-card grid-stack" },
      el("strong", {}, documents.length ? "修订 Token 文档（追加新版本）" : "提交 Token 文档（创建 v1）"),
      gate,
      fieldRow("设计系统", select, "pd-token-name"),
      fieldRow("Token 文档 JSON", editor, "pd-token-document"),
      el("div", { class: "actions" }, writeBtn)
    ),
    status,
    el(
      "p",
      { class: "view-hint" },
      "写入前服务端跑 DTCG 结构（interop-dtcg-document.schema.json）与语义校验（$type 继承、别名解析与成环、composite 成员完整性），并按项目 + 设计系统追加版本；已写入的版本不可改写，发布与回滚尚无路由。"
    )
  );
}
function renderDeliveryPanel(id, data) {
  const bundles = data.bundles;
  const heading = el("h3", { id: "pd-deliveries-heading" }, `交付包（${bundles.length}）`);
  const status = el("p", { class: "view-hint", id: "pd-deliveries-status", role: "status" }, "");
  const list = el(
    "ul",
    { class: "list", id: "pd-deliveries-list" },
    ...bundles.length ? [] : [el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, token ? "尚无交付包" : "未连接"),
        el("small", {}, token ? "任务完成并打包后，交付会在此读回。" : "连接本机设计服务后读回该项目的交付清单。")
      )
    )]
  );
  const download = async (bundle) => {
    const access = token;
    const route = `/projects/${id}/bundles/${bundle.id}/versions/${bundle.version_id}/content`;
    status.textContent = `正在核对 ${bundle.id} 的交付包…`;
    const response = await fetch("/api" + route, { headers: { Authorization: "Bearer " + access }, cache: "no-store" });
    if (!response.ok) {
      status.textContent = `交付包读取失败：HTTP ${response.status}。`;
      return;
    }
    const bytes = await response.arrayBuffer();
    const digest = Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (b) => b.toString(16).padStart(2, "0")
    ).join("");
    if (digest !== bundle.sha256.replace(/^sha256:/, "") || bytes.byteLength !== bundle.byte_size) {
      status.textContent = "交付包与记录 hash 不一致，未采纳（fail-closed）。";
      return;
    }
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `design-lab-${bundle.id.slice(-12)}.zip`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 3e4);
    status.textContent = `交付包已下载并核对 hash；字体、链接、rights 与质量仍需验收。`;
  };
  const row = (b) => el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, `交付包 · v${b.version_no}`),
      el("small", {}, `${b.id} · ${b.byte_size} 字节 · sha256 ${String(b.sha256).replace(/^sha256:/, "").slice(0, 16)}…`)
    ),
    el(
      "div",
      { class: "actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          void download(b).catch((e) => {
            status.textContent = `交付包读取失败：${errMsg(e)}`;
          });
        }
      }, "下载交付包"),
      el(
        "span",
        { class: b.rights === "NOT_REVIEWED" ? "tag warn" : "tag info" },
        b.rights === "NOT_REVIEWED" ? "权利未审查" : b.rights
      )
    )
  );
  list.append(...bundles.map(row));
  status.textContent = bundles.length ? "交付清单已读回。hash 在点击「下载交付包」时核对；权利与质量仍需独立验收。" : token ? "该项目当前没有已交付的设计包。" : "未连接：交付清单未读回，不代表该项目没有交付包。";
  return el(
    "div",
    { class: "panel", id: "pd-deliveries" },
    heading,
    list,
    status,
    el(
      "p",
      { class: "view-hint" },
      "交付包内容：宿主导出的可编辑源 + 预览 + 输入清单（manifest）。BOM 尚未生成（PLANNED，无写入口）；读取与 hash 为只读回读，权利 / 质量 / 预检仍由人工验收。"
    )
  );
}
function renderVersionsPanel(bundlesResp) {
  const bundles = Array.isArray(bundlesResp.bundles) ? bundlesResp.bundles : [];
  const unread = disconnectedNotice(bundlesResp) || shapeNotice(bundlesResp);
  const byKind = /* @__PURE__ */ new Map();
  for (const b of bundles) {
    const list = byKind.get(b.kind) ?? [];
    list.push(b);
    byKind.set(b.kind, list);
  }
  const groups = [];
  for (const [kind, list] of byKind) {
    const ordered = [...list].sort((a, b) => b.version_no - a.version_no);
    const head = ordered[0];
    groups.push(el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, kind),
        el("small", {}, ordered.length > 1 ? `${ordered.length} 个版本 · 当前 v${head.version_no}` : `1 个版本 · v${head.version_no}`)
      ),
      el(
        "ul",
        { class: "list" },
        ...ordered.map((v, index) => el(
          "li",
          { class: "list-item" },
          el(
            "div",
            {},
            el("strong", {}, `v${v.version_no}${index === 0 ? " · 当前" : " · 已被后续版本取代"}`),
            el("small", {}, `${v.version_id} · ${v.byte_size} B · sha256 ${v.sha256.slice(0, 12)}…`)
          ),
          el(
            "span",
            { class: "tag neutral" },
            `权利 ${v.rights || "未读回"} · 核验 ${v.verification || "未读回"}`
          )
        ))
      )
    ));
  }
  const panel = el(
    "div",
    { class: "panel", id: "pd-versions-panel" },
    el("h3", {}, unread ? "成果版本（未读回）" : `成果版本（${byKind.size} 类 / ${bundles.length} 版本）`),
    unread ? el(
      "p",
      { class: "error" },
      '未读回：GET /api/projects/{id}/bundles 没有给回 bundles，所以这里既不列版本，也不说"没有版本"。'
    ) : bundles.length ? el("ul", { class: "list" }, ...groups) : el(
      "p",
      { class: "view-hint" },
      '尚无成果版本：本项目的 /bundles 读回是空集合，不是"版本读不到"。'
    ),
    el(
      "p",
      { class: "view-hint" },
      "两张表分开：**格式/版本**看这里（每个版本自己的 id、字节数、摘要、权利与核验原词），**结构与视觉**看交付包清单与预检面，**局部改稿**是写入动作，入口在高级区的 patch 路由 （POST /api/projects/{id}/tasks/{job}/patch），本面板只读回、不提交改稿，也不从 version_no 推断哪一版由改稿产生。"
    )
  );
  return panel;
}
async function renderProjectDetail(id, target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回该项目…"));
  rememberProject(id);
  const listing = await apiOrEmpty("/projects", OFFLINE.projects);
  const named = listing.projects.find((p) => p.id === id);
  const [tasks2, layerResp, systemsResp, bundlesResp, tokensResp] = await Promise.all([
    apiOrEmpty(`/projects/${id}/tasks`, OFFLINE.tasks),
    apiOrEmpty(`/projects/${id}/design-layer`, OFFLINE.designLayer),
    apiOrEmpty("/design-systems", OFFLINE.designSystems),
    apiOrEmpty(`/projects/${id}/bundles`, OFFLINE.bundles),
    apiOrEmpty(
      `/projects/${id}/design-system-tokens`,
      OFFLINE.tokenDocuments
    )
  ]);
  const layer = layerResp.design_layer;
  const chosen = layer.chosen_direction ? `${layer.chosen_direction.title} · v${layer.chosen_direction.version}` : "（尚未选定方向）";
  const active = layer.active_binding ? `${layer.active_binding.design_system_name} · 绑定 ${layer.active_binding.direction_id}` : "（无活动绑定）";
  const pageHead = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, named ? named.name : id),
      el("p", {}, `项目详情 · ${id}。tasks 与 design-layer 为只读回读；下方简报区是真实写入，保存后从服务端读回。`)
    ),
    el(
      "div",
      { class: "page-actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        onclick: () => {
          window.location.hash = "#/projects";
        }
      }, "返回项目列表")
    )
  );
  const kpis = el(
    "div",
    { class: "kpi-grid" },
    kpiCard(String(tasks2.tasks.length), "任务", "读回 /tasks 台账"),
    kpiCard(String(layer.briefs.length), "简报版本", "读回 design-layer"),
    kpiCard(String(layer.directions.length), "方向版本", "读回 design-layer"),
    kpiCard(layer.active_binding ? "1" : "0", "活动绑定", active)
  );
  const taskPanel = el(
    "div",
    { class: "panel", id: "pd-tasks-panel" },
    el("h3", {}, `任务台账（${tasks2.tasks.length}）`),
    el(
      "ul",
      { class: "list" },
      ...tasks2.tasks.length ? tasks2.tasks.slice(0, 8).map((t) => el(
        "li",
        { class: "list-item" },
        el("div", {}, el("strong", {}, t.kind), el("small", {}, `尝试 ${t.attempt.attempt_no} · ${t.attempt.state}`)),
        el("span", { class: "tag info" }, t.state)
      )) : [emptyLi(tasks2, "尚无任务", "任务由工作台高级区提交")]
    )
  );
  const layerPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "设计层契约"),
    el(
      "ul",
      { class: "list" },
      valueRow("选定方向", chosen, false),
      // `active` always embeds a 32-hex direction_id, so it is a long value by
      // construction and must never go into the nowrap .tag pill (F-2).
      valueRow("活动绑定", active, true),
      valueRow("设计系统登记", String(layer.design_systems.length), false)
    )
  );
  const stageNav = buildStageNav();
  const inspector = buildInspectorPanel(id, layer);
  target.replaceChildren(
    pageHead,
    kpis,
    stageNav,
    el(
      "div",
      { class: "project-detail-layout" },
      el(
        "div",
        { class: "project-detail-main" },
        el("div", { class: "two-col spaced-top" }, taskPanel, layerPanel),
        el(
          "div",
          { class: "spaced-top" },
          renderDeliveryPanel(id, bundlesResp),
          renderVersionsPanel(bundlesResp)
        ),
        el("div", { class: "spaced-top" }, renderBriefEditor(id, layer, target)),
        el("div", { class: "spaced-top" }, renderDirectionPanel(id, layer, target)),
        el("div", { class: "spaced-top" }, renderDesignSystemPanel(id, layer, systemsResp, target)),
        el("div", { class: "spaced-top" }, renderTokenDocumentPanel(id, tokensResp, systemsResp, target)),
        el("div", { class: "spaced-top" }, renderReferencePanel(id))
      ),
      inspector
    ),
    el("p", { class: "view-hint" }, "tasks 与 design-layer 台账为只读；简报区可真实创建与修订并读回，Token 区可真实提交 DTCG 文档并按版本追加读回；参考素材区读回资产清单并按需预览。提交任务 / 运行 / 取消 / 导出仍由工作台高级区执行。"),
    ...shapeNoticeRows(bundlesResp, layerResp, listing, systemsResp, tasks2, tokensResp)
  );
}
async function renderRoute(view, target) {
  cancelPendingReads();
  target.replaceChildren();
  switch (view) {
    case "dashboard":
      await renderDashboard(target);
      return;
    case "brand-systems":
      await renderBrandSystems(target);
      return;
    case "preflight-qa":
      await renderPreflight(target);
      return;
    case "research":
      await renderResearchView(target);
      return;
    case "settings":
      await renderSettings(target);
      return;
    // DL-KB-03/04: 知识与提示词库。搜索是主视觉，列表是检索的答案；详情、修订、导入都读回服务。
    case "knowledge":
      await renderKnowledgeLibrary(target);
      return;
    case "assistant":
      await renderDesignAssistant(target);
      return;
    case "projects":
      await renderProjects(target);
      return;
    case "creative-tools":
      await renderCreativeTools(target);
      return;
    case "deliverables":
      await renderDeliverables(target);
      return;
    case "evidence":
      await renderEvidence(target);
      return;
    case "design-domains":
      await renderDomains(target);
      return;
    // owner 2026-10-28: the automation surface reads GET /api/automation-connectors and offers
    // no action, so nothing on this screen can be mistaken for a host being connected.
    case "automation-connectors":
      await renderAutomationConnectors(target);
      return;
    // R2 §2: the same registry addressed at one pack. The list stays rendered so the
    // detail is read inside its context instead of replacing it.
    case "domain-detail":
      await renderDomains(
        target,
        { openId: domainDetailId(window.location.hash) }
      );
      return;
    // DL-UI-U02 首批页面。能力目录读的是**已有**路由 GET /api/capabilities
    // （renderCapabilityLibrary 早就存在，此前只嵌在仪表盘里没有自己的入口）；它自己
    // 带标题「能力目录」，所以这里不再叠一层 h2——2026-10-09 读渲染图时发现两块标题
    // 叠在一起。界面状态与组件规范是规格面，不发请求，所以也不可能编造记录。
    case "capabilities":
      await renderCapabilityLibrary(target);
      return;
    // R2 §5: the same catalog, addressed at one record. The list stays rendered so the
    // detail is read *inside* its context instead of replacing it.
    case "capability-detail":
      await renderCapabilityLibrary(
        target,
        { openId: capabilityDetailId(window.location.hash) }
      );
      return;
    case "intake":
      await renderIntake(target);
      return;
    case "analysis":
      await renderAnalysis(target);
      return;
    // 提示词工程读的是已有设计层投影，写的是本批新加的两条 POST 路由；模型选择是一个
    // 诚实占位面——它只读 GET /api/capabilities 与 /api/environment，没有 /api/models。
    case "prompt-intelligence":
      await renderPromptIntelligence(target);
      return;
    case "model-selection":
      await renderModelSelection(target);
      return;
    // DL-KB-10 屏幕三：目标组合选择面板。选目标与配助手模型是两屏，不共用一个菜单。
    case "target-profiles":
      await renderTargetProfiles(target);
      return;
    case "plan":
      await renderPlan(target);
      return;
    case "records":
      await renderRecords(target);
      return;
    case "ui-states":
      renderUiStates(target);
      return;
    case "ui-components":
      renderUiComponents(target);
      return;
    // B07 `/projects/:id`. The id comes from the hash (renderRoute receives only
    // the resolved view, matching the existing signature).
    case "project-detail": {
      const id = projectDetailId(window.location.hash);
      if (!id) {
        await renderProjects(target);
        return;
      }
      await renderProjectDetail(id, target);
      return;
    }
    default: {
      const notOpen = VIEW_NOT_OPEN[view];
      const slotFor = (v) => v === "collaboration" ? "collaboration" : null;
      const wanted = slotFor(view);
      const cards = el(
        "div",
        { class: "card-flow" },
        ...CAPABILITY_REGISTRY.filter((c) => c.capabilityId === wanted).map(capabilityCard)
      );
      const hasCards = CAPABILITY_REGISTRY.some((c) => c.capabilityId === wanted);
      target.replaceChildren(
        el("h2", {}, notOpen ? viewLabel(view) : "工作台"),
        el("p", { class: "view-unopened" }, notOpen ?? "默认工作台。"),
        ...hasCards ? [cards] : []
      );
      return;
    }
  }
}
function mountAppShell() {
  const login = byId("login");
  const workspace = byId("workspace");
  const nav = el(
    "nav",
    { class: "app-nav", "aria-label": "DESIGN-LAB 导航" },
    // The owner's mark rides next to the wordmark rather than replacing it: the text is the
    // accessible name, so the glyph stays aria-hidden. The old sidebar tile this copies from
    // (shell.ts's commented-out legacy markup) renders at zero size, which is why the nav header
    // had no logo at all until now.
    el(
      "span",
      { class: "app-nav-brand" },
      el("i", { class: "app-nav-mark", "aria-hidden": "true" }),
      "DESIGN-LAB"
    ),
    ...navGroupChunks(ROUTE_VIEWS, (route) => el("button", {
      type: "button",
      class: "app-nav-item",
      dataset: { route: route.view },
      onclick: () => {
        window.location.hash = route.hash === "" ? "" : route.hash;
      }
    }, route.label)),
    el("span", { class: "app-nav-meta", id: "shell-connection" }, "未连接")
  );
  const navDaily = NAV_DAILY_VIEWS;
  const navMore = el("button", {
    type: "button",
    class: "app-nav-more",
    "aria-expanded": "false",
    onclick: () => foldNav(!nav.classList.contains("nav-open"))
  }, "全部功能");
  const navMeta = nav.querySelector(".app-nav-meta");
  if (navMeta) nav.insertBefore(navMore, navMeta);
  else nav.append(navMore);
  function foldNav(open) {
    const host = nav;
    host.classList.toggle("nav-open", open);
    navMore.setAttribute("aria-expanded", String(open));
    navMore.textContent = open ? "收起次要入口" : "全部功能";
    for (const item of Array.from(host.querySelectorAll(".app-nav-item"))) {
      item.classList.toggle("is-folded", !open && !navDaily.includes(item.dataset.route ?? ""));
    }
  }
  foldNav(false);
  const syncLegacyNavCue = () => {
    const mobile = typeof window.matchMedia === "function" && window.matchMedia("(max-width: 760px)").matches;
    const hasMore = mobile && nav.scrollWidth > nav.clientWidth && nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 1;
    nav.classList.toggle("has-scroll-more", hasMore);
  };
  nav.addEventListener("scroll", syncLegacyNavCue, { passive: true });
  window.addEventListener("resize", syncLegacyNavCue);
  const routeView = el("div", { class: "route-view", id: "route-view", tabindex: "-1" });
  document.body.append(nav);
  document.body.classList.add("dl-shell");
  const b10 = mountB10Shell(routeView, syncLegacyNavCue);
  if (!b10) document.body.append(routeView);
  mountThemeControls();
  const active = (view) => {
    for (const item of Array.from(nav.querySelectorAll(".app-nav-item"))) {
      const selected = item.dataset.route === view;
      item.classList.toggle("active", selected);
      if (selected) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    }
  };
  const current = () => {
    if (projectDetailId(window.location.hash)) return "project-detail";
    if (capabilityDetailId(window.location.hash)) return "capability-detail";
    if (domainDetailId(window.location.hash)) return "domain-detail";
    const match = ROUTE_VIEWS.find((route) => route.hash === hashPath(window.location.hash));
    if (!match && devMode()) return "dashboard";
    return match ? match.view : "workbench";
  };
  if (typeof document.querySelector === "function") {
    const skipLink = document.querySelector("a.skip-link");
    skipLink?.addEventListener("click", (event) => {
      event.preventDefault();
      const target = current() === "workbench" ? workspace.hidden ? login : workspace : document.getElementById("content") ?? routeView;
      target.focus();
    });
  }
  let routeGeneration = 0;
  const show = () => {
    const view = current();
    refreshThemeControls();
    const showWorkbench = view === "workbench";
    const generation = ++routeGeneration;
    const routeToken = token;
    b10?.sync(view);
    login.hidden = showWorkbench ? connected : true;
    if (showWorkbench) {
      workspace.hidden = !connected;
      active("workbench");
      return;
    }
    login.hidden = true;
    workspace.hidden = true;
    active(DETAIL_NAV_OWNER[view] ?? view);
    const target = byId("route-view");
    if (!token && !devMode()) {
      target.replaceChildren(
        el("h2", {}, viewLabel(view)),
        el("p", { class: "view-unopened" }, "请先在工作台连接本机设计服务，再读回此视图。"),
        el("button", {
          type: "button",
          class: "primary-btn",
          onclick: () => {
            window.location.hash = "";
          }
        }, "前往工作台连接")
      );
      target.removeAttribute("aria-busy");
      return;
    }
    target.replaceChildren(el("p", { class: "view-loading" }, "正在读回当前视图…"));
    target.setAttribute("aria-busy", "true");
    const pendingView = document.createElement("div");
    void renderRoute(view, pendingView).then(() => {
      if (generation !== routeGeneration || current() !== view || token !== routeToken) return;
      target.replaceChildren(...Array.from(pendingView.childNodes));
      target.removeAttribute("aria-busy");
      announceRoute(viewLabel(view));
      if (document.activeElement === document.body) target.focus({ preventScroll: true });
    }).catch((error) => {
      if (generation !== routeGeneration || current() !== view || token !== routeToken) return;
      target.replaceChildren(el("p", { class: "error" }, `视图读回失败：${errMsg(error)}`));
      target.removeAttribute("aria-busy");
      announceRoute(`${viewLabel(view)} 读回失败`);
      if (document.activeElement === document.body) target.focus({ preventScroll: true });
    });
  };
  const routeAnnouncer = el("p", { class: "sr-status", role: "status" });
  document.body.append(routeAnnouncer);
  const announceRoute = (label) => {
    routeAnnouncer.textContent = `${label} 已载入`;
  };
  const connection = byId("connection");
  const syncMeta = () => {
    byId("shell-connection").textContent = connection.textContent || "未连接";
  };
  if (typeof MutationObserver !== "undefined")
    new MutationObserver(syncMeta).observe(connection, { childList: true, characterData: true });
  mountB10Overlays();
  window.addEventListener("hashchange", show);
  show();
}
function mountB10Shell(routeView, syncLegacyNavCue) {
  if (typeof document === "undefined" || typeof document.querySelector !== "function") return null;
  const B10_NAV = ROUTE_VIEWS.filter((route) => route.view !== "workbench").map((route) => ({
    route: route.view,
    label: route.label,
    hash: route.hash,
    entry: route.entry
  }));
  const navList = el(
    "nav",
    { class: "nav", "aria-label": "DESIGN-LAB 导航" },
    ...navGroupChunks(B10_NAV, (n) => el(
      "button",
      {
        type: "button",
        dataset: { route: n.route },
        "data-hash": n.hash,
        onclick: () => {
          window.location.hash = n.hash;
        }
      },
      el("span", { class: "nav-dot" }),
      el("span", {}, n.label)
    ))
  );
  function setSidebarFold(open) {
    navList.classList.toggle("nav-open", open);
    navFold.setAttribute("aria-expanded", String(open));
    navFold.textContent = open ? "收起次要入口" : "全部功能";
    for (const item of Array.from(navList.querySelectorAll("button[data-route]"))) {
      item.classList.toggle(
        "is-folded",
        !open && NAV_DAILY_VIEWS.indexOf(item.dataset.route ?? "") === -1
      );
    }
    syncNavCue();
  }
  const navFold = el("button", {
    type: "button",
    class: "nav-fold ghost-btn",
    "aria-expanded": "false",
    onclick: () => {
      setSidebarFold(!navList.classList.contains("nav-open"));
    }
  }, "全部功能");
  navList.append(navFold);
  setSidebarFold(false);
  const sidebar = el(
    "aside",
    { class: "sidebar", id: "app-sidebar" },
    el(
      "div",
      { class: "brand" },
      el("div", { class: "brand-mark", "aria-hidden": "true" }),
      el(
        "div",
        {},
        el("h1", {}, "DESIGN-LAB"),
        // 16 characters do not fit a 168px rail on one line; break at the phrase's own seam
        // instead of wherever the browser runs out of room (measured: it split 设计 in two).
        el(
          "small",
          {},
          el("span", { class: "brand-line" }, "专业视觉智能"),
          el("span", { class: "brand-line" }, "与可复用设计能力系统")
        )
      )
    ),
    navList,
    // No identity route exists (/api/health returns status/version/scope only),
    // so the footer cannot name a logged-in workspace owner. 'Alex / Personal
    // Workspace' was leftover B10 mock-up content presented as fact.
    el(
      "div",
      { class: "sidebar-footer" },
      el("div", { class: "avatar", "aria-hidden": "true" }, "D/L"),
      el(
        "div",
        {},
        el("strong", {}, "本地单用户"),
        el("small", { id: "personal-connection" }, "本机服务未连接")
      )
    )
  );
  const modKey = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent) ? "⌘" : "Ctrl";
  const navToggle = el("button", {
    type: "button",
    class: "nav-toggle ghost-btn",
    id: "navToggle",
    "aria-expanded": "false",
    "aria-controls": "app-sidebar"
  }, "导航");
  const setNavOpen = (open) => {
    sidebar.classList.toggle("open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    const mobile = window.matchMedia("(max-width: 840px)").matches;
    sidebar.toggleAttribute("inert", mobile && !open);
    if (open) sidebar.querySelector(".nav button")?.focus();
    else if (mobile && sidebar.contains(document.activeElement)) navToggle.focus();
  };
  navToggle.onclick = () => setNavOpen(!sidebar.classList.contains("open"));
  sidebar.addEventListener("click", (event) => {
    if (event.target.closest("button")) setNavOpen(false);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && sidebar.classList.contains("open")) setNavOpen(false);
  });
  const topbar = el(
    "header",
    { class: "topbar" },
    navToggle,
    el(
      "div",
      { class: "search", id: "openPalette", role: "button", tabindex: "0" },
      `${modKey} K　搜索页面 / 命令 / 资源`
    ),
    // DL-KB-06：右上角的设置入口。它是普通 .ghost-btn，不是 .app-nav-item —— 后者必须与
    // ROUTE_VIEWS 逐条相等（browser_design_layer_e2e.mjs），多一个按钮就多一条假路由。
    el(
      "div",
      { class: "top-actions" },
      el("button", {
        type: "button",
        class: "ghost-btn",
        id: "openSettings",
        "aria-label": "打开系统设置",
        onclick: () => {
          window.location.hash = "#/settings";
        }
      }, "设置"),
      el("button", { type: "button", class: "ghost-btn", id: "openDrawer" }, "工作区")
    )
  );
  const offlineNotice = el(
    "p",
    { class: "muted", id: "b10-offline" },
    "本地浏览模式：未连接本机设计服务（无访问令牌）。页面结构为 B10 1:1 真实渲染，但所有读回值为空占位，不是真实台账。连接服务后本提示消失。"
  );
  const app = el(
    "div",
    { class: "app", id: "b10-app" },
    el("div", { class: "ambient" }),
    el("div", { class: "grid-bg" }),
    sidebar,
    el(
      "main",
      { class: "main" },
      topbar,
      el("section", { class: "content", id: "content", tabindex: "-1" }, offlineNotice, routeView)
    )
  );
  document.body.append(app);
  function syncNavCue() {
    const more = navList.scrollHeight > navList.clientHeight + 1 && navList.scrollTop + navList.clientHeight < navList.scrollHeight - 1;
    navList.classList.toggle("has-scroll-more", more);
  }
  navList.addEventListener("scroll", syncNavCue, { passive: true });
  window.addEventListener("resize", syncNavCue);
  syncNavCue();
  const legacyNav = document.querySelector(".app-nav");
  const legacyChrome = Array.from(document.querySelectorAll("body > header, body > main, body > footer"));
  const sync = (view) => {
    const routed = view !== "workbench";
    app.hidden = !routed;
    offlineNotice.hidden = Boolean(token) || !devMode();
    if (legacyNav) legacyNav.toggleAttribute("hidden", routed);
    for (const node of legacyChrome) node.toggleAttribute("hidden", routed);
    if (!routed) syncLegacyNavCue();
    byId("personal-connection").textContent = connected ? "本机服务已连接" : "本机服务未连接";
    for (const item of Array.from(sidebar.querySelectorAll(".nav button"))) {
      const highlight = view === "project-detail" ? "projects" : view;
      const selected = item.dataset.route === highlight;
      item.classList.toggle("active", selected);
      if (selected && NAV_DAILY_VIEWS.indexOf(highlight) === -1) {
        setSidebarFold(true);
      }
      if (selected) {
        item.setAttribute("aria-current", "page");
        if (typeof item.scrollIntoView === "function") {
          item.scrollIntoView({ block: "nearest", inline: "nearest" });
        }
      } else {
        item.removeAttribute("aria-current");
      }
    }
  };
  return { app, sync };
}
function mountB10Overlays() {
  if (typeof document === "undefined" || typeof document.querySelector !== "function") return;
  const toast = el("div", { class: "toast", role: "status", id: "toast" }, "Ready");
  document.body.append(toast);
  const toastTimer = { t: 0 };
  const showToast = (msg) => {
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toastTimer.t);
    toastTimer.t = window.setTimeout(() => toast.classList.remove("show"), 1900);
  };
  window.__dlToast = showToast;
  const overlay = el("div", { class: "overlay", id: "modal" });
  const modalBox = el(
    "div",
    { class: "modal" },
    el("h3", { id: "modalTitle" }, "确认操作"),
    el("div", { class: "body", id: "modalBody" }, "该操作将写入本地状态。"),
    el(
      "div",
      { class: "actions" },
      el("button", { class: "ghost-btn", type: "button", "data-close-modal": "" }, "取消"),
      el("button", { class: "primary-btn", type: "button", id: "modalConfirm" }, "确认")
    )
  );
  overlay.append(modalBox);
  document.body.append(overlay);
  const cancelBtn = modalBox.querySelector(".actions .ghost-btn");
  const closeModal = () => {
    overlay.classList.remove("open");
  };
  cancelBtn.onclick = closeModal;
  const drawer = el(
    "aside",
    { class: "drawer", id: "drawer", "aria-label": "工作区详情" },
    el("h3", { style: "margin:0 0 8px" }, "工作区 / 前端说明"),
    el(
      "p",
      { class: "muted", style: "margin-top:0" },
      "Command Palette（Ctrl/Cmd + K）、Toast、Modal 与 Drawer 由本页真实驱动；台账视图内容来自服务读回，未连接时显示未读回而不是数据。"
    ),
    el(
      "div",
      { class: "status-stack", style: "margin:14px 0 20px" },
      el("span", { class: "tag info" }, "前端浮层"),
      el("span", { class: "tag info" }, "本机界面偏好"),
      el("span", { class: "tag warn" }, "只读不回写")
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "前端能力（不代表数据读回）"),
      el(
        "ul",
        { class: "list" },
        el("li", { class: "list-item" }, el("span", {}, "本页浮层"), el("span", { class: "tag info" }, "已渲染")),
        el("li", { class: "list-item" }, el("span", {}, "动效"), el("span", { class: "tag info" }, "跟随系统偏好")),
        el("li", { class: "list-item" }, el("span", {}, "命令面板"), el("span", { class: "tag info" }, "Ctrl/Cmd + K"))
      )
    ),
    el("button", { class: "primary-btn", type: "button", id: "closeDrawer", style: "margin-top:18px;width:100%" }, "关闭")
  );
  document.body.append(drawer);
  const openDrawer = () => {
    drawer.classList.add("open");
  };
  const closeDrawer = () => {
    drawer.classList.remove("open");
  };
  drawer.querySelector("#closeDrawer").onclick = closeDrawer;
  const palette = el(
    "div",
    { class: "palette", id: "palette", role: "dialog", "aria-label": "命令面板" },
    el("input", { id: "paletteInput", placeholder: "搜索页面名称…", "aria-label": "搜索页面" })
  );
  const itemsBox = el("div", { id: "paletteItems" });
  palette.append(itemsBox);
  document.body.append(palette);
  const paletteInput = palette.querySelector("input");
  const OBJECT_GROUPS = [
    {
      label: "能力资产",
      path: "/capabilities",
      limit: 8,
      rows: (d) => searchGroupRows("/capabilities", d)
    },
    {
      label: "项目",
      path: "/projects",
      limit: 8,
      rows: (d) => searchGroupRows("/projects", d)
    },
    {
      label: "设计领域",
      path: "/domains",
      limit: 8,
      rows: (d) => searchGroupRows("/domains", d)
    },
    // See `searchGroupRows`: the projection lives outside this scope precisely so a test can
    // reach it. The route answers `{design_systems: …}` (DesignSystemListResponse) and this
    // group used to read `{systems: …}` -- a key no response carries.
    {
      label: "设计系统",
      path: "/design-systems",
      limit: 8,
      rows: (d) => searchGroupRows("/design-systems", d)
    }
  ];
  const searchCache = /* @__PURE__ */ new Map();
  const unreadNote = (path) => el(
    "p",
    { class: "error" },
    `未读回：GET /api${path} 没有给回对象集合，因此这一组既不显示条数，也不说"没有"。`
  );
  const buildGroup = (group) => {
    const body = el("div", { class: "palette-group-body" });
    const box = el(
      "div",
      { class: "palette-group", "data-group": group.label },
      el("p", { class: "palette-group-title" }, group.label),
      body
    );
    const cached = searchCache.get(group.path);
    if (cached === void 0) {
      body.replaceChildren(el("p", { class: "view-hint" }, `尚未读取：打开面板后才向 GET /api${group.path} 取这一组的对象。`));
    } else if (cached === "unread") {
      body.replaceChildren(unreadNote(group.path));
    } else {
      renderGroupRows(body, cached, group.limit);
    }
    return box;
  };
  const renderGroupRows = (body, rows, limit, needle = "") => {
    if (!rows.length) {
      body.replaceChildren(el("p", { class: "view-hint" }, needle ? `这一组没有符合“${needle}”的对象：过滤在整组读回上做，不是只查已画出的前几条。` : "这一组当前读回 0 个对象。"));
      return;
    }
    const shown = rows.slice(0, limit);
    body.replaceChildren(
      ...shown.map((r) => el("button", {
        type: "button",
        class: "item",
        dataset: { go: r.go },
        onclick: () => {
          window.location.hash = r.go;
          closePalette();
        }
      }, el("span", {}, r.name), el("small", {}, `${r.kind}`))),
      rows.length > shown.length ? el(
        "p",
        { class: "palette-more" },
        `还有 ${rows.length - shown.length} 个对象未列出：面板只画前 ${shown.length} 个，输入更具体的关键词可缩小范围。`
      ) : ""
    );
  };
  const objectsBox = el(
    "div",
    { id: "paletteObjects" },
    el(
      "p",
      { class: "palette-note" },
      '下面按对象类型分组列出可去到的真实对象。范围只限当前令牌已能读到的路由：本服务没有对象级读权限模型，所以这里不说"已按权限过滤"。'
    ),
    ...OBJECT_GROUPS.map((group) => buildGroup(group))
  );
  itemsBox.append(objectsBox);
  const readFailedNote = (path, err) => {
    const why = err instanceof Error ? err.message : String(err);
    return el(
      "p",
      { class: "error" },
      `读取失败：GET /api${path} 本次没有读回（${why}）。这一组既不显示条数，也不说"没有"——失败与空集合是两件事。`,
      el("button", {
        type: "button",
        class: "secondary",
        onclick: () => {
          void loadSearchObjects();
        }
      }, "重试这一组")
    );
  };
  let objectsLoad = "idle";
  const loadSearchObjects = async () => {
    if (objectsLoad !== "idle") return;
    objectsLoad = "loading";
    let failed = 0;
    for (const group of OBJECT_GROUPS) {
      if (searchCache.has(group.path)) continue;
      const holder = itemsBox.querySelector(`[data-group="${group.label}"]`);
      const body = holder?.querySelector(".palette-group-body") ?? null;
      try {
        const data = await apiOrEmpty(group.path, {});
        const unread = shapeNotice(data) || disconnectedNotice(data);
        const rows = unread ? "unread" : group.rows(data);
        searchCache.set(group.path, rows);
        if (!body) continue;
        if (rows === "unread") {
          body.replaceChildren(unreadNote(group.path));
        } else {
          renderGroupRows(body, rows, group.limit);
        }
      } catch (err) {
        failed += 1;
        if (body) body.replaceChildren(readFailedNote(group.path, err));
      }
    }
    objectsLoad = failed ? "idle" : "done";
  };
  const cmds = ROUTE_VIEWS.filter((r) => r.hash !== "").map((r) => ({ go: r.hash, label: r.label }));
  const routeGroup = el("div", { class: "palette-group-body" });
  itemsBox.append(el(
    "div",
    { class: "palette-group", "data-group": "页面" },
    el("p", { class: "palette-group-title" }, "页面"),
    routeGroup
  ));
  for (const c2 of cmds) {
    routeGroup.append(el("button", {
      type: "button",
      class: "item",
      dataset: { go: c2.go },
      onclick: () => {
        window.location.hash = c2.go;
        closePalette();
      }
    }, el("span", {}, c2.label), el("small", {}, "打开")));
  }
  let paletteInvoker = null;
  const openPalette = () => {
    paletteInvoker = document.activeElement;
    palette.classList.add("open");
    paletteInput.focus();
    paletteInput.select();
    applyPaletteFilter(paletteInput.value.trim().toLowerCase());
    void loadSearchObjects();
  };
  const closePalette = () => {
    palette.classList.remove("open");
    paletteInput.value = "";
    itemsBox.querySelectorAll(".item").forEach((i) => {
      i.style.display = "";
    });
    itemsBox.querySelectorAll(".palette-group").forEach((g) => {
      g.hidden = false;
    });
    if (document.activeElement === document.body && paletteInvoker && document.contains(paletteInvoker)) {
      paletteInvoker.focus();
    }
    paletteInvoker = null;
  };
  const applyPaletteFilter = (q) => {
    for (const group of OBJECT_GROUPS) {
      const holder = itemsBox.querySelector(`[data-group="${group.label}"]`);
      const body = holder?.querySelector(".palette-group-body") ?? null;
      if (!holder || !body) continue;
      const cached = searchCache.get(group.path);
      if (cached === void 0 || cached === "unread") continue;
      const hits2 = q ? cached.filter((r) => `${r.name} ${r.kind}`.toLowerCase().includes(q)) : cached;
      holder.hidden = hits2.length === 0;
      renderGroupRows(body, hits2, group.limit, q);
    }
    const routeGroup2 = itemsBox.querySelector('[data-group="页面"]');
    if (!routeGroup2) return;
    let hits = 0;
    for (const item of Array.from(routeGroup2.querySelectorAll(".item"))) {
      const match = !q || (item.textContent || "").toLowerCase().includes(q);
      item.style.display = match ? "flex" : "none";
      if (match) hits += 1;
    }
    routeGroup2.hidden = hits === 0;
  };
  paletteInput.addEventListener("input", () => {
    applyPaletteFilter(paletteInput.value.trim().toLowerCase());
  });
  window.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (palette.classList.contains("open")) closePalette();
      else openPalette();
    }
    if (e.key === "Escape") {
      closePalette();
      closeDrawer();
      closeModal();
    }
  });
  wireB10Topbar(openPalette, openDrawer);
}
function wireB10Topbar(openPalette, openDrawer) {
  const search = document.getElementById("openPalette");
  if (search) {
    search.onclick = openPalette;
    search.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openPalette();
      }
    };
  }
  const drawerBtn = document.getElementById("openDrawer");
  if (drawerBtn) drawerBtn.onclick = () => {
    openDrawer();
  };
}
const PALETTES = [
  {
    id: "design-lab",
    label: "DESIGN-LAB 色板",
    schemes: ["dark"],
    missingScheme: "这套色板没有声明过浅色值，不自造一套。"
  },
  { id: "ui2026", label: "UI-20261009 基线", schemes: ["dark", "light"], missingScheme: "" },
  // 20261023 包的 STITCH 提示词逐字给了六个值（强调 #356B92、正文 #17212B、次级 #566472、
  // 背景 #F4F6F8、内容 #FFFFFF、边界 #D8DFE5）。它只声明了珍珠白这一侧，
  // 所以这套色板只有一档：暗色值不在包里，不自造一套冒充"一比一"。
  {
    id: "stitch",
    label: "STITCH 珍珠白（20261023 包）",
    schemes: ["light"],
    missingScheme: "这份基线只声明了浅色一侧的值，暗色不自造。"
  }
];
function paletteSpec(id) {
  return PALETTES.find((p) => p.id === id) ?? PALETTES[0];
}
function urlParam(name) {
  try {
    const search = window.location.search;
    if (typeof search !== "string" || search.length === 0) return null;
    for (const pair of search.replace(/^\?/, "").split("&")) {
      const eq = pair.indexOf("=");
      if (eq <= 0) continue;
      if (pair.slice(0, eq) === name) return decodeURIComponent(pair.slice(eq + 1));
    }
  } catch {
  }
  return null;
}
function readThemeChoice() {
  const applied = typeof document !== "undefined" && document.documentElement && typeof document.documentElement.getAttribute === "function" ? {
    palette: document.documentElement.getAttribute("data-palette"),
    scheme: document.documentElement.getAttribute("data-scheme")
  } : { palette: null, scheme: null };
  const knownPalette = (value) => PALETTES.some((entry) => entry.id === value) ? value : null;
  const palette = knownPalette(applied.palette) ?? knownPalette(urlParam("palette")) ?? PALETTES[0].id;
  const spec = paletteSpec(palette);
  const fromUrlScheme = urlParam("scheme");
  const wanted = spec.schemes.includes(applied.scheme) ? applied.scheme : spec.schemes.includes(fromUrlScheme) ? fromUrlScheme : spec.schemes[0];
  return { palette, scheme: wanted };
}
function writeUrlParam(name, value) {
  const href = window.location.href;
  if (typeof href !== "string") return;
  let target;
  try {
    const url = new URL(href);
    url.searchParams.set(name, value);
    target = url.toString();
  } catch {
    return;
  }
  const history = window.history;
  if (history && typeof history.replaceState === "function") {
    history.replaceState(history.state ?? null, "", target);
    return;
  }
  window.location.href = target;
}
function applyTheme(choice = readThemeChoice()) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (!root || typeof root.setAttribute !== "function") return;
  root.setAttribute("data-palette", choice.palette);
  if (choice.scheme === "dark") root.removeAttribute("data-scheme");
  else root.setAttribute("data-scheme", choice.scheme);
}
function cyclePalette(current) {
  const index = PALETTES.findIndex((p) => p.id === current);
  return PALETTES[(index + 1) % PALETTES.length].id;
}
function themeControlNodes() {
  const choice = readThemeChoice();
  const spec = paletteSpec(choice.palette);
  const nodes = [
    el("button", {
      type: "button",
      class: "theme-toggle",
      dataset: { themeAction: "palette" },
      "aria-label": "配色主题",
      onclick: () => {
        const now = readThemeChoice();
        const palette = cyclePalette(now.palette);
        const spec2 = paletteSpec(palette);
        const scheme = spec2.schemes.includes(now.scheme) ? now.scheme : spec2.schemes[0];
        const next = { palette, scheme };
        applyTheme(next);
        writeUrlParam("palette", next.palette);
        writeUrlParam("scheme", next.scheme);
        refreshThemeControls();
      }
    }, spec.label)
  ];
  if (spec.schemes.length > 1) {
    nodes.push(el("button", {
      type: "button",
      class: "theme-toggle",
      dataset: { themeAction: "scheme" },
      "aria-label": "明暗",
      onclick: () => {
        const now = readThemeChoice();
        const next = {
          ...now,
          scheme: now.scheme === "dark" ? "light" : "dark"
        };
        applyTheme(next);
        writeUrlParam("scheme", next.scheme);
        refreshThemeControls();
      }
    }, choice.scheme === "light" ? "浅色" : "深色"));
  }
  nodes.push(el(
    "span",
    { class: "theme-toggle-note" },
    spec.schemes.length > 1 ? "" : spec.missingScheme
  ));
  return nodes;
}
function buildThemeControls() {
  return el("div", { class: "theme-toggle-group uif-row" }, ...themeControlNodes());
}
function refreshThemeControls() {
  if (typeof document === "undefined" || typeof document.querySelectorAll !== "function") return;
  for (const group of Array.from(document.querySelectorAll(".theme-toggle-group"))) {
    group.replaceChildren(...themeControlNodes());
  }
}
const STATE_SPECS = [
  {
    kind: "loading",
    title: "正在读回",
    weight: "neutral",
    producer: "renderRoute 进入视图时先写 .view-loading，读回没有到达前界面不留白。",
    next: "等本次读回；长时间不动就刷新重新发起，而不是复用上一屏的数据。"
  },
  {
    kind: "empty",
    title: "尚无记录",
    weight: "neutral",
    producer: 'emptyWording() 只在服务真的答了"这里没有"时给的说法。',
    next: "按页面提示创建第一条记录；空集合不等于失败，也不等于功能不可用。"
  },
  {
    kind: "unread",
    title: "未读回",
    weight: "neutral",
    producer: "shapeNotice() / disconnectedNotice()：服务答了但缺字段，或压根没连接。",
    next: '连接本机设计服务，或检查响应缺了哪个字段；缺字段不会被渲染成"尚无"。'
  },
  {
    kind: "unknown",
    title: "未判定",
    weight: "neutral",
    producer: "资格轴的 null 值。capabilityCard 用 .tag.neutral 显示，不借用判定的重量。",
    next: "补齐资格证据后才可能变成合格或不合格；null 既不是通过也不是失败。"
  },
  {
    kind: "offline",
    title: "未连接",
    weight: "neutral",
    producer: "dev/offline seam：apiOrEmpty() 在没有令牌时给出诚实空载荷，并打标记。",
    next: "用官方入口启动本机服务，或在高级连接里粘贴临时令牌。"
  },
  {
    kind: "forbidden",
    title: "无权进行",
    weight: "bad",
    producer: "服务端拒绝（权利门 / Human Gate 未过）时返回的结论，界面不自行降级。",
    next: "查看权利与人工门的说明；需要真人结论的动作不能由 Agent 代签。"
  },
  {
    kind: "error",
    title: "读取失败",
    weight: "bad",
    producer: "视图级 catch 会把这一面的读回失败与原因留在屏上，不吞成空白。",
    next: "刷新重读；持续失败时按给出的原因排查服务，而不是反复点击。"
  },
  {
    kind: "timeout",
    title: "本次请求超时",
    weight: "bad",
    producer: "宿主/任务读回路径：超时不等于失败，也不等于成功，先对账。",
    next: "先核对已经发生了什么再决定是否重发，避免对同一文档重复写入。"
  },
  {
    kind: "conflict",
    title: "版本冲突",
    weight: "bad",
    producer: "修订已取代的版本时服务端返回 STALE_REVISION，旧版本字节不被改写。",
    next: "在最新版本上重做这次修改；旧版本保留为历史。"
  },
  {
    kind: "cancelled",
    title: "取消已请求",
    weight: "neutral",
    producer: "原生取消没有 ack 事件：requested 与 acknowledged 分开，界面只说请求过。",
    next: '读回任务状态确认是否真的停下；"请求取消"不等于"已取消"。'
  },
  {
    kind: "queued",
    title: "已排队",
    weight: "neutral",
    producer: "计划提交后只排队不启动，启动是显式动作。",
    next: "在任务行上显式启动；提交本身不会碰宿主。"
  }
];
function stateBlock(spec) {
  return el(
    "article",
    { class: "uif-state", dataset: { stateKind: spec.kind } },
    el(
      "div",
      { class: "uif-state-head" },
      el("span", { class: "tag " + spec.weight }, spec.title)
    ),
    el("p", { class: "uif-state-reason" }, spec.producer),
    el("p", { class: "uif-state-next" }, el("strong", {}, "下一步 "), spec.next)
  );
}
function renderUiStates(target) {
  const filter = el("input", {
    class: "input",
    type: "search",
    id: "uif-state-filter",
    placeholder: "按状态名 / 来源 / 下一步过滤",
    "aria-label": "状态过滤"
  });
  const shown = el("span", { class: "muted" }, "");
  const grid = el("div", { class: "uif-states" });
  const render = () => {
    const needle = (filter.value || "").trim().toLowerCase();
    const keep = needle ? STATE_SPECS.filter((s) => `${s.title} ${s.kind} ${s.producer} ${s.next}`.toLowerCase().includes(needle)) : Array.from(STATE_SPECS);
    grid.replaceChildren(...keep.map((s) => stateBlock(s)));
    shown.textContent = keep.length === STATE_SPECS.length ? `共 ${STATE_SPECS.length} 个状态` : `${keep.length} / ${STATE_SPECS.length} 个状态，其余被过滤`;
  };
  filter.oninput = render;
  render();
  target.replaceChildren(
    el("h2", {}, viewLabel("ui-states")),
    el(
      "p",
      { class: "muted" },
      "这是产品自己的状态面：每一块写的都是这个状态由哪段代码产生、界面上必须给什么下一步，不是演示记录。没有读回过的集合一律说未读回，不说尚无。"
    ),
    el("div", { class: "uif-row" }, filter, shown),
    grid
  );
}
function tokenSwatch(name) {
  return el(
    "div",
    { class: "uif-swatch" },
    el("i", { style: `background:var(${name});` }),
    el("span", { class: "mono" }, name)
  );
}
function sampleInput() {
  return el("input", {
    class: "input",
    type: "search",
    placeholder: "例如：秋季品牌视觉",
    "aria-label": "组件样张输入框"
  });
}
function renderUiComponents(target) {
  const list = el(
    "ul",
    { class: "list" },
    el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "列表成员"),
        el("small", {}, "ul.list + li.list-item 是仓库既有约定，新页面直接用它；行卡片走 .row-card，两种语义不混。")
      )
    ),
    el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "空态有两种说法"),
        el("small", {}, 'emptyLi() 在服务真答"没有"时说尚无，在未连接或缺字段时说未读回。')
      )
    )
  );
  const table = el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      { class: "table" },
      el("thead", {}, el(
        "tr",
        {},
        el("th", {}, "规则"),
        el("th", {}, "为什么这样定")
      )),
      el(
        "tbody",
        {},
        el(
          "tr",
          {},
          el("td", {}, "状态权重"),
          el("td", {}, "非判定（未判定 / 未读回 / 计划中）用 .tag.neutral，不借用判定的饱和重量。")
        ),
        el(
          "tr",
          {},
          el("td", {}, "英文状态词"),
          el(
            "td",
            {},
            el("span", {}, "服务自己的词汇标记为 "),
            en("READY"),
            el("span", {}, "，不翻译成中文，避免产生第二套词汇。")
          )
        ),
        el(
          "tr",
          {},
          el("td", {}, "长中文文案"),
          el("td", {}, "控件与卡片 overflow-wrap:anywhere，窄窗口靠重排而不是裁切。")
        )
      )
    )
  );
  const echo = el(
    "p",
    { class: "uif-spec-note", role: "status", "aria-live": "polite" },
    "样张回显：还没有点击。"
  );
  const sample = (label, cls) => el("button", {
    type: "button",
    class: cls,
    onclick: () => {
      echo.textContent = `样张回显：已点击「${label}」，只在页面内回显，不触发产品动作。`;
    }
  }, label);
  target.replaceChildren(
    el("h2", {}, viewLabel("ui-components")),
    el(
      "p",
      { class: "muted" },
      "这里的样张按钮只做一件事：在本页回显被点击。产品动作由各自视图接线；未接线的动作在各自主页面上以禁用加原因出现，不在这个页面上假装可用。"
    ),
    el(
      "div",
      { class: "uif-spec" },
      el(
        "section",
        { class: "uif-spec-block" },
        el("h3", {}, "配色与明暗"),
        // 开关只有一份，在左侧导航底部（路由视图）或扁平导航里（遗留工作台）。这里
        // 再放一份会在同一屏出现两个控件，且两处文案会随挂载时刻不同而不一致——
        // 2026-10-09 读渲染图时就是这样被抓出来的。
        el(
          "p",
          { class: "uif-spec-note" },
          "色板与明暗开关在左侧导航底部，全站一份。下面六块是当前主题算出来的语义令牌：色块直接刷 var() 的值，所以它们显示的就是界面真正在用的颜色，不是抄来的第二份色表。"
        ),
        el(
          "p",
          { class: "uif-spec-note" },
          "UI-20261009 基线不只换颜色：在包自己的断点上它还换导航轨宽与内容沟槽（≥1200 轨 256/槽 30，768–1199 轨 216/槽 22，窄于此沿用既有折叠布局，手机端已按 owner 2026-10-19 授权移出范围）。DESIGN-LAB 默认主题一字节不变，仍是轨 168/让位 192。包里的排印尺度只有 body/small/h3/micro 已接到界面上，h1/h2 对应哪个标题角色还没定。"
        ),
        el(
          "div",
          { class: "uif-row" },
          tokenSwatch("--color-bg"),
          tokenSwatch("--color-surface"),
          tokenSwatch("--color-surface-2"),
          tokenSwatch("--color-border"),
          tokenSwatch("--color-text"),
          tokenSwatch("--color-muted")
        ),
        el(
          "p",
          { class: "uif-spec-note" },
          "品牌色族与 --border-strong 不随色板切换：它们是被实测修正过的地板值。"
        )
      ),
      el(
        "section",
        { class: "uif-spec-block" },
        el("h3", {}, "状态药丸"),
        el(
          "div",
          { class: "uif-row" },
          el("span", { class: "tag ok" }, "合格"),
          el("span", { class: "tag warn" }, "警告"),
          el("span", { class: "tag bad" }, "不合格"),
          el("span", { class: "tag info" }, "信息"),
          el("span", { class: "tag neutral" }, "未判定")
        )
      ),
      el(
        "section",
        { class: "uif-spec-block" },
        el("h3", {}, "按钮与输入"),
        el(
          "div",
          { class: "uif-row" },
          sample("主操作样张", "primary-btn"),
          sample("次操作样张", "secondary"),
          sample("危险操作样张", "danger-btn")
        ),
        echo,
        el("label", {}, "输入框样张", sampleInput()),
        el(
          "p",
          { class: "uif-spec-note" },
          "焦点环由全局 :focus-visible 规则给出，主题切换不重定义它；表单边界用 --border-strong（3:1 地板值），装饰边框用 --line。"
        )
      ),
      el("section", { class: "uif-spec-block" }, el("h3", {}, "列表"), list),
      el("section", { class: "uif-spec-block" }, el("h3", {}, "表格"), table),
      el(
        "section",
        { class: "uif-spec-block" },
        el("h3", {}, "状态面"),
        el("div", { class: "uif-states" }, ...STATE_SPECS.slice(0, 3).map(stateBlock))
      )
    )
  );
}
function mountThemeControls() {
  if (typeof document === "undefined" || typeof document.querySelectorAll !== "function" || typeof document.querySelector !== "function") return;
  const sidebar = document.querySelector("#app-sidebar");
  const flatNav = document.querySelector(".app-nav");
  if (sidebar) sidebar.append(buildThemeControls());
  if (flatNav) flatNav.append(buildThemeControls());
  applyTheme();
}
function navGroupChunks(items, make) {
  const out = [];
  let current = null;
  for (const item of items) {
    if (item.entry !== current) {
      current = item.entry;
      out.push(el("span", { class: "nav-group" }, item.entry));
    }
    out.push(make(item));
  }
  return out;
}
const DELIVERY_LEVELS = [
  { name: "分析与方向", wired: "已接线", note: "#/analysis 追加方向修订，不启动宿主、不改已交付版本。" },
  { name: "目标生成包", wired: "只排队", note: "POST /native-plans 返回 202；启动仍是任务面上的显式动作。" },
  { name: "原生可编辑工程", wired: "未取证", note: "宿主执行与关闭重开读回还没有 E2/E3 证据，这一档当前不是可交付。" },
  { name: "最终媒体（渲染/导出）", wired: "未接线", note: "仓库内没有渲染或导出路由，界面不假装这条路存在。" }
];
function intakeSelectedDeliveryLevels() {
  if (typeof document === "undefined" || typeof document.querySelectorAll !== "function") return [];
  return Array.from(document.querySelectorAll('input[name="intake-delivery-level"]')).filter((box) => box.checked).map((box) => box.value);
}
function composeConstraints(fields, freeText) {
  const parts = [];
  if (freeText.trim()) parts.push(freeText.trim());
  if (fields.exactText.value.trim()) parts.push(`精确文案：${fields.exactText.value.trim()}`);
  if (fields.lockRatio.checked) parts.push("锁定比例");
  if (fields.lockPosition.checked) parts.push("锁定位置");
  if (fields.editScope.value.trim()) parts.push(`编辑范围：${fields.editScope.value.trim()}`);
  const levels = intakeSelectedDeliveryLevels();
  if (levels.length) parts.push(`交付目标：${levels.join("、")}`);
  if (fields.toolFormat.value.trim()) parts.push(`工具与规格：${fields.toolFormat.value.trim()}`);
  return parts.join("；");
}
function intakeSelectedReferences() {
  if (typeof document === "undefined" || typeof document.querySelectorAll !== "function") return [];
  return Array.from(document.querySelectorAll('input[name="intake-reference-asset"]')).filter((box) => box.checked).map((box) => box.value);
}
function intakeForm(projectId) {
  const title = el("input", {
    class: "input",
    type: "text",
    maxlength: "160",
    id: "intake-title",
    placeholder: "例如：秋季品牌视觉"
  });
  const goals = el("input", {
    class: "input",
    type: "text",
    maxlength: "400",
    id: "intake-goals",
    placeholder: "现代, 温暖, 克制"
  });
  const freeConstraints = el("input", {
    class: "input",
    type: "text",
    maxlength: "400",
    id: "intake-constraints",
    placeholder: "可选：其它约束"
  });
  const fields = {
    exactText: el("input", {
      class: "input",
      type: "text",
      maxlength: "400",
      id: "intake-exact-text",
      placeholder: "必须逐字出现的文案"
    }),
    lockRatio: el("input", { type: "checkbox", id: "intake-lock-ratio" }),
    lockPosition: el("input", { type: "checkbox", id: "intake-lock-position" }),
    editScope: el("input", {
      class: "input",
      type: "text",
      maxlength: "200",
      id: "intake-edit-scope",
      placeholder: "例如：仅标题与副标题"
    }),
    toolFormat: el("input", {
      class: "input",
      type: "text",
      maxlength: "300",
      id: "intake-tool-format",
      placeholder: "例如：Illustrator · AI + PDF · 1080×1920 · 时长不适用"
    })
  };
  const outcome = el("div", { class: "intake-outcome" });
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "intake-submit" },
    "保存为简报"
  );
  const status = el(
    "p",
    { class: "view-hint", role: "status", "aria-live": "polite" },
    '提交即写入本机服务；这一步只固定"为什么设计"，不做制作，也不给质量结论。'
  );
  const readback = async () => {
    outcome.replaceChildren(el("p", { class: "view-loading" }, "正在读回简报…"));
    let data;
    try {
      data = await api(`/projects/${projectId}/briefs`);
    } catch (error) {
      outcome.replaceChildren(stateBlock({
        kind: "error",
        title: "读取失败",
        weight: "bad",
        producer: `GET /api/projects/{id}/briefs 被拒：${errMsg(error)}`,
        next: "刷新重读；持续失败时按给出的原因排查本机服务，而不是重复提交。"
      }));
      return;
    }
    const briefs = data.briefs;
    if (!briefs.length) {
      outcome.replaceChildren(el(
        "p",
        { class: "view-hint" },
        "本项目还没有简报。上面提交成功后这里会列出服务端返回的版本。"
      ));
      return;
    }
    outcome.replaceChildren(
      el("p", { class: "view-hint" }, `已读回 ${briefs.length} 份简报（版本与取代关系来自服务端）`),
      el("ul", { class: "list" }, ...briefs.map((b) => el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `${b.title} · v${b.version}`),
          el("small", {}, `目标 ${b.goals.join("、") || "未列"}；约束 ${b.constraints ?? "无"}；引用参考 ${b.reference_asset_ids.length} 个` + (b.superseded_by ? "；已被更新版本取代" : " · 现行版本"))
        )
      )))
    );
  };
  submit.onclick = () => {
    submit.disabled = true;
    status.textContent = "正在提交…";
    void (async () => {
      try {
        await createBrief({
          owner: projectId,
          title: title.value,
          goals: (goals.value || "").split(",").map((g) => g.trim()).filter(Boolean),
          constraints: composeConstraints(fields, freeConstraints.value),
          references: intakeSelectedReferences()
        });
        status.textContent = "简报已持久化；下面是服务端读回的版本。";
        await readback();
      } catch (error) {
        status.textContent = "";
        outcome.replaceChildren(stateBlock({
          kind: "forbidden",
          title: "未写入",
          weight: "bad",
          producer: `POST /api/projects/{id}/briefs 返回：${errMsg(error)}`,
          next: "按上面的原因修正后重试；相同内容重试会复用同一幂等键，不会重复建简报。"
        }));
      } finally {
        submit.disabled = false;
      }
    })();
  };
  return el(
    "div",
    { class: "intake-grid" },
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "需求与目标"),
      el("label", {}, "简报标题", title),
      el("label", {}, "目标（逗号分隔）", goals),
      el("label", {}, "其它约束", freeConstraints),
      el(
        "p",
        { class: "uif-spec-note" },
        "简报合同记录 title / goals / constraints / reference_asset_ids 四项；下面的输入属性会编排进 constraints 文本，不是四个独立字段。"
      ),
      el(
        "div",
        { class: "intake-hard" },
        el("label", {}, "精确文案（必须逐字出现）", fields.exactText),
        el("label", { class: "intake-check" }, fields.lockRatio, "锁定比例"),
        el("label", { class: "intake-check" }, fields.lockPosition, "锁定位置"),
        el("label", {}, "编辑范围", fields.editScope)
      ),
      el("div", { class: "uif-row" }, submit),
      status,
      el(
        "div",
        { class: "uif-row" },
        // The blanket disable here went stale the moment DL-UI-U05 landed the composer on
        // #/plan: 「不该看起来可用」 was justified by "目标生成包还没接通", which is no longer
        // true. What is still NOT wired is carrying THIS brief's fields into the package
        // (DL-FINAL-T09/T10), so the button now navigates and the note says precisely which
        // half is missing instead of hiding the whole step.
        el("button", {
          type: "button",
          class: "secondary",
          id: "intake-to-plan",
          onclick: () => {
            window.location.hash = "#/plan";
          }
        }, "到目标生成包继续"),
        el(
          "span",
          { class: "theme-toggle-note" },
          "这一步只是打开编排面：简报的标题 / 目标 / 约束留在服务端记录里，不会自动变成目标包字段，宿主与底图要重新选。把简报内容落成包结构属 DL-FINAL-T09 / DL-FINAL-T10，尚未接线，所以这里不声称已经接上。"
        )
      )
    ),
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "参考素材与职责"),
      referencePickerForProject(projectId),
      el(
        "p",
        { class: "uif-spec-note" },
        "勾选的素材作为 reference_asset_ids 随简报持久化。参考职责（结构 / 风格 / 内容来源）合同里没有独立字段，因此不假装持久化；一张风格参考不会自动成为内容来源或授权来源。"
      ),
      el(
        "div",
        { class: "uif-row" },
        el("button", { type: "button", class: "secondary", disabled: "" }, "上传音频 / 视频 / 3D 参考"),
        el(
          "span",
          { class: "theme-toggle-note" },
          "禁用：本机导入路由只接受不超过 32 MiB 的 PNG/JPEG 字节，其它模态未实现。"
        )
      ),
      el("h3", {}, "交付目标"),
      deliveryTargetPicker(fields.toolFormat),
      el("h3", {}, "能力与知识"),
      knowledgeContextForProject(projectId),
      el("h3", {}, "已提交的简报"),
      outcome
    )
  );
}
function deliveryTargetPicker(toolFormat) {
  return el(
    "div",
    { class: "intake-delivery" },
    ...DELIVERY_LEVELS.map((level) => el(
      "div",
      { class: "intake-delivery-row" },
      el(
        "label",
        { class: "intake-check" },
        el("input", { type: "checkbox", name: "intake-delivery-level", value: level.name }),
        el("span", {}, level.name),
        el("span", { class: "tag neutral" }, level.wired)
      ),
      el("p", { class: "uif-spec-note" }, level.note)
    )),
    el("label", {}, "工具与格式 / 尺寸 / 时长（可选）", toolFormat),
    el(
      "p",
      { class: "uif-spec-note" },
      "交付范围与规格会一并编排进 constraints 文本：简报合同没有为它们新造字段，所以这里持久化的是一句话，不是四个独立属性。未取证的档位可以勾选成需求，但它不会因此变成已具备的交付能力。"
    )
  );
}
function knowledgeContextForProject(projectId) {
  const host = el(
    "div",
    { class: "intake-knowledge" },
    el("p", { class: "view-loading" }, "正在读回本项目的方向、绑定与简报版本…")
  );
  void (async () => {
    let data;
    try {
      data = await api(`/projects/${projectId}/design-layer`);
    } catch (error) {
      host.replaceChildren(stateBlock({
        kind: "error",
        title: "能力上下文未读回",
        weight: "bad",
        producer: `GET /api/projects/{id}/design-layer 返回：${errMsg(error)}`,
        next: '刷新重读；未读回时本页不会把"没有方向"画成事实。'
      }));
      return;
    }
    const layer = data.design_layer;
    const chosen = layer.chosen_direction;
    const binding = layer.active_binding;
    host.replaceChildren(
      el(
        "div",
        { class: "intake-knowledge-row" },
        el("span", { class: "muted" }, "现行方向 revision"),
        el("span", {}, chosen ? `${chosen.title} · v${chosen.version}` : "未选定方向")
      ),
      el(
        "div",
        { class: "intake-knowledge-row" },
        el("span", { class: "muted" }, "绑定设计系统"),
        el("span", {}, binding ? `${binding.design_system_name} · 绑定 ${binding.direction_id}` : "无活动绑定")
      ),
      el(
        "div",
        { class: "intake-knowledge-row" },
        el("span", { class: "muted" }, "简报版本链"),
        el("span", {}, layer.briefs.length ? layer.briefs.map((b) => `v${b.version}`).join(" → ") : "尚无简报")
      ),
      el(
        "div",
        { class: "intake-knowledge-row" },
        el("span", { class: "muted" }, "获准知识 revision"),
        el("span", { class: "tag neutral" }, "未接线"),
        el(
          "span",
          { class: "theme-toggle-note" },
          "长期知识真值归 ArcheAxis，本项目只经 rights 检查与人工批准输出候选；这里不复制一份知识台账，也不声称已取回获准 revision。"
        )
      ),
      el(
        "div",
        { class: "intake-knowledge-row" },
        el("span", { class: "muted" }, "教学需要"),
        el("button", { type: "button", class: "secondary", disabled: "" }, "按教学场景导入"),
        el(
          "span",
          { class: "theme-toggle-note" },
          "禁用：教学表达是场景筛选与需求导入，属 DL-UI-U06/U07，接通前不显示为可用。"
        )
      )
    );
  })();
  return host;
}
function referencePickerForProject(projectId) {
  const host = el(
    "div",
    { class: "intake-references" },
    el("p", { class: "view-loading" }, "正在读回本项目素材…")
  );
  void (async () => {
    try {
      const data = await api(`/projects/${projectId}/assets`);
      if (!data.assets.length) {
        host.replaceChildren(el(
          "p",
          { class: "view-hint" },
          "本项目还没有已导入素材。导入后勾选，简报会引用它们。"
        ));
        return;
      }
      host.replaceChildren(el("ul", { class: "list" }, ...data.assets.map((asset) => el(
        "li",
        { class: "list-item" },
        el(
          "label",
          { class: "intake-check" },
          el("input", { type: "checkbox", name: "intake-reference-asset", value: asset.id }),
          el("span", {}, `${asset.media_type} · ${asset.width}×${asset.height} · ${asset.id.slice(-8)} · 权利 ${asset.rights} · 版本 ${asset.version_id.slice(0, 12)}…；导入与读回不等于获得素材使用权。`)
        )
      ))));
    } catch (error) {
      host.replaceChildren(stateBlock({
        kind: "error",
        title: "素材未读回",
        weight: "bad",
        producer: `GET /api/projects/{id}/assets 返回：${errMsg(error)}`,
        next: '刷新重读；未读回时本页不会把空列表画成"本项目没有素材"。'
      }));
    }
  })();
  return host;
}
async function renderIntake(target) {
  await projectPickerPanel(
    target,
    viewLabel("intake"),
    async (projectId) => intakeForm(projectId),
    el(
      "p",
      { class: "view-hint" },
      "简单任务不必走完整项目流程：在这里描述目标、勾选参考、给出强约束，就落成一份可追踪的简报。原始 RIR / JSON 属于高级开发者面，不让普通用户手填。"
    ),
    "选择项目后填写；本页会写入本机服务（保存简报），不会碰宿主也不改已有版本。"
  );
}
const TRIAGE_LABEL = {
  in_flight: "进行中",
  needs_human: "待人工核对",
  failed: "未成功",
  done: "已有回执",
  unknown: "未知状态"
};
function taskRecordRow(projectId, task) {
  const triage = taskTriage(task.attempt.state);
  const events = el(
    "div",
    { class: "record-events", id: `record-events-${task.job_id}` },
    el("p", { class: "view-hint" }, "最近确认点未读回：展开后才向 …/tasks/{job}/events 取，列表本身不替每条任务发请求。")
  );
  const detail = el(
    "details",
    { class: "record-detail" },
    el("summary", {}, "最近确认点与尝试"),
    events
  );
  detail.ontoggle = () => {
    if (!detail.open || detail.dataset.loading === "1") return;
    detail.dataset.loading = "1";
    void loadTaskEvents(projectId, task.job_id, events);
  };
  return el(
    "li",
    { class: "list-item record-row" },
    el(
      "div",
      { class: "record-head" },
      el("strong", { class: "mono" }, task.job_id),
      el(
        "span",
        { class: "tag " + (triage === "done" ? "ok" : triage === "failed" ? "bad" : triage === "unknown" ? "neutral" : "warn") },
        en(task.attempt.state)
      ),
      el("span", { class: "tag neutral" }, TRIAGE_LABEL[triage])
    ),
    el(
      "div",
      { class: "record-facts" },
      el("span", { class: "muted" }, `kind ${task.kind}`),
      el("span", { class: "muted" }, `第 ${task.attempt.attempt_no} 次尝试 · ${task.attempt.attempt_id}`),
      el("span", { class: "muted" }, task.cancel.requested ? `取消：已请求${task.cancel.acknowledged ? "且宿主已确认" : "，但宿主未确认（原生取消没有 ack 事件）"}` : "取消：未请求"),
      el("span", { class: "tag neutral" }, "领域：无该字段")
    ),
    detail,
    el(
      "div",
      { class: "uif-row" },
      ...task.kind.endsWith("-native") ? [el("button", {
        type: "button",
        class: "secondary",
        id: `record-continue-${task.job_id}`,
        onclick: () => {
          window.location.hash = "#/plan";
        }
      }, "接续：打开目标生成包")] : [],
      el("button", { type: "button", class: "secondary", disabled: "" }, "启动 / 取消"),
      el(
        "span",
        { class: "theme-toggle-note" },
        task.kind.endsWith("-native") ? "接续只做页面跳转：同一项目重新打开编排面，宿主与底图仍由你重新选一次（这里不替你选，也不把已排队任务读成完成）。启动 / 取消会驱动真实宿主并留下宿主侧效果，本会话未获该授权，本机既有工作台已提供同一动作。" : "这条记录是素材导入，没有对应的目标生成包，所以这里不给接续入口。启动 / 取消会驱动真实宿主并留下宿主侧效果，本会话未获该授权。"
      )
    )
  );
}
async function loadTaskEvents(projectId, job, host) {
  host.replaceChildren(el("p", { class: "view-loading" }, "正在读回该任务的事件…"));
  const data = await apiOrEmpty(
    `/projects/${projectId}/tasks/${encodeURIComponent(job)}/events`,
    { events: [], next_cursor: null }
  );
  const unread = shapeNotice(data);
  const offline = disconnectedNotice(data);
  if (unread || offline) {
    host.replaceChildren(stateBlock({
      kind: "unread",
      title: "事件未读回",
      weight: "neutral",
      producer: unread || offline || "响应缺少 events 集合",
      next: '刷新重读；未读回时本页不会把"没有事件"当成"任务没有进展"。'
    }));
    return;
  }
  if (!data.events.length) {
    host.replaceChildren(el(
      "p",
      { class: "view-hint" },
      "该任务还没有事件记录：事件由服务在状态迁移时写入，空集合不等于失败。"
    ));
    return;
  }
  const last = data.events[data.events.length - 1];
  host.replaceChildren(
    el(
      "p",
      { class: "view-hint" },
      `最近确认点：${last.to_state}${last.from_state ? ` ← ${last.from_state}` : ""} · 第 ${last.attempt_no} 次尝试 · ${last.at}`
    ),
    el("ul", { class: "record-event-list" }, ...data.events.slice(-8).map((e) => el(
      "li",
      {},
      `${e.at} · 第 ${e.attempt_no} 次 · ${e.from_state ? `${e.from_state} → ` : ""}${e.to_state}`
    ))),
    data.next_cursor ? el(
      "p",
      { class: "muted" },
      `还有更早的事件未取回（游标 ${data.next_cursor}）：本页只读回最近 8 条。`
    ) : ""
  );
}
async function renderRecords(target) {
  await projectPickerPanel(
    target,
    viewLabel("records"),
    async (projectId) => recordsBody(projectId),
    el(
      "p",
      { class: "view-hint" },
      "这里列出服务里真实存在的作业：状态词、尝试次数与取消标记都来自读回，不是界面推断。没有任务的项目会如实显示空列表，不会画出示例记录。"
    )
  );
}
function runtimeObservation(data, unread) {
  const word = (section, present, absent) => section.table === "NOT_READ" || unread ? "未读回：没有问到，因此既不是占用也不是空闲" : section.table === "ABSENT" ? absent : present;
  const held = (data.host_guard.rows ?? []).map((row) => `${String(row.host)}→${String(row.attempt_id)}`).join("、");
  const guardPresent = data.counts.hosts_held === 0 ? "表存在且为空：当前没有尝试持有宿主" : `当前 ${String(data.counts.hosts_held)} 个宿主被持有：${held}`;
  const quiescencePresent = `已记录 ${String((data.quiescence.rows ?? []).length)} 条，其中带回执 ${String(data.counts.attempts_quiescent_receipted ?? 0)} 条`;
  const reconciliationPresent = `开着 ${String(data.counts.reconciliations_open ?? 0)} 条。一条对账行只说明有人开了对账，不说明它查到了什么或修好了什么。`;
  const recoveryPresent = (data.recovery_protocol.rows ?? []).map((row) => `${String(row.attempt_id)}：${String(row.protocol)}`).join("、") || "表存在但没有行";
  const executionPresent = `读回 ${String((data.executions.rows ?? []).length)} 条，其中带回执 ${String(data.counts.executions_receipted ?? 0)} 条、有结果 ${String(data.counts.executions_with_result ?? 0)} 条。请求与结果正文不在这条投影里。`;
  const rows = [
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "宿主占用（native_host_guard_v1）"),
      el("small", {}, word(
        data.host_guard,
        guardPresent,
        "该状态库里没有这张表：这台服务从未记录过原生作业。"
      ))
    )),
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "静默确认（native_quiescence_v1）"),
      el("small", {}, word(
        data.quiescence,
        quiescencePresent,
        "没有这张表：从未记录过静默确认。"
      ))
    )),
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "对账（native_reconciliation_v1）"),
      el("small", {}, word(
        data.reconciliation,
        reconciliationPresent,
        "没有这张表：从未开过对账。"
      ))
    )),
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "恢复协议（native_recovery_protocol_v2）"),
      el("small", {}, word(data.recovery_protocol, recoveryPresent, "没有这张表。"))
    )),
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "执行记录与回执（native_execution_v1，仅本项目）"),
      el("small", {}, word(data.executions, executionPresent, "没有这张表。"))
    )),
    el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "占用预算"),
      el("span", { class: "tag neutral" }, "无该字段"),
      el("small", {}, ` ${data.budget_reason}`)
    ))
  ];
  for (const sentence of data.does_not_say) {
    rows.push(el("li", { class: "list-item" }, el(
      "div",
      {},
      el("strong", {}, "这条投影不说的内容"),
      el("small", {}, sentence)
    )));
  }
  return el(
    "div",
    { class: "panel" },
    el("h3", {}, "运行与恢复现场"),
    el(
      "p",
      { class: "view-hint" },
      "读的是 GET /api/projects/{id}/native-runtime —— 只读投影，不启动宿主、不排队、不取消；启动 / 取消仍是真实宿主副作用，本会话未获授权，所以这里不提供可点的动作。"
    ),
    el("ul", { class: "list" }, ...rows)
  );
}
function knowledgeNumber(value) {
  return typeof value === "number" ? String(value) : "未读回";
}
function knowledgeStateTag(className, word, fallback) {
  return word ? el("span", { class: className, lang: "en" }, word) : el("span", { class: className }, fallback);
}
function exportPanelRows(data) {
  const projection = (label, version, extra) => el("small", {}, `${label}：`, version ? el("span", { class: "value-mono" }, en(version)) : el("span", { class: "tag neutral" }, "未读回"), ` ${extra}`);
  const provenance = data.provenance ?? {};
  return [
    el(
      "p",
      { class: "view-hint" },
      el("span", { class: "tag ok" }, data.status ? en(data.status) : "状态未读回"),
      " 信封 ",
      data.schemaVersion ? el("span", { class: "value-mono" }, en(data.schemaVersion)) : el("span", { class: "tag neutral" }, "版本未读回"),
      ` · ${data.candidate_id ?? "候选 id 未读回"} · 第 ${data.revision === void 0 || data.revision === null ? "未读回" : String(data.revision)} 版`
    ),
    projection(
      "v2 导出文档",
      data.export?.schemaVersion,
      `载荷摘要 ${data.export?.payload_sha256 ?? "未读回"}`
    ),
    projection(
      "v1 投影",
      data.v1_projection?.schemaVersion,
      `source_id ${data.v1_projection?.source_id ?? "未读回"}（由提交者存下的两个编号拼接，本页不美化、不补全）`
    ),
    el(
      "small",
      {},
      `编号回显：job_id ${provenance.job_id ?? "未读回"}（`,
      en(provenance.job_id_state ?? "UNKNOWN"),
      `）· operation_id ${provenance.operation_id ?? "未读回"}（`,
      en(provenance.operation_id_state ?? "UNKNOWN"),
      "）。EXPLICITLY_UNUSED 是操作者显式声明的「不用」，USER_SUPPLIED 是被填进来的值；两者都不是本页面推断的。"
    ),
    el(
      "small",
      {},
      `来源修订 ${provenance.design_lab_sha ?? "未读回"} · freshness `,
      en(data.freshness ?? "UNKNOWN"),
      "（UNKNOWN 不等于 CURRENT）。"
    ),
    el(
      "small",
      {},
      "出站：",
      en(data.outbound?.transport ?? "未读回"),
      `；sent_count=${data.outbound?.sent_count === void 0 || data.outbound?.sent_count === null ? "未读回" : String(data.outbound.sent_count)}`,
      `；bytes=${data.outbound?.bytes === void 0 || data.outbound?.bytes === null ? "未读回" : String(data.outbound.bytes)}`,
      "。bytes 计的是这份文档被组装出来的字节，不是离开本机的字节——本服务没有传输通道。"
    ),
    ...data.does_not_say && data.does_not_say.length ? [el(
      "p",
      { class: "muted" },
      el("strong", {}, "这份导出文档不说的话："),
      ...data.does_not_say.map((line) => el("small", {}, line))
    )] : [el("small", {}, "服务未给出 does_not_say，因此本页无法说明这份导出文档不覆盖什么。")]
  ];
}
function knowledgeExportPanel(projectId) {
  const body = el(
    "div",
    { id: "knowledge-export-body" },
    el("p", { class: "muted" }, "尚未读回任何导出文档：点某一行候选上的「读回导出文档」。")
  );
  const select = async (candidateId) => {
    body.replaceChildren(el("p", { class: "view-loading" }, "正在读回导出文档…"));
    try {
      const data = await api(
        `/projects/${projectId}/knowledge-candidates/${encodeURIComponent(candidateId)}/export`
      );
      body.replaceChildren(...exportPanelRows(data));
    } catch (error) {
      const envelope = error.serviceEnvelope;
      body.replaceChildren(
        el(
          "p",
          {},
          el("span", { class: "tag warn" }, "导出被拒绝"),
          el("span", { class: "value-mono" }, ` ${candidateId}`)
        ),
        el("small", {}, `未读回：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "")),
        el("small", {}, "拒绝本身就是产品答案：它点名是哪道门拦住的（未批准、已撤销、权利门未 CHECKED 或审阅人是 agent）。本页不把它改写成一次空导出，也不自动重试。")
      );
    }
  };
  return {
    element: el(
      "div",
      { class: "panel", id: "knowledge-export-panel" },
      el("h3", {}, "导出文档（读回，不发送）"),
      el(
        "p",
        { class: "view-hint" },
        "这里走 GET …/knowledge-candidates/<id>/export：产出 v2 导出文档与 v1 投影两份出站文档，并原样回显存储中的两个编号。本服务没有 ArcheAxis 传输，outbound.transport 恒为 NOT_CONNECTED、sent_count 恒为 0，所以「读回导出文档」不等于「已经交给对方」。"
      ),
      body
    ),
    select
  };
}
function knowledgeCandidateRow(row, index, onExport) {
  const decisionClass = row.review_state === "PENDING_HUMAN_APPROVAL" ? "warn" : row.review_state === "REJECTED" ? "neutral" : row.export_ready ? "ok" : "neutral";
  const freshClass = row.freshness === "CURRENT" ? "ok" : row.freshness === "STALE" ? "warn" : "neutral";
  const revoked = row.revocation_state === "REVOKED";
  return el(
    "li",
    { class: "list-item" },
    el(
      "div",
      {},
      el("strong", {}, row.title ?? "标题未读回"),
      el("span", { class: "value-mono" }, row.candidate_id)
    ),
    knowledgeStateTag("tag " + decisionClass, row.review_state, "未读回"),
    knowledgeStateTag(
      "tag " + (revoked ? "warn" : "neutral"),
      revoked ? "REVOKED" : row.revocation_state,
      "未读回"
    ),
    knowledgeStateTag("tag " + freshClass, row.freshness, "UNKNOWN"),
    el(
      "span",
      { class: "tag " + (row.export_ready ? "ok" : "neutral") },
      row.export_ready ? "本地合同允许导出，未发送" : "导出被阻止"
    ),
    el(
      "small",
      {},
      `第 ${String(row.revision)} 版 · 类型 ${row.candidate_type ?? "未读回"} · 来源修订 ${row.source_design_lab_sha ?? "未读回"} · 权利门 ${row.rights_gate_state ?? "未读回"}` + (row.supersedes ? ` · 取代 ${row.supersedes}` : " · 不取代任何候选")
    ),
    el(
      "small",
      {},
      row.export_ready ? "export_ready=true 只表示本地合同允许导出；本服务没有 ArcheAxis 传输，因此没有发送任何内容。" : `不可导出：${row.export_blocked_by ?? "服务未给出原因"}`
    ),
    row.review_state === "PENDING_HUMAN_APPROVAL" ? el("small", {}, "尚无人工裁决：候选写入时固定为 PENDING_HUMAN_APPROVAL。") : el("small", {}, `裁决：${row.reviewer_id ?? "未署名"} @ ${row.reviewed_at ?? "未读回"}` + (revoked && row.revocation_reason ? ` · 撤销原因：${row.revocation_reason}` : "")),
    el(
      "button",
      {
        type: "button",
        class: "secondary",
        id: `knowledge-export-${String(index)}`,
        disabled: row.export_ready ? void 0 : "",
        onclick: () => onExport(row.candidate_id)
      },
      // 按钮文字带上"不发送"：一个只读回文档的动作如果被写成「导出」，就会被读成已经交付。
      row.export_ready ? "读回导出文档（不发送）" : "读回导出文档（本条被合同阻止）"
    ),
    row.payload_sha256 ? el("small", { class: "value-mono" }, `payload ${row.payload_sha256}`) : ""
  );
}
function knowledgeCreateForm(projectId, data, tasks2, reload, outcome) {
  const type = el("select", { class: "input", id: "knowledge-type" });
  for (const word of ["METHOD", "JURY_CORRECTION", "PRODUCTION_LESSON"]) {
    type.append(new Option(word, word));
  }
  const title = el("input", { class: "input", id: "knowledge-title", maxlength: "200" });
  const statement = el("textarea", {
    class: "input",
    id: "knowledge-statement",
    maxlength: "4000",
    "aria-label": "候选正文"
  });
  const appliesTo = el("input", {
    class: "input",
    id: "knowledge-applies-to",
    maxlength: "400",
    placeholder: "brand-identity, editorial-layout",
    "aria-label": "适用设计域，用逗号或空格分隔，至少一个"
  });
  const license = el("input", {
    class: "input",
    id: "knowledge-license",
    maxlength: "200",
    placeholder: "CC-BY-4.0 / project-internal / …"
  });
  const rights = el("select", { class: "input", id: "knowledge-rights" });
  rights.append(new Option("请选择权利门状态", ""));
  for (const word of ["UNCHECKED", "CHECKED", "BLOCKED"]) rights.append(new Option(word, word));
  const clientAsset = el("select", { class: "input", id: "knowledge-client-asset" });
  const thirdParty = el("select", { class: "input", id: "knowledge-third-party" });
  for (const select of [clientAsset, thirdParty]) {
    select.append(new Option("请选择", ""));
    select.append(new Option("不包含（false）", "false"));
    select.append(new Option("包含（true）", "true"));
  }
  const redaction = el("input", {
    class: "input",
    id: "knowledge-redaction",
    maxlength: "1000",
    placeholder: "包含客户素材时必填：说明如何脱敏"
  });
  const sha = el("input", {
    class: "input",
    id: "knowledge-source-sha",
    maxlength: "64",
    value: data.head_sha ?? "",
    placeholder: "40-64 位十六进制修订号"
  });
  const job = el("input", {
    class: "input",
    id: "knowledge-job",
    maxlength: "200",
    list: "knowledge-job-ids",
    placeholder: "产生这条经验的真实 job_id"
  });
  const operation = el("input", {
    class: "input",
    id: "knowledge-operation",
    maxlength: "200",
    placeholder: "产生这条经验的 operation_id（页面不推断）"
  });
  const jobMode = el("select", { class: "input", id: "knowledge-job-mode" });
  const operationMode = el("select", { class: "input", id: "knowledge-operation-mode" });
  for (const select of [jobMode, operationMode]) {
    select.append(new Option("请选择：填写编号，还是显式声明不使用", ""));
    select.append(new Option("我来填写", "fill"));
    select.append(new Option("不使用（发送字面量 UNUSED）", "unused"));
  }
  const syncProvenance = (mode, field) => {
    field.disabled = mode.value === "unused";
  };
  jobMode.onchange = () => syncProvenance(jobMode, job);
  operationMode.onchange = () => syncProvenance(operationMode, operation);
  const evidence = el("input", {
    class: "input",
    id: "knowledge-evidence",
    maxlength: "71",
    placeholder: "sha256:<64 位十六进制>"
  });
  const supersedes = el("select", { class: "input", id: "knowledge-supersedes" });
  supersedes.append(new Option("不替代：这是一条新的候选", ""));
  for (const candidate of data.candidates) {
    supersedes.append(new Option(
      `${candidate.candidate_id}（${candidate.review_state}）`,
      candidate.candidate_id
    ));
  }
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "knowledge-create-submit" },
    "记录一条待人工裁决的候选"
  );
  let candidateId = "";
  let lastFingerprint = "";
  submit.onclick = () => {
    void (async () => {
      const domains = appliesTo.value.split(/[,\n\s]+/).map((part) => part.trim()).filter(Boolean);
      const text = statement.value.trim();
      const name = title.value.trim();
      const provenanceError = (label, mode, field) => !mode.value ? `未声明 ${label} 的来源：选「我来填写」或「不使用」，页面不替你选` : mode.value === "unused" && field.value.trim() ? `${label} 冲突：已选择「不使用」，但填写框里还有内容——清空它或改选「我来填写」，页面不会替你丢掉已经打进去的东西` : mode.value === "fill" && !field.value.trim() ? `${label} 为空：选了「我来填写」就得真的填；这次确实没有编号请改选「不使用」` : "";
      const jobError = provenanceError("job_id", jobMode, job);
      const operationError = provenanceError("operation_id", operationMode, operation);
      const jobId = jobMode.value === "unused" ? "UNUSED" : job.value.trim();
      const operationId = operationMode.value === "unused" ? "UNUSED" : operation.value.trim();
      const refusal = !name ? "标题为空" : !text ? "正文为空" : !domains.length ? "没有任何适用设计域" : !license.value.trim() ? "license_id 为空：权利门不允许一个空许可证" : !rights.value ? "未选择权利门状态" : !clientAsset.value ? "未声明是否包含客户素材（页面不默认 false）" : !thirdParty.value ? "未声明是否包含第三方素材（页面不默认 false）" : !/^[0-9a-f]{40,64}$/.test(sha.value.trim()) ? "来源修订不是 40-64 位小写十六进制" : jobError ? jobError : operationError ? operationError : !/^sha256:[0-9a-f]{64}$/.test(evidence.value.trim()) ? "evidence_sha256 必须是 sha256:<64 位小写十六进制>" : clientAsset.value === "true" && !redaction.value.trim() ? "声明包含客户素材时必须填写脱敏说明" : "";
      if (refusal) {
        outcome.textContent = `未提交：${refusal}。服务端未写入任何候选。`;
        return;
      }
      const payload = {
        candidate_type: type.value,
        source: {
          design_lab_sha: sha.value.trim(),
          job_id: jobId,
          operation_id: operationId,
          evidence_sha256: evidence.value.trim()
        },
        rights: {
          license_id: license.value.trim(),
          rights_gate_state: rights.value,
          contains_client_asset: clientAsset.value === "true",
          contains_third_party_asset: thirdParty.value === "true",
          redaction_note: redaction.value.trim() || null
        },
        payload: { title: name, statement: text, applies_to: domains },
        // 合同要求 body 的顶层键集合完全一致；null 让服务用自己的时钟，
        // 而不是让浏览器时间冒充服务时间。
        created_at: null,
        revocation_entrypoint: "design-lab/knowledge/revoke"
      };
      const previous = supersedes.value;
      const fingerprint = JSON.stringify({ payload, previous });
      if (fingerprint !== lastFingerprint) {
        candidateId = "kc-" + Math.random().toString(16).slice(2, 34);
        lastFingerprint = fingerprint;
      }
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(
          `/projects/${projectId}/knowledge-candidates` + (previous ? `?supersedes=${encodeURIComponent(previous)}` : ""),
          { ...payload, candidate_id: candidateId }
        );
        await reload();
        outcome.textContent = "已记录一条候选；它仍是 PENDING_HUMAN_APPROVAL —— 批准需要下方由具名的人在场的裁决，写入动作本身不能提升它。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        outcome.textContent = `未记录：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "") + "。服务端未写入任何候选。";
      } finally {
        submit.disabled = false;
      }
    })().catch((error) => setStatus(errMsg(error), true));
  };
  return el(
    "div",
    { class: "panel knowledge-form" },
    el("h3", {}, "记录一条知识候选"),
    el(
      "p",
      { class: "view-hint" },
      "source 与 rights 的每个字段都指向一条真实记录或你的明确选择：页面不替你编 job_id、operation_id、来源修订或“是否包含客户素材”。两个编号各有三种说得过去的状态：写下来、显式选择「不使用」（服务端存字面量 UNUSED，读回报成 EXPLICITLY_UNUSED）、或什么都没选——最后一种会被拒，因为“没填”和“声明没有”不是同一件事。"
    ),
    el("label", {}, "类型", type),
    el("label", {}, "标题", title),
    el("label", {}, "正文（会被公开投影的陈述）", statement),
    el("label", {}, "适用设计域（至少一个）", appliesTo),
    el("label", {}, "许可证", license),
    el("label", {}, "权利门状态", rights),
    el("label", {}, "是否包含客户素材", clientAsset),
    el("label", {}, "是否包含第三方素材", thirdParty),
    el("label", {}, "脱敏说明（包含客户素材时必填）", redaction),
    el("label", {}, `来源修订（读回 HEAD：${data.head_sha ?? "UNKNOWN"}）`, sha),
    el("label", {}, "job_id 的来处", jobMode),
    el("label", {}, "job_id", job, el(
      "datalist",
      { id: "knowledge-job-ids" },
      ...tasks2.map((task) => el("option", { value: task.job_id }))
    )),
    el("label", {}, "operation_id 的来处", operationMode),
    el("label", {}, "operation_id", operation),
    el("label", {}, "证据摘要", evidence),
    el("label", {}, "取代哪条候选（只列读回中出现过的）", supersedes),
    submit
  );
}
function knowledgeReviewForm(projectId, data, reload, outcome) {
  const target = el("select", { class: "input", id: "knowledge-review-target" });
  for (const candidate of data.candidates) {
    target.append(new Option(
      `${candidate.candidate_id}（${candidate.review_state}）`,
      candidate.candidate_id
    ));
  }
  const decision = el("select", { class: "input", id: "knowledge-decision" });
  decision.append(new Option("APPROVE", "APPROVE"));
  decision.append(new Option("REJECT", "REJECT"));
  const reviewer = el("input", {
    class: "input",
    id: "knowledge-reviewer",
    maxlength: "200",
    placeholder: "裁决人姓名 / 标识（服务把它当作声称的身份）"
  });
  const note = el("textarea", { class: "input", id: "knowledge-note", maxlength: "2000" });
  const reason = el("textarea", { class: "input", id: "knowledge-reason", maxlength: "2000" });
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "knowledge-review-submit" },
    "记录人工裁决"
  );
  submit.onclick = () => {
    void (async () => {
      const id = target.value;
      const who = reviewer.value.trim();
      if (!id) {
        outcome.textContent = "未提交：没有可裁决的候选。";
        return;
      }
      if (!who) {
        outcome.textContent = "未提交：裁决人未署名。服务端会拒绝一个没有名字的人工裁决。";
        return;
      }
      if (decision.value === "REJECT" && !reason.value.trim()) {
        outcome.textContent = "未提交：驳回必须说明原因（服务端同样拒绝 REASON_REQUIRED）。";
        return;
      }
      const body = {
        decision: decision.value,
        reviewer_id: who,
        reviewer_kind: "human",
        reviewed_at: (/* @__PURE__ */ new Date()).toISOString(),
        note: note.value.trim() || null,
        reason: decision.value === "REJECT" ? reason.value.trim() : null
      };
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/knowledge-candidates/${id}/review`, body);
        await reload();
        outcome.textContent = decision.value === "APPROVE" ? "已记录批准。export_ready 若为真仍只表示本地合同允许导出：本服务没有 ArcheAxis 传输，这条候选没有被发送。" : "已记录驳回。被驳回的候选不会出现在导出投影里。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        outcome.textContent = `未记录：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "") + "。服务端未写入任何裁决。";
      } finally {
        submit.disabled = false;
      }
    })().catch((error) => setStatus(errMsg(error), true));
  };
  return el(
    "div",
    { class: "panel knowledge-form" },
    el("h3", {}, "人工裁决"),
    el(
      "p",
      { class: "view-hint" },
      '这是 Human Gate 的桌面入口：服务端只接受 reviewer_kind="human" 且带具名裁决人的请求，agent 无法在不署名的情况下批准。页面本身不做身份验证——名字和时间是你输入的声称，服务端无法证明这个人存在或真的审阅了内容。'
    ),
    el("label", {}, "候选", target),
    el("label", {}, "裁决", decision),
    el("label", {}, "裁决人", reviewer),
    el("label", {}, "备注（可选）", note),
    el("label", {}, "驳回原因（REJECT 必填）", reason),
    submit
  );
}
function knowledgeRevokeForm(projectId, data, reload, outcome) {
  const target = el("select", { class: "input", id: "knowledge-revoke-target" });
  for (const candidate of data.candidates) {
    target.append(new Option(
      `${candidate.candidate_id}（${candidate.revocation_state}）`,
      candidate.candidate_id
    ));
  }
  const reason = el("textarea", { class: "input", id: "knowledge-revoke-reason", maxlength: "2000" });
  const revokedBy = el("input", { class: "input", id: "knowledge-revoked-by", maxlength: "200" });
  const submit = el(
    "button",
    { type: "button", class: "secondary", id: "knowledge-revoke-submit" },
    "写入撤销回执"
  );
  submit.onclick = () => {
    void (async () => {
      if (!target.value) {
        outcome.textContent = "未提交：没有可撤销的候选。";
        return;
      }
      if (!reason.value.trim()) {
        outcome.textContent = "未提交：撤销必须说明原因。";
        return;
      }
      if (!revokedBy.value.trim()) {
        outcome.textContent = "未提交：撤销必须具名。";
        return;
      }
      const body = {
        reason: reason.value.trim(),
        revoked_by: revokedBy.value.trim(),
        revoked_at: null
      };
      submit.disabled = true;
      outcome.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/knowledge-candidates/${target.value}/revoke`, body);
        await reload();
        outcome.textContent = "已写入撤销回执并阻止导出。撤销不能撤回；如果此前已经有副本离开本机，本机撤销不能召回它（本服务没有传输，所以这里实际上没有发生过发送）。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        outcome.textContent = `未记录：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "") + "。服务端未写入任何撤销。";
      } finally {
        submit.disabled = false;
      }
    })().catch((error) => setStatus(errMsg(error), true));
  };
  return el(
    "div",
    { class: "panel knowledge-form" },
    el("h3", {}, "撤销与回执"),
    el(
      "p",
      { class: "view-hint" },
      "撤销只会阻止之后的导出，并留下一条本机回执；它不会改写既有裁决，也不会召回任何已经离开本机的副本。"
    ),
    el("label", {}, "候选", target),
    el("label", {}, "撤销原因", reason),
    el("label", {}, "申请人", revokedBy),
    submit
  );
}
async function knowledgePanel(projectId, tasks2) {
  const outcome = el("p", { class: "view-hint", id: "knowledge-outcome" }, "");
  const body = el(
    "div",
    { id: "knowledge-body" },
    el("p", { class: "view-loading" }, "正在读回知识候选…")
  );
  const exportPanel = knowledgeExportPanel(projectId);
  const panel = el(
    "div",
    { class: "panel", id: "knowledge-panel" },
    el("h3", {}, "知识回执与反馈（T16 / U09）"),
    el(
      "p",
      { class: "view-hint" },
      "这里读回本项目的 KnowledgeCandidate：写入固定为 PENDING_HUMAN_APPROVAL，只有下方具名的人工裁决能批准或驳回，撤销会留下本机回执。"
    ),
    el(
      "p",
      { class: "view-hint" },
      "没有建的那一半：本服务没有 ArcheAxis 传输 —— outbound.transport 是 NOT_CONNECTED，sent_count 的 0 表示从未发送，而不是一次失败的发送；export_ready 只表示本地合同允许导出，不代表送达或对方已接收。"
    ),
    body,
    outcome
  );
  const load = async () => {
    const data = await apiOrEmpty(
      `/projects/${projectId}/knowledge-candidates`,
      OFFLINE.knowledge
    );
    const shape = shapeNotice(data);
    const offline = disconnectedNotice(data);
    if (shape || offline) {
      body.replaceChildren(el(
        "p",
        { class: "error" },
        `${shape || offline}：这里的零值是占位，不是该项目的候选数。未读回时本页不提供裁决或撤销控件，避免对没有读到的记录动手。`
      ));
      return;
    }
    const rows = data.candidates.map((row, index) => knowledgeCandidateRow(
      row,
      index,
      (candidateId) => {
        void exportPanel.select(candidateId);
      }
    ));
    if (data.conflicts.length) {
      rows.push(el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, `存储冲突（${data.conflicts.length}）`),
          el("small", {}, "读回仍然成功；这些是存储与合同之间的分歧，本页报告它们，但不修复、也不替服务选择一个解释。")
        )
      ));
      for (const conflict of data.conflicts) {
        rows.push(el(
          "li",
          { class: "list-item" },
          el("span", { class: "tag warn" }, en(conflict.kind ?? "未读回")),
          el("span", { class: "value-mono" }, conflict.candidate_id ?? "未读回"),
          el("small", {}, conflict.detail ?? "无可读详情")
        ));
      }
    }
    if (!rows.length) {
      rows.push(emptyLi(
        data,
        "本项目尚无知识候选",
        "记录一条候选后在此读回；未读回不等于本项目没有候选。"
      ));
    }
    const outbound = data.outbound;
    rows.push(el(
      "li",
      { class: "list-item" },
      el(
        "div",
        {},
        el("strong", {}, "本读回不说什么"),
        ...data.does_not_say.length ? data.does_not_say.map((line) => el("small", {}, line)) : [el("small", {}, "服务未给出 does_not_say，因此本页无法说明这份读回不覆盖什么。")]
      )
    ));
    body.replaceChildren(
      el(
        "p",
        { class: "view-hint" },
        `共 ${knowledgeNumber(data.candidate_count)} 条候选 · 待裁决 ${knowledgeNumber(data.pending_review_count)} · 已批准 ${knowledgeNumber(data.approved_count)} · 已驳回 ${knowledgeNumber(data.rejected_count)} · 已撤销 ${knowledgeNumber(data.revoked_count)} · 不可读取 ${knowledgeNumber(data.unreadable_count)} 条行 · 本地合同可导出 ${knowledgeNumber(data.export_ready_count)} 条。freshness 对照的 HEAD 是 ${data.head_sha ?? "UNKNOWN"}：UNKNOWN 不等于 CURRENT。`
      ),
      el(
        "p",
        { class: "muted" },
        "出站边界：",
        en(outbound.transport ?? "未读回"),
        " → ",
        en(outbound.destination ?? "未读回"),
        `；sent_count=${knowledgeNumber(outbound.sent_count)}；last_attempt_at=${outbound.last_attempt_at ?? "null"}。`,
        outbound.note ?? "服务未给出出站说明。"
      ),
      el("ul", { class: "list" }, ...rows),
      knowledgeCreateForm(projectId, data, tasks2, safeLoad, outcome),
      knowledgeReviewForm(projectId, data, safeLoad, outcome),
      knowledgeRevokeForm(projectId, data, safeLoad, outcome),
      exportPanel.element
    );
  };
  const safeLoad = async () => {
    try {
      await load();
    } catch (error) {
      body.replaceChildren(el("p", { class: "error" }, `知识回执未读回：${errMsg(error)}`));
    }
  };
  await safeLoad();
  return panel;
}
async function recordsBody(projectId) {
  const [data, runtime] = await Promise.all([
    apiOrEmpty(`/projects/${projectId}/tasks`, OFFLINE.tasks),
    apiOrEmpty(
      `/projects/${projectId}/native-runtime`,
      OFFLINE.nativeRuntime
    )
  ]);
  const runtimeUnread = shapeNotice(runtime) || disconnectedNotice(runtime);
  const wrap = el("div", {});
  const unread = shapeNotice(data);
  const offline = disconnectedNotice(data);
  const tasks2 = data.tasks;
  const counts = tasks2.reduce((acc, t) => {
    const key = taskTriage(t.attempt.state);
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  wrap.replaceChildren(
    el(
      "div",
      { class: "panel" },
      el("h3", {}, `制作记录（${tasks2.length}）`),
      el(
        "p",
        { class: "view-hint" },
        unread ? `${unread}，因此这里的条数不能当作该项目的作业总数` : offline ? `${offline}，作业台账未读回` : tasks2.length ? `按服务状态词分组：${Object.entries(counts).map(([k, v]) => `${TRIAGE_LABEL[k]} ${v}`).join(" · ")}。游标分页未展开：next_cursor 存在时本页会说明还有更多。` : "该项目当前没有作业记录。空列表是读回结果，不是失败，也不代表从未运行过。"
      ),
      data.next_cursor ? el(
        "p",
        { class: "muted", id: "records-more" },
        `还有更多：服务给了下一页游标 ${data.next_cursor}；本视图不自动续读，避免把未取回的条目算进分组计数。`
      ) : "",
      tasks2.length ? el("ul", { class: "list" }, ...tasks2.map((t) => taskRecordRow(projectId, t))) : el(
        "p",
        { class: "record-empty-note" },
        "R2 §7 的三条示例记录属于原型，不在这里出现：出现在读回面里的每一行都必须对应一条真实作业。"
      )
    ),
    el(
      "div",
      { class: "panel" },
      el("h3", {}, "这个入口现在能说什么、不能说什么"),
      el(
        "ul",
        { class: "list" },
        el(
          "li",
          { class: "list-item" },
          el("span", {}, "状态词"),
          el("span", { class: "tag info" }, "来自服务"),
          el("small", {}, ' attempt.state 逐词对照 config/state-vocabularies.json，OUTCOME_UNKNOWN 显示为"未知状态/待人工核对"，不并入失败。')
        ),
        el(
          "li",
          { class: "list-item" },
          el("span", {}, "领域标签"),
          el("span", { class: "tag neutral" }, "无该字段"),
          el("small", {}, " TaskRecord 不带领域；补它属 DL-FINAL-T06 的分类工作，不由界面按 kind 猜测。")
        ),
        el(
          "li",
          { class: "list-item" },
          el("span", {}, "接续到目标生成包"),
          el("span", { class: "tag ok" }, "已接线"),
          el("small", {}, " 只做地址跳转：不发出请求、不启动宿主，宿主与底图到那一页重选。简报字段不会自动变成包结构（属 DL-FINAL-T09/T10）。")
        ),
        el(
          "li",
          { class: "list-item" },
          el("span", {}, "启动 / 取消"),
          el("span", { class: "tag warn" }, "未接线"),
          el("small", {}, " 是真实宿主副作用，本会话无该授权；按钮禁用并说明原因，不画成可点。")
        )
      ),
      // DL-UI-U06: the observation half of run/observe/recover, over the tables the existing
      // action routes already write. It reads a second route, so the panel appears beside the
      // ledger rather than restating it.
      runtimeObservation(runtime, runtimeUnread),
      // DL-UI-U09: the knowledge readback plus the human decision/revocation controls that
      // already have routes and a store. Its first read also creates the knowledge tables,
      // so it is awaited here rather than racing the rest of the view.
      await knowledgePanel(projectId, tasks2)
    )
  );
  const dock = activityDock(tasks2);
  if (dock) wrap.append(dock);
  return wrap;
}
function activityDock(tasks2) {
  const live = tasks2.filter((t) => {
    const k = taskTriage(t.attempt.state);
    return k === "in_flight" || k === "needs_human";
  });
  if (!live.length) return null;
  return el(
    "div",
    {
      class: "activity-dock",
      id: "activity-dock",
      role: "status",
      "aria-label": "当前制作任务"
    },
    el("span", {}, `${live.length} 条作业仍在进行或待人工核对`),
    el("button", {
      type: "button",
      class: "secondary",
      onclick: () => {
        window.location.hash = "#/records";
      }
    }, "回到制作记录")
  );
}
function composeTargetPlan(asset, host) {
  const node = {
    id: "reference-raster",
    type: "raster",
    name: `${asset.id.slice(-8)} · ${asset.media_type}`,
    opacity: 1,
    bounds: { x: 0, y: 0, width: asset.width, height: asset.height },
    inferred: false,
    zOrder: 0,
    visible: true,
    // D02 (batch 22): this composer declares no explicit host fallback, and the
    // lowering contract refuses any node carrying `locked` ("unsupported
    // opacity/visibility/lock/blend; explicit fallback required"). Locking only the
    // Illustrator default made that host's default plan unreachable: the service
    // answered 400 INVALID_REQUEST before a job had ever been created, while
    // Photoshop passed only because the UI happened to send `false`. Both hosts now
    // compose an unlocked layer. The contract is NOT widened -- a `locked` node is
    // still refused downstream, and that refusal is pinned by a test.
    locked: false,
    blendMode: "normal",
    raster: {
      // 导入路由登记的就是这个完整 img-ID；raster.path 必须是它，不是本地路径。
      path: asset.id,
      crop: { x: 0, y: 0, width: asset.width, height: asset.height },
      alpha: 1,
      sourceMappings: []
    }
  };
  return {
    rir: {
      schemaVersion: "design-lab/reconstruction-ir/v1",
      canvas: { width: asset.width, height: asset.height, colorSpace: "srgb" },
      layers: [node]
    },
    textStyles: {}
  };
}
async function sha256Hex(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function contentKey(parts) {
  return sha256Hex(new TextEncoder().encode(parts.join("\0")));
}
function readPlanReceipt(data) {
  return { id: data?.task?.job_id ?? "未给出任务号", state: data?.task?.state ?? "未读回" };
}
function planRefusal(error) {
  const envelope = error.serviceEnvelope;
  const code = typeof envelope?.["error"] === "string" ? envelope["error"] : "";
  if (code === "NATIVE_PLAN_IDEMPOTENCY_CONFLICT")
    return {
      // 409 is a CONFLICT, not a permission verdict: STATE_SPECS has a `conflict` kind for
      // exactly this, and `forbidden` (「无权进行」) would tell the operator to ask for access
      // when the real action is "do not reuse this key". The busy 409 below keeps `unknown`
      // because there the service decided nothing at all.
      kind: "conflict",
      title: "冲突：这个幂等键已经登记过别的内容",
      weight: "bad",
      producer: "POST /api/projects/{id}/native-plans 返回 NATIVE_PLAN_IDEMPOTENCY_CONFLICT（409）：同一把键下已有的目标包与本次提交的内容摘要不一致。",
      next: "不要换内容后复用同一个键重试——那正是这条冲突要拦的事。要么把本次改动当成新的一次排队（新键），要么放弃这次改动。服务端没有写入任何东西。"
    };
  if (code === "NATIVE_SUBMISSION_BUSY")
    return {
      kind: "unknown",
      title: "未排队：本机服务正忙",
      weight: "neutral",
      producer: "POST /api/projects/{id}/native-plans 返回 NATIVE_SUBMISSION_BUSY（409）：同一项目的上一次受理还没落账。",
      next: "这是可以重试的一次：等内容不同的排队会换键，重试同内容会沿用同一幂等键而不会产生第二份目标包。排队本身仍不等于宿主已启动。"
    };
  if (code === "NATIVE_PLAN_TOO_LARGE")
    return {
      kind: "error",
      title: "目标包超过受理上限",
      weight: "bad",
      producer: "POST /api/projects/{id}/native-plans 返回 NATIVE_PLAN_TOO_LARGE（413）：正文超过服务端 4,000,000 字节的硬上限。",
      next: "超限的是编排出来的目标包本身，不是网络。换一张更小的底图或减少节点；界面不会截断内容来凑进上限。"
    };
  if (code === "INVALID_NATIVE_KEY")
    return {
      kind: "error",
      title: "幂等键不合法",
      weight: "bad",
      producer: "POST /api/projects/{id}/native-plans 返回 INVALID_NATIVE_KEY（400）：键的形状不符合服务端要求。",
      // D01: the plan key is now the SHA-256 of (project, host, composed plan), i.e.
      // 64 lowercase hex chars -- always inside the service's allowed shape.
      next: "本页的键是 (项目 · 宿主 · 编排结果) 的 SHA-256（64 位十六进制），形状恒定合法；出现这条说明是界面自己发错了，不是用户填错，按代码排查生成处，不要让用户重填。"
    };
  if (code === "INVALID_NATIVE_PLAN")
    return {
      kind: "error",
      title: "目标包不符合合同",
      weight: "bad",
      producer: "POST /api/projects/{id}/native-plans 返回 INVALID_NATIVE_PLAN（400）：编排出的 RIR 或宿主字段没有通过合同校验。",
      next: "本页不替用户猜一个能过校验的值。核对宿主与底图是否仍在本项目的读回里；若两者都在，这是编排缺陷，按代码报修。"
    };
  if (!envelope)
    return {
      kind: "error",
      title: "请求没有到达服务端",
      weight: "bad",
      producer: `POST /api/projects/{id}/native-plans 没有拿到服务回复：${errMsg(error)}。没有回复不等于没有受理——本机可能已经写入，只是这条连接没等到答案。`,
      next: "先回「制作记录与待继续」看这次排队是否已经落账，再决定是否重试；直接重试同内容是安全的（同键），但不要在没核对前改内容重发。"
    };
  return {
    kind: "forbidden",
    title: "未受理",
    weight: "bad",
    producer: `POST /api/projects/{id}/native-plans 返回：${code || errMsg(error)}`,
    next: "按上面的原因修正目标包后重试；界面不会替你猜一个能通过校验的字段值。"
  };
}
function planComposer(projectId) {
  const hostSelect = el(
    "select",
    { class: "input", "aria-label": "目标宿主" },
    el("option", { value: "illustrator" }, "Illustrator / AI"),
    el("option", { value: "photoshop" }, "Photoshop / PSD")
  );
  const assetSelect = el(
    "select",
    { class: "input", "aria-label": "参考底图资产" },
    el("option", { value: "" }, "选择本项目已导入的资产")
  );
  const layerHost = el("div", { class: "plan-layer" });
  const preview2 = el("pre", { class: "mono plan-preview" }, "（选择资产后显示编排结果）");
  const outcome = el("div", { class: "plan-outcome" });
  const status = el(
    "p",
    { class: "view-hint", role: "status", "aria-live": "polite" },
    "提交只把目标生成包排队，不启动宿主，也不修改任何已交付版本。"
  );
  let assets = [];
  const recompute = () => {
    const asset = assets.find((a) => a.id === assetSelect.value);
    if (!asset) {
      preview2.textContent = "（还没有选择资产：没有真实底图就不编排，不给空画布填假尺寸）";
      layerHost.replaceChildren();
      return;
    }
    const composed = composeTargetPlan(asset, hostSelect.value);
    preview2.textContent = JSON.stringify(composed.rir, null, 2);
    layerHost.replaceChildren(el(
      "ul",
      { class: "list" },
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "底图 · 用户勾选，非推断"),
          el("small", {}, `${asset.id} · ${asset.media_type} · ${asset.width}×${asset.height} · 权利 ${asset.rights} · 版本 ${asset.version_id.slice(0, 12)}…`)
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "画布"),
          el("small", {}, `${String(composed.rir.canvas.width)}×${String(composed.rir.canvas.height)} · srgb（取自底图真实尺寸，不是页面臆造）`)
        )
      ),
      el(
        "li",
        { class: "list-item" },
        el(
          "div",
          {},
          el("strong", {}, "结构 / 文字 / 路径节点"),
          el("small", {}, "本页不自动编排结构：桥已接通（POST …/assets/<img-ID>/analysis 与 `design-lab analyze` 两条生产入口），但本机没有合格的 OCR/分析后端可产出观测，把猜测画进节点就是假结构。观测由操作者提供，合格模型待 owner 裁定；文字与路径节点属 U05 剩余项与 DL-FINAL-T10。")
        )
      )
    ));
  };
  hostSelect.onchange = recompute;
  assetSelect.onchange = recompute;
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "plan-submit" },
    "排队这份目标生成包"
  );
  submit.onclick = () => {
    const asset = assets.find((a) => a.id === assetSelect.value);
    if (!asset) {
      status.textContent = "没有底图资产就不提交：本机服务要求 raster.path 指向已导入的完整 img-ID。";
      return;
    }
    submit.disabled = true;
    status.textContent = "正在提交…";
    void (async () => {
      const composed = composeTargetPlan(asset, hostSelect.value);
      try {
        const data = await api(
          `/projects/${projectId}/native-plans`,
          {
            host: hostSelect.value,
            rir: composed.rir,
            text_styles: composed.textStyles,
            idempotency_key: await contentKey([
              projectId,
              hostSelect.value,
              JSON.stringify(composed.rir),
              JSON.stringify(composed.textStyles)
            ])
          }
        );
        const receipt = readPlanReceipt(data);
        status.textContent = "";
        outcome.replaceChildren(
          el(
            "p",
            { class: "view-hint" },
            `已排队：${receipt.id} · 状态 ${receipt.state}`
          ),
          el(
            "p",
            { class: "view-hint" },
            "排队不等于完成：启动宿主与读回产物在任务面上是另一步，需要显式动作。"
          )
        );
      } catch (error) {
        status.textContent = "";
        outcome.replaceChildren(stateBlock(planRefusal(error)));
      } finally {
        submit.disabled = false;
      }
    })();
  };
  void (async () => {
    try {
      const data = await api(`/projects/${projectId}/assets`);
      assets = data.assets;
      assetSelect.replaceChildren(
        el("option", { value: "" }, "选择本项目已导入的资产"),
        ...assets.map((a) => el(
          "option",
          { value: a.id },
          `${a.id.slice(-8)} · ${a.media_type} · ${a.width}×${a.height}`
        ))
      );
      if (!assets.length) {
        assetSelect.setAttribute("disabled", "");
        status.textContent = "本项目还没有已导入资产；先在「输入与目标」导入 PNG/JPEG，没有底图就不编排。";
      }
    } catch (error) {
      assetSelect.replaceChildren(el("option", { value: "" }, "素材未读回"));
      outcome.replaceChildren(stateBlock({
        kind: "error",
        title: "素材未读回",
        weight: "bad",
        producer: `GET /api/projects/{id}/assets 返回：${errMsg(error)}`,
        next: "刷新重读；读不到资产时本页不会编排任何节点。"
      }));
    }
  })();
  return el(
    "div",
    { class: "intake-grid" },
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "目标包组成（来自已记录对象）"),
      el("label", {}, "目标宿主", hostSelect),
      el("label", {}, "底图资产", assetSelect),
      el("div", {}, layerHost),
      el(
        "p",
        { class: "uif-spec-note" },
        "编排规则只有一条：每个字段指向一条真实记录或你在本页的明确选择。权利位随资产一起显示，导入与读回不等于获得使用权。"
      )
    ),
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "提交与受理结果"),
      el("div", { class: "uif-row" }, submit),
      status,
      outcome,
      // U05 的验收写的是"普通用户无需JSON"，所以 RIR 不是这一屏的主面板：它是给要核对
      // 字节的人用的次级查看面，默认收起。内容仍然来自同一次编排，不是第二份台账。
      el(
        "details",
        { class: "plan-rir" },
        el("summary", {}, "查看将提交的 RIR（JSON，供核对）"),
        preview2
      )
    )
  );
}
async function renderPlan(target) {
  await projectPickerPanel(
    target,
    viewLabel("plan"),
    async (projectId) => planComposer(projectId),
    el(
      "p",
      { class: "view-hint" },
      "这一页替普通用户写 RIR：选择宿主与底图后，界面给出将要提交的完整目标包，你审阅的是编排结果而不是 JSON。"
    ),
    "本页会向本机服务提交一个排队任务；不启动宿主，不改动已交付版本。"
  );
}
function analysisPanel(projectId) {
  const layerHost = el("div", { class: "analysis-layer" });
  const correctionHost = el("div", { class: "analysis-correction" });
  const title = el("input", {
    class: "input",
    type: "text",
    maxlength: "120",
    id: "analysis-revision-title",
    placeholder: "修订后的方向标题"
  });
  const notes = el("input", {
    class: "input",
    type: "text",
    maxlength: "600",
    id: "analysis-revision-notes",
    placeholder: "表现备注（逗号分隔，可选）"
  });
  const colorMood = el("input", {
    class: "input",
    type: "text",
    maxlength: "120",
    id: "analysis-revision-color",
    placeholder: "色彩倾向（可选）"
  });
  const typeMood = el("input", {
    class: "input",
    type: "text",
    maxlength: "120",
    id: "analysis-revision-type",
    placeholder: "字体倾向（可选）"
  });
  const target = el(
    "select",
    { class: "input", "aria-label": "要修订的方向版本" },
    el("option", { value: "" }, "选择要修订的方向版本")
  );
  const status = el(
    "p",
    { class: "view-hint", role: "status", "aria-live": "polite" },
    "修订会追加一个新版本；被取代的旧版本只保留为历史，字节不被改写。"
  );
  const submit = el(
    "button",
    { type: "button", class: "primary-btn", id: "analysis-revise" },
    "保存为方向新版本"
  );
  const load = async () => {
    layerHost.replaceChildren(el("p", { class: "view-loading" }, "正在读回设计层…"));
    const data = await apiOrEmpty(
      `/projects/${projectId}/design-layer`,
      OFFLINE.designLayer
    );
    const layer = data.design_layer;
    const chosen = layer.chosen_direction;
    const brief = chosen ? layer.briefs.find((b) => b.brief_id === chosen.brief_id) ?? null : null;
    const binding = layer.active_binding;
    target.replaceChildren(
      el("option", { value: "" }, "选择要修订的方向版本"),
      ...layer.directions.map((d) => el(
        "option",
        { value: d.direction_id },
        `${d.title} · v${d.version}${d.superseded_by ? "（已被取代）" : " · 现行"}`
      ))
    );
    const rows = [
      el("li", { class: "list-item" }, el(
        "div",
        {},
        el("strong", {}, "现行方向"),
        el("small", {}, chosen ? `${chosen.title} · v${chosen.version} · 由 ${chosen.actor ?? "未记录操作者"} 选定` : "尚无现行方向：选择方向是人工判定，界面不替你选。")
      )),
      el("li", { class: "list-item" }, el(
        "div",
        {},
        el("strong", {}, "方法 / 偏好（方向自己的字段）"),
        el("small", {}, chosen ? `色彩 ${chosen.color_mood ?? "未声明"} · 字体 ${chosen.typography_mood ?? "未声明"} · 表现备注 ${(chosen.style_notes ?? []).join("、") || "未声明"}` : "无方向即无方法记录。")
      )),
      el("li", { class: "list-item" }, el(
        "div",
        {},
        el("strong", {}, "来源与知识引用"),
        el("small", {}, brief ? `简报《${brief.title}》v${brief.version} · 目标 ${brief.goals.join("、")} · 约束 ${brief.constraints ?? "无"} · 引用参考 ${brief.reference_asset_ids.length} 个 · spec ${brief.spec_sha256.slice(0, 12)}…` : "未读回：没有现行方向就没有可引用的简报版本。")
      )),
      el("li", { class: "list-item" }, el(
        "div",
        {},
        el("strong", {}, "设计系统契约"),
        el("small", {}, binding ? `${binding.design_system_name} · v${binding.version} · spec ${binding.spec_sha256.slice(0, 12)}… · 绑定于方向 ${binding.direction_id.slice(-8)}` + (binding.superseded_by ? "（该绑定已被更新版本取代）" : " · 现行") : "未绑定：绑定决定后续制作使用的契约，缺失时不假装沿用。")
      ))
    ];
    layerHost.replaceChildren(
      el("ul", { class: "list" }, ...rows),
      el(
        "div",
        { class: "analysis-gaps" },
        stateBlock({
          kind: "unknown",
          title: "已识别结构与推断",
          weight: "neutral",
          producer: "本页不列推断节点，缺的不是入口而是合格的观测来源：analysis/plan_to_rir 这座把平面分解 Plan 转成 RIR 节点的桥已接进两条生产入口（CLI `design-lab analyze` 与 POST …/assets/<img-ID>/analysis，均由 live HTTP 测试按 E2 实跑读回），但本机没有合格的 OCR/分析后端可产出观测（readiness 模型清单 QUALIFIED_LOCAL=0），检测推断的内容因此仍无处读回。",
          next: '接通那一半已完成；剩下的是 owner 裁定是否让某个本地模型合格，或维持"结构节点由人在目标生成包里逐项给出"。在观测有合格来源之前，本页不画任何推断节点，也不把空白读成"没有结构"。'
        }),
        capabilityCardHost("research-insights")
      ),
      ...shapeNoticeRows(data)
    );
    correctionHost.replaceChildren(
      el("label", {}, "要修订的方向版本", target),
      el("label", {}, "修订后的标题", title),
      el("label", {}, "表现备注", notes),
      el(
        "div",
        { class: "uif-row" },
        el("label", { class: "capability-filter" }, "色彩倾向", colorMood),
        el("label", { class: "capability-filter" }, "字体倾向", typeMood)
      ),
      el("div", { class: "uif-row" }, submit),
      status
    );
    submit.onclick = () => {
      if (!target.value) {
        status.textContent = "未选择方向版本：修订必须指明改的是哪一版，界面不替你挑。";
        return;
      }
      submit.disabled = true;
      status.textContent = "正在提交修订…";
      void (async () => {
        try {
          const data2 = await reviseDirection({
            owner: projectId,
            directionId: target.value,
            title: title.value,
            notes: (notes.value || "").split(",").map((n) => n.trim()).filter(Boolean),
            colorMood: colorMood.value.trim() || null,
            typeMood: typeMood.value.trim() || null
          });
          status.textContent = `已保存为版本 ${data2.direction.version}；旧版本只保留为历史。` + (data2.direction.chosen ? "选定结论随新版本带走，但设计系统绑定未跟随，需要在最新版本上重新绑定。" : "该方向未被选定，不涉及绑定。");
          await load();
        } catch (error) {
          status.textContent = "";
          layerHost.append(stateBlock({
            kind: "conflict",
            title: "修订未确认",
            weight: "bad",
            producer: `POST /api/projects/{id}/directions/{dir}/revisions 返回：${revisionHint(error)}`,
            next: "若是 STALE_REVISION，请在现行版本上重做这次修订；旧版本字节不会被改写。"
          }));
        } finally {
          submit.disabled = false;
        }
      })();
    };
  };
  void load();
  return el(
    "div",
    { class: "intake-grid" },
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "判断依据（读回，不重述）"),
      layerHost
    ),
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "本次纠正"),
      correctionHost
    )
  );
}
function capabilityCardHost(capabilityId) {
  const row = CAPABILITY_REGISTRY.find((c) => c.capabilityId === capabilityId);
  return row ? capabilityCard(row) : el("p", { class: "view-hint" }, `（能力登记表无 ${capabilityId} 这一条）`);
}
async function renderAnalysis(target) {
  await projectPickerPanel(
    target,
    viewLabel("analysis"),
    async (projectId) => analysisPanel(projectId),
    el(
      "p",
      { class: "view-hint" },
      "检查设计判断并就地纠正：这一面把方向、简报、绑定与缺口分开列出，推断内容必须标为推断，没有来源的部分直说没有来源。"
    ),
    "本页的修订会写入本机服务并追加新版本；不启动宿主，也不改已交付版本。"
  );
}
const PROMPT_TARGETS = ["image-generation", "video-generation", "3d"];
const REVERSAL_ASSET_ID = /^img-[0-9a-f]{64}$/;
function promptSourceProvenance(source) {
  if (source.kind === "stored") {
    const id = source.brief_id ?? source.direction_id ?? "身份未记录";
    const version = source.version === void 0 ? "版本未记录" : `v${source.version}`;
    return `存过字段原文 · ${id} · ${version} · spec ${source.spec_sha256 ?? "未记录"}`;
  }
  if (source.kind === "framing") {
    return `本页框架句 · 规则：${source.rule ?? "未记录规则"}`;
  }
  return `来源类型 ${source.kind}（既不是 stored 也不是 framing，本页不重新标注）`;
}
function promptErrorDetail(error) {
  const envelope = error?.serviceEnvelope;
  const detail = envelope?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const lines = detail.filter((line) => typeof line === "string");
    return lines.length ? lines.join("；") : "（服务端返回了空的字段说明数组，没有给出可修正的字段）";
  }
  return "（本次回复没有携带 detail）";
}
function promptRefusal(error, route) {
  const envelope = error.serviceEnvelope;
  const code = typeof envelope?.["error"] === "string" ? envelope["error"] : "";
  if (!envelope) {
    return stateBlock({
      kind: "error",
      title: "没有拿到服务端回复",
      weight: "bad",
      producer: `${route} 没有返回可读的回复：${errMsg(error)}。没有回复不等于没有生成——这份文档不落库，但请求是否到达过只有服务端知道。`,
      next: "先确认本机设计服务仍在运行，再重新发起一次生成。装配是确定性的：同样的存过记录与同样的目标得到同一个 composition_id，所以重发同一份内容不会产生第二份文档。"
    });
  }
  return stateBlock({
    kind: "conflict",
    title: `未生成：${code || "服务端给出了一个本页没有名字的拒绝"}`,
    weight: "bad",
    producer: `${route} 返回 ${code || errMsg(error)}；detail：${promptErrorDetail(error)}。本页不替你改字段来"过校验"，也不把这次拒绝显示成已生成。`,
    next: "按 detail 修正后再发起：版本已被取代就改选现行版本，方向不属于这份简报就换回它自己的方向，目标不在接受集合里就按括号里列出的族重选，观测为空就先补观测。"
  });
}
function promptHonestyBlocks(document2) {
  const unknownRows = document2.unknown.length ? document2.unknown.map((row) => el(
    "tr",
    {},
    el("th", { scope: "row" }, row.field),
    el("td", {}, row.reason)
  )) : [el("tr", {}, el(
    "td",
    { colspan: "2" },
    '这份文档没有列出任何 unknown 项；合同要求该列表非空，所以这一行应当当作缺陷去查生成处，而不是读成"没有不知道的"。'
  ))];
  return [
    el("h4", {}, "这份提示词不知道的东西（逐条带原因）"),
    el(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "未知项表（可横向滚动）"
      },
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          el("th", { scope: "col" }, "字段"),
          el("th", { scope: "col" }, "为什么不知道")
        )),
        el("tbody", {}, ...unknownRows)
      )
    ),
    el("h4", {}, "这份文档没有说过的话（逐条来自服务端）"),
    ...document2.claims_not_made.map((line) => el("p", { class: "uif-spec-note" }, line)),
    el("h4", {}, "模型块（读回，不是本页的判定）"),
    el(
      "p",
      { class: "uif-spec-note" },
      `model.executed 读回为 ${String(document2.model.executed)}：没有模型运行过。model.selected 读回为 ${document2.model.selected === null ? "null（未选择任何模型）" : document2.model.selected}。合同层规定这两个字段在本仓当前能产出的每一份文档里都是这个形状，所以这里没有"已生成图像"或"模型已判定"可言。`
    ),
    el("p", { class: "uif-spec-note" }, `文档合同版本 ${document2.schemaVersion}。`)
  ];
}
function compositionReadbackPanel(readback) {
  const doc = readback.document;
  const sectionRows = doc.sections.map((section) => el(
    "tr",
    {},
    el("th", { scope: "row" }, section.kind),
    el("td", {}, section.text),
    el("td", {}, el("span", { class: "mono" }, promptSourceProvenance(section.source)))
  ));
  return el(
    "div",
    { class: "row-card grid-stack" },
    el(
      "p",
      { class: "uif-spec-note" },
      "状态 ",
      en(readback.status),
      " · 文档摘要 ",
      el("span", { class: "mono" }, readback.document_sha256)
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      "装配身份 ",
      el("span", { class: "mono" }, doc.composition_id),
      "（同样的存过记录与同样的目标得到同一个 ID，所以这份读回可以重算并比对）"
    ),
    el("h4", {}, "提示词正文（服务端原文）"),
    el("pre", { class: "mono plan-preview" }, doc.prompt_text),
    el("h4", {}, `逐段出处（${doc.sections.length} 段）`),
    el(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "提示词逐段出处表（可横向滚动）"
      },
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          el("th", { scope: "col" }, "段别"),
          el("th", { scope: "col" }, "正文"),
          el("th", { scope: "col" }, "出处（读回）")
        )),
        el("tbody", {}, ...sectionRows)
      )
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      `存过字段段落 ${doc.observed.length} 段，框架句 ${doc.framing.length} 段：前者每段带它自己那条记录的 spec_sha256，后者只带本页拥有的标注规则。`
    ),
    ...promptHonestyBlocks(doc)
  );
}
function reversalReadbackPanel(readback) {
  const doc = readback.document;
  const layerRows = doc.layers.map((layer) => el(
    "tr",
    {},
    el("th", { scope: "row" }, el("span", { class: "mono" }, layer.id)),
    el("td", {}, layer.type),
    el("td", {}, layer.name),
    el("td", {}, `${layer.bounds.x}, ${layer.bounds.y} · ${layer.bounds.width}×${layer.bounds.height}`),
    el("td", {}, `${String(layer.confidence.score)} · ${layer.confidence.method}`)
  ));
  return el(
    "div",
    { class: "row-card grid-stack" },
    el(
      "p",
      { class: "uif-spec-note" },
      "状态 ",
      en(readback.status),
      " · 文档摘要 ",
      el("span", { class: "mono" }, readback.document_sha256)
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      "反推身份 ",
      el("span", { class: "mono" }, doc.reversal_id),
      " · 绑定字节 ",
      el("span", { class: "mono" }, doc.asset.sha256)
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      `观测模块 ${doc.observation.module || "（未填写）"} · 分解 ${doc.observation.decomposition_id || "未提供（服务端为本次观测派生了自己的分解身份）"} · RIR 摘要 ${doc.observation.rir_sha256} · 区域数 ` + String(doc.observation.object_count)
    ),
    el("h4", {}, "反推正文（服务端原文）"),
    el("pre", { class: "mono plan-preview" }, doc.prompt_text),
    el("h4", {}, `观测到的区域（${doc.layers.length} 个；置信度属于你提交的那个观测模块）`),
    el(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "反推区域表（可横向滚动）"
      },
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          ...["节点 ID", "类型", "名称", "边界", "置信度 · 方法"].map((h) => el("th", { scope: "col" }, h))
        )),
        el("tbody", {}, ...layerRows)
      )
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      `绑定画布 ${doc.asset.width}×${doc.asset.height} · ${doc.asset.media_type} · 资产 ID `
    ),
    el("p", { class: "mono" }, doc.asset.id),
    ...promptHonestyBlocks(doc)
  );
}
function promptSelectPlaceholder(unread, count, noun, action) {
  return unread ? `未读回：${noun}未取回，不能断言为空` : count > 0 ? `选择${noun}（共 ${count} 项）` : `尚无${noun}：${action}`;
}
function promptReviewStateLabel(row) {
  switch (row.review_state) {
    case "ACCEPTED":
      return "已有人工接受";
    case "DECLINED":
      return "已有人工拒绝";
    case "NOT_CURRENT":
      return "签名描述的是另一份字节";
    case "UNREVIEWED":
      return "没人签过";
    default:
      return `状态未读回（${row.review_state ?? "字段缺失"}）`;
  }
}
function promptResultsBody(projectId, data, reload, flags) {
  const rows = data.results ?? [];
  const offline = disconnectedNotice(data);
  const target = el(
    "select",
    { class: "input", id: "prompt-review-result" },
    el("option", { value: "" }, rows.length ? "选择一条已存结果" : "没有可签署的结果：本项目还没有产过提示词"),
    ...rows.map((row) => el(
      "option",
      { value: row.result_id ?? "" },
      `第 ${row.revision ?? "?"} 版 · ${row.kind ?? "类型未记录"} · ${(row.result_id ?? "身份未记录").slice(-8)} · ${promptReviewStateLabel(row)}`
    ))
  );
  const decision = el(
    "select",
    { class: "input", id: "prompt-review-decision" },
    el("option", { value: "ACCEPTED" }, "接受"),
    el("option", { value: "DECLINED" }, "拒绝")
  );
  const reviewer = el("input", {
    class: "input",
    id: "prompt-review-reviewer",
    type: "text",
    maxlength: "120",
    placeholder: "裁决人（你自己的名字，服务端要求具名）"
  });
  const note = el("textarea", { class: "input", id: "prompt-review-note", maxlength: "2000" });
  const status = el("p", { class: "view-hint", role: "status", "aria-live": "polite" }, "");
  const outcome = el("div", { class: "spaced-top" });
  const submit = el("button", {
    type: "button",
    class: "primary-btn",
    id: "prompt-review-submit",
    disabled: rows.length ? null : ""
  }, "记录人工签署");
  submit.onclick = () => {
    void (async () => {
      const id = target.value;
      const who = reviewer.value.trim();
      if (!id) {
        status.textContent = "未提交：没有选中任何已存结果。";
        return;
      }
      if (!who) {
        status.textContent = "未提交：裁决人未署名。服务端只接受具名的人工签署。";
        return;
      }
      const body = {
        decision: decision.value,
        reviewer: who,
        reviewer_kind: "human",
        reviewed_at: (/* @__PURE__ */ new Date()).toISOString(),
        note: note.value.trim() || null
      };
      submit.disabled = true;
      status.textContent = "提交中…";
      try {
        await api(`/projects/${projectId}/prompt-results/${id}/review`, body);
        await reload();
        status.textContent = decision.value === "ACCEPTED" ? "已记录人工接受。接受只说明这个名字认领了这条摘要对应的字节：它没有导出、没有发送，也没有运行任何模型。" : "已记录人工拒绝。这条结果仍在库里——被拒绝本身也是留痕。";
      } catch (error) {
        const envelope = error.serviceEnvelope;
        outcome.replaceChildren(promptRefusal(
          error,
          "POST /api/projects/{id}/prompt-results/{result}/review"
        ));
        status.textContent = `未记录：${typeof envelope?.error === "string" ? envelope.error : errMsg(error)}` + (typeof envelope?.detail === "string" && envelope.detail ? ` —— ${envelope.detail}` : "") + "。服务端未写入任何签署。";
      } finally {
        submit.disabled = false;
      }
    })().catch((error) => setStatus(errMsg(error), true));
  };
  return el(
    "div",
    { class: "panel spaced-top", id: "prompt-results-panel" },
    el("h3", {}, "已存提示词结果与人工签署"),
    ...flags.notice ? [el("p", { class: "view-hint" }, flags.notice)] : [],
    el(
      "p",
      { class: "view-hint" },
      `${flags.countUnread ? "结果数未读回" : `读回 ${data.result_count ?? 0} 条结果`}，${flags.acceptedUnread ? "接受数未读回" : `其中 ${data.accepted_count ?? 0} 条有人工接受`}` + (data.unreadable_count ? `；另有 ${data.unreadable_count} 行的文档读不出来` : "") + "。每条结果的身份就是文档自带的 ID：同样的存过记录与同样的目标重新装配，得到的是同一条，而不是第二份。"
    ),
    offline ? stateBlock({
      kind: "error",
      title: "没有读到服务端的结果清单",
      weight: "bad",
      producer: "GET /api/projects/{id}/prompt-results 没有返回可读回复。",
      next: "先确认本机设计服务仍在运行；这一面板不做本地清单，也不补一份内存里的假记录。"
    }) : el(
      "table",
      { class: "data" },
      el("thead", {}, el(
        "tr",
        {},
        el("th", {}, "修订"),
        el("th", {}, "类型"),
        el("th", {}, "身份尾号"),
        el("th", {}, "摘要尾号"),
        el("th", {}, "生成时间"),
        el("th", {}, "签署状态")
      )),
      el("tbody", {}, ...rows.map((row) => el(
        "tr",
        {},
        el("td", {}, String(row.revision ?? "未记录")),
        el("td", {}, row.kind ?? "未记录"),
        el("td", {}, (row.result_id ?? "未记录").slice(-8)),
        el("td", {}, (row.content_sha256 ?? "未记录").replace(/^sha256:/, "").slice(-8)),
        el("td", {}, row.created_at ?? "未记录"),
        el(
          "td",
          {},
          el("span", { lang: "en" }, row.review_state ?? "unreadable"),
          " · ",
          promptReviewStateLabel(row),
          row.review?.reviewer ? `（${row.review.reviewer} @ ${row.review.reviewed_at ?? "时间未读回"}）` : "",
          row.executed === true ? " · 这一行声称执行过模型：服务端不该发出这样的文档" : ""
        )
      )))
    ),
    ...rows.length || offline ? [] : [el(
      "p",
      { class: "view-hint" },
      flags.resultsUnread ? "results 字段未读回：这一屏不知道库里有没有结果，界面不替服务端填一个空清单。" : '表里没有行：不是"没有可签的"，而是这台服务还没为该项目产出过提示词。'
    )],
    ...(data.does_not_say ?? []).map((line) => el("p", { class: "uif-spec-note" }, line)),
    el(
      "div",
      { class: "uif-spec-block" },
      el("h3", {}, "人工签署（Human Gate 的桌面入口）"),
      el(
        "p",
        { class: "uif-spec-note" },
        '服务端只接受 reviewer_kind="human" 且具名的签署，页面因此不提供代理身份选项。名字与时间是你声称的，服务端不验证这个人是否真的看过内容；签署引用的是这条结果的 content_sha256，改了输入得到的是新文档与新摘要，旧签名不再描述现在这一份。'
      ),
      el("label", {}, "结果", target),
      el("label", {}, "裁决", decision),
      el("label", {}, "裁决人", reviewer),
      el("label", {}, "备注（可选）", note),
      el("div", { class: "uif-row" }, submit),
      status,
      outcome
    )
  );
}
async function promptIntelligencePanel(projectId) {
  const layerData = await apiOrEmpty(
    `/projects/${projectId}/design-layer`,
    OFFLINE.designLayer
  );
  const assetsData = await apiOrEmpty(
    `/projects/${projectId}/assets`,
    OFFLINE.assets
  );
  const layer = layerData.design_layer;
  const briefsUnread = Boolean(shapeFieldMissing(layerData, "design_layer.briefs") || disconnectedNotice(layerData));
  const assetsUnread = Boolean(shapeFieldMissing(assetsData, "assets") || disconnectedNotice(assetsData));
  const reversalAssets = assetsData.assets.filter((a) => REVERSAL_ASSET_ID.test(a.id));
  const resultsHost = el("div", { id: "prompt-results-host" });
  const reloadResults = async () => {
    const data = await apiOrEmpty(
      `/projects/${projectId}/prompt-results`,
      {}
    );
    const notice = shapeNotice(data);
    resultsHost.replaceChildren(promptResultsBody(projectId, data, reloadResults, {
      notice,
      resultsUnread: shapeFieldMissing(data, "results"),
      countUnread: shapeFieldMissing(data, "result_count"),
      acceptedUnread: shapeFieldMissing(data, "accepted_count")
    }));
  };
  await reloadResults();
  const briefSelect = el(
    "select",
    { class: "input", id: "prompt-brief" },
    el("option", { value: "" }, promptSelectPlaceholder(
      briefsUnread,
      layer.briefs.length,
      "简报",
      "先在「输入与目标」建立这份项目的第一份简报"
    )),
    ...layer.briefs.map((brief) => el(
      "option",
      { value: brief.brief_id },
      `${brief.title} · v${brief.version} · ${brief.brief_id.slice(-8)}` + (brief.superseded_by ? "（已被取代，服务端会拒绝这次装配）" : "")
    ))
  );
  const directionSelect = el("select", { class: "input", id: "prompt-direction" });
  const targetSelect = el(
    "select",
    { class: "input", id: "prompt-target" },
    ...PROMPT_TARGETS.map((family) => el("option", { value: family }, family))
  );
  const composeOutcome = el("div", { class: "spaced-top", id: "prompt-compose-outcome" });
  const composeStatus = el("p", {
    class: "view-hint",
    id: "prompt-compose-status",
    role: "status",
    "aria-live": "polite"
  }, "");
  const composeButton = el("button", {
    type: "button",
    class: "primary-btn",
    id: "prompt-compose",
    disabled: layer.briefs.length ? null : ""
  }, "生成提示词并读回（同时存为一条可签署的结果）");
  const fillDirections = () => {
    const briefId = briefSelect.value;
    const rows = layer.directions.filter((d) => !briefId || d.brief_id === briefId);
    directionSelect.replaceChildren(
      el("option", { value: "" }, "不指定方向（只装配这份简报自己）"),
      ...rows.map((d) => el(
        "option",
        { value: d.direction_id },
        `${d.title} · v${d.version} · ${d.direction_id.slice(-8)}${d.chosen ? " · 已选定" : " · 未选定"}` + (d.superseded_by ? "（已被取代，服务端会拒绝）" : "")
      ))
    );
  };
  fillDirections();
  briefSelect.onchange = () => {
    fillDirections();
  };
  composeButton.onclick = () => {
    if (!briefSelect.value) {
      composeStatus.textContent = "未选择简报：装配必须有明确来源，界面不替你挑一份简报。";
      return;
    }
    composeButton.disabled = true;
    composeOutcome.replaceChildren();
    composeStatus.textContent = "正在提交并等待读回…";
    void (async () => {
      try {
        const readback = await api(
          `/projects/${projectId}/prompts`,
          {
            brief_id: briefSelect.value,
            direction_id: directionSelect.value || null,
            target: targetSelect.value
          }
        );
        composeStatus.textContent = "";
        composeOutcome.replaceChildren(compositionReadbackPanel(readback));
        await reloadResults();
      } catch (error) {
        composeStatus.textContent = "";
        composeOutcome.replaceChildren(promptRefusal(
          error,
          `POST /api/projects/{id}/prompts（目标 ${targetSelect.value}）`
        ));
      } finally {
        composeButton.disabled = !briefSelect.value;
      }
    })();
  };
  const assetSelect = el(
    "select",
    { class: "input", id: "prompt-reverse-asset" },
    el("option", { value: "" }, promptSelectPlaceholder(
      assetsUnread,
      reversalAssets.length,
      "可反推的图像资产",
      "先在「输入与目标」导入 PNG/JPEG；没有存过的字节就没有可绑定的反推"
    )),
    ...reversalAssets.map((a) => el(
      "option",
      { value: a.id },
      `${a.id.slice(-8)} · ${a.media_type} · ${a.width}×${a.height} · 权利 ${a.rights}`
    ))
  );
  const moduleInput = el("input", {
    class: "input",
    id: "prompt-observation-module",
    type: "text",
    maxlength: "120",
    placeholder: "观测模块名（来自你的观测来源）"
  });
  const decompositionInput = el("input", {
    class: "input",
    id: "prompt-decomposition",
    type: "text",
    maxlength: "120",
    placeholder: "decomposition_id（留空表示没有）"
  });
  const detectionsInput = el("textarea", {
    class: "input",
    id: "prompt-detections",
    rows: "10",
    spellcheck: "false",
    "aria-label": "detections 观测数组 JSON"
  }, "[]");
  const reverseOutcome = el("div", { class: "spaced-top" });
  const reverseStatus = el("p", {
    class: "view-hint",
    role: "status",
    "aria-live": "polite"
  }, "");
  const reverseButton = el("button", {
    type: "button",
    class: "primary-btn",
    id: "prompt-reverse",
    disabled: reversalAssets.length ? null : ""
  }, "按这些观测生成反推并读回");
  reverseButton.onclick = () => {
    if (!assetSelect.value) {
      reverseStatus.textContent = "未选择资产：反推必须绑定一条已存字节，界面不替你猜一张图。";
      return;
    }
    let detections;
    try {
      detections = JSON.parse(detectionsInput.value);
    } catch (error) {
      reverseStatus.textContent = `正文不是合法 JSON（界面本地检查，未提交，服务端未收到任何请求）：${errMsg(error)}`;
      return;
    }
    if (!Array.isArray(detections)) {
      reverseStatus.textContent = "detections 必须是数组（界面本地检查，未提交）：空数组由服务端作为 NO_OBSERVATIONS 拒绝，非数组由服务端作为字段校验失败拒绝，两种都不该由界面替用户改成能过校验的形状。";
      return;
    }
    reverseButton.disabled = true;
    reverseOutcome.replaceChildren();
    reverseStatus.textContent = "正在提交并等待读回…";
    void (async () => {
      try {
        const readback = await api(
          `/projects/${projectId}/assets/${assetSelect.value}/prompt-reversal`,
          {
            module: moduleInput.value,
            detections,
            decomposition_id: decompositionInput.value.trim() || null
          }
        );
        reverseStatus.textContent = "";
        reverseOutcome.replaceChildren(reversalReadbackPanel(readback));
        await reloadResults();
      } catch (error) {
        reverseStatus.textContent = "";
        reverseOutcome.replaceChildren(promptRefusal(
          error,
          "POST /api/projects/{id}/assets/{img-ID}/prompt-reversal"
        ));
      } finally {
        reverseButton.disabled = !assetSelect.value;
      }
    })();
  };
  return el(
    "div",
    { class: "grid-stack" },
    el(
      "div",
      { class: "intake-grid" },
      el(
        "div",
        { class: "uif-spec-block" },
        el("h3", {}, "装配提示词（只读已存记录）"),
        el(
          "p",
          { class: "uif-spec-note" },
          "每一句要么是某条存过字段的原文（带它自己的 spec_sha256），要么是本页的框架句（带规则名）。本页不推断画面内容：没有存过的受众、色板、情绪一律不出现在正文里，而是进 unknown 并说明为什么不知道。"
        ),
        el("label", {}, "简报", briefSelect),
        el("label", {}, "方向（可留空）", directionSelect),
        el("label", {}, "目标", targetSelect),
        el("div", { class: "uif-row" }, composeButton),
        composeStatus,
        composeOutcome
      ),
      el(
        "div",
        { class: "uif-spec-block" },
        el("h3", {}, "反推提示词（观测由你提供）"),
        el(
          "p",
          { class: "uif-spec-note" },
          "本仓没有合格的本地视觉后端（readiness 雷达 QUALIFIED_LOCAL=0，每条目 default_enabled 为 false），所以没有任何代码读过这些像素。正文里的文字与几何全部来自你在下面粘贴的观测，连同它们的置信度一起带出，不会被重新标注成本产品的观察。"
        ),
        el("label", {}, "资产", assetSelect),
        el("label", {}, "观测模块", moduleInput),
        el("label", {}, "detections（JSON 数组）", detectionsInput),
        el("label", {}, "decomposition_id（可留空）", decompositionInput),
        el("div", { class: "uif-row" }, reverseButton),
        reverseStatus,
        reverseOutcome
      )
    ),
    resultsHost,
    el(
      "p",
      { class: "uif-spec-note" },
      "本页写两条生成路由，两条都会把产出的文档存成一条可寻址的结果：装配返回的文档由存过记录推导，重发同一份请求得到同一个 ID，因此得到的是同一条结果而不是第二份；反推返回的文档绑定该资产的 sha256 与本次观测的 RIR 摘要。两者都不含模型执行与宿主调用，人工验收是下面那个面板里另一次具名写入，不是生成这一步的副作用。"
    ),
    ...assetsData.assets.length > reversalAssets.length ? [el(
      "p",
      { class: "view-hint" },
      `本项目读回 ${assetsData.assets.length} 项资产，其中 ${reversalAssets.length} 项是这条反推路由接受的图像资产身份（img- 前缀加 64 位十六进制）；其余身份这条路由不接受，本页不列出来让人误以为可以反推。`
    )] : [],
    ...shapeNoticeRows(layerData, assetsData)
  );
}
async function renderPromptIntelligence(target) {
  await projectPickerPanel(
    target,
    viewLabel("prompt-intelligence"),
    async (projectId) => promptIntelligencePanel(projectId),
    el(
      "p",
      { class: "view-hint" },
      "提示词的两端都在这一页：从已存的简报与方向装配一段可逐段追溯的正文，或把你提供的观测转成一条已存资产的反推描述。产出的文档会存下来并可被具名人工签署；两个方向都不运行模型、不调用宿主、也不替人验收。"
    ),
    "本页向本机服务提交生成请求并把产出存为一条结果（只写本机状态库，不外发）；签署同样只写本机，不导出、不发送，也不修改任何已交付版本。"
  );
}
function modelPlacementLine(counts) {
  const entries = Object.entries(counts);
  return entries.length ? entries.map(([kind, value]) => `${kind} ${String(value)}`).join(" · ") : "位置分布未读回";
}
async function modelSelectionPanel(projectId, candidates) {
  const read = await apiOrEmpty(
    `/projects/${projectId}/model-selection`,
    {}
  );
  const state = read.state ?? null;
  const selection = read.selection ?? null;
  const unread = state === void 0 || state === null;
  const modelSelect = el(
    "select",
    { class: "input", id: `ms-model-${projectId}` },
    el("option", { value: "" }, candidates.length ? "选择候选（来自读回）" : "候选未读回"),
    ...candidates.map((row) => el(
      "option",
      { value: row.model_id },
      `${row.model_id} · ${row.family} · ${row.placement ?? "未记录"} · ${row.radar_state}`
    ))
  );
  const kindSelect = el(
    "select",
    { class: "input", id: `ms-kind-${projectId}` },
    el("option", { value: "" }, "谁在做这次选择（必选）"),
    el("option", { value: "human" }, "我本人（human）"),
    el("option", { value: "agent" }, "代理（agent）")
  );
  const status = el("p", { class: "view-hint", role: "status", "aria-live": "polite" }, "");
  const outcome = el("div", { class: "spaced-top" });
  const submit = async (body) => {
    const kind = kindSelect.value;
    if (!kind) {
      status.textContent = "未记录：先说明是谁在做这次选择（界面本地检查，未提交）。";
      return;
    }
    if (body.model_id === null && !body.declared_unused) {
      status.textContent = "未记录：要么选一个候选，要么显式选择「不使用」（界面本地检查，未提交）。";
      return;
    }
    status.textContent = "正在提交并等待读回…";
    outcome.replaceChildren();
    try {
      const written = await api(
        `/projects/${projectId}/model-selection/choose`,
        {
          model_id: body.model_id,
          declared_unused: body.declared_unused,
          actor: "workbench-operator",
          actor_kind: kind
        }
      );
      status.textContent = "";
      outcome.replaceChildren(el(
        "p",
        { class: "view-hint" },
        `已记录 rev${String(written.revision_count)} · ${written.replayed ? "与上一条相同，未追加新修订" : "新修订已追加"} · 状态 ` + en(String(written.state))
      ));
      outcome.append(await modelSelectionPanel(projectId, candidates));
    } catch (error) {
      status.textContent = "";
      outcome.replaceChildren(promptRefusal(
        error,
        `POST /api/projects/{id}/model-selection/choose`
      ));
    }
  };
  const chooseButton = el(
    "button",
    {
      type: "button",
      class: "primary-btn",
      id: `ms-choose-${projectId}`,
      disabled: candidates.length ? null : ""
    },
    "记录这次选择"
  );
  chooseButton.onclick = () => void submit({
    model_id: modelSelect.value || null,
    declared_unused: false
  });
  const declineButton = el("button", {
    type: "button",
    class: "ghost-btn",
    id: `ms-decline-${projectId}`
  }, "不使用模型（显式记录）");
  declineButton.onclick = () => void submit({ model_id: null, declared_unused: true });
  const stateLine = unread ? "当前选择未读回：这次 GET 没有带回 state，本页不猜。" : state === "NEVER_ASKED" ? '当前状态 NEVER_ASKED：这个项目还没人被问过，既不是"已选择不使用"，也不是"没有答案"。' : state === "DECLINED" ? `当前状态 DECLINED：操作者显式记录了「不使用」${selection ? `（rev${String(selection.revision)} · ${selection.actor_kind} · ${selection.recorded_at}）` : ""}。这是决定，不是缺数据。` : `当前状态 CHOSEN：${selection?.model_id ?? "未记录"} · rev${String(selection?.revision ?? 0)} · 由 ${selection?.actor_kind ?? "未记录"}「${selection?.actor ?? "未记录"}」记录于 ${selection?.recorded_at ?? "未记录"}。快照（选择当时目录的说法）：${selection?.snapshot?.placement ?? "未记录"} / ${selection?.snapshot?.radar_state ?? "未记录"} / ${selection?.snapshot?.machine_state ?? "未记录"} / 权重摘要 ${String(selection?.snapshot?.weights_recorded ?? 0)} 条 / qualified_local ${String(selection?.snapshot?.qualified_local ?? false)}。`;
  return el(
    "div",
    { class: "grid-stack" },
    el("p", { class: "view-hint" }, stateLine),
    ...shapeNoticeRows(read),
    ...typeof read.revision_count === "number" ? [el(
      "p",
      { class: "view-hint" },
      `决策路径共 ${String(read.revision_count)} 个修订；改主意是追加新修订，不覆盖旧决定。`
    )] : [],
    el(
      "div",
      { class: "uif-row" },
      el("label", { class: "capability-filter" }, "候选（来自读回）", modelSelect),
      el("label", { class: "capability-filter" }, "谁在做这次选择", kindSelect),
      chooseButton,
      declineButton
    ),
    status,
    outcome,
    ...Array.isArray(read.does_not_say) ? read.does_not_say.map((line) => el("p", { class: "uif-spec-note" }, line)) : []
  );
}
async function renderModelSelection(target) {
  target.replaceChildren(el("p", { class: "view-loading" }, "正在读回模型目录…"));
  const catalog = await apiOrEmpty("/models", OFFLINE.models);
  const caps = await apiOrEmpty("/capabilities", OFFLINE.capabilities);
  const env = await apiOrEmpty("/environment", OFFLINE.environment);
  const offline = Boolean(disconnectedNotice(catalog));
  const modelsUnread = offline || shapeFieldMissing(catalog, "models");
  const selectionUnread = offline || shapeFieldMissing(catalog, "selection");
  const countsUnread = offline || shapeFieldMissing(catalog, "counts");
  const families = Array.from(new Set(catalog.models.map((row) => row.family ?? ""))).filter((value) => value !== "").sort();
  const familyFilter = el(
    "select",
    {
      class: "input",
      id: "model-family",
      "aria-label": "按读回的族过滤候选"
    },
    el("option", { value: "" }, families.length ? "全部族" : "族未读回"),
    ...families.map((family) => el("option", { value: family }, family))
  );
  const modelTable = el("div", {
    class: "table-wrap",
    tabindex: "0",
    role: "region",
    "aria-label": "模型候选读回表（可横向滚动）"
  });
  const MODEL_COLUMNS = [
    "候选",
    "族",
    "来源位置",
    "radar 状态",
    "机器状态",
    "许可 · 商用位",
    "默认启用",
    "权重摘要数",
    "阻塞原因"
  ];
  const paint = () => {
    const keep = familyFilter.value;
    const rows = catalog.models.filter((row) => !keep || (row.family ?? "") === keep);
    if (!rows.length) {
      modelTable.replaceChildren(el(
        "table",
        { class: "table" },
        el("tbody", {}, el("tr", {}, emptyTd(
          catalog,
          modelsUnread ? "未读回" : "本目录无模型候选行",
          modelsUnread ? "GET /api/models 没有把 models 带回来，本页不补任何名字。" : "这份读回里一行都没有；服务端在目录为空时本身会拒绝并命名原因，所以这一行值得核对生成处。",
          MODEL_COLUMNS.length
        )))
      ));
      return;
    }
    modelTable.replaceChildren(
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          ...MODEL_COLUMNS.map((h) => el("th", { scope: "col" }, h))
        )),
        el("tbody", {}, ...rows.map((row) => el(
          "tr",
          {},
          el("th", { scope: "row" }, row.model_id),
          el("td", {}, row.family ?? "未记录"),
          el("td", {}, row.placement ? en(row.placement) : "未记录"),
          el("td", {}, en(row.radar_state ?? "未记录")),
          el("td", {}, row.machine_state ? en(row.machine_state) : "未记录"),
          el("td", {}, row.license_id ?? "未记录许可"),
          el("td", {}, String(row.default_enabled)),
          el("td", {}, `${String(row.weights_recorded)} · ${row.weights_state ? WEIGHTS_STATE_LABELS[row.weights_state] : "未记录"}`),
          el("td", {}, row.blocking_reason ?? "（无记录）")
        )))
      )
    );
  };
  familyFilter.onchange = paint;
  paint();
  const WEIGHTS_STATE_LABELS = {
    RECORDED: "已登记摘要",
    REGISTERED_NONE: "登记为空",
    UNSTATED: "未说明"
  };
  const endpointColumns = [
    "提供方",
    "端点引用",
    "能力（读回）",
    "local_first",
    "许可",
    "许可风险",
    "证据级"
  ];
  const endpointRows = catalog.endpoints.length ? catalog.endpoints.map((row) => el(
    "tr",
    {},
    el("th", { scope: "row" }, row.provider_id),
    el("td", {}, el("span", { class: "mono" }, row.endpoint_ref ?? "未记录")),
    el("td", {}, (row.capabilities ?? []).join("、") || "未记录"),
    el("td", {}, row.local_first === null ? "未记录" : String(row.local_first)),
    el("td", {}, row.license ?? "未记录许可"),
    el("td", {}, row.license_risk ? en(row.license_risk) : "未记录"),
    el("td", {}, row.evidence_level ? en(row.evidence_level) : "未记录")
  )) : [el("tr", {}, emptyTd(
    catalog,
    shapeFieldMissing(catalog, "endpoints") ? "未读回" : "本目录无端点行",
    shapeFieldMissing(catalog, "endpoints") ? "GET /api/models 没有把 endpoints 带回来。" : "provider 登记里没有可读的端点行。",
    endpointColumns.length
  ))];
  const cacheRoot = env.roots["model_cache"];
  const modelsInLibrary = caps.capabilities.filter((row) => row.kind === "model").length;
  const head = el(
    "div",
    { class: "page-head" },
    el(
      "div",
      {},
      el("h2", {}, "模型选择"),
      el("p", {}, '只读回服务端已经登记的模型候选与可调用端点，两份清单并列呈现、不做合并。本页不维护模型名单，不写死族名，不显示任何未经读回的资格。选择按项目记录：记下的只是"谁在什么时候选了哪个"，不代表加载、推理或发送。')
    ),
    el("div", { class: "page-actions" })
  );
  const projects2 = await apiOrEmpty("/projects", OFFLINE.projects);
  const projectSelect = el(
    "select",
    { class: "input", id: "model-selection-project" },
    el("option", { value: "" }, projects2.projects.length ? "选择项目" : "尚无项目"),
    ...projects2.projects.map((row) => el(
      "option",
      { value: row.id },
      `${row.name} · ${row.id.slice(-8)}`
    ))
  );
  const selectionHost = el(
    "div",
    { class: "panel" },
    el("h3", {}, "本项目的选择（读回 + 记录）"),
    el("p", { class: "view-hint" }, "先选一个项目：选择是记在项目上的，不是一个全局开关。")
  );
  const loadSelection = async () => {
    if (!projectSelect.value) {
      selectionHost.replaceChildren(
        el("h3", {}, "本项目的选择（读回 + 记录）"),
        el(
          "p",
          { class: "view-hint" },
          projects2.projects.length ? "未选择项目：本页不替操作者挑一个项目来记录选择。" : "尚无项目可读回：没有项目就没有可记录选择的作用域。"
        )
      );
      return;
    }
    selectionHost.replaceChildren(
      el("h3", {}, "本项目的选择（读回 + 记录）"),
      el("p", { class: "view-loading" }, "正在读回当前选择…")
    );
    selectionHost.append(await modelSelectionPanel(projectSelect.value, catalog.models));
  };
  projectSelect.onchange = () => void loadSelection();
  void loadSelection();
  const choicePanel = el(
    "div",
    { class: "panel" },
    el("label", { class: "capability-filter" }, "项目（选择记在这个项目上）", projectSelect),
    selectionHost
  );
  const candidatePanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, `模型候选（读回 ${modelsUnread ? "未读回" : String(catalog.models.length)} 行）`),
    el(
      "p",
      { class: "view-hint" },
      countsUnread ? `${disconnectedNotice(catalog) || shapeNotice(catalog)}，所以本页不显示任何计数` : `合格本地模型 ${String(catalog.counts.qualified_local)} · default_enabled 为 true ${String(catalog.counts.default_enabled_true)} · 有权重摘要 ${String(catalog.counts.weights_recorded)} · 来源位置 ${modelPlacementLine(catalog.counts.placement)}。这些数是从登记里数出来的，不是本页判定的：本目录不为任何一行提升资格。`
    ),
    el("label", { class: "capability-filter" }, "族（取自读回值）", familyFilter),
    modelTable
  );
  const joinLine = shapeFieldMissing(catalog, "join") || offline ? "合并关系未读回：本次读回没有带回 join，所以本页不说两份清单是什么关系。" : `合并关系读回为 join.key ${catalog.join.key === null ? "null（服务端自己给的）" : catalog.join.key ?? "未记录"}。原因原文：${catalog.join.reason || "（本次读回没有带原因）"}`;
  const endpointPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, `可调用端点（读回 ${shapeFieldMissing(catalog, "endpoints") || offline ? "未读回" : String(catalog.endpoints.length)} 行）`),
    el(
      "div",
      {
        class: "table-wrap",
        tabindex: "0",
        role: "region",
        "aria-label": "可调用端点读回表（可横向滚动）"
      },
      el(
        "table",
        { class: "table" },
        el("thead", {}, el(
          "tr",
          {},
          ...endpointColumns.map((h) => el("th", { scope: "col" }, h))
        )),
        el("tbody", {}, ...endpointRows)
      )
    ),
    el("p", { class: "view-hint" }, joinLine),
    el(
      "p",
      { class: "view-hint" },
      "这两张表来自同一次 GET /api/models。把它们合成一张会造出一层数据不支持的关系，而那正是本项目点名的失败形状，所以本页永远分列。"
    )
  );
  const ruleLines = selectionUnread ? [el(
    "p",
    { class: "uif-spec-note" },
    "规则列表未读回：本次读回没有带回 selection.rules，本页不替它写规则。"
  )] : catalog.selection.rules.map((rule) => el("p", { class: "uif-spec-note" }, rule));
  const claimLines = shapeFieldMissing(catalog, "claims_not_made") || offline ? [el(
    "p",
    { class: "uif-spec-note" },
    "claims_not_made 未读回：本页不替服务端编它没说过的话。"
  )] : catalog.claims_not_made.map((line) => el("p", { class: "uif-spec-note" }, line));
  const selectionPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "选择在这里意味着什么"),
    el(
      "p",
      { class: "view-hint" },
      selectionUnread ? `${disconnectedNotice(catalog) || shapeNotice(catalog)}，所以本页不显示 transport 或 executed 的值，也不按记忆写一个。` : '本页不锁定模型：选择是一次被记录的动作，不改变任何一行的合格状态，而本仓没有把素材送到任何地方的通道，所以这里没有"已应用"可说。'
    ),
    selectionUnread ? el(
      "p",
      { class: "view-hint" },
      "selection.mode / transport / executed 三个值本次没有读回，所以这里不显示它们，也不按仓内记忆写一个。"
    ) : el(
      "p",
      { class: "view-hint" },
      "selection.mode ",
      en(catalog.selection.mode || "未记录"),
      " · selection.transport ",
      en(catalog.selection.transport || "未记录"),
      " · selection.executed ",
      String(catalog.selection.executed),
      "（三个值都取自读回）"
    ),
    el(
      "p",
      { class: "uif-spec-note" },
      '「记录这次选择」写的是 POST /api/projects/<id>/model-selection/choose：它把"谁在什么时候选了哪个"记在**这个项目**上，提示词文档随后会原样带出这条选择（model.selected），但 model.executed 恒为 false —— 记录不等于加载、不等于推理、不等于发送。改主意是追加新修订，旧修订仍是证据。'
    ),
    el("h4", {}, "选择规则（逐条来自服务端）"),
    ...ruleLines,
    el("h4", {}, "这份目录没有说过的话（逐条来自服务端）"),
    ...claimLines
  );
  const libraryUnread = Boolean(disconnectedNotice(caps)) || shapeFieldMissing(caps, "capabilities");
  const crossPanel = el(
    "div",
    { class: "panel" },
    el("h3", {}, "旁证：能力库投影与环境路径事实"),
    el(
      "p",
      { class: "view-hint" },
      libraryUnread ? `${disconnectedNotice(caps) || shapeNotice(caps)}，所以本页不给出旁证行数` : `GET /api/capabilities 读回 ${caps.counts.total} 条，其中 kind 为 model 的 ${String(modelsInLibrary)} 条；来源标注 ${Object.entries(caps.sources).map(([key, value]) => `${key}=${value}`).join(" · ") || "未提供"}。那是同一批登记在能力库里的投影，本页用它做旁证而不是当第二个权威：服务自己的说法是 ${caps.unmeasuredMeans}。`
    ),
    el("h4", {}, "与模型有关的路径事实"),
    el(
      "p",
      { class: "view-hint" },
      "路径诊断状态 ",
      disconnectedNotice(env) || !env.status ? "未读回" : en(env.status),
      "；" + (cacheRoot && cacheRoot.path ? `模型缓存根 ${cacheRoot.path} · 归属 ${cacheRoot.ownership ?? "未记录"} · 可写 ${String(cacheRoot.writable)}` : "模型缓存根未读回：这条响应里没有可读的 model_cache，本页不猜一个路径。")
    ),
    el(
      "p",
      { class: "view-hint" },
      "本机运行、真实推理、资格判定与许可接受都在别处取证：本页不安装、不取证、不代签许可，也不把目录里的行数说成可用模型数。"
    )
  );
  target.replaceChildren(
    head,
    candidatePanel,
    endpointPanel,
    choicePanel,
    selectionPanel,
    crossPanel,
    ...shapeNoticeRows(catalog, caps, env, projects2)
  );
}
const BAND_MS = 150;
const MAGNET_PX = 3;
const TILT_DEG = 4;
function motionMode() {
  if (typeof window === "undefined" || typeof document === "undefined") return "static";
  let requested = false;
  try {
    requested = new URLSearchParams(window.location.search).get("motion") === "enhanced";
  } catch {
    requested = false;
  }
  if (!requested) return "static";
  return reducedMotion() ? "static" : "enhanced";
}
function reducedMotion() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return true;
  }
}
function move(el2, x, y, extra) {
  el2.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)${extra}`;
}
function slideReveal(el2) {
  el2.style.transform = "translate3d(0,10px,0)";
  requestAnimationFrame(() => {
    el2.style.transition = `transform ${BAND_MS}ms cubic-bezier(.2,0,0,1)`;
    el2.style.transform = "";
    setTimeout(() => {
      el2.style.transition = "";
    }, BAND_MS + 40);
  });
}
const PARTICLE_COUNT = 24;
const PARTICLE_INKS = ["#EEF2F5", "#17212B"];
function seeded(i) {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}
function mountAmbientParticles(doc, live) {
  const app = doc.querySelector(".app");
  if (!app) return "no-app-host";
  const existing = doc.querySelector("canvas.motion-particles");
  const canvas = existing || doc.createElement("canvas");
  if (!existing) {
    canvas.className = "motion-particles";
    canvas.setAttribute("aria-hidden", "true");
    app.insertBefore(canvas, app.firstChild);
  }
  const box = canvas.parentElement.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.max(1, Math.round(box.width * dpr));
  canvas.height = Math.max(1, Math.round(box.height * dpr));
  const ctx = canvas.getContext("2d");
  if (!ctx) return "no-2d-context";
  const draw = (phase) => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < PARTICLE_COUNT; i += 1) {
      const x = (seeded(i) + phase * (0.02 + seeded(i + 99) * 0.05)) % 1;
      const y = (seeded(i + 7) + phase * 0.01) % 1;
      const r = (2 + seeded(i + 31) * 5) * dpr;
      ctx.globalAlpha = 0.1 + seeded(i + 53) * 0.12;
      ctx.fillStyle = PARTICLE_INKS[i % PARTICLE_INKS.length];
      ctx.beginPath();
      ctx.arc(x * canvas.width, y * canvas.height, r, 0, Math.PI * 2);
      ctx.fill();
    }
  };
  draw(0);
  if (!live) return "static";
  const step = (now) => {
    draw(now / 12e3);
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  return "live";
}
function particleMode() {
  try {
    const wanted = new URLSearchParams(window.location.search).get("particles");
    if (wanted === "live" || wanted === "static") return wanted;
  } catch {
  }
  return "off";
}
const MAGNETIC_SELECTOR = ".ghost-btn,.primary-btn,.danger-btn,.stage-nav-btn,.nav button";
const TILT_SELECTOR = ".row-card,.capability-card,.panel";
const REVEAL_SELECTOR = "#tp-verdicts>*,.list-item,.row-card,.grid-stack>*";
function delegate(root, selector, onTarget, onLeave) {
  let current = null;
  let queued = false;
  let pending = null;
  const paint = () => {
    queued = false;
    if (!pending) return;
    onTarget(pending[0], pending[1], pending[2]);
  };
  root.addEventListener("pointermove", (event) => {
    const target = event.target && event.target.closest ? event.target.closest(selector) : null;
    const host = target;
    if (!host) {
      if (current && onLeave) onLeave(current);
      current = null;
      pending = null;
      return;
    }
    if (current !== host) {
      if (current && onLeave) onLeave(current);
      current = host;
      host.style.willChange = "transform";
    }
    const box = host.getBoundingClientRect();
    if (!box.width || !box.height) return;
    pending = [host, event, box];
    if (!queued) {
      queued = true;
      requestAnimationFrame(paint);
    }
  }, { passive: true });
  root.addEventListener("pointerleave", () => {
    if (current && onLeave) onLeave(current);
    current = null;
    pending = null;
  }, { passive: true });
}
function mountEnhancedMotion(root) {
  const scope = root.body ? root : root;
  const hostsOf = (selector) => {
    try {
      return Array.from(scope.querySelectorAll(selector));
    } catch {
      return [];
    }
  };
  const mode = motionMode();
  if (mode !== "enhanced") {
    return { mode: "static", magnetic: 0, tilt: 0, revealed: 0, particles: "off" };
  }
  const doc = scope;
  try {
    doc.documentElement.dataset.motion = "enhanced";
  } catch {
  }
  delegate(doc, MAGNETIC_SELECTOR, (el2, event, box) => {
    move(
      el2,
      (event.clientX - box.left - box.width / 2) / box.width * MAGNET_PX,
      (event.clientY - box.top - box.height / 2) / box.height * MAGNET_PX,
      ""
    );
  }, (el2) => {
    move(el2, 0, 0, "");
    el2.style.willChange = "";
  });
  delegate(doc, TILT_SELECTOR, (el2, event, box) => {
    el2.style.transform = `perspective(900px) rotateX(${(-(event.clientY - box.top - box.height / 2) / box.height * TILT_DEG).toFixed(2)}deg) rotateY(${((event.clientX - box.left - box.width / 2) / box.width * TILT_DEG).toFixed(2)}deg)`;
  }, (el2) => {
    el2.style.transform = "";
    el2.style.willChange = "";
  });
  const revealed = hostsOf(REVEAL_SELECTOR);
  revealed.forEach(slideReveal);
  const wanted = particleMode();
  const particles = wanted === "off" ? "off" : mountAmbientParticles(doc, wanted === "live");
  return {
    mode,
    magnetic: hostsOf(MAGNETIC_SELECTOR).length,
    tilt: hostsOf(TILT_SELECTOR).length,
    revealed: revealed.length,
    particles
  };
}
byId("design-brief-form").onsubmit = (event) => {
  event.preventDefault();
  void submitBrief().catch((e) => setStatus(errMsg(e), true));
};
byId("brief-revision-form").onsubmit = (event) => {
  event.preventDefault();
  void submitBriefRevision().catch((e) => setStatus(errMsg(e), true));
};
byId("direction-revision-form").onsubmit = (event) => {
  event.preventDefault();
  void submitDirectionRevision().catch((e) => setStatus(errMsg(e), true));
};
byId("design-direction-form").onsubmit = (event) => {
  event.preventDefault();
  void submitDirection().catch((e) => setStatus(errMsg(e), true));
};
byId("design-system-bind").onclick = () => {
  void bindDesignSystem().catch((e) => setStatus(errMsg(e), true));
};
function devBypassEnabled() {
  if (typeof document === "undefined" || typeof window === "undefined") return false;
  if (typeof document.querySelectorAll === "function" && document.querySelectorAll('script[src*="@vite/client"]').length > 0) return true;
  try {
    const qs = window.location.search;
    if (typeof qs === "string" && qs.includes("dev=1")) return true;
  } catch {
  }
  return false;
}
if (typeof document !== "undefined" && document.body !== void 0 && typeof window !== "undefined" && devBypassEnabled() && document.__dlShellMounted !== true) {
  document.__dlShellMounted = true;
  mountAppShell();
} else if (typeof document !== "undefined" && document.body !== void 0 && typeof window !== "undefined" && document.getElementById("login") !== null && document.__dlShellMounted !== true) {
  document.__dlShellMounted = true;
  mountAppShell();
}
if (typeof document !== "undefined" && document.body !== void 0 && devBypassEnabled()) {
  const loginEl = document.getElementById("login");
  const workspaceEl = document.getElementById("workspace");
  const connEl = document.getElementById("connection");
  if (loginEl) loginEl.hidden = true;
  if (workspaceEl) {
    workspaceEl.hidden = false;
  }
  if (connEl) connEl.textContent = "未连接 · 本地浏览模式";
}
if (typeof window !== "undefined" && document.body?.dataset.localSession === "auto" && !devBypassEnabled()) void connectLocalService();
if (typeof document !== "undefined" && document.body !== void 0) {
  mountEnhancedMotion(document);
}
