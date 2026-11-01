---
name: regex-path-validation-pitfalls
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/regex-path-validation-pitfalls/SKILL.md
---

---
name: regex-path-validation-pitfalls
description: "Use when regex-validating paths/commands/URLs for safety."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [regex, validation, security, path-traversal, fail-closed, pathlib]
    related_skills: [project-data-boundary, stateful-workflow-security]
---

# 正则路径/命令/URL 校验的防御性陷阱

## 触发条件

当你要用正则去**校验路径、命令、URL、盘符、shell 参数**是否安全（fail-closed 拦截越界/注入/穿越）时加载。这三个陷阱是这类正则的共性缺陷，2026-08-14 在 `hermes-project-terminal-guard.py` 上一次性全部暴露（路径穿越绕过 + 含空格路径误拦 + scheme:// URL 误拦）。

## 三个陷阱

### 1. lookbehind 边界导致漏检（最危险，安全漏洞）

用 `(?<=[\s"'=<>:([{])` 之类限制匹配上下文，会**漏掉其他上下文中的危险模式**。

- 例：`RAW_PARENT_TRAVERSAL = re.compile(r"(?:^|(?<=[\s"'=<>:([{]))\.[\\/]")` 要求 `..` 前是空白/引号，导致路径**中间**的 `../`（`scripts/../../secret.txt`，前面是 `/`）漏检 → 可越界。
- **原则**：安全拦截的 lookbehind 宁缺毋滥。能去掉就去掉，让危险模式在任何位置都被命中（fail-closed 优先，宁可误拦不可漏拦）。去掉后必须验证不误伤合法形式（如 `git log A..B` 范围语法、`foo..bar` 文件名）。

### 2. 字符类截断导致误拦（干扰正常操作）

用 `[^\s"']+` 匹配路径段会**遇空格截断**，把含空格的合法绝对路径切碎误判。

- 例：`"D:/All projects/WORK-LAB/x.py"` 被截成 `D:/All`、`/All`，再误判为越界。
- **修复**：正则扫描层对"候选是项目/目标的前缀"（说明被空格截断）直接跳过，交给**精确解析器**（如 `shlex.split` 保留引号内空格的完整 token，或 `Path.resolve()`）做最终判断。
- **关键陷阱**：`Path.is_relative_to` 是**路径段**判断——`D:/All` 与 `D:/All projects` 的段是 `All` ≠ `All projects`，返回 False。字符前缀判断必须用字符串：`ntpath.normcase(ntpath.normpath(str(p)))` 后再 `str.startswith(...)`。

### 3. 前缀误吞（盘符 vs scheme）

短前缀正则（如 `[A-Za-z]:[\\/]` 匹配盘符）会**误吞**更长的合法形式（`https://` 的 `s://` 被当 `s:\` 盘符；`ABSOLUTE_PATH` 分支缺 `(?!/)` 把 `https:` 后的 `/` 当 POSIX 路径）。

- **修复**：前缀后加负向前瞻排除已知非目标形式，如 `[A-Za-z]:[\\\\/](?!/)`（`(?!/)` 排除 `//` scheme 分隔符）；各分支对齐同源正则（哪个分支已有 `(?!/)` 就补上缺失的分支）。

### 4. 消费侧连带后果：URL 里内嵌绝对路径会被拦（实测 2026-08-14）

这类 guard 不只拦裸绝对路径——`file:///D:/All%20projects/...` 这类**内嵌绝对路径的 URL** 同样命中 external_raw_* 规则（报 "child command contains an absolute POSIX path outside the Git project"）。两个功能等价的绕过，按场景选：

- **CLI 冒烟（原始命令里）**：改用**相对** `file:` URL（`file:.hermes/task-runtime/...`）——urllib `FileHandler` 对相对 file URL 按 cwd 解析并直接打开；download-manifest 里记录的就是该 URL，verify 不重新下载，不受影响。
- **测试代码内**：pytest 里用 `Path.as_uri()` 生成百分号编码的绝对 `file:///` URL——guard 只检查 raw 命令文本，不检查 Python 进程内部构造的字符串，且与真实用户路径行为一致。

**原则**：guard 拦的是「命令文本里出现越界绝对路径」，不是「进程不能访问项目内相对路径」；能在进程内构造的路径不要塞进命令行。

## 双向测试铁律

改这类校验正则后**必须跑"应拦 + 应放"双向矩阵**，单方向会漏掉一半：

| 方向 | 内容 |
|---|---|
| 应拦 | 越界绝对路径、`../`/`../../`/中间 `scripts/../../`、单独 `..`、shell 串联 `;`/`&&`/`$`、裸命令 |
| 应放 | git/pytest/项目内脚本、含空格绝对路径、scheme:// URL、`git log A..B` 范围语法、相对路径、相对 `file:` URL（`file:.hermes/...`，消费侧合法绕过） |

验证方法：用 `importlib.util.spec_from_file_location` 直接加载校验脚本，构造 payload 调 `validate()`，逐个断言"是否拦截"是否符合预期；再做一次真实端到端（真实工具调用应拦的确实拦、应放的确实放）。

## 记住

- 安全校验正则改完**即时生效还是需重启取决于执行方式**：脚本是每次调用 spawn 的独立进程（从磁盘重读）→ 即时生效；脚本在进程启动路径里注册 → 需重启。改完主动说明，别让用户问。
- 同类校验部署在多处（多项目/多机器），一个 bug 会跨项目复制；修完把通用模式沉淀成可复用的 skill/reference 随同步传播。
