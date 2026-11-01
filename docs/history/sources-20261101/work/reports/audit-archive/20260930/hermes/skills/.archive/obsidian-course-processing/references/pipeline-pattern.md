# 全流程转化管道 (Pipeline Pattern)

## 架构

```text
tools/pipeline.py          ← 主引擎：扫描 → 检测格式 → 选择转换器 → 提取 → 合并
tools/benchmark_accuracy.py ← 精确度基准测试
tools/crosscheck_accuracy.py ← 全网交叉验证
tools/content_keyframes.py  ← 内容匹配截图（概念→PDF页面/视频时间戳）
```

## 转换器矩阵（2026-07-09 benchmark）

| 格式 | 主工具 | 精度 | 备选 |
|---|---|---|---|
| PDF 文字 | pymupdf | 98% | pdftotext |
| PDF 扫描 | PaddleOCR | 90-95% | Tesseract |
| DOCX | pandoc | 98% | zipfile OOXML |
| DOC 新格式 | pandoc + antiword | 90% | - |
| DOC 老中文 | antiword | 50% | LibreOffice Portable (.paf.exe) |
| PPTX | zipfile OOXML | 95% | - |
| TXT/MD | open() | 100% | - |
| 视频/音频 | FunASR SenseVoice | 92%+ (CER 8%) | faster-whisper (CER 20%) |
| 图片 OCR | PaddleOCR | 90-95% | Tesseract |

## 模型单例加载

FunASR SenseVoice 模型 936MB，每个进程只加载一次：

```python
_MODELS = {}
def get_asr_model():
    if 'asr' not in _MODELS:
        from funasr import AutoModel
        _MODELS['asr'] = AutoModel(model='iic/SenseVoiceSmall', device='cpu', disable_pbar=True, disable_update=True)
    return _MODELS['asr']
```

## 安装

```bash
cd D:/All projects/Obsidian-Assistance/tools
pip install -r requirements.txt
# LibreOffice Portable 需手动下载 .paf.exe 解压
```

## 运行

```bash
# 全量
python tools/pipeline.py

# 单门
python tools/pipeline.py --course C0401

# 内容截图
python tools/content_keyframes.py C0401

# 交叉验证
python tools/crosscheck_accuracy.py
```

## 内容匹配截图原理

非随机关键帧。每张图对应具体课程概念：

1. 从逐节总结（`03_逐节总结/*[!ASR]*.md`）提取关键术语（2-6字中文词，去停用词），**不要从 `00_课程主页.md` 提取**（主页含大量 frontmatter 元数据词如 `课程库`、`大字体`，无法匹配实际内容）
2. PDF：搜索术语 → 提取包含该术语的页面为图片
3. 视频：搜索 ASR 转写中术语出现的时间戳 → ffmpeg 截取对应帧
4. 写入 `12_视觉索引与配图.md`，格式：`![[99_附件_重组/内容匹配截图/...]]`

## TS 视频格式限制

中国视频平台的 TS（Transport Stream）分段文件常使用私有加密，ffmpeg 无法解码。症状：`Error opening input: Invalid data found`。处理方法：
- 标记课程为 `TS加密/无法解码`
- 从同一源目录提取任何可读内容（JPG→OCR 等）作为替代证据

## 批量改名：代号→真实名称

当 Obsidian 中所有课程文件夹只显示代号（C0101, C0201）时：

```python
# 从 YAML 前导提取标题
title = re.search(r'title:\s*"([^"]+)"', content).group(1)
new_name = f'{course_id}_{safe_title}'  # "C0101_黑马Photoshop_AIGC商业设计"
```

改名后必须更新全库 wikilink：
```python
for old_id, new_name in id_map.items():
    t = re.sub(rf'\[\[({old_id})\]\]', rf'[[{new_name}]]', t)
    t = re.sub(rf'\[\[({old_id})\|', rf'[[{new_name}|', t)
```

## 防卡机制

- 超大源目录（如 C0110 有 3055 文件）→ 限制每门课最多处理 200 文件
- SenseVoice 模型下载（936MB）→ 首次运行自动下载，后续缓存
- ffmpeg 转换大视频 → 限制 120 秒采样
- **多后台进程并行**：管道 + 截图 + 交叉验证互不阻塞
