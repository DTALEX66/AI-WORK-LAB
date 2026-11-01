# 原生任务与资产工作台读回交接

状态：IMPLEMENTED_LOCAL / TESTED_LOCAL；不是 M1、复杂参考复刻或正式发布完成。
基于 `4b372e204da297fd1547984c5ac1f3a6c6311763` 加本次查询与 UI 变更。
该基线 CI `34153076373` 已直接读回 completed/success；本次提交 CI 必须另验。

## 实现与边界

- 同一项目任务查询包含 image-import、photoshop-native、illustrator-native，仍从现有 operation/attempt 数据库读取，不暴露请求、授权正文、幂等 key 或 receipt。
- 新增 `/api/projects/<project>/native-assets` 和 `/<native-asset>/verify` 只读接口。列表仅为数据库元数据；显式 verify 才重新读取文件、检查项目归属、路径、大小、链接、修改状态及 SHA-256。
- 仍使用 loopback、Host、Origin 和 Bearer 门。跨项目资源拒绝，文件篡改返回 409；没有任意路径读取、文件下载或原生 job 执行 POST。
- 工作台展示已登记 AI/PSD、持久化任务和事件，点击校验后展示 HASH_VERIFIED。rights 固定 NOT_REVIEWED，明确不等于人工接受或本次宿主重开。
- 当前只展示每项资产最新 ACTIVE 版本；未提供版本选择、完整多文件交付包、原生提交、对象 patch 或取消对账入口。不同请求返回顺序的同项目 UI 竞态尚未专项处理。

## 本轮实际验证

解释器 `.venv/Scripts/python.exe`，Pillow 12.3.0；以下命令均从仓库根执行：

```text
python -B -m unittest discover -s design-lab/tests -p test_service_http.py
python -B -m unittest discover -s design-lab/tests -p test_workbench_native_ui.py
python -B -m unittest discover -s design-lab/tests -p test_native_tasks.py
node --check apps/workbench/main.ts
```

分别 19、1、12 项 PASS，无 skipped；Node 语法检查退出 0。
HTTP 组含真实服务进程、SQLite、文件、重启、跨项目/未授权拒绝、篡改拒绝及分页游标；UI 单测执行实际 main.ts，DOM/fetch 为边界替身，不冒充浏览器。
安装解释器 `.project-local/task-runtime/workbench-installed/Scripts/python.exe -I -B` 的 HTTP 19 项另行 PASS。

最终 `python -B design-lab/scripts/verify_design_lab.py` 会话 43620 终态退出 0，`VERIFY_DESIGN_LAB=OK total=49 failed=0`；报告生成和 `--check` 均 PASS。统一检查不是全量 Python 单测，也不是本轮 Comfy 推理证明（其中历史 E3 文案不可提升本轮能力）。

Wheel：`.project-local/task-artifacts/native-workbench-wheel/design_lab-0.1.0a0-py3-none-any.whl`。
SHA256 `1352332ce3d4b13bb2424f0130ed0a341fa9dac02654b752df4c5461b9bff80e`；50 项，无缓存/运行目录污染；native_assets、http_service、task_queries、main.ts、index.html 与当前源文件逐字节一致。

内部浏览器真实测试连接已安装服务 `127.0.0.1:63902`：选择 READONLY UI QUALIFICATION，看到 photoshop-native SUCCEEDED、attempt 1 和 PSD v1；点击校验显示 210193 bytes、HASH_VERIFIED，SHA256 `b66d721b6d8f539cde4f2a5da686968bf08300f5bec59092fe558c5838b9e134`。任务明细显示 NEW→PENDING→RUNNING→RECEIPTED；页面刷新要求重新连接，连接并选择项目后记录仍存在。

此浏览器测试使用隔离合成数据库和先前真实 PSD 的副本，任务事件为专用种子，不是本轮新 Adobe 执行。测试根 `.project-local/task-runtime/native-browser-20260908/run-f0e22d36e0ae44408276c93e4462d052`，项目 ID `92167a04dda04d129f6df6e167aeac63`。测试页已关闭，服务通过原执行会话 67612 的 Ctrl-C 停止，无用户共享进程被终止。

先前测试遇到 Node 中文输出被 Windows 默认 GBK 解码的问题，测试捕获现显式 UTF-8；属于测试环境编码问题。旧内部浏览器 tab 已不存在，重新创建隔离页面完成验证，没有重启仍在运行的服务或凭旧 tab 错误推断宿主失败。

## 接续任务

保持 R3 ledger 为正式编辑源，R4.1 通过已有增量映射接入，不把旧 main 的未实现判断覆盖当前进展。
下一步是真实参考→对象计划→受控原生提交→两次局部修改→保存重开→完整交付包；查询与 hash 验证只是其中一环。
Comfy golden workflow、H3 许可与本地 15 秒内容分镜视频、复杂参考集、人类 Jury/rights/production/release 仍未完成；知识迁移延后。
本轮上传仅开发分支源码与交接，原生工程、隔离数据库和运行文件不进入 Git；main 合并及正式 release 不在本次上传范围内。
