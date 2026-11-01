# Windows 文件系统操作与搜索工具怪癖补充（validated 2026-08-14, ArcheAxis-Knowledge-OS AXW-CAP-501）

## 1. `os.replace(src, dst)` 在 Windows 上是原子的"整目录移动"（validated 2026-08-14）

`os.replace` 移动**整个目录**在 Windows 上可用（MoveFileEx 语义），前提是
**目标不存在**。无需 `shutil.move`——同卷目录迁移直接用：

```python
os.replace(staged_dir, target)   # staging/<id> → installed/<plugin_id>@<version>
```

（ArcheAxis Capability Store v1 的 stage→activate 原子迁移即此实现，10 项测试含
篡改拒绝全部通过。）

要点：
- 仅限**同卷**；跨卷会抛错（比 `shutil.move` 的静默 copytree+rmtree 回退更"响"）。
- 目标已存在必须**先检查再抛领域错误**（`raise CapabilityStoreError(...)`），
  不要依赖 `os.replace` 覆盖目录（Windows 上目录替换不可靠）。
- 比 `shutil.move` 优越：原子（无半拷贝窗口）、失败大声。做 staging/installed
  分区迁移、包管理器安装这类"移动即生效"的场景优先用 `os.replace`。

## 2. search_files 对含空格路径的两种失败形态（补充 hermes-tool-spaced-path-quirks.md）

既有参考记录了静默 `total_count: 0` 形态；2026-08-14 晚还出现**显式报错**形态：

```
Search failed: rg: /d/All projects/ArcheAxis-Knowledge-OS/app: IO error for
operation on ... 系统找不到指定的路径 (os error 3)
```

同一根因（rg 处理不了含空格路径），同样处理：改用数据边界 wrapper 单命令
`... run -- grep -n <pat> <file>` / `ls`，不要重试 search_files。
判断顺序不变：先 `file`/`ls` 确认真实状态，再决定用什么工具。

## 3. 相关：read_file 误判 binary 时 sed 分页读

见 `hermes-tool-spaced-path-quirks.md`：`app/main.py`（UTF-8 + CRLF）被 read_file
拒绝为 "Binary file"，wrapper `file` 明确报 UTF-8 文本。读取用
`... run -- sed -n '1,60p' <file>`；**编辑不受影响**，`patch` 工具正常 replace
（CRLF 也能匹配，lint 正常）。
