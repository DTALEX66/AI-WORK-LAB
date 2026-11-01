# 全局工作流规则与技能优化记录

日期：2026-10-05，Asia/Shanghai。本文保存本次变更、证据、恢复入口和未完成事项，属于非规范历史记录。下次部署必须读取当前 Authority、机器所有权合同和现有部署规范；不能把本文的数量、版本、路径或成功状态当作未来事实。

## 本次授权与范围

用户先要求检查 Workflow Assistance 与本机 Codex 技能是否仍有价值，随后授权执行合并、迁移和清理，进一步授权优化全局 AGENTS 与个性化规则，并要求保留中立、适配新 Agent 与新模型的可复用记录。没有授权 commit、push、merge，也没有部署 Hermes、DSH 或其他客户端。

工作树起点：branch `task-decomposition/atlas-gap-archive-20261001`，HEAD `2bc916895472a6d7542050ad914988cd5c1985cd`。远端 main 通过 Windows native SSH 只读查询为 `cd4daa83e107afab8438c0e85f63a10e75314d5a`；对应本地 tree 为 `a36e97ecbcb951e53a4c877e14244aa626d70fc8`。这些是本次查询快照，不是永久基线。

用户已有 `apps/observer/frontend/src/App.tsx`、`Sidebar.tsx` 和 `docs/future/` 修改，未被本次覆盖。

## 实际变更

Codex 的 14 个 Workflow Assistance 全局入口收敛到 5 个：github-delivery、project-data-boundary、safe-project-execution、update-safety、windows-development。数量仅表示本次源与本机结果，不限制未来增减。

通用执行/证据/单写者提示合并；泛化 debugging/testing 和默认 hardening 入口退出加载；Windows 条件细节迁入 references；Observer、Open Design/OpenHuman 项目边界迁至 `docs/current/workflow-assistance/skill-references/`。原文保存在项目忽略的备份中，未丢弃。

Superpowers `superpowers@superpowers-dev` 通过 Codex 原生插件管理工具卸载，工具回执为 `uninstalled`；没有删除整个插件缓存目录或更改其他插件。

全局 AGENTS 使用单一精简个性化规则文件，来源 `integrations/executors/codex/personal-guidance.md`，部署至 `C:/Users/ALEX/.codex/AGENTS.md`。大小从 16,805 B 到 5,253 B。保留授权、安全、隐私、现有修改保护、证据及完成要求；没有改模型/provider/auth/sandbox 配置。

既有同步器增加 `--skills-only`：保留 config、AGENTS 和 rules，不重置它们的旧 ownership hashes；仍验证每个技能的既有归属和哈希，删除退役根后才更新技能归属。个性化文件替换使用同一同步器的显式 `plan-personal-guidance`/`apply-personal-guidance`，绑定当前目标/源摘要，先备份，再原子写入并回读。两种模式不能被当作全量 overlay 验证。

库存生成器增加核心技能源与项目 canonical projection source，避免把生成的 .agents 文件重复计数；本次源清单为 19 个，不是所有软件的 live 总数。

中立语义源 `config/global-agent-policy.yaml` 取消强制预扫描和先加载技能；保持 on-demand 与 guidance-not-authorization。Codex golden/loss report 由已有 renderer 生成。没有建立第二个规则管理或同步系统。

全量检查发现 governance 子进程未使用已有项目 runtime 环境；修正 `_run_governance_batch` 的环境传递，并用外部 TMP 输入的负向控制验证子进程仍使用项目忽略目录。这避免未来门禁默认把测试临时产物落到系统临时目录；不声称覆盖所有第三方软件自身的写入。

## 验证边界

- Codex 技能部署：APPLIED；native `verify --skills-only` PASS、issues 空、installed_skills=5；再次 plan 写入数为 0。
- 全局 AGENTS：已发布并回读，源/live SHA-256 同为 `7c831ddf0127d5815601b4b4c153137e63eafdf2cf972dffc9932b38ca650651`；再次 personal-guidance plan 写入数为 0。
- 同步、合同、清单定向测试：32 passed，含 Windows junction 路径安全用例。policy projection/quality gate 定向测试：31 passed，含新 runtime 环境负向控制。最终合并定向检查为 63 passed / 0 skipped；机器回执为 `.project-local/artifacts/skill-convergence-20261005/completion-receipt.json`，备份清单 35 个文件的 SHA-256 全部回读一致。
- authority-reference、compile、security、skill-provenance、skill-MCP consistency 定向检查通过；provenance/MCP 两项覆盖原有核心 13 个，不冒充新 Codex 5 个的 live 证明。
- 全量 canonical verify 真实执行至 governance batch，1,903 tests / 22 failures / 12 errors / 9 skipped，exit 1。Windows 深层临时路径的仓库复制错误及 Git 沙箱临时仓库识别失败有日志；全部失败尚未逐项归因。runtime 环境修正后未把此前失败改写为 PASS。日志 `.project-local/runs/quality-gate-governance-fail.log`。
- 尚未有新会话技能发现与任务行为对照、性能基准、exact-SHA CI、commit/push/merge。没有声明模型升级已消除错误，也没有声明其他客户端已部署。

## 恢复与后续部署

备份位于 `.project-local/artifacts/skill-convergence-20261005/`：`global-AGENTS-before.md`、`backup/live-skills/`、`backup/repository-skills/`、`backup/ownership-state.json`、`backup-manifest.json`。备份属于本机恢复资料，不能假设其他机器存在，也不能上传或混入安装包。部署前需为目标机器重新备份。

全局规则恢复：以 `global-AGENTS-before.md` 为 personal source、新的独立 backup 路径生成计划，核对当前摘要并在授权范围内 apply；不要用 restore/checkout 批量覆盖未知内容。

技能恢复：构造项目内 recovery source root，skills 来自完整 live-skills 备份，保留同步器所需源布局；只用 skills-only plan/apply，验证当前归属、完整树摘要和 idempotency。不要直接抹除用户改过的技能或手填 ownership state。插件恢复使用产品原生管理入口，不能假设旧版本仍可安装。

下次部署入口是项目当前的 `official-plus-user-configuration-standard-2026-08-11.md` 与机器合同，本文只提供事件证据。持续有效的目标是官方基线、用户原生选择、最小声明 overlay、按需专项能力和可验证回退；不是这次恰好保留的五个名称。

官方依据：[OpenAI 的技能与提示精简建议](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)。该来源支持缩短触发描述、按需展开和减少过度流程，不证明本机性能改善。
