---
name: content-accuracy-crosscheck
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/research/content-accuracy-crosscheck/SKILL.md
---

---
name: content-accuracy-crosscheck
description: Cross-check book accuracy via authoritative sources.
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [verification, cross-check, fact-check, accuracy, books, pdf, sources, wikipedia]
    category: research
    related_skills: [obsidian-web-crosscheck, grounded-citations, arxiv]
---

# Content Accuracy Cross-Check

Guarantee the **factual accuracy of published content** (a book, trade
publication, PDF, course, encyclopedia entry) by cross-checking its claims
against **authoritative public sources** — Wikipedia/Britannica/encyclopedias,
publisher pages, official docs, library/catalog APIs, academic references.

## When to Use

- User asks "怎么保证准确率" / "how do we guarantee accuracy" about a
  **published book / document / PDF / course**.
- User wants a book/PDF's claims verified against public sources, or asks for
  全网对比分析 / 网络校对 / 交叉核验 of content.
- A document's factual content (physics, linguistics, history, etc.) needs
  corroboration before being trusted as a knowledge source.
- Delivering a content-accuracy report the user will act on.
- User asks how to organize the **multi-format recognition→verification
  pipeline** (which engine, when to escalate to an LLM, how to gate). See
  `references/recognition-transcription-pipeline.md` for the fork+gate+decouple
  design and the external-AI review-prompt technique.

## THE core rule (user-corrected)

**For published content, accuracy = cross-checking claims against
authoritative public sources. Do NOT reach for recognition metrics.**

Recognition metrics (CER/WER = character/word error rate vs golden
`*.truth.txt` / `*.pred.txt` pairs) measure only the **OCR/ASR pipeline** and
are `unverified` without a golden set. Using CER/WER to "guarantee accuracy"
of a *document's content* is a category error the user will correct. Reserve
CER/WER for measuring a speech/OCR recognition pipeline against human
transcripts — never for validating what a published book *says*.

Concretely: when asked how to guarantee accuracy of e.g. 《时间简史》or a
linguistics textbook, the expected answer is a **web cross-check report** of
the book's factual claims against Wikipedia/encyclopedias/library APIs — not
"label some truth.txt files and compute CER."

## Workflow

1. **Extract the content** (read the PDF/book with pdfplumber / your extractor).
   Record page count, file size, and pull the TOC + early pages to find
   *factual claim points* (names, dates, concepts, definitions).
2. **Pick 3-8 checkable claim points** per work — concrete, verifiable facts
   (e.g. "Einstein introduced the cosmological constant in 1917", "Hubble
   discovered the redshift law in the 1920s", "Saussure founded 20th-century
   linguistics").
3. **Cross-check each claim against authoritative sources** (prefer English
   Wikipedia; add Britannica/publisher/official-doc/second independent source
   for disputed claims).
4. **Assign a per-claim verdict**:
   - `PASS` — authoritative source supports it.
   - `⚠️ precision-diff` — correct but imprecise (e.g. book says "1920s",
     source says "1929"). Record both.
   - `❌ conflict` — source contradicts the book. Record both, don't overwrite.
   - `待补 source` — could not fetch/verify; mark explicitly, don't fabricate.
5. **Assign a whole-work confidence grade** (A/B/C/D): A = classic/authoritative
   work broadly supported; lower for weak/unsourced content.
6. **Write the report**: per-claim table (书中表述 / 权威来源 / 核验状态 /
   判断) + 差异记录 + 总体结论 + 待确认项. Save under the project's ignored
   runtime dir (e.g. `.hermes/task-runtime/web-crosscheck-report-YYYY-MM-DD.md`).
   Keep the book as the authoritative body — the network only corroborates its
   public-knowledge portions; never let a web source *replace* the original.

## Efficient Wikipedia batch technique

For many fact points, drive the Wikipedia REST summary API in one script rather
than the browser per page:

```python
import json, urllib.parse, urllib.request
def wiki(title):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"crosscheck/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r).get("extract","")
```

- URL-encode each title; add a `User-Agent`.
- A single `403`/timeout on one page is usually transient or a naming issue —
  retry once or fall back to the browser for that one term; **do not treat one
  failed fetch as "source absent"**.
- Confirm the page name: an odd title (e.g. "Hartle–Hawking state") may 403 on
  the summary endpoint; retry or use the browser.

## Report template (per work)

```markdown
# <书名> 全网交叉比对与可信度报告
可信度等级: A|B|C|D

## 可核验事实点交叉比对
| 书中表述 | 权威来源 | 核验状态 | 判断 |
|---|---|---|---|

## 差异记录
- <claim>: 书中 X vs 权威 Y -> 处理

## 待确认项
- ...
```

## Pitfalls

- **CER/WER instead of web cross-check** — the #1 failure this skill exists
  to prevent. Recognition metrics ≠ content accuracy. (See THE core rule.)
- **One failed fetch = "source absent"** — retry or fall back; a 403 on the
  summary endpoint is transient/naming, not absence.
- **Claiming precision the book didn't state** — if the book is approximate
  ("1920s") and the source is precise ("1929"), report it as a precision diff,
  not an error, and record both.
- **Network replacing the book** — the book stays authoritative; web only
  corroborates public knowledge. Never rewrite the book from a web source.
- **No golden-set gate for published content** — you don't need `*.truth.txt`
  pairs for a book; those belong to OCR/ASR pipelines only.
