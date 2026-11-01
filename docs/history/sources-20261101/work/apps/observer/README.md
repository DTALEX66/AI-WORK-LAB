# WORK-LAB Observer

WORK-LAB Observer 是严格只读的观测与证据层，仅从 Workflow Assistance 的公开事件与脱敏 evidence envelope 生成可重建的派生 projection。

## Boundary

- 只读读取公开事件、SSE 或等价快照；不执行任务、不写回 Ledger、不批准动作、不触发发布；
- 只持久化在项目 `.project-local/runs/observer/` 下的 Observer-owned event log；
- 不读取 Prompt/Response 正文、凭据、Cookie、auth store、私钥或 provider state；
- Open Design 已迁移至 `DTALEX66/DESIGN-LAB`，本模块不再读取、投影或维护其事件。

## Source & Architecture

- `docs/observer-source-architecture.md`：Command Center 融合布局源码位置、数据流、运行方式、测试（2026-08-16）。

## Verification

Run from the repository root:

```text
python apps/observer/tests/test_observer_runtime.py
python apps/observer/tests/test_observer_evidence.py
python apps/observer/tests/test_observer_store.py
python apps/observer/tests/test_observer_dashboard.py
```

## User-visible read-only entry

The Observer consumes the Workflow-owned loopback sidecar: GET
`/api/v1/snapshot` (schema `workflow/snapshot/v3`) + `/api/v1/events` (SSE).
The frontend is served statically; it never writes, never falls back to a
fixture as live data, and the legacy `/api/dashboard` entry is retired
(R2 third batch). The Tauri shell only accepts the loopback v3 snapshot URL.

Start the sidecar (Workflow module):

```text
python services/orchestration/sidecar.py --project-root . --runtime-root <project>/.project-local/runs/workflow --host 127.0.0.1 --port 0 --frontend-root apps/observer/frontend/dist
```

`--port 0` binds a random free loopback port and the sidecar prints the real one in its
`WORKFLOW_SIDECAR_READY` line; `sidecar-endpoint.json` under the runtime root is what tells a
launcher which port to open, so neither the README nor `start-observer.cmd` may name a port.
`--frontend-root` is what makes the same command serve the built UI at `http://127.0.0.1:<port>/`;
without it the command answers an API and shows no page.

The sidecar endpoint descriptor (`sidecar-endpoint.json`) advertises the
projection/events URLs; the frontend reads `transport.eventsUrl` to subscribe.
It does not provide task controls, approval, retry, execution, or Ledger
write-back.

When the embedded desktop frontend cannot reach a live endpoint, it shows
`OFFLINE` explicitly — a bundled snapshot is never labelled live data.

### Views (Full/Compact × Dark/Light, v3 renderer)

All views render the same Projection and share one set of Design Tokens.
The v3 renderer (render-v3.js) is the single production surface; legacy
render.js is retained for v2-rendered projections only.

| View | Query | Content |
|---|---|---|
| Full Dark | `/?view=full&theme=dark` | data chain + metric cards (projects/tasks/usage/coverage, real-data only) + workspace hero + taskpack + governance + project matrix (sorted) + optional tasks/usage + history + evidence |
| Full Light | `/?view=full&theme=light` | same layout, light surface |
| Compact Dark | `/?view=compact&theme=dark` | 360–420px wide, essentials only (projects + status) |
| Compact Light | `/?view=compact&theme=light` | essentials only, light surface |

Metric cards render only when canonical samples exist — never from UNKNOWN/0.
In-page nav links toggle view/theme without reloading the Projection.

### Visual direction

The dashboard intentionally combines the project-approved visual vocabulary:
Apple's restrained black/light-gray rhythm and translucent navigation glass,
Linear's near-black precision surfaces, indigo interaction accent and technical
mono labels, plus Vercel's shadow-as-boundary restraint. It does not use a
decorative purple gradient or generic admin-template chrome.