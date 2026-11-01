# OBS Bridge / Frontend lightweight indexes → Backend V10 integration

Use this note when the user asks for a **read-only check of OBS frontend / Bridge / Open Design files** and wants a backend V10 index integration checklist.

## Known surfaces

- Formal vault: `E:/BaiduSyncdisk/Obsidian知识库`
- Open Design / frontend design folder: `E:/BaiduSyncdisk/Obsidian知识库/TALOS-frontend-design`
- Deployed plugin folder: `E:/BaiduSyncdisk/Obsidian知识库/.obsidian/plugins/talos-frontend-ui`
- Backend helper repo: `D:/All projects/Obsidian-Assistance/Obsidian - Backend Assistance`

## Inspect read-only first

Open Design / frontend handoff:

- `TALOS-frontend-design/OPEN_DESIGN_OBS_使用层任务书.md`
- `TALOS-frontend-design/HERMES_后端交接说明.md`
- `TALOS-frontend-design/OBS_Bridge_基础调度层记录.md`
- `TALOS-frontend-design/OBS_Bridge_Localhost_Transport_记录.md`
- `TALOS-frontend-design/OBS_Bridge_真实联调清单.md`

Frontend app / Bridge scripts:

- `TALOS-frontend-design/obs-frontend-app/package.json`
- `TALOS-frontend-design/obs-frontend-app/main.js`
- `TALOS-frontend-design/obs-frontend-app/renderer/app.js`
- `TALOS-frontend-design/obs-frontend-app/scripts/validate-light-index.ps1`
- `TALOS-frontend-design/obs-frontend-app/scripts/bridge-smoke-test.ps1`

Plugin lightweight indexes:

- `.obsidian/plugins/talos-frontend-ui/obs-bridge-protocol.json`
- `.obsidian/plugins/talos-frontend-ui/obs-frontend-map.json`
- `.obsidian/plugins/talos-frontend-ui/obs-course-index.json`
- `.obsidian/plugins/talos-frontend-ui/main.js`
- `.obsidian/plugins/talos-frontend-ui/manifest.json`

Backend V10:

- `scripts/v10/course_transform_ledger.py`
- `scripts/v10/cognitive_vault_garden.py`
- `scripts/v10/course_intake_adapter.py`
- `scripts/v10/obs_task_ledger.py`
- `docs/cognitive-loop-os-backend-absorption-2026-07-07.md`

## Expected current Bridge contract

- schema: `obs-bridge-protocol/v1`
- actions: `bridge.ping`, `bridge.status`, `obs.activateRoute`, `obs.openCourseEntry`, `obs.executeCommand`
- routes: `command`, `learning`, `evidence`, `review`, `project`, `log`, `settings`
- commands: `command-palette:open`, `switcher:open`
- localhost transport default off
- endpoint: `127.0.0.1:27189`
- paths: `POST /request`, `GET /status`
- required header: `X-OBS-Bridge: obs-frontend-app`

## Backend V10 index checklist

| Index | Source | Frontend domains | Boundary / acceptance |
|---|---|---|---|
| `obs-v10-course-transform-index.json` | `course_transform_ledger.py --format json` | learning, project, log | Read-only course gaps, reports, keyframe counts, `next_action`; no course-body writes. |
| `obs-v10-vault-garden-index.json` | `cognitive_vault_garden.py` | evidence, review, project | Candidate-only backlinks/tags/thin topics; no auto tag/link edits and no verified-evidence promotion. |
| `obs-v10-source-manifest-index.json` | `course_intake_adapter.py inventory` | learning/source intake | Manifest only: format, relative path/name/size/candidate flag; no OCR/ASR/full note body. |
| `obs-v10-task-ledger-index.json` | `course_transform_ledger.py --tasks` or `obs_task_ledger.py list/report` | log/sleep-loop | Real-task statuses only; no fake `done` from heartbeat/preview/dry-run. |

## Safe command examples

Run from backend helper repo:

```bash
python scripts/v10/course_transform_ledger.py --vault "E:/BaiduSyncdisk/Obsidian知识库" --format json --limit 200
python scripts/v10/course_transform_ledger.py --vault "E:/BaiduSyncdisk/Obsidian知识库" --tasks --limit 200
python scripts/v10/cognitive_vault_garden.py --vault "E:/BaiduSyncdisk/Obsidian知识库" --include "02_课程库" --include "03_知识卡片" --include "04_复习卡片" --include "80_索引数据库" --limit 200
python scripts/v10/course_intake_adapter.py engines
python scripts/v10/course_intake_adapter.py inventory "E:/学习数据" --limit 200
```

Bridge validation lives under `TALOS-frontend-design/obs-frontend-app`:

```bash
npm run index:check
npm run bridge:expect-off
# After the user manually enables the Obsidian command “OBS Bridge：启动/停止本机传输层”:
npm run bridge:smoke
npm run bridge:routes
npm run bridge:commands
npm run bridge:course
# Then the user disables Bridge and reruns:
npm run bridge:expect-off
```

## Output shape for user

1. Start by saying the check was read-only.
2. List inspected surfaces and current verified contract facts.
3. Provide the backend V10 index table: name, source script, frontend domain, boundary, acceptance check.
4. Explicitly state non-goals: no frontend Vault scan, no note bodies in lightweight indexes, no storage-layer movement, no verified evidence fabrication, no default-on transport.
5. Summarize real commands actually run; do not imply Bridge live tests ran unless the transport was manually enabled and the command returned PASS.

## Pitfalls

- `obs_task_ledger.py summary/list/report` initializes the SQLite schema if the DB does not exist; do not call it in a strictly read-only pass unless local-state writes are acceptable or already authorized.
- Do not put `body`, `content`, `markdown`, `raw`, `text`, `frontmatter`, `cache`, OCR/ASR text, or full private source details into frontend lightweight indexes.
- Do not recommend default-enabling localhost transport.
- Keep user-facing language as `OBS`; `TALOS` is the Purple Gemstone visual-system label and compatibility plugin id.
