# V4.2 问题总结（Problem Summary）— 2026-08-11

> **HISTORICAL SNAPSHOT — NOT CURRENT EVIDENCE.** This dated report is
> retained for audit traceability. Its E-level/runtime wording describes
> the recorded tree only and does not qualify the current checkout.


> 依据 `DESIGN-LAB-Final-TaskPack-v4.2-2026-08-10`（Phase 2/3/4 执行）
> 基线：`f160240`（云端 main）

## 一、本阶段发现并已修复的问题

### Phase 2 数据模型
| # | 问题 | 修复 |
|---|---|---|
| 1 | `capability-status.json` 的 `capabilityStates` 仅字符串枚举，缺实际能力状态记录（P0#10） | 新增 `capabilityRecords`（8 能力族 state/evidenceLevel/lastVerified），schema 同步 |
| 2 | product-manifest 版本停留在 `4.0.0-staging`，产品定义文件不唯一 | 升 `4.2.0`，新建 `PRODUCT_DEFINITION_V42.md` 为唯一 SSOT，README/START_HERE/manifest entrypoints 全部指向 |

### Phase 3 manifest 合同（E3 现场发现）
| # | 问题 | 修复 |
|---|---|---|
| 3 | 2 个插件缺 `tags`（上游 marketplace 414/414 必填） | brand-visual-director、spatial-exhibition-director 补齐 |
| 4 | visual-quality-core 的 `od.taskKind: critique-repair`、production-handoff 的 `production-handoff` 不在上游枚举（仅 new-generation/code-migration/figma-migration/tune-collab） | 改为 `tune-collab` / `new-generation` |
| 5 | bundle `od.context.atoms` 引用本地自定义 atom，daemon doctor 报 `atom.unknown` error（内置表仅 22 个 FIRST_PARTY_ATOMS） | 改为引用 daemon builtin atoms；本地专业 atom 移入 `context.assets`（SKILL.md 路径），verifier 与测试同步更新 |

### Phase 4 无障碍（真实浏览器 Axe）
| # | 问题 | 修复 |
|---|---|---|
| 6 | 电商 `.promo` 对比度 4.27 < 4.5 | 色值 `#C9362B`→`#A8271F` + 背景加深 |
| 7 | 移动 `.badge.shipping` 对比度不足（rgba 叠加深色背景后 3.45） | 改为纯色 `#1D3F6E`/`#A8C9FF` |
| 8 | B2B `.trend` + 3 个 status badge 对比度不足 | KPI 绿 `#059669`→`#047857`；badge 改用深色文字 `#1D4ED8`/`#047857`/`#475569` |

### 环境（非仓库问题）
| # | 问题 | 处置 |
|---|---|---|
| 9 | Open Design daemon 需 Electron ABI node（better-sqlite3 NODE_MODULE_VERSION 145），系统 node 127 直接运行 `ERR_DLOPEN_FAILED` | 用 `ELECTRON_RUN_AS_NODE=1 "Open Design.exe" daemon-cli.mjs` |
| 10 | daemon 经 Hermes 后台管道启动后管道断开触发 EPIPE 弹窗 | 临时验证 daemon 已终止；后续用文件重定向 stdout（`.hermes/task-runtime/od-daemon.log`） |

## 二、遗留问题（未处理，属后续 Phase 或需人工）

1. **V42-0409 人工专业 Jury**：五案例总分 ≥82、增强偏好率 ≥70% → 需真人评审（E3 人工门）
2. **V42-0410 冻结**：五案例 E3 完整闭环 + 失败恢复证据 + Axe 冻结基线
3. **Phase 5+ 全部阻塞于 0410**：视觉质量引擎、大师方法、生产交付等
4. **Phase 7**：497 大师记录分层核验、77 方法卡、来源 V3 迁移（V42-0701..0707）
5. **Phase 10**：`capability-evidence-index.json` + 12 evidence card 升级
6. **Phase 11**：REUSE/SBOM/第三方 BOM/二进制 sidecar 许可 Gate
7. bundle 的 `context.skills` 引用（commercial-design-router 等）仍未注册为 skill 插件 → doctor warning（非 error），待 Phase 3 后续或注册 skill 时收敛

## 三、证据分级诚实性声明

- E3 声明均有真实运行证据（daemon 注册/回读、浏览器 axe 扫描），无文件冒充
- 未达 E3 的部分（0409/0410、Phase 5+）明确标注 pending，未虚标
