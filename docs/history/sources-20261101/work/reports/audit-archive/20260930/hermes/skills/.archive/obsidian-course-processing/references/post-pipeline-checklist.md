# 批量全分类转化后继清单

## 触发条件

`python tools/pipeline.py` 完成全部分类转化后，立即按此清单批量补充。

## 清单（按执行顺序）

### 1. 合并已有内容（T1 课程）
```python
# 将旧 00_课程总览.md 内容合并到新 00_课程主页.md
# 将 03_逐节总结/*.md 合并到主页
# 将其他子页面内容合并
```

### 2. 分类首页
每个 `10_课程库/<category>/` 创建 `00_<category>首页.md`：
- 课程列表（wikilinks）
- Dataview 查询（WHERE domain = "分类名"）
- 原始盘索引链接

### 3. 验证页批量填充
为所有课程的 `06_验证与不确定项.md` 填入实际数据：
- 检测是否有 PDF 提取（has_pdf）
- 检测是否有 ASR 转写（has_asr）
- 检测是否有 OCR（has_ocr）
- 标记不确定项（教师身份、学术引用等）

模板：
```markdown
## 已验证项
- ✅ PDF文本提取完成 (pymupdf)
- ✅ 视频ASR转写完成 (SenseVoice)

## 待验证/不确定项
- ⚠️ 内容来自源文件提取，教师/作者身份未经独立验证
- ⚠️ 术语定义来源于课程材料，未与权威学术来源交叉比对
```

### 4. 外部权威链接
为缺少 http 链接的课程添加领域权威来源（仅限有明确权威源的领域）：
- 设计类 → adobe.com, developer.mozilla.org
- 编程类 → python.org, github.com, langchain.com
- 心理类 → apa.org, verywellmind.com
- 记忆类 → wikipedia.org (spaced repetition)
- 视频类 → adobe.com (premiere)

### 5. Wikilink + Dataview 补全
确保每门课的 `00_课程主页.md` 包含：
- 内部导航 wikilink（`[[../分类名/]]`、`[[../../00_总控台/01_课程总览|课程总览]]`）
- Dataview 查询语句块

### 6. 完整性审计
```python
items = [
    has_pdf,    # PDF提取
    has_asr,    # ASR转写
    has_visual, # 视觉索引
    has_extlink,# 外部链接
    has_wiki,   # 内部导航
    has_dv,     # Dataview
    has_ver,    # 验证页
]
score = sum(items) * 100 // len(items)
```

将审计结果写入每门课主页：
```markdown
## 完整性审计
| 维度 | 状态 |
|---|---|
| PDF文本 | ✅ |
| ASR转写 | N/A |
| 视觉索引 | ⏳ |
...
**完整度: 71%**
```

## 素材型课程的诚实标记

以下课程本质上无法达到高完整度分数，因为源材料不可提取文本：

- 视频为主且无讲义的课程 → ASR 覆盖，标记 `## 本课程为视频课`
- 纯图片素材 → 标记 `## 素材型课程（图片集）`
- 软件/工具类 → 标记 `## 素材型课程（软件）`
- 古籍/扫描件 → OCR 覆盖，标记精度
- DOC 老中文格式 → 标记为已知限制（46 文件，antiword 不支持中文 OLE 格式）

## 提交

单次 commit：`git add -A && git commit -m "finalize: post-pipeline cleanup (indexes, verify, links, audit)"`
