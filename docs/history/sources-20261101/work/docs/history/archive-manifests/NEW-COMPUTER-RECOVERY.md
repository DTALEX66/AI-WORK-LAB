# 新电脑恢复指南

## 云端真源

```bash
git clone git@github.com:DTALEX66/WORK-LAB.git WORK-LAB
cd WORK-LAB
git checkout main
git rev-parse HEAD
```

当前 `main` 包含三个模块的保留历史、实体工作树、根治理、契约、CI 和交接文档：

- `10-workflow/workflow-assistance`
- `20-design/open-design`
- `30-products/minigame`

MINIGAME 的 `main` 使用此前冻结的远端版本 `d4bf0b3d…`。旧电脑本地提交 `ddd1ee18…` 另存为云端迁移分支和 tag：

```bash
git fetch origin migration/minigame-local-head
git show origin/migration/minigame-local-head
git fetch origin tag minigame/local-head-20260805T091816Z
```

## 下载迁移执行包

从 GitHub Release `migration-handoff-20260805T091816Z-v4` 下载：

```bash
gh release download migration-handoff-20260805T091816Z-v4 \
  --repo DTALEX66/WORK-LAB \
  --pattern 'work-lab-migration-handoff-20260805T091816Z-v4.zip'
```

解压后保留以下内容：

- `task-pack/`：完整 WORK-LAB v6.0 任务包；
- `evidence/`：DISC/MIG/GOV 交接证据；
- `working-state/`：已保留的 Workflow/Open Design 本地变化；
- `recovery/`：bundle 清单、SHA-256 和恢复说明。

原始 Git bundle 没有放入公开 Release；GitHub `WORK-LAB` 已包含三个选定源 tip 的完整可达历史，MINIGAME 本地 committed tip 也已通过独立 migration branch/tag 上传。原始 bundles 仍在旧机器 archive 作为额外离线恢复点。

## 新机验证

```bash
git status --short --branch
git fsck --full
python scripts/security/check_paths.py .
python tests/ci/test_governance_gate.py
python tests/contracts/test_contract_shapes.py
python scripts/ci/aggregate_gate.py <<'JSON'
{"jobs":{"workflow":"success","open-design":"success","minigame":"success","integration":"success"}}
JSON
```

## 边界

不要把旧仓 dirty patch 自动应用到活动根；先阅读 `working-state/` manifest，再按任务卡逐文件审查。不要删除原机器 archive。旧电脑的 `D:\All projects\WORK-LAB` 尚未被自动切换或清理。
