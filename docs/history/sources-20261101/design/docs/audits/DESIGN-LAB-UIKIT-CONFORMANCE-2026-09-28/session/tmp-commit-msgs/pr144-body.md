# 9 独有分支处置台账（合并 0 · 删 4 · 冻结 5）

## 范围
对 9 个持有未上云独有提交的历史分支做 blob 级审计 + 处置。每条判定附
可复现命令与铁证（`git merge-base --is-ancestor` / `git merge-tree
--write-tree` / 逐文件 `git cat-file`），非自动汇总。

## 判定与执行

| 分支 | 判定 | 铁证 | 执行 |
|---|---|---|---|
| codex/a1-provider-spi | 删 | 旧路径 reconstruction，main #112 已迁 packages/，12 模块 0 未吸收 | 远端+本地已删，tip 存 superseded-tip/ |
| codex/a2-semantics | 删 | a1 超集，omniparser/paddleocr/… 全部 byte-identical/main 超集 | 远端+本地已删，tip 存 superseded-tip/ |
| docs/oda4-1101-gate | 删 | ODA4_1101 已迁 main reports/history/，blob 相同 | 远端+本地已删，tip 存 superseded-tip/ |
| feat/oda4-0118-1005-0807 | 删 | 纯重复（同 blob 3539f53a） | 远端+本地已删，tip 存 superseded-tip/ |
| feat/ucr-activation | 冻结 | UCR-R1 = 现权威 FINAL-AUTHORITY-R2 的结构前继血统 | 远端保留 |
| feat/comfyui-e3 | 冻结 | E3 证据 main 已迁 integrations/generators/ | 远端保留 |
| fix/registry-quarantine-sync | 冻结 | 隔离同步，main SOURCE_REGISTRY 已外化 | 远端保留 |
| fix/r4-h3-prod-e3 | 冻结 | H3 证据 delta 旧布局，main 已收 | 远端保留 |
| fix/design-lab-governance-closure-r4 | 冻结 | R4 基线快照 240 文件 / 137 冲突，历史证据 | 远端保留 |

## 回滚保护
4 个已删分支的 tip 各存一个 superseded-tip/* 标签（已推远端），可
git checkout -b <new> <tag> 随时恢复。

## 红线
外置库 4 权威索引 + design-tokens 未触碰；E 盘未访问；冻结的 5 分支
含 owner-gated 实操证据与权威血统前继，不作删除对象。

完整台账：docs/handoffs/DESIGN-LAB-BRANCH-DISPOSITION-2026-09-23.md

## 附：投影重绑（防漂移）
同批 rebind 10 个 current 投影（`generate_current_reports.py`），`--check`
归零 PASS。no-drift gate 会在 CI 校验。
