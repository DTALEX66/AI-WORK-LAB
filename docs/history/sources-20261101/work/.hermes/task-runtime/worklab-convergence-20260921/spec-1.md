# SPEC 1/3 — E/F 保护盘真值统一（WS-3，P1）
repo: D:/All projects/WORK-LAB, branch u17/global-agent-policy-20260918 (HEAD 00f45a1).
Do NOT: commit, push, switch branch, create branches, touch tests/ or apps/observer or services/ (other domains), delete anything.

## 背景（mainline 已亲验的分裂面，exact 行号）
E+F 面（正确值，用户 standing rule 保护 E 和 F 两个数据盘）:
- config/global-agent-policy.yaml L99: protected_drives: [E, F]  (基准)
- .project/governance/projects.json L34-36: forbiddenRoots: ["E:\\","F:\\"]
- services/authority/machine_identity.py L39-42: _reject_protected_drive 报 "E: and F: are protected"
- services/policy/e_drive_guard.py L14: PROTECTED_DRIVE_RE = [EeFf]
E-only 面（需修成 E+F）:
- .project/governance/project-data-boundary.json L19-28: forbiddenExternalRoots 只有 E:/, E:\  ; protectedDataVolume.roots 只有 E:/, E:\
- README.md L85-86: "The `E:` data volume is protected..." (缺 F)
- packages/client-neutral-core/skills/software-development/project-data-boundary/SKILL.md L40: "E:\ 是用户保护的数据区..." (缺 F; 这是仓库内 tracked 的 skill 副本)

## 任务
1. project-data-boundary.json: forbiddenExternalRoots 与 protectedDataVolume.roots 增补 "F:/" 与 "F:\\ "（与 E 的两种写法对齐：现有是 "E:/" 和 "E:\\"，照抄加 F 版）。保持 JSON 合法、UTF-8 无 BOM、保留尾换行。
2. README.md L85: 改为同时表述 E: 与 F: 两个 data volume 受保护（措辞对齐 L85 现有句式，最小改动）。
3. 该 SKILL.md L40: 把第 8 条扩展为 E: 与 F: 双盘（最小改动，保留原语义与"当前请求授权"限定）。
4. 交叉 verifier：搜仓库内是否已有 verifier 校验 forbiddenRoots / protected_drives（git grep -n "forbiddenRoots" 和 "protected_drives" 排除 json/yaml 数据文件本身，看 scripts/packages/services/tests 下有无 verify_* 或 gate 消费）。
   - 若存在：升级为同时读 config/global-agent-policy.yaml(protected_drives)、projects.json(forbiddenRoots)、project-data-boundary.json(forbiddenExternalRoots + protectedDataVolume.roots) 并断言三者解析出的盘符集合相等。
   - 若不存在：在 packages/client-neutral-core/scripts/ 下新增 verify_protected_drives_consistency.py（stdlib-only、无网络、读仓库相对路径；对缺失文件 fail-closed；断言 E 与 F 在三个面都受保护且集合一致；PASS/FAIL + exit 0/1，风格对齐同目录 verify_external_libraries_index.py），并注册进 services/orchestration/run_quality_gate.py 的 GATES（加 def gate_protected_drives_consistency + GATES 条目，注释说明为何 in-script，参照 gate_external_libraries_index 的写法 L330）。注意：注册进 GATES 会改变 full verify 行为，必须保证新 gate 在本地跑通 PASS。
5. 负控：临时把 README 的 E-only 改回去（或构造临时文件）验证 verifier 会 FAIL，再恢复。不要提交负控文件。

## 本地验证（必须全绿才算完成；terminal 一律走 wrapper）
workdir = "D:/All projects/WORK-LAB"; 每条 terminal = python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>
- python services/orchestration/run_quality_gate.py verify   (全量, exit 0)
- 若超时太久, 至少跑: python services/orchestration/run_quality_gate.py protected-drives-consistency（新 gate 名）+ gate_external_libraries_index + gate_governance
- python scripts/ci/generate_current_state.py --check（若 README 属 CANONICAL_FILES 的 digest 输入，改了 README 需要重绑；读脚本确认其 --check 语义，必要时按其 README 说明重绑并说明）

## 报告
- 逐文件 diff 摘要（改了哪几行）
- verifier 是否存在/新建 + 负控证据（临时破坏→FAIL 的截图式引用）
- 本地 gate 结果
- 未做的事（明确留给 mainline 的）
改动全部留在工作树，不 git add/commit/push。
