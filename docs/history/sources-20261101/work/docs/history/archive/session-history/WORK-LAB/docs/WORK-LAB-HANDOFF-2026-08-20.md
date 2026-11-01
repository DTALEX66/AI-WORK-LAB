# WORK-LAB 交接总结（2026-08-20 · 晚间增量）

> 覆盖 2026-08-19 22:00 至 08-20 凌晨：TP-20260819 联邦任务包执行、Observer 数据修复与守护、Tauri 集成、DSH 界面调研。

## 1. TP-20260819 三项目联邦任务包（拆解 + 执行）

- 任务包 TP-20260819-TRI-PROJECT-FEDERATION-V2 按项目拆成三份子集：
  - WORK-LAB：50-taskpacks/TP-20260819-TASKPACK-WORKLAB.md（WL 子集）
  - ArcheAxis：docs/cross-project/TP-20260819-TASKPACK-ARCHEAXIS.md（AA 子集，已 push 13c339a）
  - DESIGN-LAB：project-memory/cross-project/TP-20260819-TASKPACK-DESIGNLAB.md（DL 子集，已 push 70a857f）
- 分析报告：00-governance/TP_20260819_FEDERATION_ANALYSIS.md（基线漂移：WORK-LAB 979ec88→7a8c90b）
- 两仓库 remote 改 SSH（HTTPS 被墙）

## 2. WORK-LAB 联邦子集执行（commit 5611728）

| 任务 | 交付 |
|---|---|
| WL-P0-001 去硬编码 | software-registry.json（7 软件注册，client-neutral）|
| WL-P0-002 越界纠正 | domain-pack owner → external-design-lab + CapabilityPackageReference |
| WL-P0-003 记忆降级 | memory-record → runtime-context-record/v1（TTL 86400 + non-authoritative 强制）|
| WL-P0-004 Observer 只读 | test_observer_readonly.py（7 写路径拒绝）|
| WL-P0-005 配置控制面 | config_control_plane.py（六层 + 13 契约 + diff/apply/readback/drift/rollback）|
| WL-P1-001/002 | CURRENT_STATE 真实回读 / 体积报告（103 obj/278KB 健康）|
| 联邦契约 | 00-governance/federation/（registry + envelope schema + contract）|
| E2E | test_federation_e2e.py（配置闭环 + 失败路径，14 测试）|
| WL-OSS×8 | OPEN_SOURCE_ADOPTION_REPORT.md（评估态 + 3 轻量 PoC）|

## 3. 知识迁移暂缓（commit 86a53c7）

- 用户决定：OS 项目（ArcheAxis）未完善，知识迁移先不做，等指示
- FEDERATION_MIGRATION_REPORT.md 状态 DEFERRED，taskpack 待命

## 4. 全部未完成任务（commit 5363166）

- 交付报告补齐：CLOUD_BASELINE / EXACT_SHA / CONTRACT_CONFORMANCE / CONFIG_INVENTORY / COMPAT_MATRIX / OBSERVER_PROOF / FED_STATUS
- **Observer Tauri 集成**：frontendDist → ../frontend/dist，app.exe 重建（内嵌 React 控制塔）
- OSS 轻量 PoC（配置控制面回环 / 注册表无明文 / 策略引擎）PASS
- 后台服务恢复（8089/8090/9100）

## 5. Observer 数据修复 + 守护方案（重要）

- **根因**：观测栈（sidecar 61867 / Prometheus 9090 / Phoenix 6006）由 DSH run_in_background job 启动，DSH 会话切换/重启时被连带终止（exit 0xC000013A）→ 前端没数据
- **守护方案（三层）**：
  1. start-observability.ps1 --watch（30s 检查 7 端口，掉线自动拉起）
  2. WORKLAB-Observability.cmd 放入启动文件夹（登录自启，脱离 DSH）
  3. 一键手动启动
- 当前观测栈 9 端口全绿（61867/9090/3000/8089/8090/9100/3100/4317/6006）

## 6. DSH 界面 main 标签调研（进行中）

- 用户反馈 DSH 前端缺 MAIN/主线标签（类似 HERMES 聊天界面输入框上方 main 标签 + 发送后续消息）
- 已调研：hermes-webui（hermes-agent.nousresearch.com）聊天界面自定义 main 标签；DSH ui-conversation 会话头只显示会话标题
- 待用户确认后实现（DSH 前端增强 + 重建 web）

## 7. 运行态

- 观测栈守护运行中（Startup 自启）
- Observer：http://127.0.0.1:8090（8089 备用），数据真实（27.33M tokens）
- 桌面版 app.exe 已重建（内嵌 React 控制塔）
- DSH 双端一致（5363166 = 远程 main）

## 7b. DSH 维护增强（2026-08-20）

- dsh-maintain.js 新增 subst-drives 清理：启动时检查残留 SUBST 虚拟盘（如 X:），自动删除（幂等，不阻塞启动）
- 已验证：模拟 X: → --fix 自动移除；--check 显示 none

## 7c. Codex 变更记录（2026-08-20）

- 曾迁移 Git CLI（npm @openai/codex 0.148.0）+ wrapper 切换 → 发现桌面版任务仍走商店捆绑 runtime（GUI 自带执行核心，不通过 wrapper）→ 迁移对桌面版无意义 → **已恢复商店版 wrapper**（hermes/bin + workflow bin 原版）
- config.toml：保持直连（model_provider=custom → OpenAI 原生，provider 定义 cc-switch-official 已恢复供旧会话解析，不走 15721 代理）
- ~/.codex 共享：会话（190+/222 线程）+ config + auth 无丢失
- 配置兜底：codex_config_sync.py --fix（官方基线+用户配置 sync，商店版更新重置后一键恢复皮肤/沙盒/provider）

## 8. 待办

- DSH main 标签（等用户确认方向）
- 知识迁移（等用户指示，ArcheAxis API 已就绪）
- OSS 正式 PoC（需人工批准安装）