// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench — design module (Lane-C split of the D002 monolith): E-SLICE-01
// design layer (Brief/Reference/Direction/DesignSystem + F-2b revision) + design state
// (export let) + this module's top-level handler wiring. resetDesignRevision() centralizes
// the 5 design-var clears so workbench.js needs no cross-module state writes.

import type {
  BriefLineageResponse,
  BriefRevisionResponse,
  DesignBrief,
  DesignDirection,
  DesignLayerResponse,
  DesignSystemBinding,
  DesignSystemRecord,
  DirectionLineageResponse,
  DirectionRevisionResponse,
} from './contracts.js';

import { api, byId, epoch, errMsg, project, selectedReferences, setStatus } from './workbench.js';


// ============================================================================
// E-SLICE-01 design layer: the first full-stack vertical slice
//   Project -> Brief -> Reference -> Direction (Human Choice) -> DesignSystem
// Present as first-class user interactions (forms + buttons), not raw JSON.
// Each step persists server-side and is read back from the API (evidence = the
// readback, the recorded spec digests, the chosen-actor fact, the binding).
// ============================================================================
export let chosenDirection: DesignDirection | null = null;
export let designRequest = 0;
export let boundSystems: DesignSystemRecord[] = [];
export let submittedBrief: { owner: string; identity: string; key: string } | null = null;
export let submittedDirection: { owner: string; identity: string; key: string } | null = null;
export let briefBusy = false;
export let directionBusy = false;
export let bindBusy = false;

// F-2b revision state. The revision forms are ONE form per record kind, loaded
// from a row: the target row supplies the parent version whose content is
// re-sent (a revision appends a new immutable version; it never edits the old
// row). `revisionBriefCarried` holds references that the checked picker cannot
// represent, so a revision never silently drops a reference.
export let revisionBriefTarget: DesignBrief | null = null;
export let revisionDirectionTarget: DesignDirection | null = null;
export let revisionBriefCarried: string[] = [];
export let highlightBrief: string | null = null;
export let highlightDirection: string | null = null;
export let briefRevisionBusy = false;
export let directionRevisionBusy = false;
export let briefLineageRequest = 0;
export let directionLineageRequest = 0;
export const REVISION_BRIEF_IDLE = '在某一简报行点击「新版本」以载入该版本内容；保存会新增一个版本，不会改写旧版本。';
export const REVISION_DIRECTION_IDLE = '在某一方向行点击「新版本」以载入该版本内容；保存会新增一个版本，不会改写旧版本。';

export const uuid = (): string => crypto.randomUUID();

export async function loadDesignSystems() {
  const current = epoch;
  const data = await api<{ design_systems: DesignSystemRecord[] }>('/design-systems');
  if (current !== epoch) return;
  boundSystems = data.design_systems;
  const select = byId<HTMLSelectElement>('design-system');
  select.replaceChildren(new Option('选择设计系统', ''));
  for (const system of boundSystems) select.append(new Option(`${system.title} · ${system.version} (${system.evidence_level})`, system.name));
  byId<HTMLUListElement>('design-systems').replaceChildren(
    ...boundSystems.map((system) => {
      const li = document.createElement('li');
      li.textContent = `${system.name} · ${system.title} · v${system.version} · ${system.evidence_level}`;
      return li;
    }),
  );
}

// F-2b helpers — plain user language only (no command/package/artifact terms).
export const shortId = (id: string): string => id.slice(-8);

export function versionOf(id: string, versions: Map<string, number>): string {
  const known = versions.get(id);
  return known === undefined ? `未知版本（${shortId(id)}）` : `版本 ${known}（${shortId(id)}）`;
}

// A row is either the live version (nothing supersedes it) or a superseded
// version whose `superseded_by` pointer names the version that continued it.
export function versionState(supersededBy: string | null, versions: Map<string, number>): string {
  return supersededBy === null ? '当前' : `已取代 → ${versionOf(supersededBy, versions)}`;
}

export function rowButton(label: string, action: () => void | Promise<void>): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.textContent = label;
  // Same contract as button(): the handled promise is returned so a caller can
  // await the whole action chain (the .catch already resolves it).
  element.onclick = () => Promise.resolve(action()).catch((error) => setStatus(errMsg(error), true));
  return element;
}

export function renderDesignLayer(data: DesignLayerResponse) {
  const layer = data.design_layer;
  const briefVersions = new Map<string, number>();
  for (const row of layer.briefs) briefVersions.set(row.brief_id, row.version);
  const directionVersions = new Map<string, number>();
  const directionsById = new Map<string, DesignDirection>();
  for (const row of layer.directions) {
    directionVersions.set(row.direction_id, row.version);
    directionsById.set(row.direction_id, row);
  }
  const activeBindingId = layer.active_binding ? layer.active_binding.binding_id : null;
  const focusRows: HTMLElement[] = [];

  byId<HTMLUListElement>('design-briefs').replaceChildren(
    ...layer.briefs.map((brief: DesignBrief) => {
      const li = document.createElement('li');
      li.tabIndex = -1;
      const refs = brief.reference_asset_ids.length;
      li.textContent = `BRIEF · ${brief.title} · ${brief.goals.join(' / ')}${brief.constraints ? ` · ${brief.constraints}` : ''} · 参考 ${refs} · v${brief.version} · ${versionState(brief.superseded_by, briefVersions)} · ${brief.spec_sha256}`;
      li.append(
        rowButton('新版本', () => loadBriefRevision(brief)),
        rowButton('版本链', () => loadBriefLineage(brief.brief_id)),
      );
      if (brief.brief_id === highlightBrief) {
        li.classList.add('highlight');
        focusRows.push(li);
      }
      return li;
    }),
  );
  byId<HTMLUListElement>('design-directions').replaceChildren(
    ...layer.directions.map((direction: DesignDirection) => {
      const li = document.createElement('li');
      li.tabIndex = -1;
      const live = direction.superseded_by === null;
      li.textContent = `DIRECTION · ${direction.title} · ${direction.chosen ? `CHOSEN by ${direction.actor}` : 'open'} · v${direction.version} · ${versionState(direction.superseded_by, directionVersions)} · 简报 ${shortId(direction.brief_id)} · ${direction.spec_sha256}`;
      if (direction.chosen && live) chosenDirection = direction;
      // Naming a superseded version "the choice" would be untrue, so the
      // choose entry is offered only on the live version of a direction.
      if (live) {
        const choose = document.createElement('button');
        choose.type = 'button';
        choose.textContent = `选为方向 · ${shortId(direction.direction_id)}`;
        choose.onclick = () => chooseDirection(direction).catch((error) => setStatus(errMsg(error), true));
        li.append(choose);
      }
      li.append(
        rowButton('新版本', () => loadDirectionRevision(direction)),
        rowButton('版本链', () => loadDirectionLineage(direction.direction_id)),
      );
      if (direction.direction_id === highlightDirection) {
        li.classList.add('highlight');
        focusRows.push(li);
      }
      return li;
    }),
  );
  byId<HTMLUListElement>('design-bindings').replaceChildren(
    ...(layer.bindings.length ? layer.bindings.map((binding: DesignSystemBinding) => {
      const li = document.createElement('li');
      const owner = directionsById.get(binding.direction_id);
      // A binding row is append-only: it stays attached to the direction VERSION
      // it was bound to and never follows a revised direction. Only the read
      // model's active_binding is current — every other row must say so.
      const state = binding.binding_id === activeBindingId
        ? '生效中'
        : owner && owner.superseded_by !== null
          ? '未生效 · 绑定留在已被取代的方向版本上，需重新建立'
          : '未生效 · 当前选定方向不是它';
      li.textContent = `BINDING · ${binding.design_system_name} · 绑定记录 v${binding.version} · 方向 ${shortId(binding.direction_id)} · ${state} · ${binding.spec_sha256}`;
      return li;
    }) : [info('design-bindings-empty')]),
  );
  const notice = byId<HTMLParagraphElement>('design-binding-active');
  const active = layer.active_binding;
  const chosen = chosenDirection;
  if (active) {
    notice.classList.remove('warn');
    notice.textContent = `当前方向已绑定设计系统：${active.design_system_name}（设计契约已固定）。`;
  } else if (chosen && layer.bindings.length) {
    // F-2b: revising a chosen direction carries the choice forward but NOT the
    // design-system binding (append-only row). Say so instead of showing the
    // retired binding as if it were current.
    notice.classList.add('warn');
    notice.textContent = `当前选定方向「${chosen.title} · 版本 ${chosen.version}」没有生效的设计契约：已有的绑定记录仍留在旧的方向版本上，不会随新版本自动跟随——绑定需重新建立（选定设计系统后点「绑定设计系统」）。`;
  } else {
    notice.classList.remove('warn');
    notice.textContent = '选择方向并绑定设计系统后，后续 Build/Review 才有固定设计契约。';
  }
  if (focusRows.length) focusRows[0].focus();
}

export function info(id: string): HTMLElement {
  // An <li>, not a <p>: this is appended straight into <ul id="design-bindings">,
  // and a non-li child breaks the list's item count for assistive tech (WCAG 4.1.1).
  const li = document.createElement('li');
  li.id = id;
  li.className = 'empty';
  li.textContent = id === 'design-bindings-empty' ? '尚未绑定设计系统。' : '';
  return li;
}

export async function refreshDesign() {
  if (!project) return;
  const current = epoch;
  const request = ++designRequest;
  setStatus('正在读取设计层：Brief / Direction / DesignSystem…');
  const data = await api<DesignLayerResponse>(`/projects/${project}/design-layer`).catch((error) => {
    if (current !== epoch || request !== designRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== designRequest) return;
  chosenDirection = null;
  const briefSelect = byId<HTMLSelectElement>('direction-brief');
  briefSelect.replaceChildren(new Option('选择简报', ''));
  for (const brief of data.design_layer.briefs)
    briefSelect.append(new Option(`${brief.title} · ${brief.brief_id.slice(-8)}`, brief.brief_id));
  renderDesignLayer(data);
  setStatus('设计层已读取。方向选择与绑定不代表制作完成或质量验收。');
}

export interface BriefDraft {
  owner: string;
  title: string;
  goals: string[];
  constraints: string | null;
  references: string[];
}

/**
 * The one rule that turns a brief draft into a persisted brief (DL-UI-U04).
 *
 * Validation and the idempotency key live here and nowhere else: the legacy form and
 * the desktop 输入与目标 page both call this, so a second copy of the rule cannot drift
 * into a different acceptance behaviour on the two surfaces. The key is kept per
 * (owner, identity) exactly as the form did -- retrying the same content reuses it, and
 * any change produces a new one, which is what stops a double submit creating two
 * briefs. Refusals throw with the server's own wording so the caller can only restate
 * what was actually said.
 */
export async function createBrief(draft: BriefDraft): Promise<void> {
  if (!draft.owner) throw new Error('未选择项目。');
  const title = draft.title.trim();
  const goals = draft.goals.map((goal) => goal.trim()).filter(Boolean);
  if (!title || !goals.length) throw new Error('请填写简报标题与至少一条目标。');
  const constraints = draft.constraints && draft.constraints.trim() ? draft.constraints.trim() : null;
  const references = draft.references;
  const body: Record<string, unknown> = {
    title, goals, constraints, reference_asset_ids: references, idempotency_key: '',
  };
  const identity = JSON.stringify({ owner: draft.owner, title, goals, constraints, references });
  if (!submittedBrief || submittedBrief.owner !== draft.owner
      || submittedBrief.identity !== identity)
    submittedBrief = { owner: draft.owner, identity, key: uuid() };
  body.idempotency_key = submittedBrief.key;
  await api(`/projects/${draft.owner}/briefs`, body);
}

export async function submitBrief() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const title = byId<HTMLInputElement>('brief-title').value;
  if (briefBusy) return;
  const goalsRaw = byId<HTMLInputElement>('brief-goals').value.trim();
  const goals = goalsRaw ? goalsRaw.split(',').map((s) => s.trim()).filter(Boolean) : [];
  const constraints = byId<HTMLInputElement>('brief-constraints').value.trim() || null;
  if (!title || !goals.length) { setStatus('请填写简报标题与至少一条目标。', true); return; }
  const references = selectedReferences();
  briefBusy = true;
  byId<HTMLButtonElement>('brief-submit').disabled = true;
  try {
    await createBrief({ owner, title, goals, constraints, references });
    if (current !== epoch) return;
    byId<HTMLInputElement>('brief-title').value = '';
    byId<HTMLInputElement>('brief-goals').value = '';
    byId<HTMLInputElement>('brief-constraints').value = '';
    for (const box of Array.from(document.querySelectorAll('input[name="reference-asset"]')))
      (box as HTMLInputElement).checked = false;
    await refreshDesign();
    setStatus(`简报已持久化（引用 ${references.length} 个参考素材）；下一步在简报下立方向。`);
  } catch (error) {
    if (current === epoch) setStatus(`简报未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    briefBusy = false;
    byId<HTMLButtonElement>('brief-submit').disabled = false;
  }
}

export async function submitDirection() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  if (directionBusy) return;
  const brief = byId<HTMLSelectElement>('direction-brief').value;
  const title = byId<HTMLInputElement>('direction-title').value.trim();
  const colorMood = byId<HTMLInputElement>('direction-color').value.trim() || null;
  const typeMood = byId<HTMLInputElement>('direction-type').value.trim() || null;
  if (!brief || !title) { setStatus('请选择简报并填写方向标题。', true); return; }
  const body: Record<string, unknown> = { brief_id: brief, title, style_notes: null, color_mood: colorMood, typography_mood: typeMood, idempotency_key: '' };
  const identity = JSON.stringify({ owner, brief, title, colorMood, typeMood });
  if (!submittedDirection || submittedDirection.owner !== owner || submittedDirection.identity !== identity)
    submittedDirection = { owner, identity, key: uuid() };
  body.idempotency_key = submittedDirection.key;
  directionBusy = true;
  byId<HTMLButtonElement>('direction-submit').disabled = true;
  try {
    const data = await api<{ direction: DesignDirection }>(`/projects/${owner}/directions`, body);
    if (current !== epoch) return;
    byId<HTMLInputElement>('direction-title').value = '';
    await refreshDesign();
    setStatus(`方向已排队：${data.direction.direction_id.slice(-8)}。请选择该方向并绑定设计系统。`);
  } catch (error) {
    if (current === epoch) setStatus(`方向未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    directionBusy = false;
    byId<HTMLButtonElement>('direction-submit').disabled = false;
  }
}

export async function chooseDirection(direction: DesignDirection) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const actor = 'workbench-user';
  const actorKind = 'human';
  const body = { actor, actor_kind: actorKind, idempotency_key: uuid() };
  try {
    const data = await api<{ direction: DesignDirection }>(`/projects/${owner}/directions/${direction.direction_id}/choose`, body);
    if (current !== epoch) return;
    await refreshDesign();
    setStatus(`方向已选定：${data.direction.direction_id.slice(-8)}（${data.direction.actor}）。下一步绑定设计系统。`);
  } catch (error) {
    if (current === epoch) setStatus(`方向选择未确认：${errMsg(error)}`, true);
  }
}

export async function bindDesignSystem() {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  if (bindBusy) return;
  const name = byId<HTMLSelectElement>('design-system').value;
  const direction = chosenDirection;
  if (!name || !direction) { setStatus('请先选定方向，再选择要绑定的设计系统。', true); return; }
  const body = { design_system_name: name, idempotency_key: uuid() };
  bindBusy = true;
  byId<HTMLButtonElement>('design-system-bind').disabled = true;
  try {
    const data = await api<{ binding: { design_system_name: string } }>(`/projects/${owner}/directions/${direction.direction_id}/bind`, body);
    if (current !== epoch) return;
    await refreshDesign();
    setStatus(`设计系统已绑定：${data.binding.design_system_name}。设计契约已固定；制作与质量验收仍未执行。`);
  } catch (error) {
    if (current === epoch) setStatus(`设计系统绑定未确认：${errMsg(error)}`, true);
  } finally {
    bindBusy = false;
    byId<HTMLButtonElement>('design-system-bind').disabled = false;
  }
}

// ============================================================================
// F-2b revision flow: every brief / direction row can append a NEW version.
// The row's content prefills the form, the POST goes to the revision route,
// and the result is READ BACK from the server (design layer + version chain),
// so the DOM only ever shows persisted state. Stale / foreign / unauthorized
// revisions fail closed through the shared error line — never silently.
// ============================================================================
export function revisionHint(error: unknown): string {
  const code = errMsg(error);
  if (code === 'STALE_REVISION') return '该版本已被取代，服务端拒绝了这次修订（STALE_REVISION）。请从版本链里的最新版本继续。';
  if (code === 'BRIEF_NOT_FOUND' || code === 'DIRECTION_NOT_FOUND') return `该版本已不在当前项目中（${code}）；请刷新后重试。`;
  if (code === 'UNAUTHORIZED') return '访问令牌无效或已过期（UNAUTHORIZED）；请断开后重新连接本机服务。';
  return `${code}；本次修订未被接受，服务端未写入任何内容。`;
}

// Long items are rejected by the service (fail closed); catch it here so the
// user sees which field is at fault instead of a bare INVALID_LIST_ITEM.
export function splitList(raw: string, maxLen: number, label: string): string[] {
  const items = raw ? raw.split(',').map((value) => value.trim()).filter(Boolean) : [];
  if (items.some((item) => item.length > maxLen)) throw new Error(`${label}每项不能超过 ${maxLen} 个字符`);
  return items;
}

export function loadBriefRevision(brief: DesignBrief, focusForm = true) {
  revisionBriefTarget = brief;
  const boxes = Array.from(document.querySelectorAll<HTMLInputElement>('input[name="reference-asset"]'));
  const known = new Set(boxes.map((box) => box.value));
  for (const box of boxes) box.checked = brief.reference_asset_ids.includes(box.value);
  revisionBriefCarried = brief.reference_asset_ids.filter((id) => !known.has(id));
  byId<HTMLInputElement>('revision-brief-title').value = brief.title;
  byId<HTMLInputElement>('revision-brief-goals').value = brief.goals.join(', ');
  byId<HTMLInputElement>('revision-brief-constraints').value = brief.constraints ?? '';
  byId<HTMLParagraphElement>('revision-brief-target').textContent =
    `正在修订简报「${brief.title}」版本 ${brief.version}（${shortId(brief.brief_id)}）：内容已按该版本预填，勾选区对应它的参考素材。保存会新增一个版本，旧版本只保留为历史。`
    + (revisionBriefCarried.length ? `另有 ${revisionBriefCarried.length} 个参考素材不在当前勾选列表里，会原样保留。` : '')
    + (brief.superseded_by === null ? '' : ' 注意：该版本已被取代，服务端会拒绝这次修订（STALE_REVISION），请改从版本链中的最新版本继续。');
  // After a successful revision the highlight/focus must stay on the NEW row,
  // so the post-revision prefill does not steal focus back into the form.
  if (focusForm) byId<HTMLInputElement>('revision-brief-title').focus();
}

export async function submitBriefRevision() {
  const current = epoch;
  const owner = project;
  const source = revisionBriefTarget;
  if (!owner || briefRevisionBusy) return;
  if (!source) { setStatus('请先在某一简报行点击「新版本」以载入要修订的内容。', true); return; }
  briefRevisionBusy = true;
  byId<HTMLButtonElement>('brief-revision-submit').disabled = true;
  try {
    const title = byId<HTMLInputElement>('revision-brief-title').value.trim();
    const goals = splitList(byId<HTMLInputElement>('revision-brief-goals').value, 300, '目标');
    const constraints = byId<HTMLInputElement>('revision-brief-constraints').value.trim() || null;
    if (!title || !goals.length) throw new Error('修订需要标题与至少一条目标');
    const references = Array.from(new Set([...selectedReferences(), ...revisionBriefCarried]));
    const data = await api<BriefRevisionResponse>(`/projects/${owner}/briefs/${source.brief_id}/revisions`,
      { title, goals, constraints, reference_asset_ids: references, idempotency_key: uuid() });
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
    byId<HTMLButtonElement>('brief-revision-submit').disabled = false;
  }
}

export function loadDirectionRevision(direction: DesignDirection, focusForm = true) {
  revisionDirectionTarget = direction;
  byId<HTMLInputElement>('revision-direction-title').value = direction.title;
  byId<HTMLInputElement>('revision-direction-notes').value = (direction.style_notes ?? []).join(', ');
  byId<HTMLInputElement>('revision-direction-color').value = direction.color_mood ?? '';
  byId<HTMLInputElement>('revision-direction-type').value = direction.typography_mood ?? '';
  byId<HTMLParagraphElement>('revision-direction-target').textContent =
    `正在修订方向「${direction.title}」版本 ${direction.version}（${shortId(direction.direction_id)}）：内容已按该版本预填。保存会新增一个版本，旧版本只保留为历史。`
    + (direction.chosen ? ' 该版本是当前已选定方向：选定结论会随新版本带走，但设计系统绑定不会自动跟随，需重新建立。' : '')
    + (direction.superseded_by === null ? '' : ' 注意：该版本已被取代，服务端会拒绝这次修订（STALE_REVISION），请改从版本链中的最新版本继续。');
  if (focusForm) byId<HTMLInputElement>('revision-direction-title').focus();
}

export interface DirectionRevisionDraft {
  owner: string;
  directionId: string;
  title: string;
  notes: string[];
  colorMood: string | null;
  typeMood: string | null;
}

/**
 * The one rule that turns a direction correction into a new version (DL-UI-U04).
 *
 * A revision never rewrites the version it came from: the route appends a version and the
 * server refuses a superseded one (STALE_REVISION), which is why the caller must pass the
 * direction id it actually loaded rather than "whatever is selected now". Validation lives
 * here so the legacy form and the 分析与方案 screen cannot drift into different acceptance
 * behaviour; each submit gets a fresh idempotency key because a correction is a new intent.
 */
export async function reviseDirection(draft: DirectionRevisionDraft): Promise<DirectionRevisionResponse> {
  if (!draft.owner) throw new Error('未选择项目。');
  if (!draft.directionId) throw new Error('请先选择要修订的方向版本。');
  const title = draft.title.trim();
  if (!title) throw new Error('修订需要方向标题');
  return api<DirectionRevisionResponse>(
    `/projects/${draft.owner}/directions/${draft.directionId}/revisions`,
    {
      title,
      style_notes: draft.notes.length ? draft.notes : null,
      color_mood: draft.colorMood,
      typography_mood: draft.typeMood,
      idempotency_key: uuid(),
    });
}

export async function submitDirectionRevision() {
  const current = epoch;
  const owner = project;
  const source = revisionDirectionTarget;
  if (!owner || directionRevisionBusy) return;
  if (!source) { setStatus('请先在某一方向行点击「新版本」以载入要修订的内容。', true); return; }
  directionRevisionBusy = true;
  byId<HTMLButtonElement>('direction-revision-submit').disabled = true;
  try {
    const title = byId<HTMLInputElement>('revision-direction-title').value.trim();
    const notes = splitList(byId<HTMLInputElement>('revision-direction-notes').value, 300, '表现备注');
    const colorMood = byId<HTMLInputElement>('revision-direction-color').value.trim() || null;
    const typeMood = byId<HTMLInputElement>('revision-direction-type').value.trim() || null;
    if (!title) throw new Error('修订需要方向标题');
    const data = await reviseDirection({
      owner, directionId: source.direction_id, title, notes, colorMood, typeMood });
    if (current !== epoch) return;
    highlightDirection = data.direction.direction_id;
    await refreshDesign();
    if (current !== epoch) return;
    await loadDirectionLineage(data.direction.direction_id);
    if (current !== epoch) return;
    loadDirectionRevision(data.direction, false);
    setStatus(`方向已保存为版本 ${data.direction.version}（${shortId(data.direction.direction_id)}）；版本 ${source.version} 只保留为历史。`
      + (data.direction.chosen ? ` 选定结论已随新版本带走（${data.direction.actor}）；设计系统绑定未跟随，绑定需重新建立。` : ''));
  } catch (error) {
    if (current === epoch) setStatus(`方向修订未确认：${revisionHint(error)}`, true);
  } finally {
    directionRevisionBusy = false;
    byId<HTMLButtonElement>('direction-revision-submit').disabled = false;
  }
}

export async function loadBriefLineage(briefId: string) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const request = ++briefLineageRequest;
  setStatus('正在读取简报版本链…');
  const data = await api<BriefLineageResponse>(`/projects/${owner}/briefs/${briefId}/lineage`).catch((error) => {
    if (current !== epoch || request !== briefLineageRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== briefLineageRequest) return;
  const versions = new Map<string, number>();
  for (const row of data.lineage.versions) versions.set(row.brief_id, row.version);
  const liveId = data.lineage.live_id;
  const live = liveId === null ? '—' : versionOf(liveId, versions);
  const first = data.lineage.versions.length ? data.lineage.versions[0] : null;
  byId<HTMLParagraphElement>('brief-lineage-title').textContent =
    `简报版本链 · 共 ${data.lineage.versions.length} 个版本 · 当前 ${live} · 起点 ${first ? `版本 ${first.version}` : '—'}`;
  byId<HTMLUListElement>('brief-lineage').replaceChildren(
    ...data.lineage.versions.map((row) => {
      const li = document.createElement('li');
      li.textContent = `版本 ${row.version} · ${versionState(row.superseded_by, versions)} · ${row.title} · ${row.goals.join(' / ')}${row.constraints ? ` · ${row.constraints}` : ''} · 参考 ${row.reference_asset_ids.length} · 记录于 ${row.created_at} · ${row.spec_sha256}`;
      return li;
    }),
  );
  setStatus(`简报版本链已读回：共 ${data.lineage.versions.length} 个版本，当前 ${live}。`);
}

export async function loadDirectionLineage(directionId: string) {
  const current = epoch;
  const owner = project;
  if (!owner) return;
  const request = ++directionLineageRequest;
  setStatus('正在读取方向版本链…');
  const data = await api<DirectionLineageResponse>(`/projects/${owner}/directions/${directionId}/lineage`).catch((error) => {
    if (current !== epoch || request !== directionLineageRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== directionLineageRequest) return;
  const versions = new Map<string, number>();
  for (const row of data.lineage.versions) versions.set(row.direction_id, row.version);
  const liveId = data.lineage.live_id;
  const live = liveId === null ? '—' : versionOf(liveId, versions);
  const first = data.lineage.versions.length ? data.lineage.versions[0] : null;
  byId<HTMLParagraphElement>('direction-lineage-title').textContent =
    `方向版本链 · 共 ${data.lineage.versions.length} 个版本 · 当前 ${live} · 起点 ${first ? `版本 ${first.version}` : '—'}`;
  byId<HTMLUListElement>('direction-lineage').replaceChildren(
    ...data.lineage.versions.map((row) => {
      const li = document.createElement('li');
      li.textContent = `版本 ${row.version} · ${versionState(row.superseded_by, versions)} · ${row.title} · ${row.chosen ? `已选定（${row.actor}）` : '未选定'} · 色彩 ${row.color_mood ?? '未指定'} · 字体 ${row.typography_mood ?? '未指定'} · 记录于 ${row.created_at} · ${row.spec_sha256}`;
      return li;
    }),
  );
  setStatus(`方向版本链已读回：共 ${data.lineage.versions.length} 个版本，当前 ${live}。`);
}

// Centralized design-layer reset (called by workbench.resetProject()). Clears the
// 5 design revision/highlight state vars + the design-layer DOM. Lives in design.js
// (the owner) so the split keeps cross-module state writes at zero.
export function resetDesignRevision() {
  // F-2b: a project switch drops the in-flight revision target, the version
  // highlight and both chains — nothing from the previous project stays
  // visible as if it were the current project's state.
  revisionBriefTarget = revisionDirectionTarget = null;
  revisionBriefCarried = [];
  highlightBrief = highlightDirection = null;
  byId<HTMLParagraphElement>('revision-brief-target').textContent = REVISION_BRIEF_IDLE;
  byId<HTMLParagraphElement>('revision-direction-target').textContent = REVISION_DIRECTION_IDLE;
  byId<HTMLParagraphElement>('brief-lineage-title').textContent = '';
  byId<HTMLParagraphElement>('direction-lineage-title').textContent = '';
  byId<HTMLParagraphElement>('design-binding-active').textContent = '';
}
