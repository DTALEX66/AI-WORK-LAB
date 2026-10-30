// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench — workbench module (Lane-C split of the D002 monolith):
// shared helpers (byId/setStatus/errMsg/api/button) + workbench state (export let) +
// connection/project/task/event/asset actions + this module's top-level handler wiring.
// Design-layer revision state is owned by design.js and cleared via the single cross-
// module call resetDesignRevision() (keeps cross-module state writes at zero).

import type {
  AssetContentResponse,
  AssetListResponse,
  AssistancePlanListView,
  BundleDownloadResponse,
  EventListResponse,
  NativeAssetListResponse,
  NativeAssetRecord,
  NativeAssetVerifyResponse,
  NativePlanResponse,
  PatchResponse,
  ProjectCreateResponse,
  ProjectListResponse,
  TaskActionResponse,
  TaskDispatchResponse,
  TaskListResponse,
  TaskRecord,
} from './contracts.js';

import { loadDesignSystems, refreshDesign, resetDesignRevision } from './design.js';

export const byId = <T extends HTMLElement = HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

export let token = '';
export let connected = false;
export let connectGeneration = 0;
export let project = '';
export let epoch = 0;
export let taskCursor: string | null = null;
export let eventCursor: string | null = null;
export let eventJob = '';
export let pendingImport: { project: string; body: Record<string, unknown> } | null = null;
export let busy = false;
export let nativeCursor: string | null = null;
export let eventRequest = 0;
export let previewRequest = 0;
export let verificationRequest = 0;
export let taskRequest = 0;
export let nativeRequest = 0;
export let refreshRequest = 0;
export let plansRequest = 0;
export let submittedPlan: { owner: string; identity: string; key: string } | null = null;
export let planBusy = false;
export let patchSource: { owner: string; job: string; attempt: string } | null = null;
export let submittedPatch: { identity: string; key: string } | null = null;
export let patchBusy = false;

// Renamed from `status`: the bare identifier `status` collides with the DOM global
// `window.status: string`, which made the helper non-callable under `strict`.
export const setStatus = (text: string, error = false) => {
  const el = byId<HTMLParagraphElement>('status');
  el.textContent = text;
  el.classList.toggle('error', error);
  // On every routed view `body > main` — which owns #status — is `hidden`, so a
  // preflight or patch failure was written into an element neither the eye nor a
  // screen reader could reach. Mirror it into the shell's live region, which
  // exists on both paths.
  // Guarded like the rest of the shell: the vm smoke's Mock document has
  // getElementById but no querySelector.
  const main = typeof document.querySelector === 'function'
    ? document.querySelector('body > main') as HTMLElement | null : null;
  if (main && main.hidden) {
    const live = document.querySelector('.sr-status');
    if (live) live.textContent = text;
  }
};

export const errMsg = (error: unknown) => (error instanceof Error ? error.message : String(error));

// Generic fetch wrapper: T is the strict contract type for the endpoint; only the
// wire-level error envelope is read from the body, everything else is typed.
// A 401 at any point means the token this page holds is no longer the token the
// service accepts (typically a service restart with a fresh token). Clearing it
// only during the initial connect left the session looking live forever: the
// route gate in shell.ts keys off `token`, so every view kept rendering 401
// text as if it were data.
const dropSession = (): void => {
  token = '';
  connected = false;
  const badge = byId<HTMLSpanElement>('connection');
  if (badge) badge.textContent = '未连接';
};

// D06 deadlines. A read is cheap to abandon and cheap to redo; a write may have landed, so its
// deadline is longer and its outcome is reported as unknown rather than as a failure. The read
// number matches the `/api/local-session` connect probe, which already carried an 8s budget of
// its own -- that probe was the only request in this app with a deadline, which is exactly why
// everything else could hang.
export const READ_TIMEOUT_MS = 15000;
export const WRITE_TIMEOUT_MS = 45000;

export interface ApiOptions { timeoutMs?: number; signal?: AbortSignal }

// One generation per rendered view. `cancelPendingReads()` is called when the route changes, so
// a slow read for a page the user has left cannot land on the next page's DOM.
//
// Created on first use, not at module load: constructing it at the top level made the bundle
// throw `AbortController is not defined` under any environment that lacks the global (the
// classic-script smoke load, for one), so merely importing the workbench failed. A module whose
// load has no side effects is importable wherever it can run, and the browser always has this.
let pageGeneration: AbortController | null = null;
const currentGeneration = (): AbortController => (pageGeneration ??= new AbortController());

export function cancelPendingReads(): void {
  pageGeneration?.abort();
  pageGeneration = null;
}

export class ReadDeadlineError extends Error {}
export class PageReadCancelledError extends Error {}

/** A write whose answer was lost. Never a failure: the service may have committed it. */
export class WriteOutcomeUnknownError extends Error {
  readonly outcomeUnknown = true;
}

export async function api<T>(path: string, body?: Record<string, unknown>,
                             options: ApiOptions = {}): Promise<T> {
  // D06. A request that never answers used to hang the page forever: `fetch` had no signal, so
  // a service that accepted the socket and then went quiet left every view spinning with no
  // deadline and no way to tell "still working" from "gone". Three endings are now distinct,
  // because they call for different operator actions -- and a write is not allowed to be
  // reported as a failure, since the service may have committed it before the answer was lost.
  const isWrite = body !== undefined;
  const timeoutMs = options.timeoutMs ?? (isWrite ? WRITE_TIMEOUT_MS : READ_TIMEOUT_MS);
  const controller = new AbortController();
  let deadlineHit = false;
  const timer = setTimeout(() => {
    deadlineHit = true;
    controller.abort();
  }, timeoutMs);
  const cancel = () => controller.abort();
  // A read belongs to the view that asked for it, so leaving the view cancels it. A write does
  // NOT: navigating away does not undo a submission, and reporting it as cancelled would invite
  // exactly the blind resend this is meant to prevent.
  const generation = isWrite ? null : currentGeneration();
  if (generation) generation.signal.addEventListener('abort', cancel, { once: true });
  options.signal?.addEventListener('abort', cancel, { once: true });
  let response: Response;
  let bodySeen = false;
  let status = 0;
  let value: { error?: string } & Record<string, unknown>;
  try {
    response = await fetch('/api' + path, {
      method: body ? 'POST' : 'GET',
      headers: { Authorization: 'Bearer ' + token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: 'no-store',
      signal: controller.signal,
    });
    bodySeen = true;
    status = response.status;
    value = (await response.json()) as { error?: string } & Record<string, unknown>;
  } catch (error) {
    if (deadlineHit) {
      // Sub-second budgets print as decimals, not as "0 秒": the deadline is real at any
      // size, and a round-to-zero would read as if nothing had been waited for.
      const seconds = timeoutMs >= 1000 ? Math.round(timeoutMs / 1000) : timeoutMs / 1000;
      if (isWrite)
        throw new WriteOutcomeUnknownError(
          `提交已发出，但 ${seconds} 秒内没有答复：结果待核对，不是失败。`
          + '请先读回该资源确认服务端是否已经落库，再决定是否重发；'
          + '同一个幂等键重发是安全的，但不要不看读回就重发。');
      throw new ReadDeadlineError(
        `读取超时（${seconds} 秒未答复）：本次读取已放弃。`
        + '读取没有产生任何写入，可以直接重试。');
    }
    if (controller.signal.aborted) {
      // Reached when the page moved on while the BODY was still arriving. A write is still a
      // write: navigating away did not undo the submission, and the body being lost is not
      // evidence that the service rejected it.
      if (isWrite)
        throw new WriteOutcomeUnknownError(
          '提交已发出，但答复在读取过程中被取消：结果待核对，不是失败。'
          + '请先读回该资源确认服务端是否已经落库，再决定是否重发。');
      throw new PageReadCancelledError(
        '页面已切换，本次读取已取消（没有产生写入）。重新进入该页会重新读取。');
    }
    if (bodySeen) {
      // A reply that starts arriving and then does not parse, or stops mid-body, is a different
      // failure from an unreachable service -- most often something in front of the workbench
      // answered instead of the workbench -- and the status code is the only clue worth keeping.
      throw new Error(`服务回复无法解析（HTTP ${status}，${errMsg(error)}）`);
    }
    // The request never got an answer. Unwrapped, this reaches the page as the browser's
    // own "Failed to fetch", which is indistinguishable from a view bug and tells the
    // operator nothing to do. Name what is unreachable, keep the browser's reason.
    throw new Error(`无法连接本机设计服务（${errMsg(error)}）`);
  } finally {
    // The deadline and the cancellation hooks cover the whole exchange, headers AND body. They
    // used to be released the moment headers arrived, so a service that answered promptly and
    // then dribbled a body could take arbitrarily long, ignore a page change, and turn a write
    // that never finished into an unclassified error.
    clearTimeout(timer);
    generation?.signal.removeEventListener('abort', cancel);
    options.signal?.removeEventListener('abort', cancel);
  }
  if (response.status === 401) dropSession();
  if (!response.ok) {
    if (value.error === 'PROJECT_PATH_TOO_LONG')
      throw new Error('项目路径过长，Windows 无法保存。请将项目放在较短的目录后重试。');
    // The envelope travels with the error. A refusal may carry field-level detail
    // (a rejected DTCG token document names the paths), and dropping it here would
    // leave the page with a code and nothing the operator can fix.
    const failure = new Error(value.error || 'SERVICE_ERROR') as Error & {
      serviceEnvelope?: Record<string, unknown>;
    };
    failure.serviceEnvelope = value;
    throw failure;
  }
  return value as T;
}

// Empty-state notice for a <ul>. Assigning `textContent` on the list itself put
// a bare text node inside a <ul>, which breaks the list's item count and is
// invalid per WCAG 4.1.1; the notice is now a real <li>.
export function setListNotice(listId: string, text: string): void {
  const list = byId<HTMLUListElement>(listId);
  const li = document.createElement('li');
  li.className = 'empty';
  li.textContent = text;
  list.replaceChildren(li);
}

export function button(list: string, label: string, action: () => Promise<void>) {
  const li = document.createElement('li');
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = label;
  // Return the handled promise (do NOT `void` it): callers/tests `await
  // button.onclick()` to let the whole action chain settle before asserting
  // status text. The `.catch` already resolves the promise, so no floating
  // rejection leaks under strict settings.
  b.onclick = () => action().catch((error) => setStatus(errMsg(error), true));
  li.append(b);
  byId<HTMLUListElement>(list).append(li);
}

export function resetProject() {
  submittedPlan = null;
  patchSource = submittedPatch = null;
  byId<HTMLParagraphElement>('patch-source').textContent = '请从已完成的 Illustrator 或 Photoshop 任务选择修改来源。';
  epoch++;
  taskCursor = eventCursor = null;
  eventJob = '';
  pendingImport = null;
  nativeCursor = null;
  byId<HTMLParagraphElement>('native-info').textContent = '';
  for (const id of ['assets', 'tasks', 'events', 'native-assets', 'reference-picker',
                    'design-briefs', 'design-directions', 'design-bindings',
                    'brief-lineage', 'direction-lineage', 'recent-plans'])
    byId<HTMLUListElement>(id).replaceChildren();
  // The sentence below must stay byte-identical to #recent-plans-info in index.html, which is
  // what it reads before this page runs any script; test_workbench_first_screen_columns.py pins it.
  byId<HTMLParagraphElement>('recent-plans-info').textContent = '未选项目，因此这一列没有读过任何方案。';
  // F-2b: a project switch also drops the design-layer revision state + its DOM,
  // which design.js owns. The single cross-module call below keeps cross-module
  // state writes at zero (everything else resetProject clears is workbench-local).
  resetDesignRevision();
  for (const id of ['preview', 'retry-import', 'more-tasks', 'more-events', 'more-native']) byId(id).hidden = true;
  byId<HTMLImageElement>('preview').removeAttribute('src');
  byId<HTMLParagraphElement>('preview-empty').hidden = false;
  byId<HTMLParagraphElement>('asset-info').textContent = '';
}

export async function projects() {
  const data = await api<ProjectListResponse>('/projects');
  byId<HTMLSelectElement>('project').replaceChildren(new Option('选择项目', ''));
  for (const p of data.projects) byId<HTMLSelectElement>('project').append(new Option(p.name, p.id));
  if (!project) {
    let remembered = '';
    try { remembered = window.localStorage.getItem('design-lab:active-project') || ''; }
    catch { /* Storage may be disabled; the service remains usable. */ }
    if (data.projects.some((p) => p.id === remembered)) project = remembered;
    else if (data.projects.length === 1) project = data.projects[0]!.id;
  }
  if (data.projects.some((p) => p.id === project)) byId<HTMLSelectElement>('project').value = project;
}

function rememberProject(): void {
  try { window.localStorage.setItem('design-lab:active-project', project); }
  catch { /* Project state itself is persisted by the service. */ }
}

export async function loadEvents(job: string, append = false) {
  if (append && job !== eventJob) return;
  const current = epoch;
  const owner = project;
  const request = ++eventRequest;
  if (!append) {
    eventJob = job;
    eventCursor = null;
    byId<HTMLOListElement>('events').replaceChildren();
    byId<HTMLButtonElement>('more-events').hidden = true;
  }
  const data = await api<EventListResponse>(
    `/projects/${owner}/tasks/${job}/events` + (append && eventCursor !== null ? `?after=${eventCursor}` : ''),
  ).catch((error) => {
    if (current !== epoch || request !== eventRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== eventRequest) return;
  for (const event of data.events) {
    const li = document.createElement('li');
    li.textContent = `${event.at} · attempt ${event.attempt_no} · ${event.from_state || 'NEW'} → ${event.to_state}`;
    byId<HTMLOListElement>('events').append(li);
  }
  eventCursor = data.next_cursor;
  byId<HTMLButtonElement>('more-events').hidden = eventCursor === null;
}

export async function tasks(append = false) {
  if (append && taskCursor === null) return;
  if (!append) {
    taskCursor = null;
    byId<HTMLButtonElement>('more-tasks').hidden = true;
  }
  const current = epoch;
  const owner = project;
  const request = ++taskRequest;
  const data = await api<TaskListResponse>(
    `/projects/${owner}/tasks` + (append && taskCursor ? `?after=${taskCursor}` : ''),
  ).catch((error) => {
    if (current !== epoch || request !== taskRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== taskRequest) return;
  if (!append) byId<HTMLUListElement>('tasks').replaceChildren();
  for (const task of data.tasks) {
    button('tasks', `${task.kind} · ${task.state} · attempt ${task.attempt.attempt_no} · ${task.job_id.slice(-12)}`, () => loadEvents(task.job_id));
    if (task.kind.endsWith('-native') && task.attempt.state === 'RECEIPTED')
      button('tasks', `导出交付包 · ${task.job_id.slice(-12)} · rights/质量待审`, () => exportBundle(task));
    if (['illustrator-native', 'photoshop-native'].includes(task.kind) && task.attempt.state === 'RECEIPTED')
      button('tasks', `修改对象 · ${task.job_id.slice(-12)}`, async () => {
        if (current !== epoch) return;
        patchSource = { owner, job: task.job_id, attempt: task.attempt.attempt_id };
        byId<HTMLParagraphElement>('patch-source').textContent =
          `来源 ${task.job_id} · ${task.attempt.attempt_id}。将在新副本修改，不覆盖原件。`;
      });
    if (task.kind.endsWith('-native') && ['PENDING', 'RUNNING', 'OUTCOME_UNKNOWN'].includes(task.attempt.state))
      button('tasks', `请求取消 · ${task.job_id.slice(-12)}`, () => cancelTask(task));
    if (task.kind.endsWith('-native') && task.attempt.state === 'PENDING')
      button('tasks', `启动任务 · ${task.job_id.slice(-12)}`, () => startTask(task));
  }
  if (!append && !data.tasks.length) setListNotice('tasks', '尚无任务。导入图片后可查看真实记录。');
  taskCursor = data.next_cursor;
  byId<HTMLButtonElement>('more-tasks').hidden = taskCursor === null;
}

export async function startTask(task: TaskRecord) {
  const current = epoch;
  const owner = project;
  const data = await api<TaskDispatchResponse>(
    `/projects/${owner}/tasks/${task.job_id}/run`,
    { attempt_id: task.attempt.attempt_id },
  ).catch((error) => {
    if (current !== epoch) return null;
    throw error;
  });
  if (!data || current !== epoch) return;
  await tasks();
  if (current !== epoch) return;
  setStatus(`工作进程：${data.worker}；不代表制作成功，请刷新查看宿主读回状态。`);
}

export async function cancelTask(task: TaskRecord) {
  const current = epoch;
  const owner = project;
  const data = await api<TaskActionResponse>(
    `/projects/${owner}/tasks/${task.job_id}/cancel`,
    { attempt_id: task.attempt.attempt_id },
  ).catch((error) => {
    if (current !== epoch) return null;
    throw error;
  });
  if (!data || current !== epoch) return;
  await tasks();
  if (current !== epoch) return;
  setStatus(`取消请求读回：${data.task.attempt.state}；请求受理不代表宿主已停止。`);
}

export async function exportBundle(task: TaskRecord) {
  const current = epoch;
  const owner = project;
  const access = token;
  setStatus('正在核对原生文件并打包；此操作不代表设计验收。');
  const data = await api<BundleDownloadResponse>(`/projects/${owner}/tasks/${task.job_id}/bundle`, {});
  if (current !== epoch) return;
  const expected = new RegExp(`^/api/projects/${owner}/bundles/bundle-native-[0-9a-f]{64}/versions/v-[0-9a-f]{32}/content$`);
  if (!expected.test(data.download_path)) throw new Error('INVALID_BUNDLE_ROUTE');
  const response = await fetch(data.download_path, { headers: { Authorization: 'Bearer ' + access }, cache: 'no-store' });
  if (!response.ok) throw new Error('BUNDLE_DOWNLOAD_UNVERIFIED');
  const bytes = await response.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (b) => b.toString(16).padStart(2, '0')).join('');
  if (digest !== data.bundle.sha256 || bytes.byteLength !== data.bundle.byte_size) throw new Error('BUNDLE_HASH_MISMATCH');
  if (current !== epoch) return;
  const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `design-lab-${task.job_id.slice(-12)}.zip`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
  setStatus('交付包下载 hash 已核对；字体、链接、rights 与质量仍需验收。');
}

export async function preview(assetId: string) {
  const current = epoch;
  const request = ++previewRequest;
  const data = await api<AssetContentResponse>(`/projects/${project}/assets/${assetId}/content`).catch((error) => {
    if (current !== epoch || request !== previewRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== previewRequest) return;
  if (!['image/png', 'image/jpeg'].includes(data.asset.media_type)) throw new Error('UNSUPPORTED_PREVIEW');
  byId<HTMLImageElement>('preview').src = `data:${data.asset.media_type};base64,${data.content_base64}`;
  byId<HTMLImageElement>('preview').hidden = false;
  byId<HTMLParagraphElement>('preview-empty').hidden = true;
  byId<HTMLParagraphElement>('asset-info').textContent =
    `${data.asset.width} × ${data.asset.height} · rights: ${data.asset.rights} · ${data.asset.sha256}`;
}

export async function refresh() {
  if (!project) return;
  const current = epoch;
  const request = ++refreshRequest;
  setStatus('正在读取项目资产与任务…');
  const result = await Promise.all([api<AssetListResponse>(`/projects/${project}/assets`), tasks(), nativeAssets(), recentPlans()]).catch((error) => {
    if (current !== epoch || request !== refreshRequest) return null;
    throw error;
  });
  if (!result || current !== epoch || request !== refreshRequest) return;
  const [data] = result;
  byId<HTMLUListElement>('assets').replaceChildren();
  for (const asset of data.assets)
    button('assets', `${asset.width} × ${asset.height} · ${asset.media_type} · ${asset.id.slice(-10)}`, () => preview(asset.id));
  // P0-05: expose the imported assets in the 05 design layer as a lightweight
  // reference picker (checkboxes). A brief may only reference assets that were
  // actually imported into THIS project — the backend fails closed otherwise.
  populateReferencePicker(data.assets.map((asset) => asset.id));
  setStatus('已读取持久化状态。参考素材权利仍需审查。');
}

// 首屏右列：最近方案。"最近"是服务的读数（assistance_plan.py::AssistancePlans.list 按
// created_at DESC 发回每个计划的最新修订），不是页面自己排的序。三种"没读到"与一种"读到 0 条"
// 各写各的句子：把前三句写成第四句，就是这个仓库反复定罪的那种谎。
export const RECENT_PLANS_LIMIT = 5;

export async function recentPlans(): Promise<void> {
  const info = byId<HTMLParagraphElement>('recent-plans-info');
  const list = byId<HTMLUListElement>('recent-plans');
  if (!project) {
    list.replaceChildren();
    info.textContent = '未选项目，因此这一列没有读过任何方案。';
    return;
  }
  const current = epoch;
  const owner = project;
  const request = ++plansRequest;
  let data: AssistancePlanListView;
  try {
    data = await api<AssistancePlanListView>(
      `/projects/${owner}/assistance-plans?limit=${RECENT_PLANS_LIMIT}`);
  } catch (error) {
    if (current !== epoch || request !== plansRequest) return;
    list.replaceChildren();
    info.textContent = `最近方案没读到：${errMsg(error)}。这不代表这个项目没有方案。`;
    return;
  }
  if (current !== epoch || request !== plansRequest || owner !== project) return;
  if (!Array.isArray(data?.plans)) {
    list.replaceChildren();
    info.textContent = '未读回：响应里没有 plans 数组，因此不能说这个项目没有方案。';
    return;
  }
  const rows = data.plans;
  if (!rows.length) {
    setListNotice('recent-plans', '还没有方案记录。设计辅助里可以立第一条。');
    info.textContent = `这一页读到 ${data.returned} 条，这个项目共 ${data.total} 条。`;
    return;
  }
  list.replaceChildren(...rows.map((row) => {
    const li = document.createElement('li');
    li.className = 'plan-line';
    const title = document.createElement('strong');
    title.textContent = row.objective;
    const meta = document.createElement('small');
    meta.textContent = `${row.created_at} · ${row.created_by}`;
    li.append(title, meta);
    return li;
  }));
  info.textContent = `这一页读到 ${data.returned} 条，服务按写入时间倒序发回；这个项目共 ${data.total} 条`
    + (data.total > rows.length ? `，还有 ${data.total - rows.length} 条在这一页之外。` : '。');
}

// P0-05: one checkbox per imported asset; checked ids are what submitBrief sends.
export function populateReferencePicker(assetIds: string[]) {
  const picker = byId<HTMLUListElement>('reference-picker');
  const selected = new Set(typeof document.querySelectorAll === 'function' ? selectedReferences() : []);
  picker.replaceChildren();
  if (!assetIds.length) {
    const li = document.createElement('li');
    li.textContent = '尚未导入参考素材。先导入 PNG/JPEG，再回来为简报勾选。';
    picker.append(li);
    return;
  }
  for (const id of assetIds) {
    const li = document.createElement('li');
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.name = 'reference-asset';
    box.value = id;
    box.checked = selected.has(id);
    label.append(box, document.createTextNode(' ' + id));
    li.append(label);
    picker.append(li);
  }
}

export function selectedReferences(): string[] {
  return Array.from(document.querySelectorAll<HTMLInputElement>('input[name="reference-asset"]:checked')).map((el) => el.value);
}

export async function verifyNative(asset: NativeAssetRecord) {
  const current = epoch;
  const owner = project;
  const request = ++verificationRequest;
  byId<HTMLParagraphElement>('native-info').textContent = '正在读取原生文件并校验 hash…';
  const data = await api<NativeAssetVerifyResponse>(`/projects/${owner}/native-assets/${asset.id}/verify`).catch((error) => {
    if (current !== epoch || request !== verificationRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== verificationRequest) return;
  byId<HTMLParagraphElement>('native-info').textContent =
    `${data.asset.kind.toUpperCase()} · ${data.asset.version_id} · ${data.asset.verification} · ${data.asset.byte_size} bytes · ${data.asset.sha256} · rights: ${data.asset.rights}。此校验不代替宿主重开或人工质量验收。`;
}

export async function nativeAssets(append = false) {
  if (append && nativeCursor === null) return;
  if (!append) {
    nativeCursor = null;
    byId<HTMLButtonElement>('more-native').hidden = true;
  }
  const current = epoch;
  const owner = project;
  const request = ++nativeRequest;
  const data = await api<NativeAssetListResponse>(
    `/projects/${owner}/native-assets` + (append && nativeCursor ? `?after=${nativeCursor}` : ''),
  ).catch((error) => {
    if (current !== epoch || request !== nativeRequest) return null;
    throw error;
  });
  if (!data || current !== epoch || request !== nativeRequest) return;
  if (!append) byId<HTMLUListElement>('native-assets').replaceChildren();
  for (const asset of data.assets)
    button('native-assets', `校验 ${asset.kind.toUpperCase()} · v${asset.version_no} · ${asset.version_id} · 数据库记录`, () => verifyNative(asset));
  if (!append && !data.assets.length) setListNotice('native-assets', '暂无已登记的 AI/PSD。');
  nativeCursor = data.next_cursor;
  byId<HTMLButtonElement>('more-native').hidden = nativeCursor === null;
}

export async function sendImport() {
  if (!pendingImport || busy) return;
  const job = pendingImport;
  busy = true;
  byId<HTMLButtonElement>('import-button').disabled = true;
  byId<HTMLButtonElement>('retry-import').hidden = true;
  setStatus('正在导入并验证图片。关闭页面不撤销服务端操作。');
  try {
    await api(`/projects/${job.project}/assets`, job.body);
    if (pendingImport === job) pendingImport = null;
    if (project === job.project) await refresh();
    setStatus('导入已保存；选择资产查看服务器读回。');
  } catch (error) {
    setStatus(`导入未确认：${errMsg(error)}。可使用同一幂等键重试；不会自动重复创建。`, true);
    byId<HTMLButtonElement>('retry-import').hidden = pendingImport !== job;
  } finally {
    busy = false;
    byId<HTMLButtonElement>('import-button').disabled = false;
  }
}

export async function connectLocalService(submittedToken = ''): Promise<void> {
  const generation = ++connectGeneration;
  if (!submittedToken) {
    setStatus('正在连接本机设计服务…');
    try {
      const response = await fetch('/api/local-session', { cache: 'no-store', signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('本机服务未开启自动连接，请使用官方 workbench 启动入口。');
      const session = await response.json() as { token?: string };
      if (generation !== connectGeneration) return;
      submittedToken = session.token || '';
    } catch (error) {
      if (generation !== connectGeneration) return;
      setStatus(errMsg(error), true);
      return;
    }
  }
  if (!/^[0-9a-f]{64}$/.test(submittedToken)) {
    token = '';
    connected = false;
    setStatus('访问令牌格式不正确。', true);
    return;
  }
  token = submittedToken;
  try {
    await projects();
    if (generation !== connectGeneration || token !== submittedToken) return;
    connected = true;
    byId<HTMLDivElement>('login').hidden = true;
    byId<HTMLDivElement>('workspace').hidden = false;
    byId<HTMLSpanElement>('connection').textContent = '本机已连接';
    setStatus('选择或新建项目。');
    if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function')
      window.dispatchEvent(new Event('hashchange'));
    if (project) {
      resetProject();
      void Promise.all([refresh(), loadDesignSystems(), refreshDesign()])
        .catch((error) => setStatus(`已连接，项目读回失败：${errMsg(error)}`, true));
    }
  } catch (error) {
    if (generation !== connectGeneration || token !== submittedToken) return;
    token = '';
    connected = false;
    setStatus(errMsg(error), true);
  }
}

byId<HTMLFormElement>('connect-form').onsubmit = async (event) => {
  event.preventDefault();
  const submittedToken = byId<HTMLInputElement>('token').value;
  byId<HTMLInputElement>('token').value = '';
  await connectLocalService(submittedToken);
};

byId<HTMLButtonElement>('disconnect').onclick = () => {
  connectGeneration += 1;
  token = '';
  connected = false;
  project = '';
  resetProject();
  byId<HTMLDivElement>('workspace').hidden = true;
  byId<HTMLDivElement>('login').hidden = false;
  byId<HTMLSpanElement>('connection').textContent = '未连接';
  setStatus('已清除页面内存中的访问令牌。');
};

byId<HTMLSelectElement>('project').onchange = () => {
  project = byId<HTMLSelectElement>('project').value;
  rememberProject();
  resetProject();
  refresh().catch((e) => setStatus(errMsg(e), true));
  loadDesignSystems().catch((e) => setStatus(errMsg(e), true));
  refreshDesign().catch((e) => setStatus(errMsg(e), true));
};

byId<HTMLButtonElement>('refresh').onclick = () => {
  void refresh().catch((e) => setStatus(errMsg(e), true));
  void loadDesignSystems().catch((e) => setStatus(errMsg(e), true));
  void refreshDesign().catch((e) => setStatus(errMsg(e), true));
};

// 首屏右列的唯一动作：把这一列的完整列表打开。这里只写 hash，不复制路由表——shell.ts 的
// ROUTE_VIEWS 才是目的地的主人，那条 hash 由 test_workbench_first_screen_columns.py 逐字核对。
byId<HTMLButtonElement>('open-assistant').onclick = () => {
  if (typeof window === 'undefined' || !window.location) return;
  window.location.hash = '#/assistant';
};

let creatingProject = false;
byId<HTMLFormElement>('create-form').onsubmit = async (event) => {
  event.preventDefault();
  if (creatingProject) return;
  creatingProject = true;
  const form = byId<HTMLFormElement>('create-form');
  const submit = typeof form.querySelector === 'function' ? form.querySelector<HTMLButtonElement>('button') : null;
  if (submit) submit.disabled = true;
  try {
    const data = await api<ProjectCreateResponse>('/projects', { name: byId<HTMLInputElement>('project-name').value });
    project = data.project.id;
    rememberProject();
    resetProject();
    await projects();
    byId<HTMLInputElement>('project-name').value = '';
    await refresh();
  } catch (error) {
    setStatus(errMsg(error), true);
  } finally {
    creatingProject = false;
    if (submit) submit.disabled = false;
  }
};

byId<HTMLFormElement>('import-form').onsubmit = async (event) => {
  event.preventDefault();
  if (busy) return;
  const input = byId<HTMLInputElement>('file');
  const file = input.files && input.files[0];
  const owner = project;
  if (!owner || !file) {
    setStatus('请先选择项目和图片。', true);
    return;
  }
  if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 32 * 1024 * 1024) {
    setStatus('仅支持不超过 32 MiB 的 PNG/JPEG。', true);
    return;
  }
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (owner !== project) throw new Error('项目已切换，请重新导入');
    let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    pendingImport = { project: owner, body: { content_base64: btoa(binary), idempotency_key: crypto.randomUUID() } };
    await sendImport();
  } catch (error) {
    setStatus(errMsg(error), true);
  }
};

byId<HTMLButtonElement>('retry-import').onclick = () => {
  void sendImport();
};

byId<HTMLFormElement>('plan-form').onsubmit = async (event) => {
  event.preventDefault();
  if (planBusy) return;
  const current = epoch;
  const owner = project;
  try {
    if (!owner) throw new Error('请先选择项目');
    const raw = byId<HTMLTextAreaElement>('plan-rir').value;
    const styles = byId<HTMLTextAreaElement>('plan-styles').value;
    if (raw.length + styles.length > 3900000) throw new Error('对象计划过大');
    const body: Record<string, unknown> = {
      host: byId<HTMLSelectElement>('plan-host').value,
      rir: JSON.parse(raw),
      text_styles: JSON.parse(styles),
    };
    const identity = JSON.stringify(body);
    if (!submittedPlan || submittedPlan.owner !== owner || submittedPlan.identity !== identity)
      submittedPlan = { owner, identity, key: crypto.randomUUID() };
    body.idempotency_key = submittedPlan.key;
    planBusy = true;
    byId<HTMLButtonElement>('plan-submit').disabled = true;
    const data = await api<NativePlanResponse>(`/projects/${owner}/native-plans`, body);
    if (current !== epoch) return;
    await tasks();
    if (current !== epoch) return;
    setStatus(`对象计划已持久化：${data.task.attempt.state}。请从任务列表显式启动；未执行质量或权利验收。`);
  } catch (error) {
    if (current === epoch) setStatus(`计划提交未确认：${errMsg(error)}。内容不变时重试复用幂等键。`, true);
  } finally {
    planBusy = false;
    byId<HTMLButtonElement>('plan-submit').disabled = false;
  }
};

byId<HTMLButtonElement>('more-tasks').onclick = () => {
  void tasks(true).catch((e) => setStatus(errMsg(e), true));
};

byId<HTMLFormElement>('patch-form').onsubmit = async (event) => {
  event.preventDefault();
  if (patchBusy) return;
  const current = epoch;
  const owner = project;
  const source = patchSource;
  try {
    if (!source || source.owner !== owner) throw new Error('请先选择当前项目的 Illustrator 来源任务');
    const raw = byId<HTMLTextAreaElement>('patch-json').value;
    if (raw.length > 900000) throw new Error('局部修改过大');
    const body: Record<string, unknown> = { source_attempt_id: source.attempt, patch: JSON.parse(raw) };
    const identity = JSON.stringify({ source, body });
    if (!submittedPatch || submittedPatch.identity !== identity)
      submittedPatch = { identity, key: crypto.randomUUID() };
    body.idempotency_key = submittedPatch.key;
    patchBusy = true;
    byId<HTMLButtonElement>('patch-submit').disabled = true;
    const data = await api<PatchResponse>(`/projects/${owner}/tasks/${source.job}/patch`, body);
    if (current !== epoch) return;
    await tasks();
    if (current !== epoch) return;
    setStatus(`局部修改已排队：${data.task.attempt.state} · 父版本 ${data.parent.version_id}。需显式启动，尚未执行或通过质量验收。`);
  } catch (error) {
    if (current === epoch) setStatus(`局部修改提交未确认：${errMsg(error)}。相同内容重试复用幂等键。`, true);
  } finally {
    patchBusy = false;
    byId<HTMLButtonElement>('patch-submit').disabled = false;
  }
};

byId<HTMLButtonElement>('more-events').onclick = () => {
  void loadEvents(eventJob, true).catch((e) => setStatus(errMsg(e), true));
};

byId<HTMLButtonElement>('more-native').onclick = () => {
  void nativeAssets(true).catch((e) => setStatus(errMsg(e), true));
};
