# WORK-LAB Observer 前端源码与架构（2026-08-16 融合版）

> 状态：IMPLEMENTED · Command Center 融合布局（SigNoz/Homepage/Langfuse/OneUptime/Beszel/Grafana）
> 数据原则：只渲染 canonical 事实，不伪造 UNKNOWN/0；UI 冻结已解除

> **2026-10-07 修订（规范）**：§1.1 描述的 `apps/observer/web/` 静态面**已退役删除**，
> 本节保留为历史设计记录，不再描述生产事实。当前前端源码是
> `apps/observer/frontend/`（React + Vite：`src/lib/api.ts` 投影与格式化、
> `src/views/*` 车道、`src/components/*` 面板与 HUD、`src/skins/*` B10 皮肤），
> 由 Tauri 打包 `frontend/dist`，也可由 sidecar `--frontend-root` 只读服务同一份 dist。
> 逐文件哈希与恢复点在 `docs/audits/OBSERVER_WEB_RETIREMENT_MANIFEST_2026-10-07.json`，
> 每条旧断言的归属在 `apps/observer/parity-matrix-u03.md`。

## 1. 源码位置

### 1.1 前端（apps/observer/web/，2026-10-07 已退役，仅作历史记录）

| 文件 | 职责 |
|---|---|
| `scripts/fusion-v3.js` | **Command Center 渲染核心**（本次重写）：信号条 + 项目总览 + 跨项目矩阵 + Token 仪表盘 + 项目健康 + 治理 |
| `styles/command-center.css` | **Command Center 样式**（本次新增，紧凑布局：窄侧边栏 52px + 矩阵行 + 卡片） |
| `scripts/app.js` | 入口：full 视图走 fusion 单壳渲染（不套 topbar，无重复矩阵） |
| `scripts/render-v3.js` | v3 渲染器（旧，含 platformStatusMatrix/tokenDashboard 等，供 fusion 参考） |
| `scripts/render.js` | 旧渲染器（v2-rendered 兼容） |
| `scripts/api.js` | 数据获取：GET /api/v1/snapshot v3 + SSE；支持 `?api=<url>` 指定端点 |
| `scripts/state.js` | 状态：view/theme/mode/lastGood |
| `scripts/charts.js` | canvas 图表（零依赖） |
| `scripts/formatters.js` | 格式化 |
| `scripts/accessibility.js` | 无障碍 |
| `index.html` | 页面壳：引入全部脚本 + 样式（含 command-center.css） |

### 1.2 数据侧（packages/client-neutral-core/scripts/）

| 文件 | 职责 |
|---|---|
| `config/project-platform-map.json` | **项目→平台映射**（work-lab/design-lab→DSH，archeaxis/obsidian→HERMES） |
| `platform_collector.py` | 平台 collector：读映射 → 写 canonical `platform_observations` 表 |
| `canonical_store.py` | store：`record_platform_observations` / `query_platform_observations` |
| `snapshot_api.py` | snapshot 输出 `agentPlatform` + per-project git（`git_map`） |
| `composition_root.py` | 组装 v3 snapshot：读 platform_observations → platform_map 传入 |
| `collectors.py` | `build_standard_collectors`：注册 git_collector（多项目）+ platform_collector |
| `sidecar.py` | loopback sidecar：启动 worker + SSE + snapshot API |

## 2. 数据流

```
project-platform-map.json（配置）
        ↓ platform_collector
canonical.sqlite → platform_observations 表
        ↓ composition_root 查询
build_v3_snapshot → projects[].agentPlatform + per-project git
        ↓ sidecar GET /api/v1/snapshot (v3)
前端 api.js ?api=<url> 拉取
        ↓
fusion-v3.js render() → Command Center
```

## 3. 布局结构（Command Center）

```
┌ 窄侧边栏 52px（SigNoz 式，图标）┐
├ 信号条：Sidecar · 事件# · 采集覆盖 · 最近采集（Grafana 式）
├ 项目总览：紧凑卡（Homepage 式）：项目名·平台·分支·SHA·状态
├ 跨项目运行状态：矩阵行（Coroot/OneUptime 式）：状态点·平台·分支·SHA·工作树·徽章
├ Token / 成本：卡片（Langfuse 式）：总·输入·输出·缓存命中·命中率
├ 项目健康：表（OneUptime 式）：状态点·项目·平台·分支·SHA·徽章
└ 配置 / 治理：chips（Beszel 式）：规则·技能·适配器状态
```

## 4. 融合来源（10 个开源项目）

| 项目 | 融合点 |
|---|---|
| SigNoz | 左侧导航 + 信号条 + Overview |
| Homepage | 项目总览卡片（总驾驶舱） |
| Langfuse | Token/成本仪表盘 |
| OneUptime | 项目健康表 + 状态徽章 |
| Coroot | 状态点着色（绿/黄/灰） |
| Beszel | 干净紧凑卡片 + 窄侧边栏 |
| Grafana | 状态着色 + 面板分组思想 |
| HyperDX | 开发者驾驶舱交互思路（参考） |
| Perses | 可移植 dashboard schema（参考） |
| OpenObserve | 统一多数据源 Control Plane（参考） |

## 5. 运行

```bash
# sidecar（数据源，并可用 --frontend-root 只读服务同一份 Vite dist）
python services/orchestration/sidecar.py --project-root . \
  --runtime-root .project-local/runs/workflow \
  --frontend-root apps/observer/frontend/dist

# 浏览器入口（api 参数指向 sidecar projectionUrl）
http://127.0.0.1:61867/?view=full&theme=dark&api=<sidecar投影URL>

# 桌面入口（生产形态）
cd apps/observer/src-tauri && cargo tauri dev   # 或 CI 产出 release 二进制
```

（2026-10-07 前这里写的是 `python -m http.server 8089 --directory apps/observer/web`；
该静态面已退役，浏览器只读入口改为 sidecar 的 `--frontend-root`，
由 `tests/workflow-assistance/test_sidecar_ui_browser_entry.py` 8 例钉住。）

## 6. 测试

```bash
# 前端渲染契约（18 tests）
node apps/observer/tests/test_render_v3.js

# 全量 JS（75 tests）
node apps/observer/tests/run_all_tests.js

# Observer Python（34 tests）
cd apps/observer && PYTHONPATH=scripts python -m unittest discover -s tests -p test_observer_*.py
```

## 7. 注意事项

- **Tauri app.exe 内嵌旧 web**：改前端后需重新构建（需 Rust）或用浏览器方案（8089 静态服务器即时生效）；
- **数据真实性**：token/项目无 canonical 样本时区块隐藏或显示占位，绝不伪造 0/UNKNOWN；
- **平台映射**：改 `project-platform-map.json` + 重跑 platform_collector 即生效；
- **只读边界**：Observer 永不写业务表、不读凭据/正文、不发起调用（模块 AGENTS.md 不变）。
