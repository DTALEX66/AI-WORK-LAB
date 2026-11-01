# DESIGN-LAB 执行错误总结与经验（2026-09-05）

> 记录本执行周期（DL-TP-20260904 + PR115 审计整改 + MULTIMODAL T01–T18 DEEPSEEK 侧）遇到并修复的错误，供后续执行与 CODEX 交接参考。每条：现象 → 根因 → 修复 → 教训。

## 环境/工具类

1. **`pwsh` 工具实为 Windows PowerShell 5.1，非 PowerShell 7**
   - 现象：DSH `pwsh` 工具进程 `$PSVersionTable.PSVersion` = 5.1（powershell.exe）。
   - 根因：DSH Desktop 固定以 5.1 启动 shell 工具，会话内无切换项。
   - 修复：约定 PowerShell 7 全路径 `C:\Users\ALEX\AppData\Local\Microsoft\PowerShell\7\pwsh.exe`，复杂脚本写 `.ps1` 用 `-File` 调用（避免 5.1/7 引号嵌套差异）。
   - 教训：不要假设工具名 `pwsh` 一定是 PowerShell 7；跨版本脚本先落盘再 `-File`。

2. **SSH push 到 ssh.github.com 需显式 443 端口**
   - 现象：`git push git@ssh.github.com:...` 报 "Host key verification failed"。
   - 根因：scp 风格 URL 走默认 22 端口，而 known_hosts 只登记了 `[ssh.github.com]:443`。
   - 修复：`git push ssh://git@ssh.github.com:443/DTALEX66/DESIGN-LAB.git <branch>`。
   - 教训：GitHub 走 ssh.github.com 时必须写显式 443 URL。

3. **CRLF/LF 归一化破坏字节冻结文件的 sealed hash**
   - 现象：history CSVs 提交后 hash 与 baseline 不一致。
   - 根因：`* text=auto eol=lf` 把 CSV 从 CRLF 归一为 LF。
   - 修复：`.gitattributes` 对两份 CSV 加 `binary`（`-text`）冻结字节，重新 add 后 hash 与 sealed 一致。
   - 教训：任何 hash 封存的字节产物必须显式 `-text`/binary，避免归一化漂移。

4. **PowerShell 5.1 数组字面量跨行解析失败**
   - 现象：`@(; 'a',; 'b')` 报 MissingExpression。
   - 根因：5.1 对 `;` 分隔的多行数组字面量解析差异。
   - 修复：改为单行逗号数组 `"a","b"`。
   - 教训：复杂命令优先 pwsh7 `-File`。

## 代码/契约类

5. **sealed-bundle 检查是死代码**
   - 现象：PR115 审计 F05 指出 `check_sealed()` 位于 `raise SystemExit(main())` 之后，0 调用者。
   - 修复：把 seal 校验接入生产 `_promote`（before_swap/after_promote 重算 seal + `_after_backup` seam），verifier 改用生产函数。
   - 教训：任何"已实现"声称必须验证可达性（调用点+测试），不能只"文件存在"。

6. **manifest ref gate 读错结构**
   - 现象：F07 指出 `check_ref_safety` 读 `capabilityFamilies[].capabilities[]`，实际 manifest 用 `paths[]` → 0 引用被扫，str 结果还会崩 print_results。
   - 修复：按真实结构重写，复用 Result/require_path。
   - 教训：引用门必须对真实 schema 结构写正/负 fixture，且结果类型一致。

7. **`.hermes` 运行根迁移遗漏重建主链**
   - 现象：F06 指出 contracts/intake/render/evidence/state 仍写 `.hermes/task-runtime/reconstruction`。
   - 修复：新增中央 resolver `runtime_roots.py`，主链+夹具统一迁移 `.project-local`，旧路径负例测试。
   - 教训：迁移必须 `rg` 全量搜索残留，不能只改入口文件。

8. **模型缓存就绪判定过保守（blobs 目录误判）**
   - 现象：faster-whisper 已下载 145MB 却被判 INCOMPLETE。
   - 根因：HF 新版缓存把真实字节放 `snapshots/`，`blobs/` 可空；原判定依赖 `blobs/` 非空。
   - 修复：READY 改为"snapshots 下存在非零字节文件"。
   - 教训：探测判据要基于"真实字节存在"，不基于目录名/布局假设。

9. **测试隔离运行器 discover 路径与模块过滤不匹配**
   - 现象：`--modules design_lab.runtime.asset_store` 导致 ran:0。
   - 根因：discover 的 top_level_dir 使 test 类 `__module__` 是 `test_asset_store` 而非源模块名。
   - 修复：同时按 test 文件名（file_key）与 module_key 过滤。
   - 教训：unittest discover 的模块命名空间与源包路径不同，过滤要做双键匹配。

10. **运行期编辑文件导致"脏树自伤"假失败**
    - 现象：reconstruction evidence 三序中 forward 报 1 error+1 failure，reverse/random 全绿。
    - 根因：forward 运行期间仍在编辑/提交测试文件，执行源闭包对比 HEAD blobs 失败。
    - 修复：静止树上重跑 forward 通过。
    - 教训：跑长测试（尤其执行源闭包校验类）前必须冻结工作树，避免边跑边改。

## 状态纪律类

11. **进度账本口径夸大**
    - 现象：PR115 审计 F10 指出"31/58""15 new tests""49-chain 全绿"等不可复核。
    - 修复：账本改为 evidence 式，区分 DONE_VERIFIED / PARTIAL / SCHEMA_DRAFT / REGISTER_ONLY / BLOCKED_RUNTIME。
    - 教训：进度只记可验证证据；"仅实测可标已验证"，宿主侧一律"待实机"。
