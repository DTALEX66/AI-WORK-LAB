# OER coverage dashboard + stop-after-current-round protocol (2026-07-03)

Use this reference for Obsidian/TALOS sleep-mode OER work after several courses already have OER crosswalk pages.

## When to switch from per-course expansion to a coverage dashboard

After 3+ manual/generated OER course samples exist, do not keep blindly applying the generator course-by-course. First create a visible coverage dashboard so the next course choice is evidence-backed.

Recommended outputs in the formal vault:

- `00_主页/18_TALOS_OER覆盖率仪表盘.md`
- `50_领域知识/开放知识与OER/06_OER覆盖率清单.md`
- `50_领域知识/开放知识与OER/06_OER覆盖率清单.json`
- a dated import/execution report under `93_导入报告/<date>_TALOS_oer_coverage_dashboard/`

Scan formal course folders by direct presence of `02_课程库/<course>/00_课程总览.md`. For each course, record:

- `14_开放知识交叉对比.md` exists
- `15_FAQ问题驱动入口.md` exists
- `13_项目转化.md` exists
- `11_证据索引.md` exists and whether it contains verified evidence
- `08_术语索引.md` exists
- `05_复习与检索练习.md` exists
- Daily Mission count from `00_主页/12_TALOS_Daily_Missions/*.md`

Use the dashboard to show both sample courses and next candidates. Suggested candidate sorting: missing OER first, but prefer courses that already have V7 + terms + review so the generator can produce a useful page without inventing facts.

## Evidence boundary language

Always include this warning in coverage dashboards and generated pages:

> OER 覆盖率只说明课程已吸收开放知识网站的结构、字段、许可意识或问答组织方式；不能把 OER 页面、FAQ 或开放网站当作课程 V6 verified 证据。

If a course lacks `11_证据索引.md` or verified evidence, generated pages must say so explicitly.

## Stop-after-current-round protocol

When the user says variants of “执行完本轮停止”, do **not** stop immediately if a named/current round is already in progress. Finish only that round to the nearest clean safety point, then stop.

Required steps:

1. Acknowledge the stop boundary: “finish current round, then stop; no new tasks.”
2. Complete the current round only: write artifacts, refresh related dashboards, validate, and commit locally.
3. Do not enqueue a new next-round task after the commit.
4. Mark the current round and the stop item completed; leave pending/in_progress empty.
5. Final report must include `vault clean`, helper repo/test state if touched, commit hash, and the explicit phrase that sleep mode is stopped.

## Concrete Round 22 pattern from this session

- Current round: apply `scripts/v9/oer_crosswalk_generator.py` to `30天考霸训练营`.
- Dry-run first confirmed `profile: learning` and no V6 verified evidence.
- Apply generated:
  - `02_课程库/30天考霸训练营/14_开放知识交叉对比.md`
  - `02_课程库/30天考霸训练营/15_FAQ问题驱动入口.md`
  - `50_领域知识/开放知识与OER/30天考霸训练营_OER交叉对比样板.md`
- Refresh coverage dashboard afterward. Coverage moved from OER `3/20` to `4/20`, FAQ `2/20` to `3/20`.
- Commit locally and stop: no new Round 23.
