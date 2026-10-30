# AI-WORK-LAB 延期与阻塞登记册（P0 冻结版）

生成：2026-10-29（P0 阶段冻结；后续批次只能追加，不得改写已完成批次的登记）
依据：02 提示词 §6 P3、09 分期与验收、05 能力族分期。复杂新增能力延期；
**不允许借延期删除已有可用实现**——每条都注明保留的实现/合同/入口。

## 延期条目（P3，保留范围与接入点）

| ID | 来源键/族 | 用户目标 | 保留的实现/合同/入口 | 未完成差距 | 依赖 | 优先级 | 后续任务 | 验收 | 恢复方式 |
|---|---|---|---|---|---|---|---|---|---|
| D-01 | work:execution 族（P3 部分） | 多 Agent 并行总控 | 适配器合同 config/adapter-registry.json、dispatch_contract、单会话单写者规则 | 并行调度/总控编排 | 执行器联网授权 | P3 | 多Agent总控设计 | 合同测试+真实执行者资格 | 从 integrations/agents 合同重启 |
| D-02 | work:session 族（P2 部分） | 跨会话接续 | 上下文服务合同（127.0.0.1:1933 单端口治理） | 协议接续实施 | 本地上下文服务可用 | P2 | 会话接续协议接线 | 新会话真实调用检索 | 按标准§5变更流程 |
| D-03 | design:design-reconstruction（P3 部分） | 深层图层重建 | reconstruction 契约/schema/adobe_job/adobe_lowering（wheel force-include 清单保留） | 复杂重建自动化 | 宿主可用 | P3 | 重建管线扩展 | E2 受控读回 | 从 packages/capabilities/reconstruction 恢复 |
| D-04 | design:design-quality（P3 部分） | 完整真人评审平台 | human_jury/qa_plane/quality_store 实现与 Human Gate 规则 | 评审平台化 | 评审人可用 | P3 | 评审工作台 | E4 独立人审 | 从 assurance 包恢复 |
| D-05 | work+design 桌面（P3 部分） | 复杂工作流画布 | desktop 后端数据与协议投影 | 画布前端 | STITCH 设计 | P3 | 画布实现 | 前端验收 | apps/desktop 合同 |
| D-06 | evolution 族（P3 部分） | 应用自改写全链路 | ImprovementCandidate 数据合同（08 约定 entities）+ 改进任务类型 | 候选隔离/验证/激活/恢复执行链 | 本批 unavailable | P3 | 自我迭代执行链 | 候选→验证→激活→回滚演练 | 合同保留于 core/evolution |
| D-07 | 新增 RAG/向量平台 | —（本批无需求） | 统一检索入口沿用 FTS5+中文短词策略 | 向量检索 | 明确需求+授权 | P3 | 评估后引入 | 检索对比验收 | 不预装任何向量库 |
| D-08 | AAOS 互联 | 未来知识系统对接 | KnowledgeCandidate 出口合同（versioned schema） | 深度互联 | AAOS 独立授权 | P3 | 版本化接缝联调 | 合同测试 | integrations/knowledge-candidate |
| D-09 | 手机端 | 明确排除（owner 2026-10-19/2026-10-29 会话） | 无（排除项，非缺口） | — | — | 排除 | 不派工 | — | — |
| D-10 | 企业团队/通用素材商城/字库 | 明确排除 | 个人范围权限确认保留 | — | — | 排除 | 不派工 | — | — |
| D-11 | BOT/IM 渠道 | 可后续增加的消息入口 | 任务/消息入口抽象（Task 外层） | 渠道适配 | 用户需求 | P3 | 单渠道试点 | 渠道合同测试 | 入口抽象不建平台 |
| D-12 | 跨机执行与远程恢复 | — | 单机恢复（重启读回）已有 | 跨机 | 授权+隔离 | P3 | 远程执行设计 | 远程恢复演练 | — |
| D-13 | 模型训练/权重更新 | — | Model library 本地资产只登记不使用 | — | 硬件+授权 | P3 | — | — | — |

## 条件实施（P2）

| ID | 内容 | 条件 | 当前状态 |
|---|---|---|---|
| C-01 | 一个已可用且不联网的宿主闭环（design-tools 适配器对受控样例真实调用/保存/重开/读回） | 本机原生软件可用+操作授权；不关共享进程 | NOT_PROBED（本批未执行，逐次走 Human Gate） |
| C-02 | 单个执行器适配与资格（ACP/原生 app-server 本地契约测试） | 不联网、替身不算真实资格 | 本地契约可测；真实执行器资格 PENDING |

## 阻塞（本批）

| ID | 内容 | 状态 |
|---|---|---|
| B-01 | 原生宿主（Photoshop/Illustrator COM 等）本批未做真实宿主验证 | 相关实现保留，标记 BLOCKED_HOST_VALIDATION，不用空 stub 替换 |
| B-02 | pytest 系统解释器缺失 | 已获用户许可按需最小下载（执行时记录） |
| B-03 | Tauri/前端未到位（STITCH 负责设计） | 后端以真实 HTTP+合同验证，不宣称桌面已运行 |
