# 第三方指令隔离（现状：仓库外隔离）

> 更新：2026-09-04（DL-DIR-MIG-R1 规范化终版）
> 历史：DLR-020（2026-08-26）曾记录"仓库内 inert blob 隔离"；DL-DIR-MIG-R1（2026-09-01~03）将第三方内容迁至 `research/candidates/`；2026-09-04 规范化后**第三方完整源码已退出 Git**，隔离由"仓库内排除"升级为"仓库外物理隔离"。

## 隔离状态（2026-09-04 起）

| 层 | 内容 | 位置 | 治理 |
|---|---|---|---|
| **Git 内（无第三方源码）** | 自有代码/文档/配置 + `research/candidates/README.md` 索引 | 仓库 tracked | license/sbom/identity gate 全覆盖 |
| **ignored cache（第三方源码）** | 37 个候选仓完整源码（含 LICENSE/SOURCE.md/AGENTS.md/CLAUDE.md/SKILL.md） | `.project-local/cache/vendor/<id>`（gitignored） | `vendor/sources.lock.json` 登记 43 项（disposition=CONDITIONAL_POC / LOCK_REFERENCE） |
| **决策登记** | 逐仓来源/许可/裁决 | `design-lab/research/global-absorption/QUARANTINE_REGISTRY.json`（162 源） | license review 已逐项核实 |

## 为什么仓库内不再保存第三方源码

1. **不进入根指令**：根 `AGENTS.md` 不引用第三方文件
2. **不进入 prompt / tool discovery**：第三方 AGENTS/CLAUDE/SKILL 不在工作树，工具无法递归发现
3. **不进入能力计数**：`capability-index` / `product-manifest` 只登记 DESIGN 自有能力（manifest v3 校验 321 项路径全绿）
4. **license 合规简化**：Git 内所有文件接受统一 SPDX 头/侧车检查（`LICENSE_COVERAGE=OK`）；第三方各自许可随 cache 保存、不混入项目许可面
5. **可追溯**：每仓有来源 URL + 原始 SHA（SOURCE.md）+ 许可核实（QUARANTINE_REGISTRY），需要时从 cache 取用

## 历史遗留参考（DLR-020 记录，2026-08-26）

下列文件曾是仓库内 inert blobs，2026-09-04 已随候选仓退出 Git（保真副本在 `.project-local/cache/vendor/`）：

| 原路径（已删除） | 来源 | 当时状态 |
|---|---|---|
| `design-lab/intelligence/ultimate-uiux/AGENTS.md` | Design Pro (第三方设计技能) | `INERT_BLOB` |
| `design-lab/intelligence/claude-design-skill/AGENTS.md` | jiji262 | `QUARANTINE` |
| `design-lab/intelligence/design-system-prompt/codex/AGENTS.md` | 第三方 Codex 技能 | `INERT_BLOB` |
| `design-lab/intelligence/motion-forensics/CLAUDE.md` | 第三方运动分析 | `INERT_BLOB` |
| `design-lab/knowledge/visual-quality/affiliate-skills/CLAUDE.md` | Affitor | `QUARANTINE` |
| `design-lab/knowledge/visual-quality/claude2figma/CLAUDE.md.template` | 第三方 | `INERT_BLOB` |
| `design-lab/knowledge/visual-quality/game-ui-mobile/CLAUDE.md` | 第三方 | `INERT_BLOB` |

## 未来资格化（DL-DIR-030）

- 候选仓验证通过 → ABSORB_MINIMAL 提取进 `packages/capabilities/<id>`（许可 + 来源 + 测试随行），**仍不整仓复制**
- 参考用 → LOCK_REFERENCE（`vendor/sources.lock.json` 已有记录）
- 不合格 → REJECT_REMOVE（decision ledger）
- 任何情况下第三方整仓不回 Git

## 创建时间

- 创建者：DLR-020 任务（2026-08-26，基线 SHA `38d322affaec163e7c7ca0e3610042285aab1f0f`）
- 更新：DL-DIR-MIG-R1 规范化（2026-09-04）

## 退役登记：`vendor/sources.lock.json` 里指向已删除目录的 6 条 LOCK_REFERENCE

补记于 2026-10-08（任务：把"悬空引用"改成"显式缺失声明"）。此前 `docs/THIRD_PARTY_ISOLATION.md`
只按**文件**列出被删的第三方 AGENTS/CLAUDE 说明件，`amend_source_lock_presence.py` 的
`pathNamedInIsolationRecord` 因此只对两条目录为真——那两条是**子串巧合命中**，不是来源退役声明，
另外 4 条整目录引用则完全没有依据。下表逐条由 `git log --diff-filter=D` 与被删前的
`git rev-parse <commit>^:<path>` 测得，不抄不改：删除提交、被删 tree 的 SHA（这就是这批字节的
内容身份，可复核、可再取）、锁记文件数、以及各树内 `SOURCE.md` 自述的上游与许可。

`revision` 列诚实标注"未记修订"：这些是 2026-08-13/14 vendoring 时只记了分支的记录，
补不出 commit 就写补不出，不用今天的 HEAD 冒充当时的字节。三条 `ABSORB_MINIMAL` 的修订状态
由 `vendor/sources.revisions.json` 单独登记，LOCK_REFERENCE 不混进去。

| lock id | 原路径（整目录，已删除） | 锁记文件数 | 删除提交 | 被删 tree SHA（内容身份） | 上游（SOURCE.md 自述） | 许可（SOURCE.md 自述） | 修订 |
|---|---|---|---|---|---|---|---|
| `anydesign` | `design-lab/intelligence/anydesign` | 19 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `5bd9befc04926072f1bd73538940591c09044516` | https://github.com/uxKero/anydesign | `MIT` | 未记修订 |
| `claude-design-skill` | `design-lab/intelligence/claude-design-skill` | 24 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `599981a99da57f718b647a6add6eebcd54635b82` | https://github.com/jiji262/claude-design-skill | `MIT` | 未记修订 |
| `design-system-prompt` | `design-lab/intelligence/design-system-prompt` | 34 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `4b745f22417812b18149d18962289f238f351f38` | https://github.com/Trystan-SA/claude-design-system-prompt | `MIT` | 未记修订 |
| `motion-engine` | `design-lab/intelligence/motion-engine` | 28 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `fe0e31cd55b12b4c9e62ed0f49c5c82e2259fed4` | https://github.com/OpaceDigitalAgency/skills | `MIT` | 未记 commit（仅 `main`） |
| `shipit-ui` | `design-lab/intelligence/shipit-ui` | 76 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `d232d4f85df01d152aeb102ea70f773a8d88bbfc` | https://github.com/shipiit/shipit-ui-design | `MIT` | 未记修订 |
| `web-content-designer` | `design-lab/intelligence/web-content-designer` | 11 | `c9cde8a54e22f84f988537e212b992de3bd7cfcd`（2026-09-04） | `0c4de6fe7925ce7e80081e987e431ec2cba24455` | https://github.com/lowtidebuild/web-content-designer | `Apache-2.0` | 未记修订 |

处置：6 条记录**保留**为历史引用（删掉记录会同时删掉"它曾存在"的唯一痕迹），但从此每条都
带删除提交与内容身份，读者可独立复算。`web-content-designer` 的许可另见
`vendor/sources.lock.json` 的 `licenseCorrection`：锁与 `rights-registry.json` 两处原写 MIT，
而 SOURCE.md、`QUARANTINE_REGISTRY`（已 reviewed）、SBOM 三处一致为 Apache-2.0，故对齐到有证据的值。

## 仓内登记补全：37 个 cache-only 第三方根的逐文件清单（补记于 2026-10-09）

上面的隔离表第 2 层声明：37 个候选仓的完整字节只存在 `.project-local/cache/vendor/<id>`。
`vendor/sources.lock.json` 对每个根只记一条 `contentDigest`。那回答"是不是我核过的那批字节"，
但不回答"里面有什么"——而一份没人能列出的摘要，别人无法复核、上游变动时无法比对、也承载不了
权利裁决。本回合把后半句补上：每个 cache-only 根一份 `vendor/manifests/<id>.json`，逐文件
`path`/`bytes`/`sha256`，加聚合 `contentDigest`、`licenseFilesPresent`（树里实测到的许可证文件名）、
以及留空的 `reviewedBy`/`reviewedAt`/`rightsDecision`。

行级配方与锁完全一致（sha256 覆盖按 `relpath` 排序的 `relpath\0<sha256(bytes)>\0`），因此
`--check` 在干净克隆里能只靠 manifest 自己的行重算出聚合摘要，再与 manifest 声称的值、锁记录的值
双向对齐——第三方字节不需要在场，也不允许进仓。进 Git 的只有路径、大小、哈希和许可证文件名，
第 14 段列的隔离理由 1–5 条照旧成立。实测：37 份清单共 360,201 字节（最大 `baoyu-design.json`
42,129，最小 `vq-design-md-skill.json` 1,475），覆盖 1,914 个文件 / 35,104,251 字节（33.48 MiB）
的第三方树，登记体积约为其 1.03%。

门与测：`design-lab/scripts/verify_vendor_manifests.py`。默认形态（也是聚合调用的形态）只读仓内
状态；`--write` 需要缓存，且只在"walk 结果、`digest_dir`、锁记 `contentDigest`、锁记文件数"四者
一致时落盘；缓存动过就报 DRIFT 并保持原清单字节不变，绝不把新字节登记在旧身份下。已接进
`verify_design_lab.py` 的 SCRIPTS（70 → 71），CI 无需缓存即可执行。当前实测输出
`VERIFY_VENDOR_MANIFESTS=OK roots=37 rows=1914 awaiting_owner_review=37 license_files_absent=0 findings=0`。
`design-lab/tests/test_vendor_manifests.py` 34 条全绿，逐条给每个 finding 埋一份假记录（缺登记、空清单、
改行哈希、锁与清单摘要分叉、文件数分叉、字节总数分叉、重复路径、截断哈希、负字节、孤儿清单、
异 schema、`id` 错位、坏 JSON），并钉住两件最容易悄悄失效的事：行配方必须逐字节复现 `digest_dir`
（否则 `--check` 只证明了自己），重生成不得代填权利裁决。

更正（带日期，实测于 `53802797^` 与 `53802797` 两个 blob）：上面写"SCRIPTS（70 → 71）"是错的，
`verify_design_lab.py` 的 `SCRIPTS` 列表是 **69 → 70**；70 → 71 只是聚合门打印的 `total=`
（`SCRIPTS` 条数 + `EXTRA_CHECKS` 1 条）。数字由 `ast` 直接数两个版本的列表元素得到，不是回忆。

与 `verify_source_registry.py` 的分工要说清，免得两道门互相冒充：那条门只审 `ABSENT_FROM_GIT`
（悬空引用必须带删除提交与退役声明），本门只审 `LOCAL_CACHE_ONLY`。两句合起来才是"46 条 vendor
引用全部有据"；单看任何一句都会高估覆盖面。

待 owner（不得代签）：37 条 `reviewedBy` 全为空，门按 NOTICE 计数并报 `awaiting_owner_review=37`，
不判红——留空是"agent 拒绝替 owner 做权利裁决"的正确形态，不是缺陷。实测 37 个根都含
LICENSE/COPYING/NOTICE 文件（`license_files_absent=0`），所以权利复核有树内文件名可查，不只靠锁的一面之词。

更正（带日期，原文不改）：本档第 11 行写"`vendor/sources.lock.json` 登记 43 项"。本回合直接对该文件
计数为 **46 条**：`LOCAL_CACHE_ONLY` 37 / `ABSENT_FROM_GIT` 6 / `IN_REPO` 3，与 `disposition` 的
`CONDITIONAL_POC` 37 / `LOCK_REFERENCE` 6 / `ABSORB_MINIMAL` 3 一一对应。43 是 2026-09-04 的数字，
其后补进了 3 条 `ABSORB_MINIMAL` 与记录修正；不改写原行是为了让读者看见这条声明曾经过期。

## 聚合项 `tool-control` 的逐源归属（补记于 2026-10-09）

`vendor/sources.lock.json` 的 tool-control 行在 `canonicalUrlAbsentReason.why` 里写的理由是：
"缓存树里没有 SOURCE.md，只有指向文档/捐赠/配色站的文内链接"。这条理由的**前提没测过**：
该树自己带两份来源表——根 `README.md`（2026-08-19）第二、三节与 `scripts/README.md`——
逐子树列了 owner/repo、许可与脚本数。锁与 taxonomy 各说这批来自"四个上游"，
而这两份表和字节本身给出**七个第三方来源**：

| 声明的来源（照表转录） | 树内位置 | 实测文件 | 实测字节 | 树内有 LICENSE？ |
|---|---|---|---|---|
| creold/illustrator-scripts（MIT，README 记 99） | `scripts/illustrator` | 100 | 3,172,528 | 有 |
| creold/photoshop-scripts（MIT，README 记 11） | `scripts/photoshop` | 12 | 87,594 | 有 |
| StefanTraistaru/batch-export（MIT，README 记 2） | `scripts/inkscape` | 2 | 23,497 | 无 |
| Comfy-Org workflow_templates（MIT，README 记 "1+"） | `scripts/comfyui` | 1 | 28,274 | 无 |
| style-dictionary examples（Apache-2.0，README 记 1） | `scripts/style-dictionary` | 1 | 4,178 | 无 |
| github/awesome-copilot 的 adobe-illustrator-scripting SKILL（MIT） | `adobe-illustrator-scripting-SKILL.md` | 1 | 35,264 | 无 |
| abdul-karim-mia/photoshop-automator（README 自写"未核实…许可未核实不吸收"） | `photoshop-automator-SKILL.reference.md` | 1 | 2,620 | 无 |
| DESIGN-LAB 自述（本仓写入的两份来源表，非第三方内容） | `README.md`、`scripts/README.md` | 2 | 2,926 | — |

八组实测文件数与字节数相加 = 120 / 3,356,881，与该清单自己的 `fileCount` / `totalBytes`
相等；README 声称的"99 脚本 / 11 脚本"与子树里的 100 / 12 个文件也对得上（多出的正是各
LICENSE 文件）。也就是说这不是新判断，是把已经写在货里的单据搬到仓内。

门：`design-lab/scripts/verify_vendor_manifests.py` 现在校验 `origins` 声明——每一条第三方
字节必须恰好属于一个已声明来源（`ORIGINS-UNASSIGNED-ROW`）、每个已声明来源必须真有字节
（`ORIGINS-EMPTY-ORIGIN`）、子树前缀不得互相嵌套（`ORIGINS-NESTED`）、来源自己发布的文件数/
字节数/摘要/许可文件名必须与它那些行算出来的一致（`ORIGINS-MEASUREDFILES` /
`ORIGINS-MEASUREDBYTES` / `ORIGINS-CONTENTDIGEST` / `ORIGINS-LICENSEFILESPRESENT`）、
不得声称比实际更多的脚本（`ORIGINS-DECLARED-COUNT-UNMATCHED`，单侧判断：子树里多出 LICENSE
或 README 是合法的，少出来说明记录在吹），且没有 URL 必须写清理由
（`ORIGINS-URL-UNEXPLAINED`）——我不把 `github.com/creold/...` 这类拼装出来的地址当证据，
表里只给了 owner/repo。`--write` 只重算实测半边，声明半边与 `reviewedBy` 一律照人写的保留。

**仍然未决（属 owner）**：八条来源的 `reviewedBy`/`rightsDecision` 全为空，门按
`origins=8 origins_unreviewed=8` 报数不判红；八个来源里只有两个带 LICENSE 文件；
`abdul-karim-mia/photoshop-automator` 那条连它自己的单据都写着"未核实"。
把锁的聚合行**拆成独立条目**这一步我没做，但不该按锁写的那个理由来定范围。锁的
`canonicalUrlAbsentReason.whatWouldCloseIt` 说"ids 被 capability index 与 quarantine registry
引用"——实测含 `tool-control` 的行数是：`design-lab/config/capability-index.json` **0**、
`design-lab/research/global-absorption/QUARANTINE_REGISTRY.json` **0**；真正要一起改的是
`SOURCE_REGISTRY.json` 8 行、`CANDIDATE-TAXONOMY.json` 3 行、`rights-registry.json` 1 行、
`knowledge-role-classification.json` 1 行、以及锁自己 3 行。外加 `sources.lock.json` 是
`scripts/deepseek_registry_ssot.py` 认定的规范文件之一、由 `generate_rights_registry.py`
生成进 `rights-registry.json`，读它的门还有 `verify_source_lock.py` /
`verify_source_registry.py` / `verify_supply_chain.py` 三道。所以拆分确实是跨记录的协同变更，
只是集合要按上面测出来的来，不能沿用那句没核过的话。
本轮先把"每个上游有多少字节、谁没有许可"变成可复核的事实与会响的门，拆分留下一次统一改。
