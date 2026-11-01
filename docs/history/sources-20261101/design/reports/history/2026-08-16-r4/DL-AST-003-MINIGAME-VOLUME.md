# DL-AST-003 — MiniGame 体积治理审计（R4）

> 边界：`fixtures/domains/game-visual/` = Game Visual Design Fixture / Runtime Reference。保持同仓与冻结边界，
> 本轮只审计体积，不改变边界、不破坏视觉回归测试。

## 审计结果（2026-08-16）

| 项 | 结果 |
|---|---|
| minigame-runtime tracked 文件 | 214 |
| minigame-runtime 总体积 | 3.86 MiB |
| >256 KiB 文件 | 0 |
| 大 GIF | 0（早期 CCTV GIF 已于 1382e2c 删除） |
| 可再生成 CCTV 资产 | 3 个 cctv PNG 副本位于 `design-lab/exports/minigame-mobile-controls/assets/`（1.4–1.7 MiB，见 DL-AST-002，分类 REGENERATE） |
| 重复输出 / 构建产物 | 0（无 dist/build/bundle 跟踪） |
| Android/WebView 重复包 | 无 APK/AAB/JAR；`game.js` 在 android-minigame 与 android-webview 各有副本，由 `scripts/check-android-drift.mjs` 做一致性漂移检查（合法模式，保留） |
| 历史截图 | 10 个 `docs/screenshots/*.png`（<0.26 MiB 各，结构化 sidecar v1 已就绪，KEEP） |
| 仓库 pack 大小 | 198.4 MiB（< 220 MiB 预警线 < 256 MiB 硬预算） |

## 目标达成

- ✅ 仓库继续低于 256 MiB（当前 pack 198.4 MiB）
- ✅ 220 MiB 预警线已写入 `verify_asset_governance.py`（WARN 输出，不失败）
- ✅ 新增二进制默认拒绝：`verify_asset_governance.py`（DL-AST-001）要求结构化 sidecar v1
  （sha256 实测 + 作者 + 许可 + 权利标志 + SourceRecord 或人工例外），缺失即 FAIL

## 后续建议（不自动执行）

- 3 个 cctv 副本为可再生成资产：优先外置共用库（`D:/All projects/Design assets`）或由 minigame
  运行时再生成；如需删除须用户明确确认（REMOVE_PENDING_APPROVAL，R4 执行原则 9）。
