# Illustrator 三轮真实批量控制审计

结论：**PARTIAL**。真实宿主完成三轮创建、修改、原生保存重开、导出和备份恢复；独立核验 **105 PASS / 1 FAIL**。不是生产适配器完成、复杂设计复刻验收或 E3/发布证书。

## 本次实际操作

- 2026-09-07 本地运行，Illustrator 29.5.1，Windows；窗口 69738，公开进程观测 PID 27888、PPID 9204，实际程序为 `C:/Program Files/Adobe/Adobe Illustrator 2025/Support Files/Contents/Windows/Illustrator.exe`。这是进程身份观察，不是全系统文件写入追踪。
- 通过本机软件 File → Scripts → Other Script 执行项目自建 JSX，使用 bundled Computer Use 技能控制菜单；未安装新桥、未修改宿主全局设置。运行入口依据 [Adobe 官方说明](https://helpx.adobe.com/illustrator/desktop/automate-visualize-data/automate-actions/install-and-run-scripts.html)。
- 只创建任务文档，不修改开始时已打开的上轮 `source.ai`。执行结束恢复原窗口，文档数由 1 回到 1；该旧文件 SHA256 仍为 `bd7a05dfd0f4d0b93861fd9ed706c0465c5c27539ba659796a936b057c34398a`。
- 1920×1080、四图层、两个真实文本对象、四条路径、一个嵌入 RGBA 位图、剪切组。PNG 输入是本项目生成的合成测试素材，不读取第三方设计图。
- 每轮：创建 → baseline.ai 保存/关闭/重开/DOM读回 → SVG/PNG → 修改标题与矩形宽度 → edited.ai 保存/关闭/重开/DOM读回 → SVG/PNG → 打开原始备份 → restored.ai 保存/关闭/重开/DOM读回 → SVG/PNG → 关闭本轮文档。
- 三轮时间：108.380 / 109.421 / 109.370 秒；总计 327.176 秒。共 9 个 AI、9 个 PNG、9 个 SVG，均留在下面的项目运行根。不是干净启动三个应用进程的测试。

## 证据与人工打开入口

运行根：`.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/`。

- [恢复后的原生 AI](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/repeat-1/restored.ai)
- [修改后的原生 AI](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/repeat-1/edited.ai)
- [修改预览](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/repeat-1/edited.png)
- [宿主终态记录](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/17-result.json)：脚本所检查的操作完成三轮。
- [独立核验与逐文件 hash](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/independent-verification.json)：106 项，其中 SVG 原始字节重复性失败。
- [SVG 差异诊断](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-batch/run-1788717978664/svg-id-diagnosis.json)：九份 SVG 的原始和诊断 hash、ID 映射、五项诊断检查。

这些是 ignored 本地证据；换机不存在应报 MISSING，不能重造日志。源码 HEAD 为 `c4dccd58331bc4561eb89265283d924b7630d113`，但本次绑定的是工作树测试脚本及其 hash，不能用 HEAD 冒充完整未提交工作快照。

## 通过、失败与限制

- 独立核验：三轮 DOM 一致、PNG 字节一致；每轮恢复后 DOM 和 PNG 像素均与基线一致；标题和几何修改保持；未修改对象保持；PNG 可解码且尺寸正确，SVG 保留文本、剪切路径和嵌入图片。
- **FAIL 保留**：三轮 SVG 原始 SHA 不同。实际 diff 只有自动生成的 `clip_<数字>_` ID 及其 `url(#...)` 引用；仅在内存做受限标签替换后同阶段结果一致，文字/几何差异没有被抹除。原始 SVG 没有重写，原失败没有改成 PASS。生产级确定性导出尚未实现。
- 位图放大边缘粗糙是故意使用 256×256 合成输入的测试条件，不是视觉质量通过。SVG 默认嵌入字体轮廓，尚未做字体分发许可审核，不发布这些输出。
- 本次未实施产品 JSX 入口；现有 `reconstruction-assemble.jsx` 仍只有创建空文档。尚缺运行授权/文档身份负例、路径逐点和颜色修改验收、取消/中断恢复、防重复图层、失败注入、产品任务/资产服务接入及不同参考图验收。
- 四个外置根继续以 `.project/paths.json` 为准，本次均未写入。实际输出落项目内，不证明 Adobe scratch 或所有其他入口的全局写入边界已经治理完成。
- Photoshop、ComfyUI、H3、工作台、全仓规范化、exact-SHA CI、云端读回与 Human Gate 不因本次测试升级。

## 接续

1. 将已实测的对象操作收敛进受授权、文档绑定、失败可恢复的产品桥；用负例和真实宿主回归约束，不能把诊断脚本直接宣布为产品。
2. 给 SVG 确定性导出制定受限、可验证的 ID/引用处理，保留原始宿主文件和来源；不能粗暴删除 ID 或忽略视觉变化。
3. 补 PS 原生图层测试，以及真实入口写入和模型资格；正式任务依赖、知识迁移延后和人工审计边界保持不变。
