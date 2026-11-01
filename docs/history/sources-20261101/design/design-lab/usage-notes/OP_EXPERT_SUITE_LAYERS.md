# DESIGN-LAB 个人专家套件 — 分层目录（可直接发给 OP）

> 用途：把本段内容整段发给 Open Design，让 OP 按层级读取全部配置资料。
> 所有路径均为本机绝对路径，OP agent（Codex）可直接读取。
> 根目录：`D:\All projects\DESIGN-LAB`

---

## 【L1】产品定位与宪章（必读，最高优先级）

| 文件 | 路径 |
|---|---|
| 唯一产品定义（SSOT） | `D:\All projects\DESIGN-LAB\project-memory\PRODUCT_DEFINITION.md` |
| 职责边界合同 | `D:\All projects\DESIGN-LAB\project-memory\BOUNDARY_CONTRACT.md` |
| 用户模式 | `D:\All projects\DESIGN-LAB\project-memory\USER_MODES.md` |
| 核心对象模型 | `D:\All projects\DESIGN-LAB\project-memory\OBJECT_MODEL.md` |
| 机器可读产品配置 | `D:\All projects\DESIGN-LAB\design-lab\config\product-manifest.json` |

## 【L2】设计系统（视觉语言基准）

| 设计系统 | DESIGN.md | Tokens | 组件 |
|---|---|---|---|
| UIUX Commercial Light（通用 UI/UX） | `D:\All projects\DESIGN-LAB\design-lab\design-systems\uiux-commercial-light\DESIGN.md` | `...\design-systems\uiux-commercial-light\design-tokens.json`（29 DTCG） | `...\design-systems\uiux-commercial-light\components.manifest.json`（19 组件） |
| Anomaly Monitor Dark（CCTV/HUD 监控） | `D:\All projects\DESIGN-LAB\design-lab\design-systems\anomaly-monitor-dark\DESIGN.md` | — | — |

## 【L3】领域方法（Domain Pack 与黄金案例）

### UI/UX Design Pack（五类案例，每个含 brief/design/tokens/实现/Axe 证据）
| 案例 | 目录 |
|---|---|
| 移动端任务流（预约/订单/客服） | `D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\benchmarks\mobile-task-flow-golden\` |
| B2B 后台工作台 | `...\domain-packs\uiux-design\benchmarks\b2b-backoffice-golden\` |
| 电商 PDP/结算 | `...\domain-packs\uiux-design\benchmarks\ecommerce-pdp-checkout-golden\` |
| 设置与无障碍中心 | `...\domain-packs\uiux-design\benchmarks\settings-accessibility-golden\` |
| 响应式内容页 | `...\domain-packs\uiux-design\benchmarks\responsive-content-page-golden\` |

每个案例内部：`design.md`（方法）+ `tokens.json` + `implementations/enhanced.html`（已通过 Axe 0-violation）+ `preflight.json`（验收标准）+ `handoff.md`（交付合同）。

### MiniGame Design Pack（参考）
- `D:\All projects\DESIGN-LAB\design-lab\domain-packs\minigame-design\`

## 【L4】可执行能力（Bundles + Atoms，仓库侧能力清单）

> 仓库中的 Bundle/Atom 定义不等于当前 Host 已注册。实际注册、最小任务执行、artifact/provenance 读回属于 Open Design live requalification，未完成前不得写“已注册”或“已集成”。

### 三个公开入口 Bundle（仓库侧公开入口；Host trust/注册待 live requalification）
| Bundle | Manifest | 语义 |
|---|---|---|
| commercial-design-core | `D:\All projects\DESIGN-LAB\design-lab\bundles\commercial-design-core\open-design.json` | 商业设计核心 |
| visual-quality-core | `...\bundles\visual-quality-core\open-design.json` | 视觉质量评审（taskKind=tune-collab） |
| production-handoff | `...\bundles\production-handoff\open-design.json` | 生产交付（taskKind=new-generation） |

### Atoms（专业能力原子；仓库定义，Host 注册待 live requalification）
目录：`D:\All projects\DESIGN-LAB\design-lab\atoms\`
（source-intake-gate / brief-normalizer / design-direction-jury / design-quality-jury / commercial-preflight / delivery-packager 等）

## 【L5】质量门禁与交付合同

| 资产 | 路径 |
|---|---|
| 视觉质量 Rubric（10 个域） | `D:\All projects\DESIGN-LAB\design-lab\evals\rubrics\` |
| 生产预检 Schema | `D:\All projects\DESIGN-LAB\design-lab\schemas\preflight.schema.json` |
| 可编辑交付合同 Schema | `D:\All projects\DESIGN-LAB\design-lab\schemas\design-handoff.schema.json` |
| UI/UX Brief Schema | `D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\schemas\brief.schema.json` |
| Axe 扫描证据（5 案例 0 violation） | `D:\All projects\DESIGN-LAB\design-lab\domain-packs\uiux-design\evidence\axe-scan-20260811.json` |
| 能力证据索引（E0-E5 诚实绑定） | `D:\All projects\DESIGN-LAB\design-lab\config\capability-evidence-index.json` |

---

## 给 OP 的载入指令（放在清单末尾一起发）

```text
以上是我（DTALEX66）的个人专家套件分层目录。请：
1. 按 L1→L5 顺序读取上述文件（路径均为本机绝对路径）
2. 记住 L1 的产品定位与边界合同（所有设计必须遵守）
3. 使用 L2 指定设计系统的 Token 与组件，不得自创风格
4. 涉及 L3 案例类型时，遵循对应案例的 design.md 方法与验收标准
5. 需要执行能力时调用 L4 Bundle/Atom（实际可用性须以 Host live requalification 证据为准）
6. 交付前按 L5 合同校验（Axe critical/serious=0、schema 校验、证据记录）
7. 不请求 API key（走 Codex OAuth 订阅）；不修改套件源文件
完成后请确认已载入层级数，并等待我的具体任务。
```
