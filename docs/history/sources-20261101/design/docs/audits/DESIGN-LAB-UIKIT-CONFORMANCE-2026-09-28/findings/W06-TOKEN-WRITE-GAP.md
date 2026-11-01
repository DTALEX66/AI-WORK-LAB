# W06 缺口分析 —— Token 写 API（包内要求「先复用 catalog/bind；核查 Token 写 API 缺口」）

**性质：** 只读核查 + 最小设计提案。**本轮未实现 Token 写 API，也未做假的编辑器。**
**已交付的 W06 前半：** catalog + bind（见 `renderDesignSystemPanel`，harness 13/13）
**证据：** `evidence/W06-DESIGNSYSTEM.json`

---

## 1. 已有可复用件（包内要求「复用已有 DTCG 转换器与测试，不另造格式」——成立）

| 件 | 位置 | 能力 |
|---|---|---|
| DTCG 校验/互操作 | `src/design_lab/interop/dtcg.py` | **仓库自带** JSON Schema（`load_schema()` 会断言 schema 的 `$id` 属本仓库）、`_schema_errors()` 走 draft 2020-12 结构校验，另有语义校验：数值、非空文本、别名解析 |
| DTCG 结构 schema | `design-lab/schemas/interop-dtcg-document.schema.json` | 文档格式定义 |
| DTCG CLI | `design-lab/scripts/convert_tokens_dtcg.py` | 转换并打印 `DTCG_OK tokens=N` |
| DTCG 测试 | `design-lab/tests/test_interop_dtcg.py` | 含 **write-and-reload-unchanged**、类型继承、根 token 扁平化、别名链、**无法解析的别名 fail-closed**、**别名环 fail-closed 并给出环路径** |
| 目录读回 | `GET /api/design-systems` | `design_layer.design_systems()` → `catalog()`（来自 `design-lab/design-systems/*`，实测 4 个包装系统） |
| 绑定 | `POST /api/projects/{id}/directions/{dir}/bind` | 绑定到**已选定方向** |

**结论：格式与校验层无需新建。**「不另造格式」这条已有充分基础。

## 2. 缺口（实测，非推测）

枚举服务全部写路由后确认：现有的写路径只有 briefs / directions / choose / bind /
native-plans / tasks patch·run·cancel / assets 导入。因此：

| # | 缺口 | 证据 |
|---|---|---|
| **G1** | **完全没有 Token 写路由** | `http_service.py` 无 `/tokens` 任何匹配；`src/design_lab/**` 无 token 存储读写 |
| **G2** | **项目级没有 Token 文档** | 目录是**只读的包装设计系统**；项目侧不存在可编辑的 token 状态 |
| **G3** | **没有版本存储 / diff 基线** | 简报与方向已有 `revisions` + `lineage` + `superseded_by`；token 侧一个都没有 |
| **G4** | **没有字段级错误契约** | `dtcg` 会产出错误列表，但没有路由把它按字段返回给表单 |
| **G5** | **没有发布 / 回滚语义** | 无「发布到项目」与「回滚到某版本」的任何端点 |
| **G6** | 权限模型仅「Bearer + 项目作用域」 | 单用户单令牌；资产已拒绝跨项目读取，token 侧需沿用同一约束 |

## 3. 最小设计提案（下一轮实现，本轮不写）

1. **格式**：直接采用 DTCG 文档（复用 §1 的 schema 与校验器），**不新增格式**。
2. **存储**：**照抄简报/方向的既有模式**——追加式版本 + `superseded_by` + lineage，落在项目既有的
   design-layer 表里。不新造文件型存储，避免第二套真值来源。
3. **校验**：持久化**之前**跑 `dtcg` 校验；把错误**按字段路径**回传（`path` + `message`），
   直接驱动表单的字段级错误（对应验收「非法 Token 有字段级错误」）。
4. **冲突**：沿用简报修订已有的 **409 语义**（`STALE_REVISION` 一族），使 UI 现有的
   `revisionHint` 错误词表可直接扩展，不引入第二套冲突语言（对应「冲突返回可恢复状态」）。
5. **发布 / 回滚**：都实现为**追加**（发布 = 让某版本成为项目活动 token 文档；回滚 = 再发布一个更早的版本），
   历史只追加不改写。
6. **品牌边界（验收「工作台品牌不随项目 Token 改变」）**：**当前已由构造满足**——实测
   `apps/workbench/*.ts` 中**没有任何**代码把项目 token 写入 `documentElement`/`:root`；
   唯一的 `--color-*` 出现处是**固定**的 B10 名称（一个静态 SVG 渐变）。
   → 设计约束：编辑器的「即时预览」必须**作用域限定在容器内**，**永不**写 `:root`/`documentElement`；
   并应加一条检查守住它。

## 4. W06 验收对照（现状）

| 包内验收 | 现状 | 还缺什么 |
|---|---|---|
| 颜色/字号等改动**真实保存** | ⏳ | G1/G2 |
| **重启一致** | ⏳ | G2/G3（需持久化 + 重启后读回测试） |
| **冲突返回可恢复状态** | ⏳ | G3/G5（沿用 409 语义） |
| **工作台品牌不随项目 Token 改变** | ✅ 已由构造满足（§3.6） | 需**守住**：加一条「不得写 :root」的检查 |
| **非法 Token 有字段级错误** | ⏳ | G4（校验器已在，缺路由与字段映射） |

## 5. 本轮**未**做的事（明确声明）

- **未**新增任何 token 写端点、schema 或版本存储——它是后端变更（schema/版本/权限），值得单独一轮，
  且需要你先确认 §3 的存储与冲突契约。
- **未**提供任何形式的假编辑器：面板明写「Token 编辑/预览/版本 diff/发布/回滚在服务端尚不存在」，
  并由 harness 断言**不存在** token 编辑控件。
- 未改 `dtcg` 的 schema 或测试。

---

**END — W06 缺口分析。**
