# WORK-LAB → Hermes 交接更新（2026-08-20）

> 增量覆盖 08-11 版。今日关键变更（Codex 链路 + Observer + 观测栈）。Hermes 接手时以本文件 + AGENTS.md + config-ownership.json 为准。

## 1. Codex 链路变更（重要）

- **CC Switch 已关闭/代理退役**：Codex 不再走 CC Switch 本地代理（15721）。
- **Codex config.toml 直连 OpenAI**：model_provider = custom（[model_providers.custom] name=OpenAI, requires_openai_auth=true, 无 base_url → 原生直连）。
- **cc-switch-official provider 定义保留**（重定向直连）——旧会话（引用该 provider）可继续解析。
- **wrapper 恢复商店版**：hermes\bin\codex.cmd + workflow bin\codex.cmd + bin\codex → 商店版（hash 校验）；曾试 Git CLI 后恢复（桌面版任务不走 wrapper，迁移无意义）。
- **皮肤/沙盒已恢复**：appearanceTheme=dark / sandbox=elevated / conversationDetailMode=STEPS_COMMANDS。
- **配置兜底**：codex_config_sync.py --fix（官方基线+用户配置 sync；商店版更新重置后一键恢复皮肤/沙盒/provider）。
- **Codex 会话/数据零丢失**（~/.codex 共享：190+ 会话/222 线程索引/config/auth）。

## 2. Observer 变更

- **运行时平台动态化**：任何 agent 跑任何项目如实显示（活跃执行 agent 优先/最近执行兜底/未知 agent 显示本名；不锁死静态配置）。
- **观测栈守护**：start-observability.ps1 --watch（30s 检查 7 端口掉线自动拉起）+ Startup 自启（脱离 DSH 会话）。
- 9 端口全绿：61867/9090/3000/8089/8090/9100/3100/4317/6006。

## 3. 联邦任务包（TP-20260819）

- WORK-LAB 子集全部执行完成（WL-P0×5/P1×2/OSS/E2E/交付报告）。
- 知识迁移 DEFERRED（用户指示：OS 未完善等指示）。
- 三仓库双端一致：WORK-LAB eafccad 后 7730738 / AA 224c9ea / DL a6fdc5e。

## 4. Hermes 自身

- Hermes overlay 无变更（config-ownership: hermes=USER_OVERLAY/MANAGE/preserve_unknown 不变）。
- 本文件仅供 Hermes 知晓 WORK-LAB 侧状态，无需动作。

## 5. 待办

- 知识迁移（等用户指示）。
- DSH main 标签（等用户确认方向）。
- 商店版 Codex 更新后跑 codex_config_sync.py --fix 恢复配置。