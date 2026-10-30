# DL-CI-004 — Release exact-SHA gate

- 任务：DL-CI-004 Release exact-SHA gate
- 状态：🔄 配置就绪（E3/验收前置未完成前不启用）

## 门禁定义

Release 必须同时满足：
1. CI run、artifact、SHA 回读一致（exact-SHA）
2. 人工审批（DL-REL-001 验收通过）
3. clean worktree
4. boundTreeSha + exact command + environment + readback 证据齐备
5. `capability-evidence-index.json` 中每个 capability 的 `actualEvidence` 不低于其 `minimumRequiredEvidence`
6. 12 张 Evidence Cards 全部完成人工 calibration，并处于 authoritative accepted 状态

## 前置（未满足 → 保持未启用）

- DL-REL-001 人工可视验收（UI/UX、平面、3D、游戏视觉各 ≥1 有效案例）
- E3 取证（Adobe PS / ComfyUI / MiniMax H3，用户下载安装运行时后）
- ComfyUI 与 MiniMax H3 当前**由用户下载安装，本任务暂停推进**

## 启用流程

1. 全部 E3 取证完成 + DL-REL-001 通过
2. capability evidence floors 和 Evidence Cards 全部满足
3. `verify_release_evidence.py` 全绿
4. 人工批准发布 → 标记启用

## CI 入口

正式发布尝试通过 `.github/workflows/release-gate.yml` 的
`workflow_dispatch` 触发。该 workflow 先运行 Canonical verifier，再运行
不带 `--skip-dirty` 的 release gate，最后要求提交并校验
`design-lab/config/release-evidence.json`；任一前置不满足即失败。
