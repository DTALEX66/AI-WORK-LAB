# 三项目会话历史归档（2026-08-20）

> 汇总 HERMES + CODEX + DSH 三个软件的会话记录与历史文档，去重去冗余，按项目保留完整时间节点历程。

## 结构
- timeline-ALL.md — 三项目总时间线（229 节点，CODEX/DSH/HERMES 聚合）
- <项目>/timeline.md — 各项目会话历程时间线
- <项目>/docs/ — 该项目交接/决策/审计等历史文档（内容哈希去重）
- timeline-raw.json — 原始时间线数据（机器可读）

## 来源与统计
| 软件 | 会话数据 | 归档方式 |
|---|---|---|
| CODEX | 227 线程（state_5.sqlite）| 时间线索引（raw rollout 111MB 引用原路径，不复制）|
| DSH | 69 会话（dsh-home/sessions）| 时间线索引（raw 65MB 引用原路径）|
| HERMES | 76 转储（hermes/sessions）| 时间线索引（raw 转储引用原路径）|
| 三项目文档 | WORK-LAB 50-taskpacks + AA cross-project + DL project-memory | 去重复制（文档）|

## 原始数据位置（raw 不复制，引用）
- CODEX: C:\Users\ALEX\.codex\sessions + state_5.sqlite
- DSH: D:\All projects\DSH\deepseek-harness\dsh-home\sessions
- HERMES: C:\Users\ALEX\AppData\Local\hermes\sessions

## 原则
- 时间节点 = 会话/文档时间戳聚合（不改变原始数据）
- 去重 = 内容 SHA-256 哈希（文档）
- 去冗余 = 排除 node_modules/dist/build/cache
- 去过时 = 保留全部时间节点（历史完整），不删旧记录
