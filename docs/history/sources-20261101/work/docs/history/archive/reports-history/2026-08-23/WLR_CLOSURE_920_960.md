# WLR 收口批次（920-960）

> E5/E6 验证 + 一次性批准包。需要人工批准/环境（如实标注）。

| 任务 | 状态 | 需要 |
|---|---|---|
| WLR-920 canary（WL + OS 只读）| PENDING | E6 Windows 实机 + 用户批准 allowlist |
| WLR-930 长期运行/恢复 | PENDING | E6 soak（sleep/断网/worker crash）|
| WLR-940 exact-SHA CI | PENDING | CI 全绿后（observer SSE 3 测试待观察）+ 批准 |
| WLR-950 一次性批准包 | PENDING | 候选 SHA/diff/测试/审计汇总 + 逐项批准 |
| WLR-960 收口审查 | IN_PROGRESS | 全部 P0 闭环后执行 |

## 当前阻断

- CI observer 3 个 SSE 测试失败（heartbeat/SSE fence/malformed）待观察
- WLR-940 需 CI 全绿才能 exact-SHA 验证
- E5/E6 需要真实云端 CI + Windows 长期运行（需人工运行）