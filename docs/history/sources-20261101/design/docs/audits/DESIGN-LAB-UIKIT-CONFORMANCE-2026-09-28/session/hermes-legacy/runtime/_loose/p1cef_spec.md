# P1-C/E/F 规格：治理同步（每项先取证，证伪即跳过并在交付里说明）

工作区 `D:/All projects/DESIGN-LAB`。改动留给主线 commit，你不 commit/stash/push。全部 stdlib、不联网。
先跑 `git status --porcelain` 确认只有你自己改的文件。逐项按下面执行；**每项动手前先取证，证据不成立就跳过并在交付中写"已证伪+证据"**，不得凭空改文档。

## P1-E authority-index 移除已消失的 drift
文件：`.project/governance/authority-index.json`
1. 取证：读 `AGENTS.md` 前 30 行。P1-E 前提是"index 仍把 AGENTS 'Authority first read' 视为 drift，而 AGENTS 当前已要求先读 Authority"。
2. 若属实：从 `currentButDrifted` 数组移除 AGENTS.md 对应条目（第 43-46 行的 `{path: AGENTS.md, reason: ...}` 对象），保留 LANGUAGE-POLICY 条目（它由 P1-F 处理，改完后也移除，见下）。
3. 若 AGENTS.md 仍不含"先读 AUTHORITY"的措辞：跳过本项并记录证据。
4. 同文件：`observedMainSha` 当前是 `0e9f687c...`（R2 落仓时的快照），注释说 "snapshot only; refetch on every audit"。按 authority 语义**不要**把当前 HEAD 写进 index（index 是静态快照，更新 observedMainSha 属于 audit 动作；仅当 §15/CI 有明确要求才改——先查 `scripts/verify_top_level_authority.py` 是否校验 observedMainSha 新鲜度，若无校验就保持不动并在交付中说明）。

## P1-F LANGUAGE-POLICY 同步 Node 构建现状
文件：`docs/architecture/LANGUAGE-POLICY.md`
1. 取证：`ls package.json pnpm-lock.yaml pnpm-workspace.yaml apps/workbench/package.json apps/workbench/build/main.js`（主线已确认前四个 + build/main.js 都存在）。再读 `pnpm-workspace.yaml` 与 `package.json` 的 name/scripts 字段确定 workspace 根与构建命令（如 `pnpm -r build` 或 `pnpm --filter workbench build`，以实际 scripts 为准）。
2. 改 §4 表格 4 行失真事实（82-86 行区域）：
   - `Product Node build`：由 "none" 改为真实现状——`apps/workbench` 由 pnpm workspace（根 `pnpm-workspace.yaml` + 根 `package.json`）驱动，Vite 构建产物 `apps/workbench/build/main.js` 已 tracked 并由 `verify_workbench_packaging.py` 门禁校验（D003）。措辞须与仓库事实一致，不夸大。
   - `Root package.json`：由 "absent" 改为 "present（product workspace root）"。
   - `Lockfile`：由 "absent" 改为 "present（pnpm-lock.yaml，workspace lockfile）"。
   - `package.json in tree`：保持 fixture 那条（仍准确）+ 补充 root 与 apps/workbench 的 package.json。
3. §4 "The rule this fixes"（90-99 行）：把 "Today the second is true, and that is now stated" 更新为当前已是 "one package manager, one lockfile, one workspace boundary"（即 pnpm 单一真值）——以取证的实际 workspace 结构为准。
4. 顶部 status 行第 4 行 `frozen policy; enforcement gap recorded honestly` 可保留（ruff 的 CONFIGURED_NOT_ENFORCED 事实未变，勿动 §3）。
5. 改完后：若 authority-index 的 P1-E 已移除 LANGUAGE-POLICY drift 条目——**先取证 LANGUAGE-POLICY 是否还有任何 drift**：若唯一 drift 就是本节改的 Node 失真句，则 P1-E 步骤 2 里把 LANGUAGE-POLICY 条目一并移除；若还有其他 drift（如某处仍写 DECLARED_NOT_ENFORCED——先 grep `DECLARED_NOT_ENFORCED` 全仓确认），保留条目并在交付中说明。

## P1-C reports/current projection 新鲜度标记
文件：`reports/current/` 目录（先 `ls reports/current` 看全貌，主线已知该目录含 CONTRACT-GRAPH.json、LANGUAGE-BOUNDARY-SCAN.json、DEEPSEEK-AUTHORITY-CHAIN.json 等）
1. 取证：读 `reports/README.md`（P0-I 跑 verify_capability_evidence_v4 时已确认其 boundary 文本含 "historical"/"current capability index"/"not current runtime proof" 标记）。
2. 改动 = 生成物加显式 provenance，**不是**删目录：
   - 对每个 reports/current 下的 .json：加顶层键（若 JSON 是 dict；非 dict 则跳过并在交付中列名）`{"projection": true, "subjectSha": <当前 HEAD 40hex>, "fresh": false, "generatedBy": "<生成该文件的 script 名>"}`。`fresh=false` 表示"这是某一刻的投影，不是实时真值"。用 `git rev-parse HEAD` 取 subjectSha。
   - `generatedBy` 的取值：先读文件头部/内容特征，找仓库里对应的生成脚本（`scripts/generate_*.py` / `scripts/verify_*.py` 的 docstring 或 workflow 引用）；确不确定就写 "unattributed"，不要猜。
   - 若 reports/current 下某文件是手工维护的 Markdown（非投影）：不动。
3. 同时确认 `reports/current` 是否被 `reports/history` 的 gitignore/边界规则覆盖：不改 gitignore，不改 history 文件。
4. 若 `reports/README.md` 已有 projection 说明但缺 `fresh` 语义，可加一段"current = latest projection, fresh=false, re-validate against live tree/CI before relying on it"——只增不删。

## 禁区
- 不碰：capability-status.json、capability-evidence-index.json、release-evidence.schema.json、verify_release_evidence.py、verify_capability_evidence_v4.py、effective_evidence 相关（另一子代理的域）。
- 不碰 AUTHORITY.md §15（P1-D 主线做，证据已齐）。
- 不 commit/stash/push；不装依赖；不联网；stdlib only。
- 每改一个文件，跑一次 `python -c "import json,pathlib; json.loads(pathlib.Path('<file>').read_text())"` 验证 JSON 合法。

## 交付
- 文件级 diff 摘要 + 每项 P1-C/E/F 的"已取证做/已证伪跳过 + 证据" + 验证输出原文（git status、JSON 校验、grep 结果）。
