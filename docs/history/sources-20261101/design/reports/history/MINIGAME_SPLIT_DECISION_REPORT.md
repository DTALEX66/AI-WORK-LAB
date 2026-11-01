# MiniGame 拆仓只读决策报告（ODA4-1005）

- **任务**：ODA4-1005（生成 MiniGame 后续是否拆仓的只读决策报告）
- **状态**：**COMPLETE**（只读分析，未执行物理拆仓，未移动文件）
- **日期**：2026-08-14（boundTree=`cbae9fa`）
- **结论**：**建议保留同仓**（不拆仓、不移回 WORK-LAB）

## 1. 现状数据

| 维度 | 值 |
|---|---|
| `fixtures/domains/game-visual/` 规模 | 686 文件 / 228 MiB（含 cctv gif 资产 ~90 MiB） |
| 仓库总规模 | 工作树 629 MiB / .git 202 MiB |
| MiniGame 占仓库比例 | 文件 686/总 ~5000；体积 228/629 = **36%** |
| 仓库 `product-manifest.json` | 明确声明 `make MiniGame operational/advertising/monetization the platform mainline` 为**禁止项**（J0 冻结边界） |
| `MINIGAME_FROZEN_BOUNDARY.md` | MiniGame = 冻结的独立参考产品，仅安全/构建/资产/测试/Fixture 维护 |

## 2. 依赖分析（公共 Core → MiniGame）

- **代码级 import**：`design-lab/scripts/` 与 `tests/` **无** import minigame-runtime 代码（仅 verifier 排除路径声明）
- **登记引用**（47 处）：capability-index 登记 `domain-packs/minigame-design/`（8 条路径）、product-manifest 边界声明、SBOM、inheritance-matrix——均为**元数据登记**，非运行时依赖
- **反向**：minigame-runtime **不 import 公共 Core**（冻结边界已实施）
- **结论**：双向依赖已断 → 拆仓技术上可行，但**无必要**

## 3. 拆仓 vs 保留成本对比

| 维度 | 保留同仓（推荐） | 拆出独立仓 |
|---|---|---|
| **CI** | 现有 `canonical-verify-v4.yml` 一个 gate 覆盖（node-gate 已隔离 minigame 测试） | 需新建独立 CI workflow + token + secrets |
| **历史** | 完整保留（git 历史含 minigame 演进） | 需 `git subtree split` 或 filter-repo（历史重写风险） |
| **体积** | minigame 228 MiB 占 36%——有 KNOWN 豁免（cctv gif 已登记例外） | 仓库瘦身 ~36%，但 cctv 资产仍在（需外置） |
| **维护** | 单仓单 PR 流程，verifier 链统一 | 双仓双 PR，需同步版本（增加维护面） |
| **发布** | minigame 冻结无独立发布节奏 | 拆仓后无独立发布需求（仍冻结） |
| **协作** | 单 writer 纪律延续 | 双 writer 边界成本 |

## 4. 结论

1. **不拆仓**：MiniGame 已冻结（无独立开发/发布节奏），拆仓收益仅"仓库瘦身 36%"但引入 CI/历史/维护三重成本——**净收益为负**
2. **不移回 WORK-LAB**：违反既定边界（ODA4-0117 已确立 MiniGame 留在 DESIGN-LAB），且 WORK-LAB 是只读投影
3. **体积治理替代方案**：cctv gif（~90 MiB）若 minigame 运行时生成则移出 Git（KNOWLEDGE_ASSET_POLICY 例外条款已预留），比拆仓更精准
4. **触发拆仓的条件**（未来若发生）：MiniGame 解冻恢复独立产品开发 + 独立发布节奏 + 公共 Core 开始反向依赖——三项同时出现才重评

## 5. 合规

- ✅ 只读分析（未执行物理拆仓、未移动文件、未改配置）
- ✅ 不建议移回 WORK-LAB
- ✅ 默认不执行物理拆仓
