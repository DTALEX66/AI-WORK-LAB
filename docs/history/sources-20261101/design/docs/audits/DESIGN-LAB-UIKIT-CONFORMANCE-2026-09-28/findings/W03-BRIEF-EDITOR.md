# W03 —— 真实 Brief 全流程落地（create / open / edit / save / version）

**状态：** W03 的「真实 Brief 全流程」**已完成并验证**（W03 其余项见 §5）
**证据：** `evidence/W03-BRIEF-EDITOR.json`（21 项检查）
**harness：** `harness/w03-brief-editor-verify.py`（Python 起真实服务）+ `harness/w03-brief-editor.mjs`
**性质：** 本轮**首次修改产品代码**（`apps/workbench/shell.ts` + 重新构建的 `build/main.js`）。

---

## 1. 交付内容

在路由壳的 `/projects/:id` 页面（**不是**导航项——`.app-nav-item` 必须保持 12，
B10 侧栏保持 11，均由 E2E 断言）新增**真实可写**的简报区：

- **create**：`POST /projects/{id}/briefs`
- **open / edit**：点某一版本的「新版本」→ 载入该版本内容 + 读回版本链
- **save as new version**：`POST /projects/{id}/briefs/{brief_id}/revisions`
- **version 读回**：`GET /projects/{id}/briefs/{brief_id}/lineage`，并标注 live/已被取代

**复用而非重写**：端点、`splitList` 校验、`revisionHint` 错误词表、`uuid` 幂等键来源
全部来自既有 `design.ts` —— 这就是包内所说「统一旧单页与新路由的用户流程」。
旧单页入口**未改动**，并由仓库自己的浏览器 E2E 实测仍然通过（见 §4）。

**标记语言遵循 B10 而非旧表单**：B10 用 `.input` + placeholder，**全文没有 `<label>`**。
这里若用裸 `<label>`，会把本轮刚清掉的 pre-B10 元素规则耦合**重新引回 `.app`**
（见 `W02-LEGACY-COUPLING.md`）。所以字段用 `.input`，标题用 `.list-item > strong`。

## 2. 验收对照（包内 W03 验收原文）

| 包内验收 | 本轮验证方式 | 结果 |
|---|---|---|
| 从项目卡进入真实 Brief 并**保存读回** | 创建 → 从服务端重新读回 → 列表出现 `v1` | ✅ |
| **刷新保留项目上下文** | reload 后 hash 仍指向该项目 | ✅ |
| **失败不弹「保存成功」** | 对已被取代的版本提交修订 → 服务端 409 `STALE_REVISION` → 断言**整页不存在任何成功文案** | ✅ |
| 旧工作入口在迁移完成前可用 | 仓库自带浏览器 E2E（驱动旧单页）实测通过 | ✅ |
| **无假 KPI** | 空项目渲染「尚无简报」，无编造数字 | ✅ |
| 保存状态 / 焦点 / 错误定位 | 空提交 → 焦点落在出错字段 + `aria-invalid=true`；「新版本」→ 焦点进入被修订字段 | ✅ |

`21/21` 检查通过（真实 loopback 服务 + 生产 CSP + 已提交 build）。
**连续两次运行均 21/21**（第一次暴露了下面的顺序不稳定，见 §3.3）。

## 3. 本轮发现的问题

### 3.1 产品代码里一个真实 bug（由验证暴露，已修）

第一次运行时：**状态栏显示「已保存并读回」，但列表里没有那条简报**。

根因：经路由进入时，`show()` 先把视图渲染进一个**离屏 staging div**，再把子节点搬进
`#route-view`。所以 `renderProjectDetail` 拿到的 `target` 在写入完成时**已经是空的、脱离文档的**。
我用它做自我刷新 → 实际更新的是那个离屏节点：**页面看起来保存成功，列表却是旧的**。
状态栏之所以还更新，是因为那个元素已被搬进 live 树。

修法：刷新与状态写入都按 id 解析**当前 live 节点**（`#route-view` / `#pd-brief-status`）。
这个 bug 只有真跑浏览器才会暴露——静态检查与类型检查都不会发现。

### 3.2 harness 的两个错误

| 错误 | 假结果 | 修法 |
|---|---|---|
| `#pd-brief-lineage` 计数未等待异步 `loadLineage` | 报 0 项，误判「版本链未读回」 | 等 `.list-item` ≥ 2 再断言 |
| 无条件断言「控制台零错误」 | 把**故意**触发的 409 当成缺陷 | 给控制台错误打**阶段标签**，只允许 stale 阶段的那条 409 |

### 3.3 一个观察（未擅自变更）

同一秒内创建的多个版本，服务端返回**顺序不保证**——harness 用 `.first()` 选「已被取代的行」
时，某次实际选中了 live 版本，于是**又成功创建了 v3**，把「失败诚实性」测试变成了成功。
harness 改为**按状态标签选行**（`.tag.ok` live / `.tag.warn` superseded）。

产品侧的顺序不稳定本轮**未改**：它属于体验问题，不属于 W03 验收，改排序是未获授权的行为变更。
建议后续按 `version` 显式排序（一行改动），但不在本轮。

## 4. 验证证据

| 项 | 结果 |
|---|---|
| W03 专项 harness（真实服务 + 生产 CSP + 已提交 build） | **21/21 PASS**，两次连续运行一致 |
| 仓库自带浏览器 E2E（旧单页 brief 流） | `BROWSER_E2E ran=2 skipped=0 failed=0`（`E2E_OK` 已断言） |
| `tsc --noEmit`（strict） | exit 0 |
| workbench smoke + appshell 回归 | 全通过 |
| `vite build` 可复现（CI clean-tree gate） | 重建前后 `main.js` SHA256 一致 |

## 5. W03 仍未完成 / 明确未覆盖

- **参考素材选择器**：路由壳内**没有**参考选择器（那是 W04）。因此修订时
  `reference_asset_ids` 是**原样携带**源版本的 id，而不是可编辑——静默丢弃会丢数据，
  已在代码注释里写明。
- **「最近项目」持久化**：本轮验证的是**路由/hash 上下文跨刷新保留**。
  包内提到的「最近项目」列表式持久化（记住上次项目）**未做**。
- **「待审 / 失败列表」**：未在本轮验证。
- **个人版隐藏协作入口**：未处理。
- 本页只做 Brief；Direction / DesignSystem 的写入仍在旧单页（W05/W06）。
- 证据等级：**E2 CONTROLLED_RUNTIME**（合成临时项目、本机 loopback、无头固定 Chromium）。

---

**END — W03 真实 Brief 全流程记录。**
