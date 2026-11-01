/**
 * Isolated state-transition reproduction, NOT the product or a browser E2E.
 * Source: DESIGN-LAB PR 135, commit 085a0f6ed8e0cd0db6e459cae9ce9c6f772f8ce2,
 * apps/workbench/main.ts, mountAppShell().show(), fetched lines 1234–1316.
 * The visibility assignments below reproduce the fetched control flow.
 * No network, credentials, repository writes, or dependencies are involved.
 */
import assert from 'node:assert/strict';

const login = { hidden: false };
const workspace = { hidden: true };
const routePanel = { hidden: true };
const trace = [];
const token = ''; // An explicitly unauthenticated initial state.

function show(view) {
  const showWorkbench = view === 'workbench';
  routePanel.hidden = showWorkbench;
  login.hidden = showWorkbench ? login.hidden : true;
  if (showWorkbench) {
    workspace.hidden = login.hidden ? false : workspace.hidden;
    return;
  }
  login.hidden = true;
  workspace.hidden = true;
  if (!token) return; // The actual UI renders a connection hint here.
}

for (const view of ['workbench', 'dashboard', 'workbench']) {
  show(view);
  trace.push({ view, loginHidden: login.hidden, workspaceHidden: workspace.hidden,
               routePanelHidden: routePanel.hidden });
}
console.log(JSON.stringify({ kind: 'ISOLATED_LOGIC_REPRO', trace }, null, 2));
// This safety expectation FAILS with the fetched visibility assignments.
assert.equal(login.hidden, false,
  'Returning to workbench while unauthenticated should restore the login panel');
assert.equal(workspace.hidden, true,
  'Unauthenticated navigation must not present the workspace as connected');
