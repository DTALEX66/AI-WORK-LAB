# 工作流配置 + 技能调用机制审计（2026-08-23）

> 用户问题：①整个工作流配置规则技能审计 ②软件执行任务不先调用插件/技能直接开干。

## 1. 工作流模块规模（10-workflow/workflow-assistance）

| 项 | 规模 | 评估 |
|---|---|---|
| config | 17 文件 | 合理（六层配置 + 契约）|
| skills | 13 文件 / 72KB | 合理（WORK-LAB 核心技能：codex/github-*/model-switch/windows-dev 等）|
| scripts | **133 文件** | 偏多——大量一次性/历史脚本可能闲置 |
| tests | 111 文件 | 全量审计负担（上一轮已列）|

## 2. 核心问题：技能不被调用（直接开干）

### 根因链
```
1. Hermes skills 82 个 / 866KB，含大量 macOS/Apple 专用技能
   （apple-notes / apple-reminders / findmy 等）
   → Windows 机器上任务描述永不匹配 → 永不触发 → 白占空间

2. 技能触发 = frontmatter description 语义匹配任务
   → 无强制"先查技能"步骤，不匹配就静默跳过
   → 执行直接推理，技能形同虚设

3. 结果：维护了 866KB 技能 + 648 个 DESIGN-LAB 运行时副本，
   但执行时几乎不调用 → 纯负担，零收益
```

### 各软件技能调用现状

| 软件 | 技能库 | 触发方式 | 问题 |
|---|---|---|---|
| Hermes | 82 个（官方+WORK-LAB 13）| description 语义匹配 | macOS 技能永不匹配；无强制先查 |
| Codex | skills（17 个已归档）| AGENTS.md 引用/目录约定 | 引用弱，执行常不加载 |
| DSH | 会话 skill catalog（available_skills）| 任务名匹配 | 匹配后需手动调 skill 工具 |

## 3. 解决方案（两条腿）

### A. 精简（删白维护）
```
- Hermes skills：82 → ~25 核心（删 macOS/无关技能，归档 40-knowledge）
- 只留：Windows 相关 + WORK-LAB 13 个 + 实际会触发的
- DESIGN-LAB .hermes 648 副本：确认后清理
```

### B. 强制调用（先查技能再干）
```
各软件执行任务前，加一个强制步骤：
  1. 扫描可用技能清单（description）
  2. 匹配当前任务
  3. 命中 → 加载技能指令再执行
  4. 未命中 → 直接执行（不阻塞）

落地：
  Hermes：pre_tool_call hook 或 SOUL.md 指令（任务开始先列相关技能）
  Codex：AGENTS.md 明确"执行前先查 skills/"
  DSH：已有 skill 工具（会话 catalog）——强化"任务匹配即调 skill"
```

## 4. 审计结论汇总（三层全部）

| 层 | 主要负担 | 处理 |
|---|---|---|
| 全局（跨软件）| Hermes skills 866KB + 全量质量门 + bundle-skew 过频 | 精简 + 分层 + 降噪 |
| 项目级（三项目）| DESIGN-LAB 6MB 副本 + ArcheAxis CI 108 steps | 清理副本 + CI 分层 |
| 工作流模块 | scripts 133 + tests 111 全量 | 归档闲置脚本 + 测试分层 |
| 技能调用 | 不先查技能直接干（白维护）| 精简 + 强制先查机制 |

## 5. 状态

- 审计完成（三层 + 技能调用机制）
- 待用户选择执行项