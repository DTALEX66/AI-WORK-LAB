# OCR 观测到对象计划

状态：IMPLEMENTED_LOCAL / 定向测试及历史实测结果接入通过；不是实时 OCR provider、复杂参考重建、原生工程或 Human Jury 闭环。

## 实施范围

复用 `src/design_lab/analysis/decomposition.py` 的现有 Plan，而非新建第二种对象真值。新增 `Plan.from_ocr(...)`，接收明确源 hash、画布和像素坐标 OCR 观测，将文字、区域、原始四边形与置信度保留下来。源路径是无 I/O 的记录字段，调用方仍负责验证实际源文件。

- 所有识别文字均保持 `mapping_state=unmapped`、`font_status=unknown`、`host_object_id=null`。
- 不把 OCR 置信度作为字体匹配、视觉相似度或宿主通过分数。
- 每个计划保留一个 `unknown/unrecovered` 对象，说明非文字、遮挡与背景尚未分析；不是整图贴底图层。空白检测也不冒充完整背景恢复。
- 对象 ID 绑定源 hash、文字和规范化多边形，不受识别列表顺序、多边形起点/方向或置信度变化影响。重复对象拒绝，不静默合并。
- 拒绝越界、非有限数、布尔数值、退化/非凸四边形、伪造宿主字段、异常源 hash 与超量文字；上限 256 个检测、单条 4096 字、总计 16384 字。
- 原 planar-decomposition/v1 schema 增加可选 `confidence` 与 `source_polygon`，旧输出不增加空字段；该转换不执行任何文件或宿主写入。

## 测试和真实观测接入

先运行新测试，观察缺少 `Plan.from_ocr` 的预期失败。实现后 Windows 测试读取中文 schema 曾遇到默认 GBK 解码失败，修正为明确 UTF-8；没有改变 schema 内容来规避编码。

最终定向命令：

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p test_ocr_object_plan.py
.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p test_planar_decomposition.py
.venv/Scripts/python.exe -I -B design-lab/tests/host_fixtures/qualify_ocr_object_plan.py
```

新测试 7 项、原模块测试 10 项通过。资格夹具固定读取此前真实 ONNX 推理 receipt，先核验 receipt SHA 与逐张 PNG SHA，再仅从预测文本/坐标/分数构造计划，不使用期望答案。5 张图产生 13 个文字对象及各自未恢复内容说明，全部通过 JSON Schema 验证；没有再次调用模型或宿主。

运行目录：`.project-local/task-artifacts/ocr-qualification/object-plan-20260907T195541256926Z`。
读回 `readback.json` SHA256：`9e84ce5dccc2cfb2c144e171ead86bfc7280850bface8255f48bd6cb53912acf`。
生产模块 SHA256：`011b44dafb3d48f1f005ade0231389ba2e4be367810be0b43cd8264a47273012`。

综合验证首次暴露上一提交 `qualify_ocr_onnx.py` 缺失 SPDX 注释，已补 MIT 头，独立许可证检查通过。原始 OCR 测试绑定的旧脚本 hash 保留，未回写历史结果。本批综合门终态及分支交付状态需从真实命令读回，不以定向 17 项抵扣。

修复后的综合重跑会话 66046 终态退出 0：`.venv/Scripts/python.exe -B design-lab/scripts/verify_design_lab.py`，`VERIFY_DESIGN_LAB=OK total=49 failed=0`。首次失败会话 37854 保留。综合门的历史 Comfy E3 文案不证明本轮生成视频；本批未运行 Comfy。报告 `--check` 与 `git diff --check` 通过。上传仍受前一交接记录的环境审批策略阻断，不绕过；当前成果仅本地提交，不宣称云端 CI 或双端一致。

## 后续

接入实时 OCR runner 与工作台受控提交；将对象修正及明确字体/样式选择接到现有 RIR/Adobe producer。复杂参考仍需图像分区、遮挡恢复和专业质量验收，不能把本次合成 OCR 结果算作知名设计网站 5–10 张复刻集。H3 及 15 秒视频、人工 gates、发布等仍独立未完成。
