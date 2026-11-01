# 视觉质量校验的运行根剪枝修复

状态：IMPLEMENTED_LOCAL / TESTED_LOCAL；完整统一门 49 PASS / 0 FAIL，CI 未重跑。

基于开发分支 `codex/r3-runtime-correctness`、基线 `a97e951b01d575b774d0ca81939cc365bcfec96a` 接续。用户已授权继续全量推进；本项处理 R3-04 新失败，也属于 R4.1 DL-R4-003 的增量，不重置旧账本或历史证据。

## 根因与修复

`design-lab/scripts/verify_visual_quality_v21.py` 使用全仓 `rglob('*.json')`，在判断路径前进入运行环境及私有目录。Paddle 依赖中的调优文件因此被误当源码 JSON，既污染校验结论又扩大读取范围。

改用 top-down walk，进入子目录前剔除 `.project-local`、旧 `.hermes`、依赖环境、Git 和已知私有状态名称；JSON 凭据名称也不读取。活动树中的链接/reparse 记录为错误，不跟随。目录读取和普通源码 JSON 解析失败仍会导致失败，新的源码目录不被默认排除。不修改依赖，不删除环境求绿。

## 已执行证据

解释器：`D:/All projects/DESIGN-LAB/.venv/Scripts/python.exe`，Python 3.13.14；标准库 unittest，无新依赖。项目没有 `scripts/workflow/execution_preflight.py`，使用精确解释器导入和版本检查替代，不虚构该脚本已执行。

- RED：新增合成夹具三项回归，2 PASS / 1 FAIL；失败为原校验器读取 12 个运行/私有合成 JSON。没有读取实际凭据。
- GREEN：同三项回归全部 PASS；audit hook 确认被排除目录没有被 scandir 枚举。
- 后补原生链接回归后：4 项中 3 PASS / 1 SKIP。Windows WinError 1314 不允许本次创建 symlink；未提权，所以不宣称本机链接拒绝实测通过。
- 真仓定向命令：`.venv/Scripts/python.exe -B design-lab/scripts/verify_visual_quality_v21.py`，输出 `ERRORS=0`、`VERIFY_VISUAL_QUALITY_V21=OK`。
- `git diff --check` 通过。
- 完整统一门：`.venv/Scripts/python.exe -B design-lab/scripts/verify_design_lab.py`，执行会话 90197 终态 exit 0，`VERIFY_DESIGN_LAB=OK total=49 failed=0`。其中 Open Design repository verifier 为 `total=549 failed=0`；这是静态/受控仓库检查，不是打开 Open Design 软件。旧 Comfy 门打印的历史 E3 文案也不能当作本次模型运行证据。

测试：`design-lab/tests/test_visual_quality_scan_boundary.py`。其测试目录和合成输入仅在 `.project-local/task-runtime/visual-quality-boundary-tests/` 内，测试自行回收自己的夹具。

## 限制与接续

本修改针对全仓通用 JSON 扫描；固定研究文件和 atom/scenario 路径的直接加载尚未做统一 ancestor-reparse 硬化。原生 Windows 链接测试受权限限制。不要将本定向结果提升为全项目所有入口已隔离。

完整统一门已读回终态。正式 ledger 仍保留先前 47 PASS / 2 FAIL receipt，下一次追加新 receipt，而不是覆盖旧失败。报告提交自引用漂移仍未修复。第一次统一门调用的会话元数据未被工具包装保留，确认其进程结束后重新执行了上述可读回的 90197；不使用丢失结果的运行作通过证据。
