# 2026-10-19 归档区（archive-2026-10-19）

这里存放 2026-10-19 归档波次从明面搬走的全部旧文档：过时的任务包、按日期堆积的 handoff、
一次性计划、研究草稿、旧的当前面记录。字节未改写，只有路径变化，逐文件的
`原路径 → 新路径 → blob SHA-1 → 字节数` 登记在 [`MANIFEST.json`](MANIFEST.json)。

Owner 指令（2026-10-19）：任何旧的、过时的、冗余的、陈旧的材料不再留在明面上，整体搬到该去汇总的
位置，并按规范化处理，防止下一轮会话再把旧路径当成当前入口。

## 这里没有什么

- 没有派工入口。唯一派工入口是 `docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md`
  （`DL-TP-20261019-DIRECTION-R1`），接续位置是 `docs/current/NEXT-AGENT-PROMPT.md`。
- 没有当前能力真值。当前真值顺序见 `AUTHORITY.md` 与 `reports/README.md`：
  `design-lab/config/capability-evidence-index.json` → `design-lab/config/capability-status.json`
  → `design-lab/scripts/verify_design_lab.py` → `design-lab/scripts/verify_release_gate.py`。
- 没有可执行的正确性证明。这里的 E3/E4/E5 措辞只是历史证据，不覆盖当前 checkout。

## 检索与使用规则

1. 本目录属于 `docs/history/**` 冻结家族（见 `docs/current/HISTORY-FREEZE-RULES.md`）：
   只用于 lineage、决策理由、差分对照、证据溯源与回滚，不得改写。
2. 需要引用某份旧文档时，先查 `MANIFEST.json` 确认它的新路径，再引用新路径；
   不要在指引面（AGENTS.md / README.md / AUTHORITY.md / NEXT-AGENT-PROMPT.md）写旧路径。
3. 旧路径不是错误信息，而是移动记录：`MANIFEST.json` 的 `from` 字段就是权威对照表。
4. 禁止 mass-delete。需要物理删除时，必须先确认 replacement、callers、历史保全与 hash/链接更新。

## 同级归档目的地

| 目的地 | 内容 |
| --- | --- |
| `docs/history/archive-2026-10-19/**` | 本次归档主体（任务包、handoff、计划、研究、旧当前面记录） |
| `AGGREGATED-RECORD-2026-10-19.md` / `HANDOFF-PROMPT-DIGEST.json` | 83 份已删交接与提示词的逐份汇总：标题、自述、结论、只有它记载的事实 |
| `REMOVALS.json` | 已删文件的 blob sha1/sha256/crc32/字节与 `restoreAt`；`git show <restoreAt>:<path>` 可还原原件字节 |
| `handoffs/deepseek-r3-20260906/**` | owner 随包提供的 17 件 R3 审计输入原件——故意没删，删它等于销毁输入 |
| `reports/history/**` | 5 份按日期命名的 reports 交接摘要（同一波次搬入）；其中 10 份 loose 交接件已按删除指令移出 |
| `docs/history/record-imports-2026-10-08/**` | DL-REC-29 从 Record 导入的冻结原件，逐文件定态见其 `RECORD-IMPORT-MANIFEST.json` |
| `docs/history/next-agent-prompts/**` | 历史提示词血统登记 `PROMPT-LINEAGE.json`（5 份按日期副本已删，逐份 sha256/字节仍登记在表内） |
| `.project-local/task-artifacts/**` | 大型位图、字体、原 ZIP 等不随 Git 克隆的本机产物 |

要读回一份被删文档的内容，不要手写路径解析：`scripts/archive_records.py:read_record(rel)` 按
工作区 → 归档移动 → `REMOVALS.json` 的 `restoreAt` 三层取字节并回写来源，三层都不到即报错。
