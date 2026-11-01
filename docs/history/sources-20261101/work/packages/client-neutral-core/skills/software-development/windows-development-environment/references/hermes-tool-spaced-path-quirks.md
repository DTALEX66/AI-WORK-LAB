# Hermes 工具在含空格 Windows 路径上的怪癖（validated 2026-08-14, ArcheAxis-Knowledge-OS）

`D:\All projects\...` 这类含空格的项目根会静默破坏两个 Hermes 读取工具，症状像"项目没文件"：

## search_files 静默返回 0（或直接报 IO error）

对 `path="D:\\All projects\\ArcheAxis-Knowledge-OS"` 的 `target=files` / `target=content`
搜索（`pattern="*"` / `pattern="*.py"`）有两种失败形态：

1. **静默空结果**：返回 `total_count: 0`，无任何报错——既不是"没匹配"，也不是路径不存在。
2. **显式报错**（2026-08-14 又见）：`Search failed: rg: /d/All projects/...: IO error for operation on /d/All projects/...: 系统找不到指定的路径 (os error 3)`——这是同一根因（rg 无法处理含空格路径）的报错形态，不是路径真的不存在。

两种形态都别信。验证改用数据边界 wrapper 单命令：
  `python "C:/Users/ALEX/AppData/Local/hermes/bin/hermes-project-data.py" --project . run -- ls <dir>`
  `... run -- grep -rn <pattern> --include=*.py <子目录>`（逐目录搜）
- 无 wrapper 场景（本机 Hermes 项目工具）也优先 `ls`/`grep`/`sed`，不要反复重试 search_files。

## `find` 在含 GBK 文件名树里 UnicodeDecodeError 崩溃

`find <dir> -maxdepth N -type f`（经 wrapper）在含非 UTF-8（GBK）文件名的目录树里，
stdout 解码线程抛 `UnicodeDecodeError`（`'utf-8' codec can't decode byte 0xb2...`），
整个命令 exit 2、结果全丢。改用 `ls <具体目录>`（wrapper 内）逐层看，不要 find 全树。

## read_file 把普通 UTF-8 Python 误判为 "Binary file"

25KB 的 UTF-8 Python（app/main.py，CRLF 行尾）被 read_file 拒绝：
`error: "Binary file - cannot display as text"`，而 wrapper 内 `file app/main.py` 明确报
`Python script, Unicode text, UTF-8 text executable`。

- 读取：wrapper `sed -n '1,60p' <file>` 分页读（`sed` 是单命令，不触发 chaining 拦截）。
- **编辑不受影响**：`patch` 工具对同一文件正常做 replace（CRLF 行尾也能匹配），改完语法 lint 正常。
- 判断顺序：先 `file` 确认真实类型，再决定用 sed 还是换编码读；不要直接认定文件损坏或 UTF-16。

## 通用规则

任何"目录空 / 文件读不了"的怀疑，先用 wrapper `file` / `ls` 验证再下结论；
本机所有 Hermes 项目工具调用优先走 wrapper 单命令，而非 search_files。

## 相关参考

- 数据边界 wrapper 的 chaining 禁令（连 `| head` 也被拦）见 project-data-boundary 技能。
- CRLF 相关（read_file binary 误判与行尾翻译）见本技能 7 节 `Path.write_text on Windows translates \n to \r\n`。
