# Bounded Sleep Mode + Autonomous Course Loop (2026-07-01)

## Trigger

The user wanted Hermes to continue Obsidian course-processing while they slept, without repeatedly choosing courses or approving every low-risk write. They explicitly asked for bounded permissions and later asked the agent to keep listing and executing follow-up tasks in a loop.

## Key workflow lesson

Do not treat “autonomous” as unlimited yolo. Use a bounded work contract:

- Write only in the vault and the external backup directory.
- Do not delete/move course body/source materials.
- Do not touch system files, unrelated projects, credentials, installs, uploads, pushes, or destructive git commands.
- Every round: backup → write → validate → local commit → queue next task.

## Approval pitfall

A chat message such as “开启本任务 yolo” is not necessarily enough to alter Hermes tool approvals. In this session, `execute_code` returned:

```text
BLOCKED: execute_code script timed out without user response.
The user has NOT consented to running this code.
Do NOT retry, do NOT rephrase the script, and do NOT attempt the same outcome via a different tool.
```

Correct behavior:

1. Stop immediately.
2. Do not bypass by switching tools or rewriting the script.
3. Preserve the task queue/resume point.
4. Tell the user to actually enable `/yolo` or configure approvals, e.g. `hermes config set approvals.mode smart`, then continue.

## Autonomous course selection pattern

When the user says they no longer want to choose courses:

1. Read the course processing workbench and P1 queue.
2. Rank candidates by:
   - alignment with current knowledge-system theme;
   - source completeness (docs/transcripts/titles/PDFs);
   - manageable size;
   - ability to create course portal + summaries + cards + review + terms + indexes + report.
3. Choose a course and state the reason only briefly.
4. Continue without asking the user to pick.

## Concrete second-course example

Chosen course: `30天考霸训练营，北大博士后教你通关任何考试（完结）`.

Why:

- It was the #1 recommended second-course candidate in the existing workbench.
- It aligns with the completed `知识内化训练营` course and can reuse learning-method templates.
- Size is manageable compared with very large candidates (`张宇`, `记忆圣经`).
- It supports a full learning-method loop: motivation → progress notebook → recall/repetition → exam application.

Important evidence constraint:

- The course had many MP4s and docs, but `.txt` files were mostly tiny placeholders, not full transcripts.
- The course directory PDF was image-heavy and not usable as text.
- Reliable source basis came from video titles + DOCX/PDF/PPTX materials + duplicate source-directory cross-check.
- Therefore summaries must say “organized from titles + document pack mainline,” not pretend to be transcript-derived.

Extracted course mainline:

```text
压倒一切的理由
→ 点滴进步
→ 进步本
→ 熟练才能上瘾
→ 5分钟收获追问
→ 满分考生心态
→ 认知回路
→ 费曼阅读/讲解
→ 题目反馈
→ 知识复现
→ 焦虑转行动
→ 在现有条件下做到极致
```

## Pause / resume commands for the user

Treat these as hard stops:

```text
暂停
停止
打断
不要继续
```

On stop: report current stage, artifacts written, artifacts pending, git status if available, and a concise resume command.

Treat these as resume signals:

```text
继续
继续第二门
继续下一门
只更新索引，不继续处理新课程
```

## Minimal todo seed for future loops

```text
1. Finish current course artifact write/validation/commit.
2. Re-scan P1 candidates.
3. Select next course using relevance + completeness + manageable size.
4. Run material inventory → verification limits → summary → workflow → terms → cards → review → indexes → report.
5. Validate JSON/hrefs/mojibake and local git commit.
6. Repeat unless interrupted.
```
