# 三项目项目级配置审计（2026-08-23）

> 审计 WORK-LAB / ArcheAxis-Knowledge-OS / DESIGN-LAB 各自项目内部配置与规则。

## 1. 实测数据

| 项目 | 项目 skills | yaml 配置 | hook/gate 脚本 | CI steps | 规则文件 |
|---|---|---|---|---|---|
| WORK-LAB | 36 / 122KB | 18 | 8 | 47 | AGENTS.md 6.7KB |
| ArcheAxis-Knowledge-OS | 0（合理）| 29 | 4 | **108**（ci 67 + nightly 23 + release 18）| AGENTS.md 6.0KB |
| DESIGN-LAB | 648 / **6MB**（在 .hermes 运行时）| 1 | 8 | 46 | 无 AGENTS.md（README 4.5KB）|

## 2. 关键发现

### A. DESIGN-LAB 648 skills / 6MB —— 实际是运行时冗余副本

```
路径：.hermes\w\a1\design-lab\adapters\hosts\open-design\expert-suite\skills\
（b2b-backoffice-designer / brand-identity-director / design-source-curator 等）

性质：Open Design expert-suite 的设计专家技能库，被复制到 .hermes 运行时
结论：不是 DESIGN-LAB 项目源配置，是 agent 运行时副本——疑似冗余（需确认是否该清理）
```

### B. ArcheAxis CI 108 steps 过重

```
ci.yml 67 steps（每次 push 全跑）+ nightly 23 + release 18
知识项目（文档/真源）CI 67-step 主流水——可能过度（编译/测试/部署全堆一条）
```

### C. WORK-LAB 相对合理

```
36 skills/122KB、47 CI steps——三项目中负担最轻
但全局侧（Hermes skills 866KB + 111 测试全量）仍是负担（上一轮已审计）
```

## 3. 精简建议

| 项 | 建议 | 收益 |
|---|---|---|
| DESIGN-LAB .hermes 6MB skills 副本 | 确认来源，若冗余 → 清理（保留项目源 expert-suite 一处）| 释放 6MB + 运行时负担 |
| ArcheAxis CI 67-step ci.yml | 分层：快速（lint/关键测试）+ nightly（全量）| push 等待缩短 |
| ArcheAxis 29 yaml | 核对 .worklab/ vs config/ 是否重复定义 | 配置单一化 |
| 三项目规则文件 | 统一精简（AGENTS.md 6-7KB 可接受，但去掉冗余段落）| 降低遵守成本 |

## 4. 三项目规则一致性

```
WORK-LAB：AGENTS.md（五维基线+单写者+审批）——规则最多
ArcheAxis：AGENTS.md 6KB（知识项目规则）
DESIGN-LAB：无 AGENTS.md（靠 README）——缺统一执行规则
→ 建议：三项目规则对齐（精简版通用规则 + 各项目特有规则），DESIGN-LAB 补执行规则
```

## 5. 状态

- 审计完成（实测）
- 待用户选择处理项（DESIGN-LAB 运行时副本 / ArcheAxis CI / 规则对齐）