# DESIGN-LAB 派生物清理与规范化 — 2026-10-28

- 授权：owner 2026-10-28 逐字「并行执行 项目体积清理与规范化  执行合并迁移清理等相关执行，
  任何过时的陈旧的冗余的，该归档的归档 包括目录子文件夹等」，并在选择面板里把范围点定为
  **只清派生物** + **仓库内历史归档合并** + **PR #277 合并与分支收口**。
  决定件：`docs/taskpacks/20261028-automation/OWNER-DECISION-2026-10-28.md`。
- 读数全部是本轮现测的，不是引用的旧数；每条测量都点名它测的是哪一刻。

## 1. 基线（先量，再动）

| 面 | 实测 |
|---|---|
| `.git` | 260 MiB |
| 受跟踪树 | 4,019 个文件 / 79.1 MiB |
| `.project-local/`（整树，含被忽略内容） | 10,605.0 MiB / 182,083 个文件 |
| 其中 `task-runtime/` | 7,624.2 MiB / 27,769 条目 |

`.venv/` 200.2 MiB 与 `node_modules/` 181.1 MiB 是工具链，不在清理范围内。

## 2. 删除前逐个查过"谁点名它"

被跟踪代码/配置/文档的引用面用 `git grep` 现数（4,019 条索引项），结论按三类处置：

- **每跑自增的纯派生物**（删）：`task-runtime/reconstruction` 的命名者
  `design-lab/tests/test_reconstruction_contracts.py:102` 每次运行写一个新 `run_id` 目录，
  累积 2,355 条目＝1.978 GiB；`contract-bindings-scratch`、`kb13-weight`、`workbench-launch`
  同理分别被 `test_contract_bindings.py:70-72`、`test_workbench_weight.py:183`、
  `test_workbench_launch.py:43` 按需创建（`mkdir(parents=True, exist_ok=True)`）。
- **被受跟踪清单点名"要能按摘要补回"的 owner 原件**（留）：
  `.project-local/record-archive-2026-10-23/`、`record-archive-2026-10-27/`、
  本轮新增的 `record-archive-2026-10-28-design-automation/`，以及
  `task-artifacts/record-archive-2026-10-09/objects/**`。
- **删了会让闸门静默变 skip 的本地便利件**（留）：`task-runtime/playwright/npm-cache` ——
  五把浏览器闸（design-layer / contrast / overflow / theme-geometry / motion）靠
  `test_workbench_design_layer_e2e.py:41-56` 探测它，探不到就 `self.skipTest` 而不是判红。

## 3. 结果（本轮实测）

- `observed_at_utc = 2026-10-28T11:53:26Z`
- before：**10,966,116,254 B / 174,231 文件**
- after ： **2,200,656,713 B /  15,014 文件**
- 释放：**8,765,459,541 B（8,359.4 MiB）＝ 实测运行根的 79.93%**，移除 27,970 个条目
- 前 12 大条目（其余为长尾小 scratch）：`reconstruction` 2,074,048,098 B；
  `python-tests-shard-1` 268,454,545；`sdist-repro` 233,222,958；`scratch-stitch-20261022` 216,981,368；
  `scratch` 207,652,993；`vc` 207,213,090；`runs/ci-clean-venv` 203,472,569；`tmp` 114,168,855；
  `runs/npm-cache` 66,877,358；`python-tests-shard-2` 55,546,935；`contract-bindings-scratch` 47,020,549；
  `ui-capture` 37,718,913。

两个陈旧 `git worktree`（`b2cd710c`、`bb514458`）先按**内容**比对再移除：`b2cd710c` 里那份"未提交改动"
是比 HEAD 更旧的草稿（手机端仍写 `FROZEN_DEFERRED`，而 HEAD 已按 owner 2026-10-19 的
「再说一遍 不做手机端 只做桌面端」改成排除项；§7.1 的 CI 回执本身已在 HEAD 内），
两者提交都是 HEAD 与 `main` 的祖先。合计 140.7 MiB，已计入上面的 before/after。

## 4. 一处必须如实说的过程缺陷

**第一遍清理在写完账目之前就中断了**：`shutil.rmtree` 撞上 scratch 仓库里
`.git/objects/**`（git 在 Windows 上把自己的对象文件写成只读），抛
`PermissionError [WinError 5]`，因此那一遍删掉的字节没有逐条记录。
修法是把 `force_remove()` 加上 chmod 重试，并**先测后删、删完立刻落 JSON 账目**。
所以上面第 3 节的 before 是第二遍自己测的 **10,457.5 MiB**，比第 1 节普查的 **10,605.0 MiB**
少 147.5 MiB；其中 140.7 MiB 就是中间移除的两个 worktree，其余 6.8 MiB 是本轮自己的探针与核验
在两次测量之间写入又删掉的字节。两个数都公布，不拿后一个冒充前一个。

## 5. 清理后重跑，证明没打断工具链

- `design-lab/tests/test_workbench_design_layer_e2e.py` → `Ran 2 tests in 12.583s / OK`
  （真 Chromium、真环回服务；若 npm-cache 被误删，这里会变成 skip 而不是 OK）
- `.venv/Scripts/python.exe ... tsc --noEmit` / `vite build` / node 三套测试在本轮改动后各自通过。

## 6. 没做的事

- 没动 `.project-local/projects/`（持久作品，`design-lab/config/external-assets-index.json` 就是这么写的）。
- 没动 `task-artifacts/`（254 条冻结区回执点名它；删了不是"回收空间"，是把历史读回永久变成不可读）。
- 没动 `cache/vendor`（`vendor/sources.lock.json` 里 37 个源的唯一本地持有面）。
- 没动 `cache/models`、`backups/`、`archive/`、`quarantine/`、`personal-audit-src/`、`ui-kit/`、
  `brand-probe/`、`artifacts/`、`b10/`、`runs/{pw-browsers,node-libs,design-review}`。
- **没删任何受跟踪文件，没做历史归档合并的字节改写**：第 ② 层（仓库内归档合并）按冻结规矩
  只换指针与取代关系、原字节不动，且要连着重钉登记件/权威链/现行投影，另刀执行。
- 没碰 E 盘。
