# R3 本地工作台入口交接（2026-09-08）

## 范围与定位

本次交付是实际本机项目/参考导入/读回/任务历史入口，不是完整复刻产品。基于开发分支 `codex/r3-runtime-correctness` 的 `6e1b223009efaaabbf923e9011466b4f95b98ecf` 继续实现。R3 ledger 仍是唯一状态源；R4.1 附件只完成审阅，未被替换为新的任务真值。知识迁移继续延后。

## 实现

- `apps/workbench/`：中文页面、真实项目创建与选择、PNG/JPEG 导入、服务器内容读回、任务/事件分页、同幂等键重试。未接通的 AI/PSD 生成按钮明确禁用。
- `src/design_lab/workbench.py`：仅提供三个固定静态资源；优先读取 wheel 内资源，源码路径回退不依赖用户工程目录。
- 静态资源无需 Bearer，但保留 Host/Origin/Sec-Fetch-Site 限制；业务 API 继续鉴权。CSP、nosniff、no-store、no-referrer；无外部资源、无浏览器令牌持久化。
- `main.ts` 使用浏览器有效 JS 子集，作为 `/workbench/main.js` 原样响应。不是已完成 TypeScript 类型检查或构建系统迁移的声明。

## 已取得证据

1. 新增 HTTP 页面测试先因 401 失败，实现后通过。源码 HTTP 全套 17 项通过；本轮接回安装包测试进程 95633，终态 17 项、8.259 秒、OK、退出码 0。
2. 安装包测试通过 `DESIGN_LAB_QUALIFICATION_PYTHON` 启动项目内独立 venv 的 `python -I -B -m design_lab`，从非源码目录运行真实 HTTP 子进程。安装依赖按 uv.lock 导出清单校正；numpy 从首次解析的 2.5.3 校正为锁定的 2.5.2。
3. wheel 位于本地忽略路径 `.project-local/task-artifacts/workbench-wheel/design_lab-0.1.0a0-py3-none-any.whl`；SHA256 `d00dab7bac26a6d6ae0d7ee7c1ab4ca9ec4fdecc10bb1b8ab976457d07f3a4b8`。构建后检查 44 个归档项，三项 UI 资源与源文件字节一致，无 `.project-local` 或 `__pycache__` 项。wheel 未上传为 release。
4. 内部浏览器实际完成连接 → 新建“工作台端到端验证” → 选择合成 PNG → 导入 → 点击读回预览 → 查看真实任务三条事件。测试服务使用独立合成工程 `.project-local/task-runtime/workbench-browser-20260908`，当时端口 58904；端口不是持续可用承诺。
5. 输入/读回图像为 256×256 PNG，SHA256 `b957f69c5db42b973beb44d3e7b63de125002d396af99245ecf0cdde83846520`。事件时间 2026-09-07T17:16:56Z：NEW→PENDING→RUNNING→RECEIPTED。rights 显示 NOT_REVIEWED，没有替用户审批。
6. 刷新页面后令牌为空；重新连接并选择同一项目后资产和任务恢复；浏览器 console error 列表为空。未把截图或此合成图片升级为复杂参考复刻验收。
7. 本轮源码 HTTP 再验 17 项、7.795 秒、OK；`.venv/Scripts/python.exe -B design-lab/scripts/verify_design_lab.py` 新进程 47335 完成 `total=49 failed=0`、退出码 0。`node --check apps/workbench/main.ts` 与当前报告生成/`--check` 均退出 0。统一门里的历史 E3 文案不表示本轮重新运行过 Comfy 或模型。

## 限制与已遇到问题

- 单一启动器和安全令牌交付尚未完成；当前入口仍需服务启动步骤。
- Adobe/Comfy 尚未通过这个页面执行；没有对象编辑、任务取消写操作或原生导出入口。完整 AI/PSD 闭环、5–10 张复杂参考、小说分镜 15 秒视频均未完成。
- rapid double submit 在 file.arrayBuffer 等待阶段尚未被完整防重；同项目并行预览/事件请求没有逐请求序号屏障。不得把幂等重试等同于所有 UI 竞态已经覆盖。
- 手机布局、完整键盘导航、断网重试与分页交互未全面实测；TypeScript 类型检查 NOT EXECUTED。
- 浏览器 label 选择项目首次超时，重新观察 DOM 后通过 combobox role 选择成功；这是定位器失败，不是持久化恢复失败。
- 再次查询已结束的旧统一门进程 91213 得到 Unknown process id；本轮新运行统一门，不把句柄丢失当测试失败或成功。
- 根规则提及的 `scripts/workflow/execution_preflight.py` 当前不存在；使用实际 `.venv/Scripts/python.exe` 验证版本和 jsonschema/PIL/numpy imports，不声称不存在的脚本已执行。

## 下一步（原目标未缩减）

1. 为图像读取、防重和同项目响应乱序增加确定性前端测试，再接单一启动入口。
2. 将 Illustrator 原生对象装配/局部修改接入持久化任务协调器及工作台；补执行回执、重试、失败恢复与取消对账。
3. Photoshop 仍需真实 UXP 宿主执行和读回；现有 Node/结构测试不算 PSD 实机。
4. 恢复 5–10 张复杂、多类型参考的 rights、拆解、两次修改、重开读回及人工质量验证。复杂对象支持分层透明图，但不得整图贴底冒充可编辑复刻。
5. 独立推进 Comfy 视频与 H3 许可/资源资格；未通过前 fail closed，不静默替换成云端。

本文件随源码在开发分支交付；提交后的精确远端 SHA/CI 由真实 GitHub 读回确认。开发分支发布不表示 main 合并、正式 release 或全部任务完成。
