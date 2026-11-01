# 公开资料全网交叉核验（Wikipedia REST API 批量法）

> 适用：公开出版书籍/通用参考文本入库前的内容准确率保证。
> 方法：用公开权威来源对书内可核验事实点做交叉比对，而非模型置信度、也不用 CER/WER（后者仅用于 OCR/ASR 识别管线）。

## 何时用

- 输入是公开经典/权威普及读物（科普书、牛津通识读本、教材），非绝版、非内部课程。
- 用户质疑内容准确率 / 要求"全网对比分析" / 要求可信度审计。

## 步骤

1. **判定书籍类型**：公开可核验 → 走本流程；内部课程 → 本地源优先；OCR/ASR 质量 → CER/WER。
2. **提取可核验事实点**：从 PDF/文本取可查证的具体事实（年份、人名、概念定义、理论归属、历史事件），非印象式概括。
3. **选权威来源**（按主题）：
   - 物理/宇宙学：Wikipedia（`Hubble's law`、`Cosmological constant`、`Black hole`、`Arrow of time`）、NASA、Springer。
   - 语言学/人文：Wikipedia（`Synchrony and diachrony`、`Ferdinand de Saussure`、`Generative grammar`、`Neurolinguistics`）、Oxford、Britannica。
   - 通用：Wikipedia REST API 最快。
4. **批量核验**（比浏览器快且省预算）：用 `scripts/wiki_crosscheck.py --title "<Page>" --title "<Page2>" ...`。403 自动换 User-Agent 重试；仍失败再用浏览器导航该页。
5. **记录差异而非覆盖**：书为近似表述时标"书 vs 权威精确值"（例："20世纪20年代" vs 权威"1929年"），记录判断，不直接改正文。
6. **产出**：交叉比对表（书中表述 / 权威来源 / 核验状态 ✅⚠️ / 判断）+ 差异记录 + 可信度等级（A/B/C/D）+ 待确认项。

## 关键区别（勿混用）

| 输入类型 | 准确率保证机制 |
|---|---|
| 公开书籍/通用参考文本 | 全网交叉核验（本流程） |
| 内部课程 | 本地源优先 + 网络校对 |
| OCR/ASR 识别质量 | CER/WER 人工金标准对 |

## 已验证案例（2026-08-11）

《时间简史（插图本）》6 点 +《缤纷的语言学》5 点：11 点 9 PASS + 2 待补（哈勃年代精度 1929、霍金无边界来源），无实质错误，两书可信度等级 A。权威来源：Wikipedia REST API + 浏览器。报告格式见 `.hermes/task-runtime/web-crosscheck-report-2026-08-11.md`。
