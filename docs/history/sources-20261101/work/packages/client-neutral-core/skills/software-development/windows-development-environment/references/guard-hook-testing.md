# guard hook 测试手册（hermes-project-terminal-guard.py）

validated 2026-08-14（云端 #92/#97 升级后实测）。

## payload 结构（#92 起）

guard 是 `pre_tool_call` hook，直测用 importlib 加载 + 构造 payload：

```python
import importlib.util, os
os.environ['HERMES_HOME'] = 'C:/Users/ALEX/AppData/Local/hermes'
spec = importlib.util.spec_from_file_location(
    'guard', f"{os.environ['HERMES_HOME']}/bin/hermes-project-terminal-guard.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

def call(cmd, workdir='D:/All projects/WORK-LAB'):
    payload = {'tool_name': 'terminal', 'tool_input': {'command': cmd, 'workdir': workdir}}
    return g.validate(payload)   # None=放行, str=BLOCK 消息
```

⚠️ **先读源码确认 `validate` 签名**：旧版是多位置参数（`validate(cmd, workdir, root, home, ...)`）；#92 起改为 `validate(payload: dict) -> str | None`。用错签名直接 `TypeError`，会误报"全失败"（2026-08-14 曾因此误判 19/19 回归失败，实为测试方式过时）。

## wrapper 形式命令构造

回归测试必须用 wrapper 形式——裸命令（`git`/`curl`/`python`）会被 wrapper 强制拦，那不是 bug 而是设计：

```python
WRAPPER = f"{os.environ['HERMES_HOME']}/bin/hermes-project-data.py"
def wrap(child): return f'python "{WRAPPER}" --project . run -- {child}'
```

## 23 项回归矩阵（2026-08-14 全通过）

### A. wrapper + child 越界（应拦 7）

| 用例 | child |
|---|---|
| E盘越界 | `cat E:/server/x.txt` |
| C盘越界 | `cat C:/Windows/win.ini` |
| 穿越（中间../） | `cat scripts/../../secret.txt` |
| 穿越（开头../） | `cat ../secret.txt` |
| 穿越（带引号） | `cat "D:/All projects/WORK-LAB/../secret.txt"` |
| UNC | `type \\\\server\\share\\file` |
| POSIX越界 | `cat /etc/passwd` |

### B. wrapper + child 正常（应放 9）

| 用例 | child |
|---|---|
| git status | `git status` |
| https URL | `curl -sI https://example.com` |
| http URL | `curl -s http://example.com` |
| git clone https | `git clone https://github.com/foo/bar` |
| pytest | `pytest tests/ -q` |
| 项目内脚本 | `python scripts/test.py` |
| 相对路径 | `ls .` |
| pip install | `pip install requests` |
| 含空格项目内路径 | `python "D:/All projects/WORK-LAB/tools/x.py"` |

### C. wrapper 层校验（应拦 5）

| 用例 | 命令 |
|---|---|
| 裸命令 | `git status` |
| 非 python 调用 wrapper | `"C:/.../hermes-project-data.py" --project . run -- git status` |
| 错误 wrapper 名 | `python other.py --project . run -- git status` |
| 缺 `--project .` | `python "<wrapper>" run -- git status` |
| 外层 shell 串联 | `git status && git log` |

## 常见误区

1. **旧多参数签名调用** → TypeError。先读源码确认签名再测。
2. **用裸命令测"应放"** → 全被 wrapper 强制拦，误判 guard 回归。所有用例走 wrapper 形式。
3. **live guard 可能被并行会话更新**：多 Hermes 会话并行时，别的会话可能 push 新版并同步 live。测试前先确认 live==repo（`sha256` 对比，注意 CRLF 规范化 `\r\n→\n`）再跑矩阵。
4. **URL 误判已在 #90 修复**：`https://` 不应再被当盘符 `s:\`；若 URL 仍被拦，查盘符正则是否丢了 `(?!/)`。
5. **guard 改动即时生效**（每次 terminal 调用 spawn 新进程从磁盘重读），无需重启；区别于 `web_server.py` 启动路径补丁（需重启）。
