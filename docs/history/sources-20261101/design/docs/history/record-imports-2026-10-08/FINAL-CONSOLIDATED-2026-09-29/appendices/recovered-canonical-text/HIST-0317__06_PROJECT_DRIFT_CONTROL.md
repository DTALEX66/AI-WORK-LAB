# 项目漂移防护合同

## 1. 目的

本合同防止项目在长期执行中从“Open Design 原生专业设计增强产品”漂移成资料库、第二套设计平台、Agent/聊天工具、MiniGame 产品、泛 AI 平台或只有文档没有真实作品的工程。

漂移状态只有：

- `ALIGNED`：定位、边界、优先级、证据和仓库关系一致；
- `AT_RISK`：出现趋势，但尚未形成事实偏离；
- `DRIFTED`：实现、文档、任务或能力声明已偏离；
- `BLOCKED_REAUTH`：触碰不可变边界，必须停止并由用户重新授权。

## 2. 不可变锚点

以下内容未经用户明确重新授权不得改变：

1. 产品是 Open Design-first、Agent-compatible 的专业设计智能、视觉质量、商业生产与可编辑交付增强产品。
2. Open Design 是主入口，负责应用壳、项目、Studio/画布、Agent、插件运行、GenUI、Artifact、预览和导出。
3. 本仓库负责 Domain Packs、专业方法、视觉质量、权利门禁、预检、交付、Benchmark 和证据。
4. 不建设第二套 Open Design/Lovart，不建设聊天客户端、Agent runtime、模型网关或通用工作流平台。
5. 不把项目降级成纯知识库、Prompt 仓、资料导航或大师风格生成器。
6. MiniGame 只作设计 fixture/runtime reference；禁止平台、广告、变现、发行、运营和产品逻辑扩张。
7. UIUX 黄金纵切优先；未通过前不得同时铺开多个空壳领域。
8. 知识是燃料，真实运行能力与可编辑 Artifact 才是产品；声明不得高于证据。
9. 不重新耦合 WORK-LAB；两仓只可通过公开、版本化接口协作，不共享活动模块或内部状态。
10. Windows 本地优先、格式开放、客户端与模型中立、版本可演进，不锁死单一 Agent 或固定工具路径。

## 3. 八类漂移

| 类型 | 典型表现 | 默认处理 |
|---|---|---|
| 定位漂移 | 改成知识库、独立平台、Agent 或聊天产品 | `BLOCKED_REAUTH` |
| 边界漂移 | 复制 Open Design 画布/项目/模型路由；重耦合 WORK-LAB | `BLOCKED_REAUTH` |
| 优先级漂移 | UIUX 未闭环就批量创建新 Domain Pack | `DRIFTED`，停止扩张 |
| 证据漂移 | 文档、Schema、mock、VLM 自评冒充 E3/E4 | 降级并阻断发布 |
| 数据漂移 | 未核验资料、来源、许可进入 runtime | 隔离并阻断能力调用 |
| 技术漂移 | 无必要新增数据库、SaaS、daemon、框架或硬锁版本 | ADR + 用户批准 |
| 体验漂移 | 专业工作流退化成通用聊天和一键生成 | `DRIFTED`，回到职业任务 |
| 范围漂移 | MiniGame、商业化、运营或无关工具吞噬主线 | 移出 backlog 或重新授权 |

## 4. 允许的演进

无需改变定位即可持续增强：

- 新增或深化职业 Domain Pack；
- 提升视觉质量、反 AI 痕迹、可控编辑、评审和修复；
- 增强生产预检、权利、可编辑交付和证据；
- 适配 Open Design 的公开新接口；
- 扩充经核验的开源标准、方法、案例和失败模式；
- 增强 Open Design 内部的 GenUI、Artifact、插件和面板体验；
- 在证据支持下替换工具、模型、Agent 或版本。

## 5. 强制检查点

必须在以下时点生成 `drift-report.json`：

1. 每个任务开始前；
2. 每个 Phase Gate；
3. 引入新目录、新依赖、新服务、新数据库或新运行时之前；
4. PR 创建前；
5. merge 前；
6. main 回读和 release 前。

每份报告至少包含：

```json
{
  "task_id": "V42-0000",
  "status": "ALIGNED",
  "product_anchor": "open-design-native-professional-design-intelligence",
  "user_value": "",
  "changed_scope": [],
  "upstream_duplication_check": "pass",
  "work_lab_recoupling_check": "pass",
  "minigame_boundary_check": "pass",
  "domain_priority_check": "pass",
  "evidence_claim_check": "pass",
  "knowledge_maturity_check": "pass",
  "new_subsystem_or_dependency": false,
  "reauthorization_required": false,
  "decision": "continue",
  "reviewer": "",
  "timestamp": ""
}
```

## 6. 每张任务票必须回答

- 这项任务帮助哪类用户完成哪一步职业设计任务？
- 它属于 Open Design 还是 Assistance 的职责？
- 是否复制上游已有能力？
- 是否引入新子系统、服务、数据库、运行时或长期维护负担？
- 是否改变 MiniGame 或 WORK-LAB 边界？
- 最低证据等级是什么，怎样产生真实 Artifact？
- 如果取消，如何回滚且不损害现有能力？

无法回答时不得进入 `IN_PROGRESS`。

## 7. 必须重新授权的变化

以下变化必须提交 Drift Change Request，并等待用户明确批准：

- 改产品定位、名称主身份或核心用户；
- 建立独立前端、独立 SaaS、账户/计费或云端多租户；
- 建立新的 Agent、聊天入口、模型网关或通用任务平台；
- 新增长期运行 daemon、数据库或大型服务；
- 将 MiniGame 恢复为活动产品；
- 与 WORK-LAB 重新合仓、共享活动模块或共享内部数据库；
- 降低 E3/E4、人工评分、偏好率、权利或生产 Gate；
- 大规模吸收未审查开源代码、模型、字体或素材；
- 调整 UIUX→平面/品牌/电商→复杂媒介的优先顺序。

## 8. CI 与 Reviewer Gate

- `drift-report.json` 缺失、状态为 `DRIFTED/BLOCKED_REAUTH` 或 reauthorization 未附批准证据时，PR/release Gate 必须失败。
- Reviewer 必须独立回答：定位是否改变、是否复制上游、是否重新耦合 WORK-LAB、是否扩张 MiniGame、是否把资料冒充能力。
- README、产品定义、架构、任务卡和能力索引之间出现矛盾时，以不可变锚点为准并标记 `DRIFTED`。
- 任何“临时例外”必须有到期时间、责任人和删除任务；不得永久沉淀成隐性新方向。

## 9. 漂移修复顺序

1. 停止新增写入；
2. 冻结当前 tree 与证据；
3. 标记偏离的任务、文件、提交和能力声明；
4. 判断回滚、隔离、降级或重新授权；
5. 修复 SSOT、任务依赖、证据和 CI；
6. Reviewer 确认恢复为 `ALIGNED` 后才继续主线。

