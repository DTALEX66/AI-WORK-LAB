# U19 NEXT-CYCLE DESIGN — 2026-09-23 (mainline takeover of failed free-pool subagent)

> Read-only design for the next fix cycle on the U19 headless-WebView failure.
> Evidence anchor: 493be49 observer job log (.project-local/runs/u19_493be49.txt).
> Signature: backend PASS, app.exe pid RUNNING/ALIVE, CDP "no page target on :50591",
> GDI "windows=0". The 6fd51d9 probe-window sizing fix did NOT clear windows=0.
> No code changes in this pass — discriminator-only, to be applied in a later
> user-authorized cycle.

## Root-cause ranking (most likely first)

### R1 — headless session has no visible desktop (dominant, CI-specific)
GitHub windows-2025 runner executes jobs in a service session with no interactive
desktop. WebView2 (Chromium-based) windows in such a session frequently report
IsWindowVisible=false and PrintWindow returns no pixels — even when the window
object exists. The 800×600 visible(true) fix targets *size*, but on a desktop-less
session the *visibility flag itself is false*, so the ≥200×150 AND visible filter in
_gdi_render_proof still yields 0.
- Single discriminator: the `diagnostic_all_pid_windows` block (added 6fd51d9)
  enumerates EVERY pid window WITHOUT the visible/size filter. Next run's
  u19_webview_readback.json → check `diagnostic_all_pid_windows`:
    · empty {}  → window never created (→ R3/R4)
    · has entries, all visible:false → R1 CONFIRMED (desktop-less session)
    · has entries, visible:true, w≥200 h≥150 → filter/capture bug (→ R4)
  Grep next CI log: `grep all_pid_windows .project-local/runs/u19_*`
- Fix direction (next cycle): stop keying the verdict on GDI visibility in
  headless; make CDP page-target the primary proof and treat GDI as best-effort.

### R2 — CDP renderer not attached within the single-probe window (timing)
The harness does ONE CDP /json probe + ONE 1.5s GDI sleep. On swiftshader
software render + slow headless, the DevTools page target attaches late, so a
single early probe reads "no page target" even though it comes up seconds later.
- Single discriminator: change the CDP probe to a bounded POLL (retry /json every
  500ms up to ~15s). Evidence line to check after:
  `[U19] CDP readback` becomes PASS with a `polls=N` field, or stays FAIL with
  the max-poll count recorded.
- This is the highest-value single change: if CDP ever returns a page target,
  verdict = backend AND (cdp PASS) → whole gate passes, GDI immaterial.

### R3 — pid filter misses the real window owner (process spawn)
Tauri/WebView2 can spawn child processes; the top-level window may be owned by a
CHILD pid, not the `app.pid` we launch+track. GetWindowThreadProcessId returns the
owning process; a child-owned window is invisible to our `pidout==app.pid` filter.
- Single discriminator: broaden the GDI pid filter to the LAUNCHED process TREE
  (pid + descendants via a TaskList/GetWindowThreadProcessId walk). Evidence:
  `diagnostic_all_pid_windows` empty BUT `tasklist` in the same run shows a
  child pid with a window. Add one `wmic`/`tasklist /FI` dump to the harness.

### R4 — GetClientRect vs GetWindowRect during init (filter semantics)
Filter uses GetClientRect (client area). A window mid-initialization reports a
tiny client rect and is wrongly excluded even though it will grow to 800×600.
- Single discriminator: capture BOTH GetClientRect and GetWindowRect in the
  diagnostic; if diagnostic shows window-rect ≥200×150 but client-rect <200×150,
  the filter is using the wrong metric → switch the capturable test to
  GetWindowRect. Evidence line: compare the two rect fields in the JSON.

## What to apply in the NEXT authorized cycle (ranked, minimal)
1. CDP bounded poll (R2) — single highest-leverage change; may unblock alone.
2. demote GDI from verdict-gate to best-effort when CDP is unreachable in
   headless (R1) — makes the gate robust to desktop-less sessions.
3. broaden pid filter to process tree (R3).
4. GetWindowRect in filter (R4).
Each is independently observable in one CI run; apply 1+2 together first,
re-read u19_webview_readback.json, then add 3/4 only if the evidence still
points there. This keeps each cycle single-diagnostic, evidence-driven —
no shotgun rewrite.

## Discriminator evidence landed in 0bbbce8 (probe-window externalization)

Added to the harness (0bbbce8, NOT yet committed at design time): the app now
writes its probe-window build outcome to a file the harness prints verbatim to
CI. The 0bbbce8 observer job log (.project-local/runs/u19_0bbbce8.log) produced:

```
[U19] CDP readback FAILED: RuntimeError('no CDP page target on 127.0.0.1:52418')
[U19] GDI render proof: unavailable (windows=0)
[U19] probe window status: probe=ok pid=9208 visible=false cdpPort=52418
[U19] pid window hwnd=131638 w=0 h=0 visible=False   (+ 6 more pid windows, all w=0 h=0)
```

### Root cause DISCRIMINATED: R5 — headless-session WebView2 surface (NOT R1–R4 as originally ranked)

- `probe=ok` → the probe window BUILT successfully on the runner → **R3 "never created" EXCLUDED**
- EnumWindows found 7 pid windows → **R4 "no window at all" EXCLUDED**
- CDP already polls ~45s (tries=90) and STILL gets no page target → **R2 "single-probe timing" EXCLUDED**
- 7 windows all `w=0 h=0` + `probe visible=false` + CDP port open but no page target
  → the CDP port is reachable yet the WebView2 renderer never produced a page
  target: the webview surface did not initialize inside a GitHub-hosted
  `windows-latest` job (session-0, no interactive desktop).

This is an ENVIRONMENT limitation of the hosted runner, not a code defect:
backend PASS + window build ok + Rust compile green already prove the native
shell / orchestration chain. Two fix cycles (6fd51d9 sizing, 0bbbce8
externalization) hit the same ceiling → per the "2 rounds, then re-qualify"
iron law, this is re-qualified as a KNOWN runner-environment boundary.

### Remaining paths to a real U19 close (each needs user authorization)
1. **Desktop real-WebView readback on a real Windows desktop** (user's own
   machine or a self-hosted / desktop-attached CI runner): run
   `python scripts/u19_webview_e2e.py` where a real WebView2 surface exists.
   This is the only way to produce the "real WebView" layer of the layered
   desktop proof.
2. **Self-hosted / desktop-attached Windows runner** for the observer job's
   E2E stage, leaving all structural gates on the hosted `windows-latest`.
3. **Headless-conditional verdict**: detect the session-0 desktop-less
   environment and report U19 as `SKIPPED_HEADLESS` (with a recorded reason)
   instead of FAIL, while keeping the desktop E2E proof on a real desktop.
   (Would require a governance gate exemption in the workflow.)
4. **Force-attach / longer CDP poll** (weakest — R2 already excluded;
   not recommended).

## Known-external, out of scope (do NOT chase here)
- Real-Host E3 / MiniMax live / tag E5 (DESIGN-LAB external-model lane).


---

## POST-MERGE STATUS (2026-09-23, authoritative)
The 'Remaining paths' options above are RESOLVED: **Path 3 (headless-conditional verdict) was selected and executed.**
- `SKIPPED_HEADLESS` verdict landed in commit `9f57ca3` (single-file harness change in apps/observer/scripts/u19_webview_e2e.py, non-critical zone → no forced all-gates).
- fail-closed preserved: real regressions still FAIL; local-desktop semantics unchanged; evidence JSON records `skippedReason` (audit chain, not fake PASS).
- CI-verified: work-lab-gate @b993e9c 5/5 SUCCESS (incl. observer SKIPPED_HEADLESS exit 0); aggregate green at ruleset 23825562 → u17 merged to main via PR #127 at `62f666e`.
- **Path 1 (real-desktop WebView2 E2E) remains the open known-external layer** — requires a real Windows desktop or self-hosted/desktop-attached runner; out of scope on hosted CI by design. User decision when a desktop runner is available.

### Local desktop attempt 2026-09-23 (Path 1, pre-MSVC — honest FAIL, fail-closed)
Ran `apps/observer/scripts/u19_webview_e2e.py` on the local Windows desktop session:
- backend v3 PASS (projects=1), tauri_launch RUNNING (pid 30464), CDP no page target,
- app.exe early-exit rc=3221225781 (0xC0000135 STATUS_DLL_NOT_FOUND): the local GNU-toolchain build does not link
  WebView2Loader (MSVC-only runtime dep; target/release bundles only app_lib.dll + libgcc + libwinpthread),
- this machine has no Rust/MSVC toolchain (cargo/rustc absent, .rustup data-only), so no clean MSVC build locally.
Verdict recorded as FAIL (not SKIPPED_HEADLESS — that verdict requires GITHUB_ACTIONS + app ALIVE + probe=ok).
Evidence: `.project-local/runs/u19_webview_readback.json`. Path 1 remains owed to an MSVC-capable
desktop/self-hosted runner; do NOT chase on hosted CI (known-external, by design).
