# Deep vs Shallow Absorption: User Preference

## Signal

When the user says "能直接复用的源码等深度的内容也要吸收" or "不是只吸收策略和结构",
they are rejecting the thin-wrapper approach. They want actual source vendoring, not
`pip install` + wrapper.

## What "Deep Absorption" means

### ❌ Shallow (what the user rejects)
```
pip install <library>
→ write a 5-line wrapper function
→ call it "absorbed"
```

### ✅ Deep (what the user wants)

1. **Clone upstream** → read the actual inference/model code
2. **Copy source code** directly into `shared/` or vendored directories
3. **Copy model files** (ONNX, weights, configs) into the project
4. **Remove pip dependency** — the vendored code + model replaces it
5. **Keep LICENSE file** alongside vendored assets
6. **Deep pipeline integration** — not standalone, but wired into the core processing chain

## Concrete example: Magika

Shallow (wrong):
```python
# shared/magika_wrapper.py
import magika  # pip dep
m = magika.Magika()
def detect(b): return m.identify_bytes(b)
```

Deep (right):
```python
# shared/file_detection.py  ← NO magika pip dep
# shared/models/magika/model.onnx  ← 3.1MB vendored
# shared/models/magika/config.min.json  ← vendored
# shared/models/magika/LICENSE  ← vendored
```

The deep version:
- Reads the upstream `magika.py` feature extraction algorithm
- Copies `model.onnx` + `config.min.json` + `LICENSE` into `shared/models/magika/`
- Writes a self-contained inference module using only `onnxruntime` + `numpy`
- No `import magika` anywhere

## Pitfalls of deep absorption

1. **Model resolution**: vendored model version may differ from pip's bundled model.
   Pip magika uses `standard_v3_3` (Rust backend for feature extraction). A vendored
   `standard_v3_0` ONNX model with pure-Python feature extraction may produce different
   (lower accuracy) results. Document the gap honestly.

2. **Feature extraction fidelity**: the upstream may use compiled (Rust/C) code for
   performance-critical paths. A pure Python port must replicate the algorithm exactly.
   Smoke-test against real files of each type.

3. **ONNX dtype sensitivity**: the model expects `int32` input tensors. `np.array(...,
   dtype=np.int64)` silently fails at inference time with `Unexpected input data type`.
   Always check the model's input signature.

4. **Model size in Git**: 3MB+ binary files bloat the repo. Consider whether the model
   should be in the repo or fetched on first use. The user may prefer vendoring
   regardless of size.

## When to use shallow (pip) absorption

- The library is 1000+ lines and well-maintained with frequent security patches
- The library has compiled extensions (Rust/C) that are impractical to port
- The library's API surface is stable and the pip package is the canonical distribution
- Examples: `pydantic`, `numpy`, `fastapi` — no one vendors these

## When to use deep absorption

- Small, stable libraries with clear algorithms (<500 lines of core logic)
- Libraries where you need to modify the algorithm for project-specific needs
- Model files that should be bundled offline (no runtime download)
- User explicitly requests source-level absorption
- License is permissive (MIT, Apache-2.0, BSD) and allows redistribution
