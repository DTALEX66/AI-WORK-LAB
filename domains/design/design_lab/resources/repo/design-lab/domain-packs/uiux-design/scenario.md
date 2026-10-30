# UI/UX Design Domain Pack — Scenario

- Pack: `uiux-design`｜版本：`0.1.0`｜任务：V42-0401｜证据：E2（结构）
- 场景是五个黄金纵切案例的统一执行管线（V42-0402..0406 分别实例化）

## 场景

`uiux-golden-slice` — 商业 UI/UX 设计黄金纵切。

## 执行管线（stages）

| # | Stage | 产出 | 原子（daemon builtin 或本地专业原子） |
|---|---|---|---|
| 1 | `brief` | Brief 标准化与验收定义 | `brief-normalizer`（本地） |
| 2 | `research` | 参考/来源/Reference DNA | `reference-dna-analyzer`（本地）、`research-search`（builtin） |
| 3 | `directions` | 三种结构方向 + 锁定 | `design-direction-jury`（本地）、`direction-picker`（builtin） |
| 4 | `system` | DESIGN.md / DTCG Tokens / 组件 | `token-map`（builtin）、design-system 合同 |
| 5 | `create` | 三视口实现（320/768/1280+） | `file-write`（builtin）、媒体原子 |
| 6 | `critique` | 视觉质量 + 设计评审 | `design-quality-jury`（本地）、`critique-theater`（builtin） |
| 7 | `preflight` | 生产预检（无障碍/性能/资产） | `commercial-preflight`（本地） |
| 8 | `handoff` | 可编辑交付 + provenance | `delivery-packager`（本地）、`handoff`（builtin） |
| 9 | `evidence` | Benchmark / 评审 / 证据卡 | `live-artifact`（builtin）、evidence 卡 |

## 每案例必须包含（Phase 4 Gate）

1. Brief（schema 校验）
2. 参考/来源（含 license_status）
3. 三种结构方向 + 选择与锁定记录
4. DESIGN.md / DTCG Token
5. 组件清单
6. 三视口（320 / 768 / 1280+）
7. 键盘路径
8. 无障碍（Axe critical/serious = 0）
9. 基线/增强对比（偏好率 ≥70%）
10. 可编辑 Artifact + 评审 + 预检 + 交付 + 证据

## 复现

- 每个案例目录：`benchmarks/<case-id>/`（brief/directions/system/critique/preflight/handoff/evidence）
- 每个案例以 `python design-lab/scripts/verify_domain_pack_v2.py design-lab/domain-packs/uiux-design` 验证包完整性
- Axe 检查以真实浏览器跑分（不得以自评代替）
