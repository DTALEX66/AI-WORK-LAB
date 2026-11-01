# JSONL 数据丢失：read_file 去重

## 故障模式

当在 `execute_code` 中执行以下操作时：

```python
from hermes_tools import read_file, write_file
existing = read_file(path).get("content", "")
```

**如果同一文件的 `read_file` 在对话早期被调用过**，则第二次调用会返回：

```json
{"status": "unchanged", "message": "File unchanged since last read. The content from the earlier read_file result in this conversation is still current — refer to that instead of re-reading.", "dedup": true, "content_returned": false}
```

由于提供了 `"content"` 的默认值 `""`，调用 `.get("content", "")` 不会引发 `KeyError`——它静默地返回一个空字符串。然后，该智能体将 JSONL 视为空，写入仅新条目，并销毁所有先前条目。

## Hermes 会话中的真正恢复

记录于 `job_id=4cb922c18e8b`，`run_id=sleep-20260726-231058-r0`，周期 `O-008`（2026-07-27）。

### 步骤 1：从上下文重建

先前的活动日志条目仍然可以在对话上下文中通过更早的 `read_file` 工具结果中获得。从仍然在上下文的 JSON 字符串中逐字复制它们。

对于冗长的日志，写成一系列 `dict.append()` 调用，每个条目一个 dict（不是字符串构建，以避免引用/嵌套错误）。

### 步骤 2：写入临时文件并验证

```python
import json, os

content = "\n".join(json.dumps(e, ensure_ascii=False) for e in all_entries) + "\n"
tmp_path = ledger_path + ".tmp"

with open(tmp_path, "w", encoding="utf-8") as f:
    f.write(content)

# 验证：解析回并检查最后一个条目
with open(tmp_path, "r") as f:
    parsed = [json.loads(l) for l in f.readlines() if l.strip()]
print(f"Written {len(parsed)} entries, last={parsed[-1]['event']}")
```

### 步骤 3：原子替换（Windows 安全）

```python
os.replace(tmp_path, ledger_path)
```

**为什么是 `os.replace()` 而不是 `Path.rename()`：**
- `Path.rename()` 在目标已存在时会在 Windows 上引发 `FileExistsError`。
- `os.replace()` 在所有平台上覆盖现有目标，且在同一文件系统上是原子的。
- Git Bash 的 `mv` 也会正确处理覆盖。

### 步骤 4：最终验证

```python
with open(ledger_path, "r") as f:
    final = [json.loads(l) for l in f.readlines() if l.strip()]
print(f"Final ledger: {len(final)} entries, last={final[-1]['event']}")
```

### 步骤 5：清理

```bash
rm .hermes/sleep-mode/_recover_ledger.py
```

## 预防性变通方案

1. **终端读取：** 使用 `terminal("cat " + path)` 并在 `execute_code` 中解析其输出，而不是依赖 `read_file()`。
2. **单次读取 + 缓存：** 只读取日志一次，将内容保存在一个 Python 变量中，并在整个循环期间重复使用它。绝不重读。
3. **仅追加脚本（首选）：** 完全绕过读取。使用一个小的临时 Python 脚本，在追加模式下打开日志（`open(LEDGER, "a")`）：
   ```python
   import json
   entry = {"event": "cycle_done", ...}
   with open(".hermes/sleep-mode/activity.jsonl", "a") as f:
       f.write(json.dumps(entry, ensure_ascii=False) + "\n")
   ```
   通过 `terminal("python script.py")` 运行它。没有 `read_file` 调用 = 没有去重数据丢失。
4. **组合：** 通过 `terminal()` 读取，在 Python 中处理，通过 `terminal()` 使用一个小脚本写入。读取和写入都在终端中完成，不调用 `read_file`/`write_file`。
