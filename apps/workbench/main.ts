// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench — product entry (Lane-C split of the D002 monolith). Owns only
// the mount guard; all behavior + handler wiring lives in the workbench/design/shell
// modules. Vite inlines them into ONE flat classic-script bundle (D003 Build Output
// Truth / D004 classic-script loadability): `export let` state emits as bare top-level
// globals so the native-UI vm contract tests keep driving the bundle. Entry module has
// no exports, so the emitted bundle keeps ZERO top-level import/export.

import { byId, errMsg, setStatus } from './workbench.js';
import { bindDesignSystem, submitBrief, submitBriefRevision, submitDirection, submitDirectionRevision } from './design.js';
import { mountAppShell } from './shell.js';
import { mountEnhancedMotion } from './motion.js';
import { connectLocalService } from './workbench.js';

byId<HTMLFormElement>('design-brief-form').onsubmit = (event) => {
  event.preventDefault();
  void submitBrief().catch((e) => setStatus(errMsg(e), true));
};
byId<HTMLFormElement>('brief-revision-form').onsubmit = (event) => {
  event.preventDefault();
  void submitBriefRevision().catch((e) => setStatus(errMsg(e), true));
};
byId<HTMLFormElement>('direction-revision-form').onsubmit = (event) => {
  event.preventDefault();
  void submitDirectionRevision().catch((e) => setStatus(errMsg(e), true));
};
byId<HTMLFormElement>('design-direction-form').onsubmit = (event) => {
  event.preventDefault();
  void submitDirection().catch((e) => setStatus(errMsg(e), true));
};
byId<HTMLButtonElement>('design-system-bind').onclick = () => {
  void bindDesignSystem().catch((e) => setStatus(errMsg(e), true));
};

// Dev-mode bypass (local single-user research use): when the page is served by
// a Vite dev server, the login panel auto-hides and the workspace + AppShell
// route views mount directly so all 19 ROUTE_VIEWS screens are browsable without a
// service token.  API reads stay readback-honest: an API view without a
// connected token says "请先连接" instead of faking data.  Production
// builds connect automatically through the official loopback launcher.
//
// NOTE: detection lives here and is re-implemented in shell.ts as devMode();
// keep the two marker checks in sync (@vite/client script OR ?dev=1).
function devBypassEnabled(): boolean {
  if (typeof document === 'undefined' || typeof window === 'undefined') return false;
  // Vite dev server injects @vite/client — the definitive dev-server marker.
  // Substring-match the src: the injected tag is src="/@vite/client" (no base)
  // or src="/workbench/@vite/client" (--base /workbench/); both contain the
  // "@vite/client" marker.
  if (typeof document.querySelectorAll === 'function'
      && document.querySelectorAll('script[src*="@vite/client"]').length > 0) return true;
  // Explicit ?dev=1 query (local single-user research use without a service
  // token). Guarded: the vm unit-smoke Mock window.location may lack `search`.
  try {
    const qs: string | undefined = (window.location as { search?: string }).search;
    if (typeof qs === 'string' && qs.includes('dev=1')) return true;
  } catch { /* vm */ }
  return false;
}

if (typeof document !== 'undefined'
    && document.body !== undefined
    && typeof window !== 'undefined'
    && devBypassEnabled()
    && (document as Document & { __dlShellMounted?: boolean }).__dlShellMounted !== true) {
  (document as Document & { __dlShellMounted?: boolean }).__dlShellMounted = true;
  mountAppShell();
} else if (typeof document !== 'undefined'
    && document.body !== undefined
    && typeof window !== 'undefined'
    && document.getElementById('login') !== null
    && (document as Document & { __dlShellMounted?: boolean }).__dlShellMounted !== true) {
  (document as Document & { __dlShellMounted?: boolean }).__dlShellMounted = true;
  mountAppShell();
}

// Dev-mode: hide the login panel and show the workspace (readback-honest).
if (typeof document !== 'undefined' && document.body !== undefined && devBypassEnabled()) {
  const loginEl = document.getElementById('login');
  const workspaceEl = document.getElementById('workspace');
  const connEl = document.getElementById('connection');
  if (loginEl) loginEl.hidden = true;
  if (workspaceEl) { workspaceEl.hidden = false; }
  if (connEl) connEl.textContent = '未连接 · 本地浏览模式';
}

// Official loopback launcher: page reload reconnects without copying credentials.
if (typeof window !== 'undefined' && document.body?.dataset.localSession === 'auto'
    && !devBypassEnabled()) void connectLocalService();

// Enhanced motion (owner 2026-10-25: 「STITCH 更多是静态页面 … 加入更多动画动效」). Opt-in
// through ?motion=enhanced and inert under prefers-reduced-motion, so the static screens the
// pack and every geometry gate were measured against stay exactly as measured.
if (typeof document !== 'undefined' && document.body !== undefined) {
  mountEnhancedMotion(document);
}
