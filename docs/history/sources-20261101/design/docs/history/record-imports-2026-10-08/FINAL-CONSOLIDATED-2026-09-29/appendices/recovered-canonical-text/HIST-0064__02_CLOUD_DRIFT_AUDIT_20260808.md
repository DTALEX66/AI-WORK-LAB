# OPEN-DESIGN-Assistance 云端偏航审计与 V4.1 纠偏令

审计日期：`2026-08-08`  
审计性质：只读云端事实审计  
目标：`DTALEX66/OPEN-DESIGN-Assistance`  
观察到的 `main`：`d053a9b7feb966a0dedcd63ebf51356787661da8`  
状态：`V4.1_EXECUTION_OVERRIDE`

> 本文件不是第二套任务包。它是 V4.1 对 V4.0 的事实更新和执行优先级覆盖；发生冲突时，执行时的当前事实优先，其次为 V4.1，再其次为 V4.0 历史内容。

## 1. 最终判断

项目定位没有偏离：当前 README、`PRODUCT_DEFINITION_V4.md` 与 `product-manifest.json` 已把项目定义为 Open Design-first、模型/风格/领域/工具中立、权利安全的专业设计智能与视觉质量增强层；MiniGame 也被声明为参考产品与 Benchmark，而不是公共内核。

项目执行结构仍然偏斜：已完成工作集中在仓库治理、历史清理、CI、Open Design 对接准备和 MiniGame，Phase 04/05 的真实专业设计能力尚无对应提交。按交付重心估算，当前约 `70%` 为治理/工程/运行准备，少于 `30%` 为真实职业设计能力。若后续仍继续新增治理文档、CI 或 MiniGame 工作，而不进入 UI/UX、平面、品牌和电商纵向闭环，项目将发生实质偏航。

因此 V4.1 的策略是：先用一个有限纠偏波修复事实漂移和虚假门禁，然后强制切换到专业设计能力交付。

## 2. 云端事实基线

| 项目 | 2026-08-08 观察 |
|---|---|
| 默认分支 | `main` |
| `main` HEAD | `d053a9b7feb966a0dedcd63ebf51356787661da8` |
| 最新提交 | `docs: upgrade project positioning to V4 (neutral design platform)` |
| 远端分支 | `main`、`migration/work-lab-minigame-cutover-20260807` |
| 分支关系 | 两分支观察时指向同一 SHA |
| PR | 未读到 PR |
| 仓库元数据体积 | 约 `358108 KB`；远端缩减效果未独立证实 |
| 旧 V4.0 基线 | `345684153ad05b5bffaead8d66308bd2ad437811`，与当前历史无共同祖先；历史已被重写 |
| 已完成主线 | Phase 00–02，Phase 03 部分完成 |
| 未发现主线提交 | Phase 04、05、06 |
| Open Design 观察版本 | `0.18.1` |
| 显式 Domain Pack | 继承矩阵仍报告 `1`，即 MiniGame |

云端连接器对 Actions 的可见性有限。未读到 PR 触发的 workflow run 或当前 SHA status，不能推断 GitHub Actions 从未运行；只能结论为：`E4 未被当前证据证明`。

## 3. 已经对齐的部分

- `PRODUCT_DEFINITION_V4.md` 已明确五种中立、Open Design/本仓库边界和三个公开入口；
- `product-manifest.json` 为 `4.0.0-staging`，MiniGame 角色为 `reference product + benchmark`；
- 根许可证已选择 MIT，并有 `NOTICE` 与许可决定记录；
- 已建立根 CI、依赖入口、迁移状态、产品 Manifest、Domain Pack Spec、Evidence 合同和 Adapter 注册表；
- MiniGame 已完成安全、导出漂移和大规模重复媒体治理的若干工作；
- Open Design `0.18.1` 的真实进程、命名管道、项目位置和一个设计系统导入已有部分 E3 记录。

这些成果必须继承，但只能按实际证据标为 `INHERITED_VERIFIED`、`INHERITED_NEEDS_REVERIFY` 或 `PARTIAL`，不能整体宣称 Gate 已关闭。

## 4. 必须纠正的 13 项事实与门禁

1. `OPEN_DESIGN_COMPATIBILITY_MATRIX.md` 仍写 `0.13.0`，与 README、baseline 和 E3 的 `0.18.1` 冲突。
2. `V4_HANDOFF_SUMMARY_20260807.md` 仍报告旧分支、旧 SHA、main 未合并和未重写历史，已与云端事实不符。
3. 根 README 示例传入脚本不存在的 `--permission-root` 参数，命令会失败，也违背窄根权限原则。
4. `configure_open_design_windows.py --apply` 会写 Open Design 私有 `app-config.json` 和安装目录附近 launcher，却声称只触碰项目根；该路径必须从默认安全入口移除、禁用或变成单独授权工具。
5. 根 MIT 许可只解决了许可证选择；逐文件 SPDX、二进制 `.license` sidecar、SPDX/CycloneDX SBOM 和第三方 BOM 仍未闭环。
6. Canonical workflow 的“Assert full tree clean”只打印行数，没有在非零时失败，属于虚假 clean-tree gate。
7. 根 CI 的许可检查只检查根 LICENSE 和敏感文件名，没有执行 REUSE、sidecar、SBOM/BOM 覆盖门禁。
8. 预期的 `capability-evidence-index.json` 未在当前 main 读取到，因此 Phase 00 不得整体标为完成。
9. Adapter registry 将 Figma、Penpot、browser 标为 `available`，但未展示 live/version/task/artifact 证据；应降级为 declared/structural/unverified。
10. 当前 SHA 未取得 exact-SHA CI、PR 和冻结复审证据，E4 只能为 `UNVERIFIED`。
11. 本地历史清理报告称 `.git` 从约 351 MiB 降至 185 MiB，但 GitHub 元数据仍约 358108 KB；需独立核验，不得直接宣称远端瘦身完成。
12. Product Manifest 的 source governance 仍指向已“解决”的 `LICENSING_DECISION_REQUIRED.md`，名称与状态漂移。
13. 继承矩阵中插件计数为 8，而其他描述组合可能得到 10 个 manifest；必须统一统计口径。

## 5. V4.1 强制执行顺序

### Wave C0：有限事实纠偏

执行 `ODA4-0110…ODA4-0118`：刷新云端基线、修正 SSOT/交接报告、收缩 Windows 配置脚本、修复 clean-tree 与许可门禁、补能力证据索引、降级无证据 Adapter、重开 Gate 0、冻结 MiniGame、独立核验历史体积。

这不是无限治理阶段。完成纠偏后，除阻断 Phase 04/05 的安全、许可、构建失败外，暂停新增治理文档和基础设施任务。

### Wave C1：专业设计公共内核

按 `ODA4-0401…0406` 完成：

- 专业设计方法公共内核；
- 100 分视觉质量系统与真实人工 Jury；
- 去 AI 味与人物/产品/材质/排版真实性失败回归；
- 跨格式一致性与真实 Production Preflight；
- 可编辑交付合同与可运行 `production-handoff`；
- 三公开 Bundle 的真实注册和证据。

### Wave C2：UI/UX 黄金纵切

UI/UX 是下一主交付，先做完整 Domain Pack 和五个 Benchmark：

1. B2B 数据仪表板；
2. 消费者移动应用核心流程；
3. 电商 PDP 与 Checkout；
4. 设置、权限和无障碍复杂状态；
5. 复杂响应式内容页面。

每案必须包含三档视口、键盘路径、axe critical `0`、视觉回归、可编辑产物、DTCG Tokens、DESIGN.md、baseline/enhanced、人类评分 `>=82/100`、baseline 偏好率 `>=70%`。至少一个案例必须取得真实 Open Design E3。

### Wave C3：Wave A 与后续职业领域

完成 UI/UX 后依次推进平面/视觉、品牌、电商；再推进展厅展馆、3D、动画/视频、音频、游戏视觉/UI/音频；最后补齐包装/印刷、编辑/出版、插画/IP 和数据可视化。

### Wave C4：开源、标准、大师方法与证据

- 将现有 `112 + 22` 条来源迁移到 `SOURCE_REGISTRY_V3`；
- 每项记录版本、固定来源、许可、权利状态、吸收模式、成熟度、领域、测试和禁用条件；
- V1 最多晋级 20 张高质量、来源充分、匿名化、非模仿的 runtime 方法卡；
- 420 条未核验研究种子保持 quarantine；
- 大师姓名只用于研究索引，不进入最终运行提示。

## 6. MiniGame 功能冻结

MiniGame 永久保留在 `OPEN-DESIGN-Assistance/minigame-runtime`，不移回 WORK-LAB，也不再作为平台主线扩张。

允许修改范围仅限：

- 安全修复；
- 可复现构建和导出漂移；
- 资产去重、许可 sidecar 和包体治理；
- 现有测试、CI 和平台兼容修复；
- Game Domain Pack 的 HUD/UI/图标/动效/声音/皮肤/视觉规范/Fixture/失败案例；
- 只读拆仓成本评估。

禁止：新玩法、广告、变现、商店、运营、上架、平台发布扩展，或让 MiniGame Runtime/主题/资产反向进入公共 Core。

## 7. 资源与提交配额

纠偏波结束后执行以下防偏规则：

- 每新增 1 个治理/文档/CI 修复提交，必须先完成或同时交付至少 1 个 Phase 04/05 的真实能力提交；
- 未取得 UI/UX 第一个真实 E3 前，禁止新增第二个参考产品；
- 未完成四个 Wave A Domain Pack 前，禁止把 MiniGame 或基础设施工作列为版本主叙事；
- 任务完成必须以真实产物和对应等级证据为准，不能以文件数、测试数或声明替代。

## 8. V4.1 通过判定

V4.1 本地阶段只有在以下条件成立后才能报告 `READY_FOR_USER_APPROVAL`：

- 13 项事实/门禁漂移均已关闭或有明确 `BLOCKED` 证据；
- Phase 04 专业内核完成；
- UI/UX 五案例完成且至少一个真实 E3；
- 平面、品牌、电商四个 Wave A Domain Pack 完整；
- 来源、许可、SBOM/BOM、Evidence、Preflight 和可编辑交付均可读回；
- MiniGame 保持冻结且不污染公共 Core；
- frozen exact tree 通过 Canonical Gate 和独立只读复审；
- 未执行任何未经用户授权的 commit、push、PR、merge、ruleset、tag 或 release。

没有 E3 不得称运行可用；没有 E4 不得称发布完成；没有 E5 不得称商业验证完成。
