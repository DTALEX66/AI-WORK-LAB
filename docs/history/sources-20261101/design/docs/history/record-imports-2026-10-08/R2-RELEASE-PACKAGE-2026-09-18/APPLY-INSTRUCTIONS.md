# CLOUD APPLY INSTRUCTIONS — R2

当前 ChatGPT GitHub integration 对 Contents 写入返回 `403 Resource not accessible by integration`，所以本包**尚未从本会话上传**。

最新核实 target：`main@0e9f687ca306226f984f9ac49d222c0d8ff8a1e5`；main protected；PR #116/#120 已 merged。

新增：AUTHORITY.md、authority-index、HISTORY-FREEZE-RULES、最终 TaskPack。  
更新：AGENTS.md、UCR handoff 首屏历史 banner、LANGUAGE-POLICY 一个 Ruff stale wording。

因为 main protected：
1. 从最新 main 建短生命周期 authority branch
2. 应用本包
3. 跑 Authority consistency verifier
4. PR -> main
5. Canonical Verify
6. Authority gate 稳定后加入 required checks
7. merge 后从 main 重新 readback AUTHORITY/index/AGENTS/TaskPack
8. 此后 GPT 云端审计强制从 AUTHORITY 开始

禁止再把 PR #116 当 pending；禁止把 PR #120 handoff 当顶层 authority。
