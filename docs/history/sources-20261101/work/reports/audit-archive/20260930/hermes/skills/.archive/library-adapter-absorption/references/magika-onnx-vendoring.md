# Magika ONNX Model Vendoring Pattern (ADS-009)

Complete recipe for absorbing google/magika (Apache-2.0) as a vendored ONNX model
with self-contained inference code. No `magika` pip dependency — only `onnxruntime`.

## Source

- Repository: https://github.com/google/magika (Apache-2.0)
- Model: `standard_v3_0` (3.1MB ONNX, 200+ content type labels)
- Config: `config.min.json` (feature extraction params + label space + thresholds)
- Inference: `python/src/magika/magika.py` (Google LLC, Apache-2.0)

## What to vendor

```bash
git clone --depth 1 https://github.com/google/magika.git /tmp/magika-vendor
mkdir -p shared/models/magika/
cp /tmp/magika-vendor/assets/models/standard_v3_0/model.onnx shared/models/magika/
cp /tmp/magika-vendor/assets/models/standard_v3_0/config.min.json shared/models/magika/
cp /tmp/magika-vendor/LICENSE shared/models/magika/LICENSE
```

## Feature extraction (adapted from magika.py)

The core algorithm extracts byte-level features from file content:

```python
def _extract_features(content: bytes) -> np.ndarray:
    """Extract byte features: first 1024 bytes (lstripped) + last 1024 bytes (rstripped).

    Adapted from magika.py (Google LLC, Apache-2.0).
    """
    cfg = _config  # loaded from config.min.json
    beg_size = cfg.get("beg_size", 1024)
    end_size = cfg.get("end_size", 1024)
    padding = cfg.get("padding_token", 256)
    block = cfg.get("block_size", 4096)

    # Beginning: read first block_size bytes, lstrip, take first beg_size bytes
    buf = content[:block]
    beg_raw = buf.lstrip(b"\r\n\t ")
    beg_ints = list(beg_raw[:beg_size].ljust(beg_size, b"\x00"))
    if len(beg_ints) < beg_size:
        beg_ints += [padding] * (beg_size - len(beg_ints))

    # End: read last block_size bytes, rstrip, take last end_size bytes
    if len(content) > block:
        tail = content[-block:]
    else:
        tail = content
    end_raw = tail.rstrip(b"\r\n\t ")
    end_ints = list(end_raw[-end_size:] if len(end_raw) >= end_size else end_raw)
    if len(end_ints) < end_size:
        end_ints = [padding] * (end_size - len(end_ints)) + end_ints

    # CRITICAL: dtype=int32, not int64. The ONNX model rejects int64 with
    # "Unexpected input data type. Actual: (tensor(int64)), expected: (tensor(int32))"
    features = np.array([beg_ints + end_ints], dtype=np.int32)
    return features
```

## Critical traps

### ⚠️ Pure Python feature extraction is BROKEN — model returns "unknown" for all inputs

**Status as of 2026-08-12**: The vendored ONNX model + pure Python feature extraction
produces `label="unknown"` with confidence ~0.01 for **every** input, including known-good
files (docx, pdf, json). The pip magika package works correctly (returns correct labels)
on the same files, proving the model itself is fine — the feature extraction code does not
produce the exact same tensors the model was trained with.

**Root cause**: The pip magika (v1.0+) uses a **Rust backend** for feature extraction,
not the pure Python fallback. The Python `_extract_features()` in `magika.py` is a
legacy/fallback path that does not match the Rust-produced features the model expects.

**Impact**: The vendored model is **not usable for production routing** until the feature
extraction is ported from Rust or calibrated against known-good outputs.

**Workaround**: Keep the pip `magika` package for production accuracy. The vendored
model files and inference code remain in the repo as a **pure Python reference
implementation** — a starting point for a future calibrated port, not a drop-in
replacement.

**Do not claim the vendored model works** until you have verified that `detect()` returns
correct labels (not "unknown") on at least 5 diverse file types.

### int32 vs int64 dtype

The ONNX model expects `tensor(int32)` inputs. Using `np.int64` produces
"unknown" for every input with confidence ~0.01. Always use `dtype=np.int32`.

### Model version mismatch

Pip magika uses `standard_v3_3` with Rust feature extraction. Our vendored
`standard_v3_0` with pure Python feature extraction may have slightly lower
accuracy. Keep both paths available — the pip package for production, the
vendored model for offline/baseline.

### Feature extraction depends on _load_model() call

The `_config` global is set by `_load_model()`. If you call `_extract_features()`
directly without first calling `detect()` (which invokes `_load_model()`),
`_config` will be `None` and you'll get an `AssertionError`. Always go through
`detect()`.

## Label-to-group classification

The model outputs one of 200+ content type labels. For ingestion routing,
map labels to high-level groups:

```python
TEXT_LABELS = {"txt", "markdown", "json", "jsonl", "csv", "tsv", "xml", "html", ...}
OFFICE_LABELS = {"doc", "docx", "xls", "xlsx", "xlsb", "ppt", "pptx", "pdf", "epub", ...}
IMAGE_LABELS = {"png", "jpeg", "gif", "bmp", "webp", "tiff", "ico", "psd", ...}
AUDIO_LABELS = {"mp3", "wav", "flac", "ogg", "midi", "m4a"}
VIDEO_LABELS = {"mp4", "mkv", "webm", "flv", "avi"}
ARCHIVE_LABELS = {"zip", "tar", "gzip", "bzip", "xz", "sevenzip", "rar", ...}
BINARY_LABELS = {"elf", "macho", "pebin", "wasm", "apk", "jar", "sqlite", ...}
```

Unknown labels (with confidence below format-specific threshold or below 0.5) → "unknown".

The config.json includes `overwrite_map` (e.g. "randombytes"→"unknown", "randomtxt"→"txt")
and per-label `thresholds` (e.g. "markdown": 0.9, "latex": 0.95).

## Dependencies added

- `onnxruntime>=1.18` (ONNX runtime, already needed for other models)
- `numpy>=1.24` (already in project deps)

The `magika` pip package is NOT added — the inference code is self-contained.

## Test pattern

```python
def test_magika_vendored_txt(self):
    from shared.file_detection import detect, is_available
    if not is_available():
        pytest.skip("model not present")
    r = detect(b"Hello world\nThis is plain text content.\n" * 50)
    assert r["label"] in ("txt", "randomtxt")
    assert r["group"] == "text"

def test_magika_vendored_json(self):
    r = detect(json.dumps({"k": "v"}).encode() * 10)
    assert r["label"] in ("json",)
    assert r["group"] == "text"
```
