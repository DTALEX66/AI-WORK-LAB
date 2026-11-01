# V4 Inheritance Matrix（继承与废止矩阵）

- 版本：`V4-INHERITANCE-2026-08-07`
- 任务包：`DESIGN-LAB-Authoritative-TaskPack-v4.0`
- 规则：**只执行净缺口，不机械重跑旧 V3 的 90 张任务卡。**

## 原则

旧 V2/V2.1/V3/V4 文件不删除，作为继承证据与历史参考。每项旧资产必须标记处置状态；只有 `PARTIAL`、`NET_NEW`、`BLOCKED` 修复项及确需复核的 `INHERITED_NEEDS_REVERIFY` 才进入执行队列。

## 处置状态定义

| 状态 | 含义 |
|---|---|
| `INHERITED_VERIFIED` | 已继承且验证通过，V4 直接复用 |
| `INHERITED_NEEDS_REVERIFY` | 已继承但需在 V4 中复核/升级（多为结构 E1 → 真实 E3） |
| `PARTIAL` | 部分有效，需补齐 |
| `SUPERSEDED` | 被新入口/新命名空间替代，仅作参考 |
| `NOT_APPLICABLE` | 不适用于 V4 |
| `NET_NEW` | V4 净新增 |
| `BLOCKED` | 存在阻断 |

## 废止的旧入口

| 旧入口 | 处置 | 理由 |
|---|---|---|
| V2 execution pack | SUPERSEDED | 被 V3 product-manifest/runtime contracts 替代 |
| V2.1 execution pack | SUPERSEDED | 被 V3 visual-scoring gates 替代 |
| Complete-TaskPack-v3.0 活动入口 | SUPERSEDED | V4 taskpack 替代 |
| 旧 `OD-0001…OD-1504` | SUPERSEDED | 被 ODA4 替代 |
| 旧 `V4-OD-*` | SUPERSEDED | 被 ODA4 替代 |
| WORK-LAB/Open Design 长期耦合方案 | SUPERSEDED | WORK-LAB 完全切割，本项目独立生命周期 |

## 当前能力普查（2026-08-07）

| 资产 | 数量 |
|---|---:|
| 插件 | 8 |
| Atom | 21 |
| Scenario | 6 |
| Bundle | 2 |
| Rubric | 19 |
| Profile | 12 |
| 设计系统 | 1（anomaly-monitor-dark） |
| Domain Pack | 1（minigame-design） |
| 视觉包 | 1 |
| 导出示例 | 1 |
| project-memory 文档 | 8 |

## 核心资产继承处置

| 资产 | 处置 | 说明 |
|---|---|---|
| V3 product-manifest / capability-status | INHERITED_VERIFIED | V4 扩展为 PRODUCT_DEFINITION_V4 |
| V3 runtime-contracts schemas | INHERITED_VERIFIED | 223/223 通过 |
| V3 visual-scoring schemas | INHERITED_VERIFIED | 10/10 通过；V4 加人类评审协议 |
| V3 21 atoms / 6 scenarios | INHERITED_NEEDS_REVERIFY | 仅结构 E1，V4 需真实 E3 |
| V3 2 bundles | INHERITED_NEEDS_REVERIFY | V4 增加第三入口 production-handoff |
| V3 19 rubrics | INHERITED_VERIFIED | 绑定人类校准与真实 Benchmark |
| V3 12 profiles | INHERITED_VERIFIED | 对齐 Domain Pack profiles |
| V3 8 plugins | INHERITED_NEEDS_REVERIFY | V4 收敛为 3 公开入口，8 插件转兼容 Profile/Adapter |
| V3 anomaly-monitor-dark | INHERITED_VERIFIED | 仅作设计系统参考，非全局默认审美 |
| V3 domain-pack minigame-design | INHERITED_NEEDS_REVERIFY | 需补全 Domain Pack Spec 十要素 |
| V3 112+22 来源注册 | INHERITED_NEEDS_REVERIFY | V4 迁移至 SOURCE_REGISTRY_V3 |
| V3 497 大师记录 / 77 方法卡 / 47 风格谱系 | INHERITED_NEEDS_REVERIFY | V4 核验匿名化，晋级 ≤20 运行卡 |
| V3 12 evidence cards | INHERITED_NEEDS_REVERIFY | 当前 not-run，V4 换真实能力证据 |
| V3 验证脚本 | INHERITED_VERIFIED | V4 根 Canonical CI 全跑 |
| MiniGame runtime | INHERITED_NEEDS_REVERIFY | 独立参考产品 + 跨媒体 Benchmark，隔离 |
| packages/design-system/ 吸收资产 | INHERITED_VERIFIED | Open Design 参考材料 |

## V4 净缺口分组

1. P0 安全/许可/CI/生成物漂移/体量（Phase 01）
2. V4 产品定义 + 三公开入口 + Domain Pack Spec（Phase 02）
3. Open Design 真实 E3 黄金场景（Phase 03）
4. 专业内核 + 视觉质量 + 人类评审（Phase 04）
5. Wave A 四领域 Domain Pack（Phase 05）
6. Wave B 五领域 Domain Pack（Phase 06）
7. Wave C 四领域 Domain Pack（Phase 07）
8. 来源/许可/大师/风格证据化（Phase 08）
9. 真实 Benchmark + 人类评审 + 失败回归（Phase 09）
10. MiniGame 逻辑隔离 + 资产治理（Phase 10）
11. Canonical Gate + 冻结 + 独立复审 + 授权（Phase 11）

## 证据

机器可读：`design-lab/config/inheritance-matrix.json`
审计基线：`ODA4-0001 baseline.json`、`ODA4-0002 tool-inventory.json`
