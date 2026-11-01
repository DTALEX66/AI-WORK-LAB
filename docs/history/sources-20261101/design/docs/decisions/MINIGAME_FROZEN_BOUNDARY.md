# MINIGAME 云端状态与冻结边界（DL-GV-001/002/003）

## 云端事实（2026-08-10 回读，迁移后复核）

- `fixtures/domains/game-visual/` 已存在于云端 `main`（当前 HEAD `5c4fe55`，DESIGN-LAB R3 迁移后）。
- 它在本仓库中的角色是 **游戏视觉设计 fixture / runtime reference**
  （`fixtureRole: game-visual-design-reference`，任务包 H2），
  不是独立游戏产品仓库，也不是本仓库的产品主线。
- 现有内容：游戏运行样板（`src/`、`platform/`）、平台样板（wechat/douyin/android）、
  schema、模板、测试、构建脚本、精简视觉资产（CCTV GIF、面板纹理）。

## 允许的改动（白名单）

1. 安全修复（fail-closed、权限、秘密泄漏、供应链风险）。
2. 构建修复（保持既有 npm test / build / verify 通过）。
3. 资产完整性（已引用运行资产的可用性、尺寸、hash 校验）。
4. 既有测试的维护与修复（不改测试掩盖问题）。
5. 与 Open Design 设计能力相关的内容：HUD / UI / 图标 / 视觉规范 / 皮肤 /
   提示词 / 设计 fixture / runtime reference 的维护与增强。

## 禁止的改动（冻结边界）

- 平台工程（新平台接入、发行渠道工程）。
- 广告 / 变现 / IAA 逻辑扩张。
- 发行 / 运营 / 商业化流程。
- 完整产品逻辑扩张（新玩法系统、新游戏产品线、集合平台定位）。
- 将 minigame-runtime 重新变成活动产品仓库。

## 判定口径

- `fixtures/domains/game-visual/README.md` 顶部定位必须以 fixture/runtime reference 为准；
  任何"合集平台 / IAA 变现 / 独立产品"表述必须指向本文件或回归冻结口径。
- 涉及 minigame-runtime 的改动在 PR/review 时执行 MiniGame 边界检查
  （对应 `06_PROJECT_DRIFT_CONTROL.md` 的 `minigame_boundary_check`）。
- 违反白名单的改动 = `DRIFTED`，按漂移修复顺序处理。

## 相关记录

- `docs/MINIGAME_RUNTIME_CLEANUP.md`：吸收与精简记录。
- `docs/MIGRATION_STATUS.md`：迁移状态。
- `fixtures/domains/game-visual/AGENTS.md`：模块内执行规则。
