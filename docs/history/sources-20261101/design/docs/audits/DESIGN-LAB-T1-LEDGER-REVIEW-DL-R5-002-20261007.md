# T1 账本逐任务复核 · 第二项：DL-R5-002

**复核对象**：`design-lab/config/task-ledger-r3.json` → `DL-R5-002`「仓库路径规范与旧运行根治理」
**观测 exact SHA**：`main` = `ba38204326`（`gh api commits/main` 实读；本分支基点）
**观察窗口**：2026-10-06T17:36Z–17:38Z
**结论**：A1 结构上成立但**当期无法出具完整认证**；A2 未核；A3 成立。**四轴不抬升。**

| 轴 | 现状 | 证据 |
|---|---|---|
| `implementation` | PARTIAL | `r5-runtime-root-boundary-live-20260927` |
| `unit` | PARTIAL | `r5-002-static-unit-20260928` |
| `host_live` | PARTIAL（required_axes 内，**证据为空**） | — |
| `delivery` | PARTIAL（不在 required_axes 内） | — |

---

## A1「已安装 Agent、CLI、UI、Adobe 入口无新增项目数据写入 `.hermes`」

**代码面成立**：全仓 `.hermes` 的**非文档**引用只有 4 处，全部是**排除列表**（扫描时跳过该目录），
没有任何写入方：

| 文件:行 | 用途 |
|---|---|
| `design-lab/scripts/verify_identity_gate.py:43,51` | `EXCLUDED_NAMES` / 前缀排除 |
| `design-lab/scripts/verify_product_manifest_v3.py:181,324` | 根相对前缀排除 |
| `design-lab/scripts/verify_visual_quality_v21.py:57,64` | 同上 |

策略面也有登记：`.project/governance/path-risk.yaml:6` 把 `.hermes/` 列为风险路径。
`AGENTS.md` 与 `AUTHORITY.md` §7 均声明 `.hermes` 不是活跃写入根。

**但当期认证拿不到。** 直接跑零外溢守卫：

```
python scripts/verify_zero_spill.py --self-test
  → ZERO_SPILL_SNAPSHOT=... repo_entries=9662 repo_complete=False agent_entries=19962 external_roots=0
  → task under test: generate_current_reports.py --check exit=0
  → ZERO_SPILL=INCOMPLETE spill=0 repo_new=1 repo_changed=1
     incomplete_roots=['agent:.codex', 'agent:.dsh', 'repo', 'repo-current']   exit=2
```

要点：

1. `spill=0` —— 在被扫到的范围内确实没有新外溢。
2. **`external_roots=0` 且 `repo_complete=False`** —— 外置根与 agent 根没有绑定进来，
   所以守卫**拒绝给 PASS，返回 `INCOMPLETE` 且 exit 2**。这是 fail-closed 在正确工作，
   不是门的缺陷。
3. `repo_new=1 repo_changed=1` 是自检自身的产物
   （`.project-local/task-artifacts/zero-spill/self-test-*.json`），属自指噪声，不是被测命令写出去的。

**因此 A1 的准确判定是**：写入方为零（结构证据，E1），但"无新增外溢"的**运行态认证在本机当前
配置下不可得**。根因与工具链审计的"有但未绑定"同源：**外置根存在却没登记给零外溢守卫**。
这条在绑定完成前不能升 `PASS`。

## A2「旧数据 hash 对应」— **本次未核**

`docs/history/DESIGN-LAB-HISTORY-EVIDENCE-MANIFEST-2026-09-04.csv` 与
`DESIGN-LAB-HISTORY-TASK-ID-CROSSWALK-2026-09-04.csv`（1451 行、含 `source_sha256` / `context_sha256` 列）
承载旧数据哈希。逐条复核需要独立一轮，本文**不声称已做**。

## A3「历史引用保留且不作为执行指令」— 成立

`docs/taskpacks/*.md` 中带 `SUPERSEDED` / `HISTORICAL` 标记的文件 **13** 个；
`.project/governance/authority-index.json` 用 `historicalGlobs` + `historicalSpecific` +
`taskpackClassificationRule` 给出机器可读分类，`nonAuthoritativeKinds` 显式列出
`HANDOFF_SUMMARY` / `BRANCH_NAME` / `COMMIT_COUNT` 等。历史不是被删掉，而是被标成不可执行——
这正是该条 acceptance 要的语义。

---

## 为什么仍然不抬升任何轴

1. **A1 缺当期运行态认证**，且缺的原因（外置根未绑定）本身是可修的具体缺口，不是"再等等"。
2. **A2 未核**。三条 acceptance 里有一条完全没验，抬升就是无证据抬升。
3. `host_live` 在 `required_axes` 内且**证据为空**；本任务三条 acceptance 都不涉及真实宿主，
   所以该轴为空是自洽的，但不得被读成已验证。
4. 本会话**没有在当前 SHA 重跑套件**；仓内 `Ran 1807 — OK` 属于 `28667300`，是前一会话观测。

## 抬升 DL-R5-002 的最小充分动作

1. 把外置根绑定给零外溢守卫，使 `external_roots > 0` 且 `repo_complete=True`，
   重跑得 `ZERO_SPILL=PASS`（这是 A1 缺的那一块，也是唯一需要动手的一块）。
2. 逐条复核 A2 的两份 CSV 哈希。
3. 在合并后的 exact main SHA 上重跑套件，取 `commands_and_exit_codes` + `environment_versions`。
4. 新证据的 `artifact_hashes` **只绑 tracked 路径**。

---

## 补充实测（同日 17:41Z–17:46Z）：机制已定位，且本文首轮结论需要精确化

首轮我写"根因是外置根存在却没绑定给守卫"。方向对，但**机制说错了**，在此更正：

`verify_zero_spill.py` 的 `main()` 里 `externals = tuple(args.external or ())` ——
外置根**只能通过 `--external` 命令行参数传入**，脚本**从不读 `.project/paths.json`**。
所以 `external_roots=0` 不是配置缺失，而是**默认调用必然为 0**。
声明其实一直都在，只是没人把它们递进去。

### 把 4 个声明根真的递进去之后

```
--self-test --external "…/Model library" --external "…/Design assets"
            --external "…/OS External Configuration" --external "…/Design External Configuration"
  → external_roots=4
  → spill=0
  → ZERO_SPILL=INCOMPLETE
     incomplete_roots=['agent:.codex','agent:.dsh',
                       'external:D:\All projects\Design External Configuration',
                       'external:D:\All projects\OS External Configuration',
                       'repo','repo-current']
```

判据从"看不见外置根"变成"**看见了 4 个根、其中 2 个因遍历被截断而不完整**"。
`spill=0` 是 5000+ 条外部条目上的真实读数；`INCOMPLETE` 仍不是 PASS，
剩余缺口是 `agent:.codex` / `agent:.dsh` 两个 agent 家目录不可观测。

### 一次假阳性，以及为什么不能单看一次 MODIFIED

第一轮 4 根自检报了 10 条 `SPILL: MODIFIED:…\Design assets\benchmarks\pixel-reconstruction-v1\…`。
核查后**不是外溢**：

| 检查 | 结果 |
|---|---|
| 这些目录的真实 mtime | **2026-08-14 / 2026-08-23**，不在运行窗口内 |
| 中间**不跑任何 DESIGN-LAB 命令**、只快照两次再比对 | `spill=0`，0 条 SPILL |
| 干净重跑同一 4 根自检 | `spill=0`，0 条 SPILL（不可复现） |

机制原因：`scan()` 的指纹是 **`(size, mtime)`，且把目录本身也当条目**。共享库根是多写者的，
任何无关进程碰一下目录，就会在单次运行里造出 MODIFIED。

**结论口径**：外部根上的 `MODIFIED` 列表在**未串行化观测**或**未改用内容指纹**之前，
不能作为一次运行的证据。改指纹是更大的独立决定，本次只记录不动。

### 已落地的修复（PR #234）

`scripts/verify_zero_spill.py`：
1. `main()` 自动折入 `.project/paths.json` 的 `shared_inputs` 声明根，与显式 `--external` 去重合并；
   `--no-declared-externals` 保留旧的仅仓库行为。
2. 更关键：`scan()` 对不存在的路径返回 `complete=True` + 空清单，
   若不处理，"这台机器上没有这个根"会被折成一个看起来干净的判据。
   现已记为不完整。**证伪过**：`--external <不存在的路径>` 会进入 `incomplete_roots`，
   判据是 `INCOMPLETE` 而非 PASS。
3. 既有 `ZeroSpillFa05Tests` 3 项仍 OK（它显式传 `externals=` 调函数，改动只在 CLI 层）。

### 对 A1 判定的影响

**仍然不抬升**，但缺口位置变了、也变小了：
- ~~"外置根未绑定"~~ → 绑定已由 #234 完成；
- 剩余阻塞是 `agent:.codex` / `agent:.dsh` 两个 agent 家目录不可观测，
  以及 A2 未核、当期 SHA 套件未重跑。
