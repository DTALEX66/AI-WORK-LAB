# Git 历史瘦身审计（History Rewrite Cleanup Audit）

- 日期：2026-08-07
- 授权：用户明确授权历史重写 + force-push 清理云端/本地冗余历史
- 结果：`.git` 351M → **185M**（回收 ~166M）

## 清理内容

移除 9 个**历史中已删除、当前 HEAD 零引用**的大 GIF（均为旧资产版本，已被 HEAD 的 `lite-loop` / `real.png` 压缩/静态版完全取代）：

| 历史资产 | 大小 | 取代版本（HEAD 保留） |
|---|---|---|
| cctv-factory-native-loop.gif | 24M | cctv-factory-native-lite-loop.gif (10M) |
| cctv-hospital-ward-native-loop.gif | 23M | hospital-ward-native-lite-loop.gif (10M) |
| cctv-basement-lift-door-open-loop.gif | 22M | basement-lift-door-open-lite-loop.gif (11M) |
| cctv-security-room-native-loop.gif | 21M | security-room-native-lite-loop.gif (9M) |
| cctv-basement-lift-native-loop.gif | 20M | basement-lift-native-lite-loop.gif |
| cctv-hotel-lobby-native-loop.gif | 19M | hotel-lobby-native-lite-loop.gif (8M) |
| cctv-subway-platform-native-loop.gif | 19M | subway-platform-native-lite-loop.gif (8M) |
| cctv-basement-lift-door-open-real-loop.gif | 7M | real.png 静态版 |
| cctv-basement-lift-native-lite-loop.gif | 8M | door-open-lite-loop.gif |

## 吸收说明
- 上述历史资产**内容已完整被 HEAD 的 lite/static 版本代表**（同一资产的压缩/静态变体），功能内容未丢失，**无需复制冗余二进制**。
- 保留的 `lite-loop.gif`（6 个，8-11M）为当前游戏实际使用的合法资产。

## 操作记录
1. `git filter-repo --invert-paths --paths-from-file ...` 重写全部 50 提交，移除 9 路径。
2. 新历史 HEAD `0401065`（内容=旧 main 全部 + 21 个 V4 提交）。
3. 云端：`main` 强制提升到 `0401065`；删除无独有内容的 `migration/work-lab-design-extraction-20260807`。
4. `migration/work-lab-minigame-cutover-20260807` 也更新到 `0401065`。
5. 本地：更新 main 指针、`reflog expire`、`git gc --prune=now` 清除旧对象。

## 最终状态
- 云端分支：`main` = `migration/work-lab-minigame-cutover-20260807` = `0401065`（干净历史）
- 本地 main = 云端 main = `0401065`（对齐）
- `.git` = 185M，工作树 clean
- 9 个历史大 blob 已从所有历史移除
- 所有 50 个提交内容完整保留（V4 工作无损）

## 边界遵守
- 用户明确授权历史重写 + force-push（覆盖默认 exact-SHA 纪律，属授权例外）
- 保留所有合法当前资产（lite/real/overlay）
- 全程无 E:\、无凭据、无破坏性内容丢失
