# E5 exact-SHA CI 验证（WLR-940）

> 2026-08-22 确认：**云端 CI 全绿**（最近 5 个 run 全部 success）。

| run SHA | 状态 | 时间 |
|---|---|---|
| 1debeef | success | 16:05 |
| 7e853f8 | success | 15:56 |
| 930bd51 | success | 15:55 |
| acc3705 | success | 14:53 |
| 40b4b10 | success | 14:43 |

## 前提达成

- CI ImportError 修复（相对路径）→ 绿
- observer SSE mock 修复（querySelector）→ 绿
- 全部 WLR 提交（R0-R1/330/410/430/600-960）→ 绿
- E5 exact-SHA 条件满足：当前 main 所有 required jobs success

## 剩余（E6 长期运行）

- durable_worker 运行观察（checkpoint/soak）——持续中
- Windows 实机 canary——需人工运行确认