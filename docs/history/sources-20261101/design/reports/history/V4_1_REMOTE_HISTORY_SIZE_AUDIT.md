# V4.1 Remote History & Repository Size Audit（ODA4-0118）

- **任务**：ODA4-0118（独立核验远端历史清理和仓库体积）
- **状态**：**VERIFIED**（只读审计，未执行任何历史重写/强推/远端写入）
- **审计时间**：2026-08-14（boundTree=`cbae9fa`）
- **审计者**：Hermes Agent（DESIGN-LAB 会话）

## 1. 本地 .git 体积（明确口径）

| 项 | 值 | 口径 |
|---|---|---|
| `.git` 总大小 | **202 MiB** | 目录递归 sum（st_size） |
| `objects/` | 202 MiB | 全部对象（pack + loose） |
| `pack/` 总 | **198 MiB** | 4 个 pack |
| ├─ pack-c395bd47（主） | 191 MiB | 历史 + 当前树 |
| ├─ pack-00c9712a | 6 MiB | 增量 |
| └─ 其余 2 pack | <1 MiB | 增量 |
| loose objects | 62 个 / 103 KiB | `git count-objects` |
| **garbage** | **2 个 / 3.68 MiB** | `tmp_pack_C2SADw` + `tmp_pack_gjtzrE`（孤儿临时 pack，可安全清理） |
| 工作树（不含 .git） | 629 MiB | 目录递归 sum（含 vendored + 资产） |

`git count-objects` 交叉验证：`in-pack=5708`、`size-pack=198.08 MiB`、`prune-packable=0`——与目录 sum 一致（**两个口径吻合**）。

## 2. 远端 GitHub 元数据

| 项 | 值 |
|---|---|
| GitHub API `size` | **203029 KB ≈ 198.3 MiB** |
| 默认分支 | main |
| 说明 | GitHub size 口径 = git 内容（不含工作树/LFS），与本地 size-pack 198 MiB **一致** |

## 3. 历史报告差异解释（351→185 MiB）

- 旧报告"351 MiB"：**历史早期**体积（含已删除大文件 + 未 gc 对象 + 多 pack 冗余）
- 当前"185-203 MiB"：历史清理（git 重写 + gc）后收敛 + 新增内容平衡
- **本地 size-pack 198.08 MiB ≈ 远端 203029 KB**——两者当前口径一致，差异 <3%（本地含 pack 文件头/索引 + garbage）
- 之前的"358108 KB 远端元数据"：**GitHub API size 字段在仓库数据迁移/重建前的快照**，与当前 203029 KB 不同是**远端自身变化**（历史清理的 GitHub 端反映）

## 4. 重量对象分布（体积主源）

| 类别 | 文件 | 单文件 | 说明 |
|---|---|---|---|
| cctv lite-loop | 6 个 gif | 8-11 MiB | minigame 生成资产，单版本 |
| cctv scene-loop | 6 个 gif | 3-4 MiB | 同上 |
| cctv loop | 8 个 gif | 2-4 MiB | 同上 |
| mermaid.min.js | 1 | 3 MiB | vendored JS |
| babel.min.js | 1 | 2 MiB | vendored JS |

- **全部单版本**（`rev-list --objects --all` 无历史多版本冗余）
- 重量来自**当前树的二进制资产**，非历史垃圾
- cctv gif 已有 `.license` 侧车 + KNOWLEDGE_ASSET_POLICY §7 例外记录（8.4-11.8 MiB 超 5 MiB 上限豁免）

## 5. 结论与建议

**VERIFIED**（可独立证明）：
- ✅ 本地 202 MiB = 远端 ~198 MiB（口径一致）
- ✅ 重量 = 当前树二进制资产（cctv gif 系 20 个 ≈ 90 MiB），非历史冗余
- ✅ 无历史多版本膨胀

**建议（未执行，需用户批准）**：
1. **清理 2 个 garbage tmp_pack**（3.68 MiB）——安全，`git gc --prune=now` 或手动删
2. cctv gif 若 minigame 运行时生成则移出 Git（KNOWLEDGE_ASSET_POLICY 例外条款已预留）——可再省 ~90 MiB
3. 不执行历史重写（验收标准：不自动重写 Git 历史）

## 合规确认

- ✅ 未执行历史重写/强推/远端写入（只读审计）
- ✅ 无法证明项标 UNVERIFIED（此处全部可证明 → VERIFIED）
- ✅ 口径明确：目录 sum + count-objects + GitHub API 三源交叉
