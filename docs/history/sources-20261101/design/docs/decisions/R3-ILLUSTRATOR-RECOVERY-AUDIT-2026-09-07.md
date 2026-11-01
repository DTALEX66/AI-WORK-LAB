# Illustrator 原生恢复补测与产品路径缺陷

结论：**PARTIAL**。2026-09-07 本地 Illustrator 29.5.1 完成专用诊断，耗时 44.020 秒；独立读取输出得到 **39 PASS / 1 FAIL**。失败是实际产品桥拒绝合法 Windows 子路径，并非宿主安装或启动失败。产品修复尚未实施，R3-11 不升级为完成。

## 本次覆盖与边界

通过 Computer Use 的 File → Scripts → Other Script 运行项目自建 JSX，只创建两个新文档：任务工程与用于负例的保护文档。既有 `source.ai` 未被脚本定位、修改或关闭。开始及结束均保留一个既有文档，窗口已观察恢复；本次没有另行读取既有文件字节，不能把窗口和数量证明扩大为全系统文件未变。

| 场景 | 实际动作与读回 | 结果 |
|---|---|---|
| 非任务文档 | 将新建保护文档作为错误目标，带另一任务的文件身份调用诊断 patch；拒绝前不修改，两个文档 DOM 不变 | PASS，诊断范围 |
| 部分执行 | 创建一个操作标记图层，将第二锚点从 `[300,120]` 改成 `[360,100]`，注入异常；颜色、文字仍是旧值 | PASS，确有部分修改 |
| 保存后恢复 | 保存 `interrupted.ai`，关闭并重开，DOM 与中断前一致；继续改填色及标题，再保存重开 | PASS |
| 重复尝试 | 连续三次运行同一诊断 patch，最终只有一个操作标记图层，DOM 与恢复版本一致；另存重开后 PNG 像素相同 | PASS |
| 回退 | 打开不可变 `baseline.ai`，另存 `restored.ai` 并重开；DOM 及 PNG 像素与基线一致 | PASS |
| 产品校验 | 载入实际 `reconstruction-assemble.jsx`，只调用 `validateJob`，不调用创建文档函数；合法子路径被拒，旁支及父目录穿越也被拒 | 2 PASS / 1 FAIL |

图形锚点修改保留原左右控制柄，导出呈弯曲边缘；这是此次逐点编辑的真实结果，不宣称它仍是直线四边形。字体为本机 ArialMT；没有 SVG 字体分发或第三方参考复刻，未进行 rights/quality 人工验收。

本次是受控合成诊断，**不是**生产幂等协议、异请求键冲突、跨进程恢复、应用崩溃、运行取消或 R3-14 设计复刻验收。诊断使用固定文档身份和操作层名，不是可以直接用于任意作业的授权/恢复实现。现有生产桥仍只有创建空文档功能。

## 已证实的产品缺陷与建议修复

实际源码：`integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx`，本次 SHA256 `f2ba20d98479cca301c47420f6d6dd30b4ce4d8166a429099191b30607ef4cd1`。

`File(child).fsName` 和 `Folder(root).fsName` 在当前 Windows 宿主均返回反斜杠；`assertInside` 却在根末尾追加正斜杠，随后直接做前缀比较。合法的同目录 `valid.ai` 因而得到 `target outside run root`。负例全拒不能证明校验器正确，因为合法路径也被拒绝。

建议仅统一比较双方的分隔符并保留目录分隔边界，再用合法子路径、同名前缀旁支、父目录穿越回归，真实宿主复测。此项属于小范围行为修复，已按 brainstorming 技能提交设计确认，未收到明确确认前不改产品桥。不要用关闭边界或只比较裸前缀的方式修复，也不要把纯词法检查称为完整 reparse 防护。

## 人工审计入口

所有产物位于 `.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/`，Git ignored；换机缺失须报 MISSING，不得重造日志。

- [原始工程](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/baseline.ai)
- [中断时工程](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/interrupted.ai)
- [恢复后的可编辑 AI](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/recovered.ai)
- [恢复后预览](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/recovered.png)
- [原生回退工程](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/restored.ai)
- [产品校验失败原件](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/2-production-validator.json)
- [独立核验及全部 22 个原始输出 hash](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run-1788727466747/independent-20260906T204650558825Z.json)
- [诊断脚本](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/run.jsx)
- [独立读回脚本](../../.project-local/task-artifacts/adobe-live-20260907/illustrator-recovery-v1/verify.py)

独立验证使用 `.venv/Scripts/python.exe -I -B`（Python 3.13.14、Pillow 12.3.0），读取上述 run 参数；exit 1 是保留产品失败的预期结果，不应改写为全绿。项目未提供 `scripts/workflow/execution_preflight.py`，本轮改用该精确解释器直接验证版本和 Pillow 导入，未虚构预检成功。

原 HEAD `c4dccd58331bc4561eb89265283d924b7630d113` 不包含当前全部未提交成果；证据绑定工作树文件 hash。未提交、推送、发布或修改全局配置；四个外置根仍保存在 `.project/paths.json`，本次未写入。PS 无可操作窗口，未重复其已失败的启动路径。其余 R3、OCR 隔离、UI/API、H3、知识迁移延后和 Human Gate 状态不被本次升级。
