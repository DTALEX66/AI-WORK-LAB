# W02 step 1-2 交付物 —— 组件体系裁决的**证据基础**

**观察 SHA：** `d116b14995fcdbba1b165ec5bc3124f5daed3d15`
**性质：** 只读分析。**本轮未修改任何 tracked 文件。**
**机读产出：** `.project-local/.../W02-COMPONENT-COVERAGE.json`
**脚本：** `w02-component-coverage.py`、`w02-extras-judgement.py`（均可重跑）

> ⚠️ 更正：上一轮我称 B07 registry 有 45 个组件。**实际是 46 个**
> （navigation 6 + inputs 8 + data 10 + feedback 6 + overlay 6 + workflow 5 + layout 5 = 46）。

---

## 1. 核心问题

包内 W02 要求「首选 Spectrum Web Components，备选 Web Awesome Core，选定上游稳定代际并锁版本」。
但**在选库之前**必须先回答一个更基本的问题：

> **B07 自己声明的 46 组件契约，现有 CSS/DOM 能表达多少？**

只有答案是「大量不能，且缺口恰好是通用原语」时，引入外部库才成立。
（这也符合 AUTHORITY §9 REUSE-FIRST，以及 §3 对新增依赖要求 ADR 的规定。）

---

## 2. 结果：B07 46 组件 vs 现有实现

| 判定 | 数量 | 含义 |
|---|---|---|
| **已覆盖**（有对应 CSS 类或 DOM 结构） | **25 / 46** | 直接可用 |
| **可部分由已有 B10 原语承担** | **10 / 46** | 需少量补充或收紧 |
| **真正缺失**（无任何原语） | **11 / 46** | 必须新建 |

### 2.1 按 family 覆盖

| family | 覆盖 | 备注 |
|---|---|---|
| data | 8/10 | 缺 Tree、Timeline |
| feedback | 5/6 | 缺 InlineAlert |
| navigation | 4/6 | 缺 Breadcrumb、Tabs |
| inputs | 4/8 | 缺 Select、MultiSelect、TagInput、DateRange |
| layout | 2/5 | 缺 Section、ResizablePanel、ResponsiveGrid |
| overlay | 2/6 | 缺 Popover、ContextMenu、Tooltip、ConfirmDialog |
| **workflow** | **0/5** | **ApprovalStep / VersionCompare / ConflictResolver / PermissionGate / AuditEvent 全部缺失** |

### 2.2 可复用的 10 项（其中 1 项有重要限制）

| B07 组件 | 可用原语 | 限制 |
|---|---|---|
| Tabs | `.seg` | ⚠️ **`SCOPED`：B10 规则是 `.toolbar .seg`**，脱离 `.toolbar` 不生效 → 需补一条非作用域规则 |
| Section | `.metric-row` / `.metric-box` | 网格容器 |
| Tree | `.node` / `.node-dot` | 是**图节点**，非树视图 |
| Timeline | `.review-card` | 是 3D 翻转卡，非时间线 |
| Popover | `.overlay` | 定位语义不同（需锚定） |
| ContextMenu | `.palette` | 是命令列表，非锚定右键菜单 |
| ConfirmDialog | `.modal` | **当前已在用于确认** |
| InlineAlert | `.soft-btn` | 语义不符（按钮变体） |
| ResizablePanel | `.split` | 静态两栏，**不可拖拽** |
| ResponsiveGrid | `.metric-row` | 固定 4 列，B07 要 1/2/12 响应式 |

### 2.3 真正缺失的 11 项

**通用原语（6）**：`Tooltip`、`Breadcrumb`、`Select`、`MultiSelect`、`TagInput`、`DateRange`
**领域组件（5）**：`ApprovalStep`、`VersionCompare`、`ConflictResolver`、`PermissionGate`、`AuditEvent`

---

## 3. 由此得出的裁决依据（**不是**选型结论，是选型的**输入**）

### 3.1 外部库最多只能覆盖 46 项中的 6 项 ≈ 13%

那 5 个 `workflow` 组件（ApprovalStep / VersionCompare / ConflictResolver /
PermissionGate / AuditEvent）是 **DESIGN-LAB 的领域组件，不是通用 UI 原语** ——
**没有任何第三方组件库会提供它们**，无论选 Spectrum 还是 Web Awesome。它们**必须自建**。

所以「引入组件库」这件事能解决的，只有 Tooltip / Breadcrumb / Select / MultiSelect /
TagInput / DateRange 这 **6 个通用原语**。

### 3.2 而引入外部库的代价（本项目特有，已核实）

| 代价 | 证据 |
|---|---|
| 新增运行时依赖 | `apps/workbench/package.json` 现有依赖仅 `typescript`/`vite`/`playwright` |
| **资源路由会 404** | `src/design_lab/workbench.py` 的 `ROUTES` **只有 3 条固定路径** |
| wheel 打包需同步 | `pyproject.toml` force-include `design_lab/resources/workbench/` |
| CSP 需实测 | `style-src 'self'`（无 `unsafe-inline`）、`script-src 'self'` |
| **可能破坏 classic-script 契约** | `build/main.js` 必须无 top-level import/export、`minify:false`、可 vm 加载 |
| AUTHORITY §9 全套登记 | source/revision/license/mapping/destination/implementation/tests/evidence/rollback |

**为 6 个原语承担 6 类架构代价（其中 2 类已在上一轮 CI 造成过真实失败）——代价与收益明显不成比例。**

### 3.3 但这不等于「不引入任何东西」

诚实表述：**当前证据不支持"为了 6 个通用原语而整体引入组件体系"**；
它支持的是：

1. **先把 10 项可复用的补齐/收紧**（尤其把 `.toolbar .seg` 放开为非作用域规则）
2. **自建 5 个 workflow 领域组件**（无论如何都要建）
3. **6 个通用原语**：可自建（成本可控，且能保持零新增运行时依赖），
   或**仅对这 6 项**做一次有界的库评估
4. 任何引入都必须先解决 `ROUTES` 只有 3 条这一硬阻塞

---

## 4. 与包内 W02 要求的关系

| 包内要求 | 本轮证据的回应 |
|---|---|
| 首选 Spectrum Web Components | **证据不支持整体引入**：它只能覆盖 46 项中的 6 项（13%），却带来 6 类架构代价 |
| 备选 Web Awesome Core | 同上 |
| 「在一个现有页面上接 10 类基础控件」做兼容试验 | 若仍要做，应**限定于那 6 个缺失原语**，而不是 10 类（其余 40 项已有实现） |
| 「未过门则回退现有组件并切备选」 | 现有组件已覆盖 25/46 + 10 项可复用，**"回退现有"本身就是一个合理终局**，不必视为失败 |
| 兼容裁决后只保留一个主体系 | 可满足：**现有 B10 类体系**即可作为主体系 |

---

## 5. W02 状态

**W02 step 1-2 完成（只读证据基础已建立）。W02 的整体裁决 `PENDING_OWNER`。**

**因以下 2 项未决，不能宣告 W02 完成：**
1. `D-3`（选型路径）——本轮给出了证据基础，但**选型是你的决定**，我不代定
2. **硬阻塞仍在**：`ROUTES` 只有 3 条 —— 任何新增资源的方案都必须先解决它

**建议的 W02 下一步（按包内"受阻时推进不依赖该阻塞的工作"原则）**：
跳过依赖新资源的路径，先做 **W03 首个用户可见交付**（真实 Project/Brief 页面 + 补
`project-detail` 路由），因为 W03 只改现有 5 个文件（`shell.ts`/`main.ts`/`workbench.ts`/
`index.html`/`design.ts`），**不触发 `ROUTES` 阻塞**。

---

**END — W02 step 1-2 交付物。本轮只读分析，未修改仓库。**
