# Illustrator 原生 COM 调度与安装包实测

## 本轮结果

已从“菜单选择脚本”推进到 **安装包内部适配器直接调用 Illustrator COM → 原生 JSX → 保存/重开/结构读回 → 文件 hash 封存**。未使用 GUI 点击、未改变 Adobe 安全设置、未安装插件或全局工具、未终止 Adobe。

基线为 `1d468722b246ba8a453ec1d791589fd3846a6da0`；该 SHA 的 CI `34148941597` 已确认 success。本轮提交需另行核验远端 CI。整体任务仍 PARTIAL，R3 ledger 是唯一任务真值。

## 接口与安全边界

`src/design_lab/adapters/illustrator_com.py` 提供内部接口：

```python
execute(job, *, project_root, approved_root, timeout=120)
```

- 固定调用仓库/安装包自带 `reconstruction-assemble.jsx`，job 用 ASCII JSON 字面量编码；没有接收任意用户脚本文本的 HTTP 入口。
- 显式项目根、run 根、封闭 root 字段和目标类型；文件必须在当前项目 `.project-local` 内并位于批准 run 下，不越过 reparse/hardlink 边界，不覆盖已存在输出。
- 入参深拷贝冻结；输入图像类型、帧数、像素预算、字节预算及调用前后 hash 校验；输出 AI/PNG/SVG 有独立 hash，PNG 尺寸读回，AI 要求 PDF-compatible 文件头。
- 对象、字体、蒙版等完整 host job 校验由固定产品 JSX 在建文档之前执行。Python preflight 不冒充所有宿主语义都已在本机外部静态通过。
- 子进程使用已安装 `powershell.exe -NoProfile -NonInteractive` 和 COM，不改 execution policy；程序文本走 stdin，不写命令行参数或日志。无凭据、无用户会话读取。
- COM 超时/异常、回执绑定不符、输入变化、输出缺失均不能成为成功。`outcome_unknown=True` 表示不能证明宿主没有副作用；不自动重试、不杀 Adobe、不删除部分工程。
- 回执绑定完整 job hash、RIR hash、bridge hash、宿主版本、输入/输出 hash 和前后文档数。只证明当前适配器读回，不替代 rights、单写租约、operation/attempt、独立质量或 release 证据。

仍需调用方持有宿主写租约。当前模块没有持久化 task queue、取消对账或接管崩溃任务；没有开放给网页直接提交任意 job。它是可调用、已实测的内部适配器，而非成熟服务闭环。

## 实机证据

首先通过 COM 只读查询实际返回 `Version=29.5.1, Documents=0`；随后 `DoJavaScript('app.version')` 返回 `29.5.1`，证明原生脚本入口可用。没有由 COM 名称或接口配置推测成功。

两轮均使用 `prepare_illustrator_lowered.py` 生成真实 builder payload，再通过产品适配器运行，不执行该目录的测试 `run.jsx`。输出根均在 `.project-local/task-artifacts/illustrator-lowering-20260908/`：

| 运行 | 目录 | 结果 |
|---|---|---|
| 源码适配器，进程 74110 | `run-e679ff5700754ada9e2459e0450aa8a1` | NATIVE_READBACK；Illustrator 29.5.1；文档 0→0 |
| 安装包适配器，进程 20480 | `run-9c4c7a833568400091e0df61f2e46697` | NATIVE_READBACK；Illustrator 29.5.1；文档 0→0 |

安装包运行用 `.project-local/task-runtime/workbench-installed/Scripts/python.exe -I -B`，cwd 是新 run 目录；实际模块路径为该 venv 下 `Lib/site-packages/design_lab/adapters/illustrator_com.py`，没有注入 repo/src 到子进程。

三轮预览（前轮 GUI 脚本、本轮源码 COM、本轮安装包 COM）PNG 字节一致：`cfebd891f3d146baec76c1706627a1894ca3ace1085efc9f711a62c3e389a7c1`，800×600 RGB。AI/SVG 包含宿主元数据，hash 不相同，不把预览一致宣称为原生二进制逐字节一致或复杂参考像素复刻。

安装包轮核心 hash：

- 完整 job：`87eaeb7317e3ebaf38eecd2d0038c38f5532125e847495a656f307501587fe7d`
- RIR 规范化内容：`8c133c3ed2473d0e236a6fc6dade84e26596f6a93f57c3833caecbcfc6d1083a`
- AI：`f8848d85613dbb073e6cf02da52effd80cc6842857cd3cc51cf8fc9e00c83bd5`
- SVG：`d44aa02f013416af71f564981d36c7eb2455b90953972ab895e96cc14790bd47`
- 输入 PNG：`b957f69c5db42b973beb44d3e7b63de125002d396af99245ecf0cdde83846520`
- com-readback.json：`f096c316fbdc8e5e9ee375be931d5638d57a1e0084a4bf6cebdb61a8e5af15d8`
- installed-qualification.json：`2d9c0de188bb54b9fc5f7dd05a1a02d24b1f38b2badc2a68dde1db7ac3c8e6ed`

源码轮 com-readback.json hash 为 `474ee94872bfaeab791264f3e3db57fbd9ab0a389cc4e2c19e8ee58c64e531e2`。回执和原生产物保留本地 ignored；SVG 可能嵌入字体，不上传这些素材。

## 构建与测试

- 适配器源码 SHA256 `869934ed79be8001fca6b5d341d080ba84a375f3e40a7a15e6b53601f677e178`。
- 桥源码 SHA256 `b1a7542d47fdcb0af2acb922654dc48f5904dde7f69fee2e7d7aa14916d1c48c`。
- wheel `.project-local/task-artifacts/illustrator-com-wheel/design_lab-0.1.0a0-py3-none-any.whl` SHA256 `9267a6184a60e2935f07e187bfd456d6dfad094884efd8af6b444642321fbfe6`，46 个归档项；桥资源逐字节等于仓库源码；无缓存或 `.project-local` 项。
- uv 构建提示 cache 在 source 下；已检查实际归档，不把警告忽略为没有污染证据。此 wheel 仅本地资格安装，未发布 release。
- 测试先观察适配器不存在的 RED，然后实现。`test_illustrator*.py` 合计 8 个方法 PASS，其中 COM 适配器 5 项在 COM 外部边界使用 double、文件校验为真实文件；这些单测不充当实机证明。
- 安装包 HTTP 17 项 PASS，8.095 秒；真实隔离 CLI 子进程验证服务、静态页面和鉴权仍工作。
- 统一门进程 97412：`total=49 failed=0`、退出码 0；报告生成/`--check` PASS。统一门历史 Comfy E3 文案不是本轮推理证据。

## 下一步与剩余目标

1. 将 RIR builder/校验资源纳入安装后的服务入口，保持源码兼容门面，不能把 RIR 静默替换为另一个手写 job。
2. 将 COM execute 接到持久化 operation/attempt/lease 与 asset publication，补异常/取消/重启对账，再启用工作台原生生成。
3. 对接参考图拆解和对象修正，完成 5–10 张复杂多类型真实参考以及两次局部修改/恢复；当前合成图不计入参考集验收。
4. Photoshop 实机、Comfy/H3 小说分镜 15 秒视频、Human Jury、rights、production 和 release 仍待完成；知识迁移继续延后。

COM 已证实可用，后续 Illustrator 自动调度不应继续重复昂贵菜单点击。PS 是不同宿主，不能据此假定它的 COM/UXP 链路已通过。
