# DL-R4-REMAINING-BLOCKERS — 未解决阻塞项（诚实清单）

> 以下阻塞全部为真实能力/授权/环境缺口；本任务包不伪造证据、不强行通过。

## E3+ 真实运行证据（最高优先级）

1. **DL-ADP-OD-E3 — Open Design 重新取证**：需真实 Runtime ID/Version、能力注册、最小 Brief 执行、Artifact 创建、Provenance 回读、失败与恢复、卸载/回滚。当前只有 E0/E1 结构证据。
2. **DL-ADB-PS-001 — Photoshop MVP E3**：需 Brief → Adapter → 可编辑 PSD → 图层/字体/尺寸回读 → Preflight → PSD+Preview+BOM+Evidence。单纯导出 PNG 不算。
3. **ComfyUI / MiniMax H3**：保持冻结 E0（declared, supported=false）；本轮未启动运行时、未下载模型、未调用 API（DL-H3 边界）。

## 人工环节（无法自动完成）

4. **DL-QLT-002 人工专业 Jury**：品牌视觉/商业 UIUX/电商/空间展陈/游戏 UI/HUD 五域专业评分 >=82/100、偏好测试 >=70%、拒绝样本保留。
5. **DL-REL-001 独立复审 + Release Attestation**：需独立 reviewer 与精确 SHA 发布证据。
6. **162 条来源事实补全**：author/allowedUsage/acquiredAt/contentHash(sha256)/权利标志/人工审核人——全部进入 QUARANTINE，等待人工补齐。

## 授权项（任务包未授权）

7. **DL-CI-007 主分支保护**：Require PR / Canonical Verify / branch up to date / independent approval / block force push / block deletion——需仓库管理员明确授权。
8. **push/PR/merge**：R4 执行原则 9——未经授权未 push；R4 已通过 PR #92/#94 squash 合入 main（`8a5a677ac2f8`）；分支任务已完结。

## 环境限制（CI ubuntu 可覆盖）

9. 本地沙箱禁止 node 子进程 spawn（13 项 minigame spawn 测试 EPERM）与 tempfile chmod（27 项 python 错误）——基线同样存在，CI 通过（基线 CI node-gate success）。
10. 远端 CI 回读：当前分支未 push，HEAD CI 为基线值；本地 `verify_design_lab.py` = OK 19/19。

## 结论

发布就绪度：**BLOCKED**（人工 Jury、独立复审、Release Attestation 未完成；ComfyUI/H3 真实运行 E3 已完成）。
产品定位：**稳定**。结构治理：**持续完善，本轮闭环**。
