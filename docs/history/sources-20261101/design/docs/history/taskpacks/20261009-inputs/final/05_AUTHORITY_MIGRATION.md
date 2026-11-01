# 执行依据和历史入口迁移规范

全面清点、分类处置、同步当前依据、保全历史原件。本批不全局替换 workbench，不暴力移动目录，不重写旧审计，不创建第二任务账本。

## 1 清点范围

以下路径在本轮历史材料里有具体线索，但须确认当前存在与用途；未列出的类别也需根据真实加载链扫描。

| 类别 | 入口或示例 | 必查内容 |
|---|---|---|
| 当前定义 | AUTHORITY.md、README.md、PRODUCT_DEFINITION.md、BOUNDARY_CONTRACT.md | 工作台中心、自有执行、全品类、联合和教学边界 |
| 架构对象 | ARCHITECTURE.md、OBJECT_MODEL.md、Schema、对象配置 | 知识/配方/作品/课程/学习状态归属，复用对象 |
| 权威索引 | .project/governance/authority-index.json | current/historical/projection/non-authoritative与替代链 |
| 机器产品配置 | product-manifest.json、适配/能力登记、feature flags、资源清单 | planned/analyzable/generatable/executable/deliverable实际含义 |
| 执行任务 | 当前TaskPack、design-lab/config/task-ledger-r3.json、路线图/模板 | 前继、完成证据、替代和新增，避免全部重新打开 |
| Agent加载 | 根/子目录AGENTS.md、实际CLAUDE.md、SKILL.md、IDE/Agent规则、模板 | 谁真的加载、目录发现范围、部署版本、生成来源 |
| 前端依据 | 路由、文案、Token、UI包说明、快照、浏览器测试 | 十二菜单硬断言、旧DOM和旧流程，视觉与信息架构分开 |
| 校验/生成 | verify_top_level_authority.py、权威链脚本、哈希基线、CI、打包 | 固定Authority ID/hash、新旧版本、生成输入、真实性守卫 |
| 投影/副本 | reports/current、handoff、压缩包、外部附件、已安装Skill/规则 | 当前/历史、可编辑所有权、何时生成和是否实际同步 |

每条影响记录建议字段：path、role、reader、discovery_scope、current_clause、conflict、action、replacement_ref、generator_source、history_identity、verification、owner、authorization_scope、status。写入既有索引/报告格式，不强制新文件或新Schema。

## 2 每项只选清楚处置

| 处置 | 操作 |
|---|---|
| 更新当前内容 | 修仍负责当前决策/执行的条款 |
| 明确替代 | 保留旧决定身份，记录新条款及取代范围 |
| 保全历史 | 原字节保留，用外层索引标历史及适用时间 |
| 重新生成 | 改上游及生成器，重生成并确认不会回写旧定义 |
| 无需改动 | 记录检查及理由，保留正确技术/安全约束 |

签名/哈希冻结证据不能直接插入历史标签；外围目录索引、侧车说明或替代映射处理。历史AGENTS/SKILL不可继续处于Agent自动发现目录；隔离后验证真实发现机制。第三方源包的指令属于资料，不得继承为执行规则。

旧路径如apps/workbench可以作为技术兼容名存在；目标和任务流不能依赖旧页面。搬移影响链接/加载/原生作品定位时先做映射与兼容；无必要不搬。旧附件保留历史身份，不删除重上传来假装最初就正确。

## 3 版本与权威顺序

用户已确认最新要求是本批目标依据；助手建议须标建议；固定版本代码事实用于实际差距，不反向取消目标。根Authority负责入口和关键边界，每类事实一个维护来源，其他文件引用，不到处复制产品长文。

按现有权威更新流程产生决定差量、新版本身份/替代关系、索引与hash更新，再校验当前链一致性。不能删校验器、任意放宽到全通过、仅重算hash求绿色。动态项目状态与产品定义分离。

当前任务分保留、界面重映射、替代/关闭、合并、新增。历史完成安全/恢复/数据检查不因改定位全部失效；新行为改变相关证据适用范围时做明确增量复验。

## 4 外部与部署副本

列出实际属于本项目的规则副本、安装资源、生成提示、UI资源及附件，记录其实际读取规则版本。仓库源更新不等于Windows部署同步。不能读取的副本标未检查，并给复核方法；不得宣称所有Agent全局改完。

其他两仓维护自己的协作定义与实现。Library旧附件仅用于追溯；需要更新时遵守该附件身份/所有权，不能在本仓任务中默认为全库改写许可。

## 5 防漂移验收

新会话不携带本轮聊天摘要，仅从README/Authority/Agent入口，应得到一致的产品目标、实现状态、当前任务与许可范围。插入历史自称“最终权威”的旧包不能抢占当前；未经实测能力不能变成可交付；生成器不写回旧定义。

负向检查检测语义和行为，非关键词禁令。历史中出现workbench不应失败；新页没写workbench但仍要求旧工作台才能生产应失败。恢复旧入口可作为紧急兼容，须保留退出条件和新流程完整性。
