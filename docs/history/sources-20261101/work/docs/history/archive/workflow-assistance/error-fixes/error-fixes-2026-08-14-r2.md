# R2 修复批次错误经验归档（2026-08-14）

范围：R2 云端重审计第一批~第三批修复（PR #97~#101）中发现的错误、根因、修复与防复发。
对应 Error Ledger：ERR-055~ERR-060（含本轮 R2 特有错误；其余见各 PR 记录）。

## 1. Guard 路径前缀修复的两连坑（P0-8）

### 坑 A：Windows 下 drive 映射 POSIX 路径
- **现象**：修复 `root_str.startswith(res_str)` 前缀绕过时，`external_raw_posix_path` 在 Windows 对 MSYS 风格路径（`/tmp/...`，来自 git-bash `TMPDIR=/tmp`）做 `Path(f"{drive}{full}")` 再 resolve，解析成完全错误的路径 → 内部含空格路径被误 BLOCK。
- **根因**：POSIX 路径在 Windows 无法可靠 drive 映射。
- **修复**：Windows 下改用规范化文本 + 分隔符边界比较（`ntpath.normcase(normpath(full))` 与 `root_norm + "\\"` 前缀），不 resolve。
- **防复发**：Windows 路径处理优先文本边界比较；resolve 仅用于同风格路径。

### 坑 B：同一路径被正则双匹配
- **现象**：`C:/Users/...` 被 ABSOLUTE_PATH 的 drive 分支和 POSIX 分支各匹配一次，第二次匹配起点在 `C:` 后（前一个字符是 `:` 不是引号）→ `_quoted_full_path` 无法恢复 → fail-closed 误 BLOCK 内部路径。
- **修复**：`_quoted_full_path` 向后扫描包围引号（片段不直接跟引号时也恢复完整路径）。
- **防复发**：正则多分支匹配同一文本时，恢复逻辑必须容忍非直接引号起点。

## 2. 第三方 Docker action 的 input 映射不可靠（P0-7/WLOSS-200）

- **现象**：`woodruffw/zizmor` action 在 CI 报 `zizmor==`（空版本）——Dockerfile 用 `ARG ZIZMOR_VERSION`，action.yml 未可靠映射 `inputs.version`；尝试 `uv tool run` 后 runner 无 uv；最终 `pipx run zizmor==1.29.0`。
- **防复发**：第三方 Docker action 的 input 映射不可靠时改用 shell 安装（pipx/uvx）；CI 工具安装优先本机已有运行时；`verify_supply_chain_tools.py` 已接受 pipx 形式并强制版本 pin。

## 3. schema 升级必须四方同步（WLOSS-000）

- **现象**：source-ledger v3→v4 只更新 JSON，遗漏 `contracts/source-ledger.schema.json`（const v3 + additionalProperties:false 拒绝新字段）、`verify_source_ledger.py`、`test_source_ledger.py`（entries==5）——CI integration 失败暴露。
- **防复发**：schema 升级一次更新：JSON + schema 文件 + verifier + 测试断言（含计数断言）。

## 4. SQL 查询引用不存在的表（composition root）

- **现象**：`max_watermark` 引用 `telemetry_samples`（实际表名 `telemetry_events`）；ad-hoc 验证时 sqlite3.OperationalError 暴露。
- **防复发**：新增 SQL 查询先核对真实表结构（`PRAGMA table_info`）。

## 5. 删除依赖时丢失 fail-closed 契约（第三批退役）

- **现象**：删 CanonicalProjectionReader 时连带删除"打开即校验文件存在"逻辑 → ObserverStore 不再抛 FileNotFoundError；旧测试断言暴露。
- **防复发**：删除依赖时保留其 fail-closed 契约，用既有测试反向验证。

## 6. 验证脚本自身 bug（meta-经验）

- ad-hoc 验证脚本的 `env = {..., **os.environ}` 顺序错误会覆盖 PYTHONPATH（子进程找不到模块）；unittest 输出在 stderr；断言用错方法名/路径——三处假失败。
- **防复发**：ad-hoc 脚本 `env = {**os.environ, ...}`（显式值在后）；断言前先跑通单个行为；区分"被测代码失败"与"验证脚本失败"。

## 7. PR merge 的 graphql 瞬断（操作经验）

- `gh pr merge` 多次报 `Post ".../graphql": EOF`，merge 实际可能成功或失败——**不要相信一次调用**，用 `gh pr view --json state` 确认，失败重试；merge 后 `git fetch && git pull --ff-only` 确认本地同步。

## 8. convergence check 的环境检测（check_9）

- cargo 检测用 `shutil.which("cargo")` 在 git-bash 找不到（PATH 无 ~/.cargo/bin）——需显式 `Path(os.path.expanduser("~/.cargo/bin/cargo.exe"))` 兜底。
- **防复发**：环境检测同时检查用户级安装路径（rustup 默认不在 PATH）。
