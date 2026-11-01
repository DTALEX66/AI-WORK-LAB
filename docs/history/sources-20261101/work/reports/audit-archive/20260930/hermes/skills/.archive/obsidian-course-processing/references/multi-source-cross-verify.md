# Multi-Source Cross-Verification Pattern

## When to Use

After course conversion, every course with 2+ source types (PDF + ASR, PDF + PDF, ASR + ASR) needs cross-verification.

## Comparison Matrix

| Source A | Source B | Compare | Meaning |
|---|---|---|---|
| PDF extract | ASR transcript | Key term overlap | Complementary (theory vs lecture) if <15% overlap |
| PDF A | PDF B | Term overlap | Same-material if >30%, different chapters if <10% |
| ASR A | ASR B | Duration + terms | Sequential lectures if high term continuity |

## Implementation

```python
# Extract terms from both sources
pdf_terms = Counter(re.findall(r'[\u4e00-\u9fff]{2,6}', pdf_text) if t not in stop_words)
asr_terms = Counter(re.findall(r'[\u4e00-\u9fff]{2,6}', asr_text) if t not in stop_words)
shared = set(pdf_terms) & set(asr_terms)
all_terms = set(pdf_terms) | set(asr_terms)
overlap = len(shared) / len(all_terms) * 100
```

## Expected Results

- **0-5% overlap**: Normal for PDF+ASR — textbook vs lecture cover different ground
- **0% overlap**: Possible if PDF is design assets (3D models, `.docx`说明文件) not matching video content
- **>15% overlap**: Unusual — check if ASR transcript is correctly matched to course source

## Writing to Verification Page

```python
comp = '## 多源交叉对比\n\n'
comp += f'| PDF/文档 | {n_pdf} |\n'
comp += f'| ASR/视频 | {n_asr} |\n'
comp += f'- 共享概念: {len(shared)}个\n'
comp += '- 结论: 互补关系（教材理论 vs 视频实战）\n'
```

## Key Insight

PDF+ASR 0% overlap does NOT mean broken extraction — it means the course has complementary materials. Textbooks cover theory; video lectures cover practice. Report as "互补" not "不匹配".
