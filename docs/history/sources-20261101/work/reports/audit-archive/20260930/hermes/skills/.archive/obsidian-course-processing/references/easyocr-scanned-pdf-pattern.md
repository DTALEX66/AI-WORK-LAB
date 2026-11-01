# EasyOCR for Chinese Scanned PDFs (Windows)

## When to Use

When `fitz.get_text()` returns empty for a PDF — the PDF is image-only (scanned, no text layer).

## Installation

```bash
pip install easyocr
```

## Pattern: fitz.get_pixmap() + EasyOCR

```python
import fitz, easyocr, tempfile, os

reader = easyocr.Reader(['ch_sim'], gpu=False)  # load once per session

def ocr_pdf_page(pdf_path, page_num=1, dpi=150):
    doc = fitz.open(pdf_path)
    pg = doc[page_num]
    pix = pg.get_pixmap(dpi=dpi)
    
    # Save to temp file (EasyOCR needs file path or numpy array)
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(pix.tobytes('png'))
        tmp = f.name
    
    result = reader.readtext(tmp)
    os.unlink(tmp)
    doc.close()
    
    return '\n'.join([r[1] for r in result])
```

## Why NOT pdf2image

`pdf2image` requires `poppler` which is not available on Windows. `fitz.get_pixmap()` works without external dependencies.

## Why NOT PaddleOCR on Windows

PaddleOCR has a known OneDNN bug on Windows CPU:
```
NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]
```
Fall back to EasyOCR for all Windows-based Chinese OCR.

## Watermark Filtering

```python
import re
text = re.sub(r'试读样张.*', '', text)
text = re.sub(r'http\S+', '', text)
text = re.sub(r'侵权举报.*', '', text)
text = re.sub(r'\s+', ' ', text).strip()

# Skip if only watermark
if len(text) < 100:
    return None
```

## Batch Processing

```python
for pdf in source_dir.rglob('*.pdf'):
    out = summaries_dir / f'{pdf.stem}.md'
    if out.exists() and out.stat().st_size > 500:
        continue  # already processed
    
    doc = fitz.open(pdf)
    text = ''
    for pg_num in range(1, min(4, len(doc))):  # skip cover page (pg 0)
        pg = doc[pg_num]
        pix = pg.get_pixmap(dpi=150)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(pix.tobytes('png'))
            tmp = f.name
        result = reader.readtext(tmp)
        os.unlink(tmp)
        text += '\n'.join([r[1] for r in result]) + '\n'
    doc.close()
    
    text = clean_watermarks(text)
    if len(text) > 100:
        out.write_text(f'# {pdf.stem}\n\n> EasyOCR\n\n{text[:3000]}', encoding='utf-8')
```
