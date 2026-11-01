# guard.py 正则防护三缺陷修复归档（2026-08-14）

## 背景

用户要求对 `pre_tool_call` 终端守卫（`hermes-project-terminal-guard.py`）做多角度、多维度测试，确认两件事：
1. **防护有效**（E盘访问、数据外溢、路径穿越确实被拦）；
2. **不干扰任何项目的正常操作**（该放行的确实放行）。

测试方法：直接构造 payload 调用 `guard.validate()`，覆盖「应拦 + 应放」双向矩阵。

## 发现的三个缺陷

### 缺陷 1：路径穿越绕过（严重安全漏洞）

**现象**：`cat scripts/../../secret.txt`、`cat ./../x`、`ls ..`、`cat ..` 全部**放行**，可越界读取项目外文件。

**根因**：`RAW_PARENT_TRAVERSAL` 的正则用了 lookbehind `(?<=[\s"'=<>:([{])`，要求 `..` 前面是空白/引号/括号。路径**中间**的 `../`（前面是 `/`，如 `scripts/../`）不满足 lookbehind，漏检；单独的 `..`（后面无斜杠）也不匹配 `\.\.[\\/]`。

**修复**：去掉 lookbehind，改为 `\.\.(?:[\\/]|(?=[\s"']|$))`，让 `../`、`..\` 及单独 `..` 在任何位置被检测。验证 `git log A..B` 范围语法、`foo..bar` 文件名不误伤。

### 缺陷 2：含空格路径误拦（干扰正常操作）

**现象**：项目内 `python "D:/All projects/WORK-LAB/x.py"` 被误判越界。

**根因**：`RAW_WINDOWS_ABSOLUTE_PATH`、`RAW_POSIX_ABSOLUTE_PATH`、`ABSOLUTE_PATH` 三个正则都用 `[^\s"']+` 匹配路径段，遇到空格截断，把 `D:/All projects/...` 截成 `D:/All`、`/All`，再误判为项目外路径。

**修复**：
- `external_raw_windows_path` / `external_raw_posix_path` 对「candidate 是项目字符前缀」的情况跳过，交给 `external_child_path` 精确判断；
- `external_child_path` 优先用 shlex 完整 token（引号内空格保留）精确判断；
- 注意 `Path.is_relative_to` 是**路径段**判断（`All` ≠ `All projects`），含空格前缀要用字符串 `startswith` 判断。

### 缺陷 3：scheme:// URL 误拦（干扰正常操作，比别的项目更严重）

**现象**：`curl https://example.com`、`git clone https://github.com/foo/bar`、`curl http://...` 全部**误拦**，所有 `scheme://` URL 都被当盘符路径。

**根因**：
- `RAW_WINDOWS_ABSOLUTE_PATH` 的 `[A-Za-z]:[\\/]` 把 `https://` 的 `s://` 误当盘符 `s:\`；
- `ABSOLUTE_PATH` 分支 3 缺 `(?!/)`，且 lookbehind 集合含 `:`，把 `https:` 后的 `/` 当 POSIX 绝对路径。

**修复**：盘符正则后加 `(?!/)` 排除 `//`（scheme 分隔符）；`ABSOLUTE_PATH` 分支 3 对齐 `RAW_POSIX_ABSOLUTE_PATH` 补 `(?!/)`。

## 测试矩阵（最终回归 41 项全通过）

| 维度 | 项数 | 结果 |
|---|---|---|
| 应拦：E/C/D盘、legacy spill、UNC、POSIX、file:// 越界 | 7 | 全拦 |
| 应拦：路径穿越（6 种变体） | 6 | 全拦 |
| 应拦：shell 串联/展开/裸命令 | 4 | 全拦 |
| 应放：URL（curl https/http、git clone、pip） | 5 | 全放 |
| 应放：git 操作、pytest、项目内脚本、含空格路径 | 9 | 全放 |
| 非 terminal 工具（read_file/search_files/execute_code/write_file） | 4 | 不受影响 |

端到端验证：真实 terminal 调用 `cat E:/server/x.txt` 返回 `PROJECT DATA BOUNDARY BLOCKED`；`curl -sI https://example.com` 真实放行返回 HTTP 200。

## 关键机制

guard.py 是每次 terminal 调用时 spawn 的**独立进程**（从磁盘重读脚本），因此改脚本**即时生效、无需重启**。这与 `web_server.py start_server()` 里注册 hook 的补丁（需重启进程）不同。

## 教训

1. **正则路径防护必须跑双向矩阵**：只测"应拦"会漏掉"误拦正常操作"（含空格路径、scheme URL）；只测"应放"会漏掉"漏拦越界"（中间路径穿越）。
2. **lookbehind 边界是漏检高发区**：要求 `..` 前是空白，会漏掉路径中间的 `../`；要求 `.` 前是特定字符，会漏掉所有其他上下文。
3. **`[^\s"']+` 截断是误拦高发区**：含空格路径是 Windows 常态，任何"遇空格停"的路径正则都会截断。
4. **盘符正则必须排除 `//`**：`[A-Za-z]:` 会误吞 `scheme://` 的 `s:`，加 `(?!/)` 是必要护栏。
5. **同源防护的 bug 会跨项目复制**：别的项目（ArcheAxis 等）部署同一套 `project-data-boundary` 会有完全一样的问题，修复经验应沉淀进 skill 随同步传播。

## PR 清单

| PR | 内容 | 合并 SHA |
|---|---|---|
| #89 | 路径穿越绕过 + 含空格路径误拦 | `734cb47` |
| #90 | scheme:// URL 误判 | `d3f060c` |

（skill 经验沉淀见 PR #88 `6711e28`。）
