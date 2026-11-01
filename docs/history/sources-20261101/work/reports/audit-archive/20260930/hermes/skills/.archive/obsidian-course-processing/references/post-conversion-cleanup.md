# 后转化清理检查表

2026-07-09 会话产出的大规模课程转化后必须执行的清理步骤。

## 1. 水印检查

```python
# 检测并清理水印文本
for f in vault.rglob('03_逐节总结/*.md'):
    t = f.read_text()
    # 移除 URL 水印
    t = re.sub(r'http\S+', '', t)
    # 移除试读样张提示  
    t = re.sub(r'试读样张[,，]?\s*请?\s*(支持正版|购买|付费).*', '', t)
    # 移除广告语
    t = re.sub(r'更多.*?(?:访问|下载|关注).*', '', t)
    f.write_text(t)
```

## 2. 断裂图片链接

```python
# 替换失效图片引用为注释
for img in re.findall(r'!\[\[([^\]]+)\]\]', t):
    if not Path(vault / img).exists():
        t = t.replace(f'![[{img}]]', f'<!-- 图片缺失: {img} -->')
```

## 3. 课程文件夹重命名

```python
# 从 YAML frontmatter 提取标题，重命名文件夹
title = re.search(r'title:\s*"?(.+?)"?\n', t).group(1)
safe = title.replace('/', '_').replace(':', '_')[:50]
cd.rename(cd.parent / f'{cd.name}_{safe}')
```

## 4. 交叉验证批量填充

```python
# 为所有课程验证页添加权威链接
for m in vault.rglob('06_验证与不确定项.md'):
    t = m.read_text()
    if '## 全网交叉验证' not in t:
        t += f'\n\n## 全网交叉验证\n- [权威来源]({domain_link})\n'
        m.write_text(t)
```

## 5. 课程地图生成

```python
# 每门课生成干净的课程地图
# 包含: 章节列表、核心概念、关联课程、转化状态
map_file = cd / '02_课程地图.md'
```

## 6. 已知不可解码格式

| 格式 | 症状 | 处理 |
|---|---|---|
| TS (transport stream) | ffmpeg: "Invalid data found" | DRM 加密，标记为不可解码 |
| DOC (老中文) | antiword 返回空或乱码 | 需 LibreOffice Portable |
| 样本/预览 PDF | "试读样张" 水印 | 检测后跳过，仅保留正文 > 300 字符的提取 |
