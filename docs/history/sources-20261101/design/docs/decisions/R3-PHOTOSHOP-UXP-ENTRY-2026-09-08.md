# Photoshop UXP 原生入口增量与启动阻塞

基线：`a39726be2ebe34245a3397a717649b61bb800c1d` 加本次工作区修改。
本项状态：IMPLEMENTED_LOCAL、隔离测试通过；HOST_LIVE = NOT_EXECUTED。
不代表 R3-12、完整 PSD 复刻或用户验收通过。

## 本次启动实测

Computer Use 的 `list_apps` 返回 Adobe Photoshop 2025，isRunning=false、windows=[]。
以返回的 app id 调用 `sky.launch_app`，得到
`accessibility window-opened handler did not become ready`。
后续 `list_windows` 未发现 Photoshop 窗口，`Get-Process -Name Photoshop` 未发现进程。
这与此前记录同类，归为 AUTOMATION_LAUNCH_FAILURE，不推定软件未安装或产品图层操作失败。
未重装、未修改权限/安全设置、未杀共享进程、未读取 Adobe 私有状态。

## 当前入口合同

实现位置：`integrations/hosts/adobe/photoshop-reconstruction/index.js`。
`executeJob(job, approvedFolder)` 要求调用方提供真实 UXP Folder 对象，不能从 job 自己构造授权。
它的根必须与 job.runRoot 相同；只创建该目录下尚不存在的简单 ASCII `.psd` 文件名。
既有文件采用不区分大小写拒绝，createFile 使用 overwrite=false。
所有文档修改均在 executeAsModal 内；输入先校验再快照，进入 modal 后重新校验。

当前 job 闭合字段：`runRoot,outputName,width,height,layers`。
尺寸是 1–16383 整数像素，RGB、72 ppi、透明底；1–100 个图层请求。
当前仅 text 记录：`{id,kind:"text",contents,fontSize}`，ID 唯一、文字非空且不超过 10000 字符。
字体大小 1–1296；其余层类型和未知字段均拒绝，不静默贴底或丢弃。
字体选择、定位、样式、位图、组与蒙版还未实现，不是任意参考图拆解器。

产品调用 app.createDocument → createTextLayer → saveAs.psd → closeWithoutSaving → app.open。
读回验证文档原生路径、宽高及每个指定名字的唯一文字层/文字内容。
`NATIVE_READBACK` 只表示该次调用实际完成上述检查，不提升账本/能力等级；结果含新文档 ID、输出路径和已检查文字数。
默认空层是否保留、字号/位置/颜色、完整图层数和像素预览仍需真实宿主验证。
成功后保留新打开的任务文档供编辑；失败保留任务文档 ID 与输出路径，供协调器对账。
绝不以失败后删除/关闭用户文档“清理”状态。创建的空输出也可能作为失败残留保留。
调用方还必须补 rights、输入来源、attempt/租约、文件哈希、审批与崩溃恢复；本入口不是可直接部署的完整插件 UI。

## 证据与回归

`test_photoshop_runtime_entry.py` 在 Node VM 运行实际模块，仅 Photoshop/UXP 边界为 doubles。
最初断言得到 NOT_EXECUTED 而非 NATIVE_READBACK（RED），实现后通过（GREEN）。
正向验证真实模块选择创建/文字/保存/关闭/重开分支与返回的重开 ID。
14 个拒绝场景要求零创建/写入；另验证错误文字读回拒绝、保存异常和写入中取消保留任务句柄且不继续重开。
这些是隔离行为测试，不能证明 Adobe 宿主 API 兼容或 PSD 内容正确。
两个既有 `test_reconstruction_photoshop_adapter.py` 静态测试也通过。
统一门 `design-lab/scripts/verify_design_lab.py` 本轮 session 70197 终态为 49 PASS，退出码 0。
报告生成及 `generate_current_reports.py --check` 通过；只证明绑定输入完整性，不代表当前云端或宿主验收。

本次查阅 [Adobe Document API](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/document)
与 [Photoshop app API](https://developer.adobe.com/photoshop/uxp/2022/ps-reference/classes/photoshop)。
createTextLayer 从 24.2 起提供，所以 manifest 最低宿主从 23.5 调整到 24.2，入口也在副作用前检查版本。
这只支持 API 选择，不是安装/运行成功证据。

## 下一步

1. 在可启动 Photoshop 的受控会话里加载项目 UXP 桥，补真实文件 token、PSD 保存重开与异常测试。
2. 扩展原生位图/组/蒙版、字体定位和独立对象 patch；实现两次修改后的读回/预览/恢复。
3. 与产品服务的 operation/attempt/asset 事务连接，再进行 5–10 类复杂参考图质量验收。
4. 启动阻塞只限制 Photoshop 实机线，不阻塞 Illustrator、服务/工作台、Comfy 的其他可执行工作。

知识迁移仍延后；本次不改 R3 定义或伪造 host_live 证据，不写仓外运行数据。
