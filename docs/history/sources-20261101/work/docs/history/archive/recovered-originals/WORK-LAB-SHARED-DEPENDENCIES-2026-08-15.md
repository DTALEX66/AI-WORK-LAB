# WORK-LAB 共享外置依赖登记

> 日期：2026-08-15
> 来源项目：WORK-LAB（`DTALEX66/WORK-LAB`，`D:\All projects\WORK-LAB`）
> 本目录：OS External Configuration（跨项目共用的 Windows 开发工具链库）
> 状态：**只读登记完成，未迁移任何文件、未改任何缓存指向**

## 一句话定位

WORK-LAB 是客户端中立的工作流控制面，实际消费本目录已有的通用工具链
（Node / Git / uv）。DSH（DeepSeek Harness agent runtime）需要 Node
`^22.19.0 || >=24.0.0` 与 `pnpm@11.7.0`。以下登记 WORK-LAB 实际依赖的
共享工具，以及哪些**绝不外置**（边界铁律：构建产物/下载缓存/运行数据留项目内）。

## 1. 共用的通用工具链（WORK-LAB → 本目录已有项）

| WORK-LAB 依赖 | 用途 | 本目录已有项 | 版本一致性 | 状态 |
|---|---|---|---|---|
| Node.js LTS | DSH agent runtime（engines `^22.19.0 || >=24.0.0`）+ pnpm 运行 | `10-toolchains/scoop/apps/nodejs-lts` | 共用库 **24.18.0**（满足 DSH 要求；旧本机 node v22.23.1，以共用库新稳定版为准） | ✅ 共用，重复以共用库新稳定版为准 |
| Git | 版本控制 / CI / github-delivery | `10-toolchains/scoop/apps/git` | 共用库 2.54.0 == WORK-LAB 当前 2.54.0 | ✅ 共用，无需迁移 |
| uv | 依赖锁定 / venv / 测试环境（`uv run --frozen`） | `uv-cache/` 跨项目共用缓存 | uv 0.12.0 | ✅ 共用缓存；uv 本体当前来自 Hermes bin，登记不迁移 |
| Python 3.11 | 质量门禁 / 测试运行器（`run_quality_gate.py`） | `10-toolchains/python`（3.12/3.13） | WORK-LAB 当前用 Hermes venv 3.11.15 | ⚠️ 通用解释器可共用；Hermes venv 为专属运行时，暂不切换 |

## 2. 项目内工具（由项目自身管理，不迁入共用库）

| 项 | 说明 |
|---|---|
| corepack / pnpm@11.7.0 | `run-pnpm.js` 逐次 pin，缓存位于 `.hermes/task-runtime/cache/node/corepack` + `cache/pnpm`（下载缓存，边界铁律留项目内） |
| actionlint / shellcheck | CI 本地下载的二进制（`.hermes/task-runtime/actionlint-bin`、`shellcheck-bin`），属下载缓存 |
| DSH `node_modules`（~1.5 GB） | DSH 项目自身的 pnpm workspace 依赖树，不是共享工具链 |
| venv / logs / artifacts / session / cargo-target | 项目运行数据与构建产物，一律留 `.hermes/task-runtime/` |

## 3. WORK-LAB 侧缓存指向现状（本次不动）

`run_quality_gate.py` 的 `project_runtime_environment()` 把 `UV_CACHE_DIR`、
`NPM_CONFIG_CACHE`、`CARGO_TARGET_DIR` 等指向**项目内** `.hermes/task-runtime/cache/`。
这是 WORK-LAB 自洽的运行时环境；本次仅登记，不改为共用库指向。
未来如需跨项目共用 uv-cache，可另立任务将 `UV_CACHE_DIR` 指向
`D:\All projects\OS External Configuration\uv-cache`，并回归验证质量门禁。

## 4. 版本冲突策略

- 两边已有项当前完全一致或兼容（Node 共用库 24.18.0 满足 DSH；Git 同为 2.54.0）。
- 未来若产生重复/漂移，以**最新且最稳定**版本为准，由本目录
  `EXTERNAL_DEPENDENCIES.md` / `00-registry/project-tool-index.yaml` 登记新版本，
  各项目 activation 脚本统一引用。

## 5. 边界声明

- WORK-LAB 的 Hermes/Codex 全局配置（skills / managed-config / SOUL.md）**不属于
  本目录范畴**，由 WORK-LAB 仓库自身管理（与本目录既有范畴声明一致）。
- 本轮未移动、未删除、未复制任何文件；未改动本目录已有的
  `00-registry/ 10-toolchains/ 20-runtimes/ 40-models/ 60-cache/ 80-build/`
  内容与 WORK-LAB 项目内任何缓存指向。
- 本文档为新增登记文件，**未提交**（本目录有 ArcheAxis 侧未提交 WIP；提交需另行授权）。
