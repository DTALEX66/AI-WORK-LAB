# DESIGN-LAB DP 交接纠错 V2 Implementation Plan

> **给 DP / DEEPSEEK：** 这是对第一轮交接的限范围修订任务，不重跑 DS-01—DS-12，不接管 GPT 核心代码。若执行环境有 executing-plans 技能，按该技能逐项执行；没有则按本文 checkbox 执行，不为此安装插件。

**Goal:** 修正五类已复核的资料错误，新增可独立验收的 V2 交接包，保留 V1 原件与所有已有代码。

**Architecture:** 原始交付只读；V2 用独立目录保存修订记录和外部校验清单。DP 负责机械核对与公开资料核实；GPT 负责最终接受、运行验证、rights 判断与正式状态更新。

**Tech Stack:** Windows PowerShell、项目 Python、JSON/Markdown、只读 ZIP 成员检查、公开网页核对。

**Spec:** [第一轮 DEEPSEEK 执行包](DESIGN-LAB-DEEPSEEK-EXECUTION-2026-09-06.md)及[R3 权威任务包](DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.md)。本文仅修订交接材料，不改变 R3 任务、依赖、Human Gate 或知识迁移延后决定。

## 1. 接管信息与已确认问题

项目根：`D:/All projects/DESIGN-LAB`。
交接分支：`codex/r3-runtime-correctness`。
交接 HEAD：`c4dccd58331bc4561eb89265283d924b7630d113`。
工作区有大量未提交/未跟踪成果；HEAD 不包含全部当前成果。本次未发布或做远端读回。

V1 原件目录：`docs/handoffs/deepseek-r3-20260906/`，实际 17 个文件。
入口为 `12-DEEPSEEK-RETURN.md` 和 `12-results.json`。

GPT 已实查：

- V1 的 16 个非自身文件，大小与完整 SHA-256 均符合 `12-results.json`；该 JSON 当前 SHA-256 为 `02746f731f5e6e4797874e911f5b512727f645fd3ebdbee31acafee0692a687e`。
- `12-DEEPSEEK-RETURN.md` 当前 SHA-256 为 `cca1fe6b62a05969748fc283bc986f08fb8cc494cd175a6312cecace6a1fc03b`。
- 两份历史 CSV 为 1450 / 536 条，与 ZIP 成员字节一致。67 个已登记测试源文件无漂移；报告生成器 `--check` 通过。这些不必全量重做，但接管时核对输入是否变化。
- DS-01 的 66 行都把顶层 `implementation` 实施步骤数组误当四轴状态，且 `unit` 全是 null。
- “当前 ComfyUI 未安装”无证据支持：外置安装中的 `python.exe` 和 `ComfyUI/main.py` 存在；当前工作流尚未验证。
- ZIP 的 `old-new-crosswalk.csv` 位于根目录，错误 locator 是 `history/old-new-crosswalk.csv`。
- `12-results.json` 内自身 hash 注记为旧 `e463…`，与当前字节不一致；不能使用自引用 hash 证明自身完整性。
- 参考候选 11 条，超过约定的 5—10 条；作者、URL及公开许可信息仍需实际核对，不能因写出候选清单就算资料验收全部通过。

## 2. Global Constraints：只允许这些操作

1. 先读取项目根及更近的 `AGENTS.md`、V1 两入口和本文涉及的具体输入；先确认同一 checkout 没有其他写入者，再新增文件。
2. V2 交付只写 `docs/handoffs/deepseek-r3-20260906-v2/`。运行日志、临时辅助脚本、缓存只写 `.project-local/task-artifacts/deepseek-r3-20260906-v2/`、`.project-local/task-runtime/deepseek-r3-20260906-v2/`。先核对路径/reparse边界和 ignored 状态；若已有同名交付，停下核对所有权，不覆盖。
3. V1 的 17 文件全部只读；不改本任务包、正式 ledger、`reports/current/`、config、schema、源代码、tests、workflow、锁文件、根指令。也不复制原17文件再整套换时间戳。
4. 不提交/push/PR/发布，不安装软件/模型，不启动宿主/ComfyUI/GPU，不运行模型，不修改 trust 或代签任何审批，不迁移/删除数据，不写全局设置。
5. 不访问 E 盘、凭据、`.env`、私钥、tokens、浏览器数据、Agent 私有配置/记忆/会话数据库。知识迁移延后。
6. 只核对下面指明的 ZIP 成员和两个 ComfyUI 文件的存在性/元数据；不要扩成共享库扫描。ZIP 不运行脚本、不 ExtractAll、不恢复原始私人对话正文。
7. 官方任务状态的唯一编辑源仍是 `design-lab/config/task-ledger-r3.json`；V2 的 `results.json` 只管理 DP 本轮修订状态，不能称作项目唯一真值表。

接管只读命令（PowerShell，逐条执行，记录退出码）：

```powershell
Set-Location -LiteralPath 'D:/All projects/DESIGN-LAB'
git branch --show-current
git rev-parse HEAD
git status --short
git diff --name-only
git diff --cached --name-only
git check-ignore .project-local/task-artifacts/deepseek-r3-20260906-v2
& '.venv/Scripts/python.exe' -B -c 'import sys; print(sys.executable); print(sys.version)'
& '.venv/Scripts/python.exe' -B 'scripts/generate_current_reports.py' --check
```

不要去掉 `--check`，报告漂移只回交 GPT。文本读写明确 UTF-8（读取可用 utf-8-sig）；终端中文乱码不能直接判文件已损坏。不得重跑固定输出目录的旧测试 runner 覆盖已登记日志。

## 3. DP-V2-01：修正四轴需求矩阵

**输入：** V1 `01-requirements-matrix.json`、`design-lab/config/task-ledger-r3.json`、`reports/current/TASK_PROGRESS.json`、`docs/history/taskpacks/r3-tasks-2026-09-06.json`。

**新增：** V2 `01-requirements-matrix.json`。

- [ ] 保留 24 个 R3 ID、66 个验收行的稳定 `record_id`、验收原文、序号、原依赖与交付物。数量以冻结定义计算，若不是 24/66 先列基线变化，禁止删行凑数。
- [ ] 按任务 `id` 关联两份状态数据，顶层 `implementation` 仅作实施步骤，不能当状态。
- [ ] 每行 `notes.current_axis` 保存 `progress_status` 与 `axes`；每轴同时保存 ledger 声明值、进度投影值、evidence 和 reasons，避免把声明值当已核验值。

字段读取规则（以下仅为数据转换片段，不改核心模块）：

```python
axes = ("implementation", "unit", "host_live", "delivery")
ledger_by_id = {t["id"]: t for t in ledger["tasks"]}
progress_by_id = {t["id"]: t for t in progress["tasks"]}
lt = ledger_by_id[task_id]
pt = progress_by_id[task_id]
current_axis = {
    "progress_status": pt["status"],
    "axes": {
        axis: {
            "ledger_state": lt["axes"][axis]["state"],
            "progress_state": pt["axes"][axis]["state"],
            "declared_state": pt["axes"][axis]["declared_state"],
            "ledger_evidence": lt["axes"][axis]["evidence"],
            "evidence": pt["axes"][axis]["evidence"],
            "reasons": pt["axes"][axis]["reasons"],
        }
        for axis in axes
    },
}
```

若真实字段缺失，报告 schema/输入差异，不默认填 PASS/null。声明与投影不同可能是合法的过期降级，保留原因，不能强制改为相等。

**验收：** 逐行与输入原字段比对一致；状态值是字符串而非数组；当前基线 R3-01 的 implementation 为 IMPLEMENTED_LOCAL、unit为PASS、host_live为NOT_REQUIRED、delivery为NOT_EXECUTED。若输入已变，按新证据记录差异，不硬编码旧值。附校验用例：故意把局部内存副本的 implementation 换成步骤数组，校验必须拒绝；不改磁盘原件。

## 4. DP-V2-02：修正 ComfyUI 与历史证据措辞

**输入：** V1 `07-capability-evidence-gaps.json`、`12-DEEPSEEK-RETURN.md`、`12-results.json`。

**新增：** V2 `02-capability-corrections.json`（仅修正记录，不重抄全部候选）。

- [ ] 只读核对以下两条精确路径的存在性、文件类型、大小和观测时间，不启动程序：
  - `D:/All projects/Design External Configuration/toolchains/comfyui/ComfyUI_windows_portable/python_embeded/python.exe`
  - `D:/All projects/Design External Configuration/toolchains/comfyui/ComfyUI_windows_portable/ComfyUI/main.py`
- [ ] 记录被纠正的 V1 文件/record_id/字段；撤回“当前无 ComfyUI/ComfyUI 未安装”的断言和由此推出的冲突。
- [ ] 分开写：安装文件存在（仅文件观测）、当前进程/服务可用性未执行、当前生成工作流未验证、历史 E3 仅历史证据须重新资格验证。不要反向升级为“已安装且可运行”。

**验收：** 每条修正有 V1定位与本轮依据；历史 E3仍保留，不抹掉历史记录，不改正式 capability/profile。无法访问路径时写本机范围内未验证，不写不存在。模型资格、真实启动和生成由 GPT 负责。

## 5. DP-V2-03：修正 ZIP locator 与缺失语义

**输入：** V1 `02-history-locators.json`；ZIP `C:/Users/ALEX/Desktop/DESIGN-LAB-CLOUD-REAUDIT-TASKPACK-2026-09-06.zip`。

**新增：** V2 `03-history-locator-corrections.json`。

- [ ] 读取 ZIP 中央目录，核对精确成员 `old-new-crosswalk.csv`（此前观测3152 bytes）与 `evidence/history-current-tree-coverage.json`（此前262249 bytes）。
- [ ] 明确 `history/old-new-crosswalk.csv` 是错误定位，不是另一个待恢复文件。
- [ ] 对这两个小型公开索引成员流式读取并计算 SHA-256，先限制单成员≤2 MiB；不解压、不执行、不输出成员正文。记录 archive路径、member、size、SHA-256、观测时间。
- [ ] 对“ZIP存在、仓库未落盘、尚未恢复、来源缺失”分别记录；只有确实查过的范围才可写未找到。找不到ZIP时保留历史locator并写本轮未复核。

**验收：** 精确成员可按记录重新取到并匹配hash；不再把“未提取”写成“原始来源丢失”，也不把两个索引存在当536份原文恢复齐全。原1450/536 CSV不改、不重新构造私人原文。

## 6. DP-V2-04：参考集收敛与公开来源核对

**输入：** V1 `08-reference-candidates.json`、`08-reconstruction-acceptance.md`。

**新增：** V2 `04-reference-candidates.json`、`04-reference-exclusions.json`。

- [ ] 逐一访问原11条候选的具体作品页；记录 requested_url、final_url、访问时间、页面标题、具名作者、作品类别、证据URL及实际访问结果。搜索摘要或“Dribbble shot author”不能替代作者核实。
- [ ] 优先从原候选保留5—10个不同作品，覆盖文字几何海报、照片+蒙版、复杂纹理及电商/2D/3D需求；若需要替补，仅查公开作品原页，不重新无限调研。
- [ ] 每条公开许可信息必须有来源URL及适用范围；没有就写 UNKNOWN。明确区分“页面可访问/作者已核实”和“复刻/下载/再发布已授权”。不登录、购买、下载图像或复刻，不把本任务当 rights 审批。
- [ ] 未入选的原候选全部放入 exclusions，保留原 candidate_id 与原因；不静默丢弃。候选集只计作品，不把合集、搜索列表、重复裁切视作独立作品。

**验收：** 主候选数在5—10之间、作者和作品页可核验、类型覆盖明确；全部旧11条均可在保留/排除记录追踪。无法核验或少于5个时标 PARTIAL，不能为满足数量编作者/URL。公开许可UNKNOWN不妨碍“元数据核对完成”，但必须保持 `approved_for_reconstruction: false`，实际采用交GPT/用户。

## 7. DP-V2-05：整合回交与非自引用 hash 链

**前置：** DP-V2-01—04 分别完成或有精确未满足条件。

**新增：** V2 `05-DP-RETURN.md`、`05-results.json`、`SHA256SUMS.txt`。

- [ ] 回交正文列五项修订的完成/未完成、GPT待办、输入hash、V1修正定位及九个最终文件名。明确 V2 只替代对应错误结论，不替代未改的V1材料与正式ledger。
- [ ] `05-results.json`逐项记录 `task_id`、`status`（PASS/PARTIAL/BLOCKED/NOT_EXECUTED）、`evidence`、`unmet`、`r3_ids`、实际观测时间；文件落盘不是PASS条件。另记录 `acceptance_by_gpt: "PENDING"`。
- [ ] 先固定所有八个交付内容文件（包括05正文与05结果），再生成独立 `SHA256SUMS.txt`，按文件名字典序记录其余八个文件的完整SHA-256，不包含该清单自身。不在05正文或05结果回填这张清单的hash。
- [ ] 最后单独计算 `SHA256SUMS.txt` 的hash，仅在回交用户的消息中给出。正文/JSON只能说“清单不含自身，清单hash见交付消息”，不要制造hash循环依赖。
- [ ] 重新核对清单八行均匹配；再核对V1原17文件的接管前后hash不变，复查Git变化仅在允许的新目录；其他进程造成差异只报告，不自行恢复。

**验收：** 内容八文件 + 校验清单一文件 = V2共九文件；所有JSON可解析；manifest不自引用；V1无变化；五个任务结果不自动全PASS；报告中不再有“15文件/17文件”或“含自身hash”的矛盾。helper脚本/日志不放V2交付目录。

V2九个交付文件：

```text
docs/handoffs/deepseek-r3-20260906-v2/
  01-requirements-matrix.json
  02-capability-corrections.json
  03-history-locator-corrections.json
  04-reference-candidates.json
  04-reference-exclusions.json
  05-DP-RETURN.md
  05-results.json
  SHA256SUMS.txt
  00-input-baseline.json
```

`00-input-baseline.json` 在接管时建立：记录项目root/branch/HEAD、V1原17文件及本轮输入文件的size/hash、原有Git变更文件列表、检查时间。它是第八个内容文件，并随其余七个内容文件一起进入SHA256SUMS。只记路径和hash，不复制源码diff、凭据或私密正文。

## 8. 不在本轮 DP 范围

CI workflow实际修改、ComfyUI启动/取消/生成、OCR/ASR/H3加载推理、模型许可适用判断、核心事务和锁、服务/API/UI、Adobe控制、正式ledger与profile更新、去重删除、安装迁移、提交上传，全部留给GPT。本轮不要求重跑280/49测试或全量历史恢复。

## 9. 直接给 DP 的执行话术

请执行本修订包 DP-V2-01—05。先核对单写接管和输入hash，只新增V2目录，保留V1及GPT未提交成果。修四轴、ComfyUI措辞、ZIP定位、参考候选和hash交付方式。做到一项验收一项，无法核对就明确PARTIAL；不要修改核心代码或替GPT做人审/运行资格。回交V2的05-DP-RETURN.md、05-results.json、SHA256SUMS.txt，并在消息中提供SHA256SUMS.txt自身的完整hash。
