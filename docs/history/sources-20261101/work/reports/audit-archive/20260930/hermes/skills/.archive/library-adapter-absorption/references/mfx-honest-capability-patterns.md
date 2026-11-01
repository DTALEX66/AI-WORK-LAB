# MFX honest-capability fixes: exact reproduction patterns

Reference for the three "honest capability" fixes (MFX-010/012/001) made to a
FastAPI multi-format ingestion stack (Cognitive-Loop-OS style). Each is a
concrete, reusable pattern.

## MFX-010 — metadata-only adapter must not satisfy content conversion

Symptom chain: a format's docstring claims OCR/ASR, but the engine map
`_ENGINES` puts a metadata/probe adapter (Pillow, FFprobe) first and the
orchestrator returns the first `success=True`. Image "converts" from
width/EXIF; media "converts" from container metadata. No OCR/ASR ever runs.

Fix in the engine-map + orchestrator:

```python
def _via_image_ocr(file_path: str) -> AdapterResult:
    import shared.adapter_fixtures as _af
    from shared.adapter_contract import AdapterInput
    if not (_af._tesseract_available() and _af._pytesseract_importable()):
        return AdapterResult(success=False, content="", engine="ocr-unavailable",
            error="Image OCR requires Tesseract-OCR + pytesseract; no metadata is claimed as content.")
    # real pytesseract.image_to_string(...)
    if not text.strip():
        return AdapterResult(success=False, content="", engine="pytesseract",
            error="OCR returned no text; treat as degraded (no content).")
    return AdapterResult(success=True, content=text, engine="pytesseract+tesseract",
        metadata={"char_count": len(text)})
```

Engine map: `_ENGINES["image"] = [("pytesseract+tesseract", _via_image_ocr), ("markitdown", _via_markitdown)]`.

Orchestrator content post-condition (the actual guard):

```python
if result.success and result.content.strip():
    return result.content, result.engine
reason = result.error or "returned empty content"
errors.append(f"{engine_name}: {reason}")
```

Tests:
- monkeypatch `_tesseract_available`/`_pytesseract_importable` to False; assert
  `convert_file(blank.png)` raises RuntimeError mentioning OCR, not success.
- assert `"pillow" not in [n for n,_ in _ENGINES["image"]]`.
- stub an engine returning `success=True, content="   "`; assert RuntimeError.

## MFX-012 — legacy heuristic isolation from verified state

`score_credibility` (domain + keyword signals) must carry a classification and
never promote to verified:

```python
return {"score": score, "level": level, "domain": domain,
        "factors": factors, "classification": "legacy_heuristic"}
```

Pipeline stage guard:

```python
cred = score_credibility({...})
cred["classification"] = "legacy_heuristic"
cred["verified"] = False
result["stages"]["crossref"] = cred
```

Tests: `classification == "legacy_heuristic"` even for a high-score case
(trusted domain + "peer-reviewed" + DOI-shaped URL); `verified is not True`.

## MFX-001 — supply chain licence-gate ledger

Structured JSON (not just prose NOTICES) with per-component `code_license`,
`model_license`, `gate`, `revision_ref`, `notes`. Gates:
`approved` | `review_required` | `blocked`.

Validator test sketch:

```python
import json, pathlib
_LEDGER = pathlib.Path(__file__).resolve().parents[1] / "docs" / "truth" / "SUPPLY_CHAIN_LEDGER.json"
def _ledger(): return json.loads(_LEDGER.read_text(encoding="utf-8"))

def test_all_gates_allowed():
    for c in _ledger()["components"]:
        assert c["gate"] in {"approved", "review_required", "blocked"}

def test_blocked_not_in_default_chain():
    from app.ingestion import multi_format
    blocked = {c["name"].lower() for c in _ledger()["components"] if c["gate"] == "blocked"}
    chain = json.dumps(multi_format._ENGINES, default=str).lower()
    for name in blocked - {"docling", "marker", "paddleocr"}:  # allow known PDF/OCR fallbacks
        assert name not in chain, f"blocked component {name} leaked into default chain"
```

## Worktree pytest-tmp collision (non-code trap)

Tests using `tmp_path` under a worktree in `.hermes/task-runtime/<name>/` can
hit `FileNotFoundError` on their own tmp files. Before debugging code:
- rerun the same test file in a clean untouched worktree on the same base SHA;
  if it fails there too, it's environment, not your edit;
- the PR's `test (3.12)` job (independent tmp dir) passing confirms this.
