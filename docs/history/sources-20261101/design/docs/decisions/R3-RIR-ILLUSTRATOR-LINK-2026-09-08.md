# R3 RIR → Illustrator 接口修复与实机交接

## 结论与边界

本轮修复了真实接口断点，并完成 Python 生成 payload → Illustrator 29.5.1 → AI 保存重开/读回的合成资格测试。不是完整 UI/API 调度，不是复杂参考复刻、人审通过或 E4/E5。

开发基线 `6d4e9c794f5ce9c03ca233ab2ba933915c019581`；其 exact-SHA CI `34147814044` 已读回 completed/success。本轮的新提交需要另行绑定 CI。R3 账本仍为唯一状态源，R4.1 未替代现行任务 authority；知识迁移延后。

## 根因及修复

旧 `build_adobe_job` 原样复制 RIR layers，并输出 `artboard.colorSpace`、`targets.masterAI/previewPNG/masterSVG/job/readback`。JSX 实际要求 `{width,height}`、`{ai,png,svg}` 及 `{id,items}` 层，内含原生对象。两端各自测试绿，但没有连接测试。

新增交叉测试把 **Python 生成结果** 送入 **实际产品 JSX 的 validateJob**，RED 明确为 `unknown field: colorSpace`。修复后通过。POSIX CI 仅把文件路径映射到合成 Windows mount；对象 payload 不重建。Windows 本机使用真实生成路径；Node DOM/font 边界是 doubles，另有下述实机证据。

代码：

- `packages/capabilities/reconstruction/adobe_job.py`：与 JSX 对齐字段；深拷贝输出；非零 hash、ID、精确字段、目标扩展名、已存在输出和路径边界校验。
- `packages/capabilities/reconstruction/adobe_lowering.py`：将顶左原点转为 Illustrator 原点，保留 Bézier 左右控制柄、zOrder、矩形/多边形、分组、单个交集蒙版、已落盘整幅 PNG/JPEG 和显式 live text 样式。
- `design-lab/tests/test_reconstruction_adobe_job.py`：8 个测试方法；覆盖生产者/消费者连接、坐标与控制柄、样式拒绝、显式文字、组/蒙版/透明 PNG、输入别名、篡改、同层顺序歧义和拒绝覆盖。
- `design-lab/tests/host_fixtures/prepare_illustrator_lowered.py`：生成独立 project-local 实机夹具；使用真实 builder，而非另外手写一份恰好匹配的 job。生成动作不启动宿主、不代签 rights。

## 不静默降级的边界

支持绝对单轮廓 M/L/C/Z。圆弧、复合路径、相对命令、渐变、描边、特殊混合/透明度、隐藏/锁定、复杂蒙版和未落盘裁切明确拒绝，不能当作完整 SVG/RIR 编译器。

RIR v1 没有足够的字号、色彩及 PostScript 字体名字段；live text 必须以 `text_styles` 按对象 ID 明确提供。不能猜字号/字体，也不能把转曲当 live text。位置是当前 RIR bounds 到原生 position 的显式投影，不证明文字像素一比一。

位图必须已在同一 run root，且是完整裁切、单帧 PNG/JPEG。裁切/外部来源需上游先核验和落盘。本模块不复制用户素材、不完成 rights、不实现单写租约或防御所有文件 TOCTOU。调度器必须绑定完整 host job/hash（包括 text_styles 投影、输入字节和目标）而不是只用 RIR hash；jobId 的 RIR 身份不是最终幂等授权。

## 实机路径与结果

忽略目录：`.project-local/task-artifacts/illustrator-lowering-20260908/run-f326f58012eb4cbda79292b3c4a1462c/`。

通过 Computer Use 选择 Illustrator 已有窗口，File → Scripts → Other Script，执行此目录 `run.jsx`。未启动 PS、未改全局配置、未接触用户工程、未访问 E 盘目录。

实机结果：`PASS host=29.5.1 text=DESIGN LAB / LINKED font=ArialMT anchor=40,240 right=200,540 documentsBefore=0 documentsAfter=0`。

运行走过产品 `runApprovedJob`：建原生文字/路径/位图/蒙版 → AI 保存 → 关闭重开/结构读回 → PNG/SVG 导出 → 再开 AI/读回 → 夹具关闭自己的文档。屏幕观察到原生图层及生成内容。独立文件检查确认 PNG 800×600 RGB，AI 为 PDF-compatible 文件；文件头检查不单独当宿主证据。

| 内容 | SHA-256 |
|---|---|
| RIR 规范化内容（不是 JSON 文件字节 hash） | `36e0db1bf342b52fff81dc968aab08819e9da5ac0266d59f1d2ad9185201e782` |
| source-rir.json | `6c849d18256495305bc096c28a02a9d9c91d156839906d6f6235d123c1931352` |
| adobe-host-job.json | `ae26061abc18424aa1ba9bc702598cad9ea6f4d6a9257ffdb6a4432ce154f93b` |
| input.png | `b957f69c5db42b973beb44d3e7b63de125002d396af99245ecf0cdde83846520` |
| master.ai | `5e278e7d12d7c637fc72d7caf481bf96ac7619c1c87b68ee9232fb9b257b17de` |
| illustrator-preview.png | `cfebd891f3d146baec76c1706627a1894ca3ace1085efc9f711a62c3e389a7c1` |
| master.illustrator.svg | `1fddbb089fd8e6b4efb1e71f81ba87c88dba98a019e07afb5b0025ac9ad36ebe` |
| run.jsx | `d6b74b95f0ecf9e2acb4e0b3f9e03a4d9cfd92404948e942c41074ddabd77ace` |
| result.tsv | `4e44da268e604b012aabbec7c773544547c56f5b3b07536a0dd73ead0464af93` |

运行中首次查询 result.tsv 尚不存在，SVG 仍 0 字节且被 Illustrator 锁定。这是执行未结束，不重启脚本、不关闭进程。继续观察同一个窗口后正常完成，随后才读取完整 hash。生成 SVG 可能含字体，仅本地保存，未上传原生产物。

源码绑定：`adobe_job.py` SHA256 `75f311f164df23e31e7eba5acd39d0ce94c4865d4a231a4a548adb91ee2c6602`；`adobe_lowering.py` 为 `2c0de0a9796cb1023e88641144467045d82fa76a147307f3325e6bfc73b2cf39`；本轮未修改的产品 JSX 为 `b1a7542d47fdcb0af2acb922654dc48f5904dde7f69fee2e7d7aa14916d1c48c`。

上述是实机生成时的源码 hash。收尾连接审查另发现 Python 字典比较把授权整数 `1` 当作 `True`；新增负例观察失败后改为严格 `is True`，与 JSX 一致。最终 `adobe_job.py` SHA256 为 `072d9c0c96462a2769559e4d80e5cb8ae0cc3b5863fe1990ff47b6d139028d3c`。最终 8 项连接测试通过；没有因这一条收紧校验而重跑/覆盖已完成的原生产物。

验证命令均使用 `.venv/Scripts/python.exe -B`：`-m unittest discover -s design-lab/tests -p test_reconstruction_adobe_job.py` 8 PASS；`-p 'test_illustrator*.py'` 3 PASS；`design-lab/scripts/verify_design_lab.py` 进程 27644 终态 `total=49 failed=0`、退出码 0。报告生成和 `scripts/generate_current_reports.py --check` 通过；其含义仅 bound-input/output integrity，非远端或实时宿主证明。统一门的历史 Comfy E3 文案不作为本轮模型推理证据。

严格布尔修复后的最终统一门进程 47680 同样 `total=49 failed=0`、退出码 0；既有 `test_reconstruction_illustrator_adapter.py` 2 个静态测试也通过。

## 继续执行

1. 把已验证的 RIR→job 链接入 service-owned operation/attempt/asset lease，纳入安装包；当前 reconstruction 仍在 capabilities 源码树，不能声称已装服务会自动调用。
2. 在同一请求身份下做原生 dispatch/readback/异常对账，再启用工作台生成按钮；未知结果不能自动重复创建。
3. 补直接从参考图进入的 OCR/分层/几何，以及 5–10 张复杂多类型参考；本夹具不占这些案例名额。
4. PS 实机、两次 UI 对象编辑、生产事务恢复、Comfy/H3 小说分镜 15 秒视频、独立质量/rights/production/release 门仍未完成。

本轮未重新跑此前的两次 native patch/恢复夹具，不把旧 patch 证据升级为当前完整服务验收。
