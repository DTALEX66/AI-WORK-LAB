# E0–E5 证据矩阵

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

唯一采用顶层定义：E0 DECLARED；E1 STRUCTURAL；E2 CONTROLLED_RUNTIME；E3 REAL_WORKFLOW；E4 INDEPENDENT_ACCEPTANCE；E5 RELEASED / REPEATABLE。证据等级必须带范围、subject SHA、时间、环境和artifact。没有足够证据写NOT_ESTABLISHED，不能随意将整个项目压成单一数字。


| 对象 | 证据来源 | 支持等级 | 不足/限制 | 升级条件 |
| --- | --- | --- | --- | --- |
| 历史文件完整性 | 522条hash原件 | 文件证据；不是产品E等级 | 10未恢复/4占位 | 恢复原件并重新hash |
| Authority/对象契约 | exactSHA文件读取 | E1 | 不能证明执行 | 契约覆盖与真实流程 |
| Python/TS/许可/clean-tree等CI | exactSHA run36501310080 job success | E2（CI覆盖范围） | artifact字节未由本轮独立下载验算 | 下载对应artifact、hash与subject绑定 |
| Workbench浏览器测试 | exactSHA CI job success | E2 | 不是用户Windows生产使用 | 安装后的真实任务+人审 |
| 项目/Brief/资产/方向 | API/TS与受控测试存在 | E1/E2子集 | 业务整链仍不完整 | 真实用户项目闭环 |
| Bundles列表 | class+query tests | E2受控 | HTTP list route/UI未接 | 路由隔离/分页/空/错误和UI |
| Bundle导出 | create/content与元数据 | E1/E2子集 | rights/quality/fonts仍NOT_REVIEWED等 | 真实交付接收与源文件重开 |
| Adobe PS/AI | 当前代码+历史报告 | E1/E2；历史实机单列 | 本轮无当前设备/素材操作 | 当前SHA实机记录与独立专业接受 |
| Comfy model-free workflow | 历史EmptyImage/SaveImage/hash/readback | 历史局部E3可记录 | 当前stale且非模型任务；cancel/WS未闭合 | 真实模型10次及取消恢复 |
| H3 | 文件校验/计划/官方能力说明 | E0/E1 | 没有本轮load/inference | 固定模型/hash/硬件实测 |
| Jury/Visual Quality | 24轴/rubrics/脚本 | E1，部分算法受控可E2 | VLM自评不是E4 | 独立专业评审与可复验记录 |
| E4独立接受 | 未发现当前全产品充分证据 | NOT_ESTABLISHED | 不能凭截图/CI赋值 | 独立评审人+Brief+输出+修改记录 |
| E5 release/repeatable | 历史release不可继承当前 | NOT_ESTABLISHED | fresh=false；运行包闭环未证明 | 安装/升级/复跑/回滚与接受后发布 |

## 证据封套建议

`capability_id, task_id, subject_sha, subject_files_hashes, environment_fingerprint, host/model/version, input_rights_ref, observed_at, test_run_at, artifact_path+sha256, scope, outcome, reviewer, rollback_result`。历史最高等级与当前有效资格分开显示。某版本E3可以因文件缺失/subject变化成为STALE，不擦除过去事实，也不冒充当前合格。

产品11轴（contract/backend/frontend/persistence/host/readback/quality/rights/preflight/delivery/evidence）用于审计完整性，ledger四轴（implementation/unit/host_live/delivery）用于当前状态；二者做映射，不另建一份可编辑完成账本。
