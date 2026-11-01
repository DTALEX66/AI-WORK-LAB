---
name: ocr-asr-bakeoff
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/ocr-asr-bakeoff/SKILL.md
---

---
name: ocr-asr-bakeoff
description: "Use when evaluating OCR/ASR engines with CER/WER bake-offs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ocr, asr, cer, wer, evaluation, bakeoff, recognition]
    related_skills: [python-testing, windows-development-environment]
---

# OCR/ASR Bake-off (Engine Evaluation)

## When to Use

- Comparing OCR engines (Tesseract, PaddleOCR, RapidOCR, EasyOCR) or ASR engines
  (faster-whisper, whisper.cpp, sherpa-onnx) against a fixed fixture corpus.
- Selecting an engine for a language mix (CJK vs Latin) and needing honest CER/WER,
  not engine-reported confidence.
- Re-running an existing bake-off framework (e.g. `shared/bakeoff.py` +
  `shared/bakeoff_engines.py` in Cognitive-Loop-OS) with new engines or fixtures.

## Core Workflow

1. **Build fixtures**: image/audio file + a same-stem `.txt` sidecar with ground-truth
   text. `load_fixtures(dir, pattern)` pairs them automatically; fixtures without a
   `.txt` sidecar get `cer=None` (no truth, no accuracy claim).
2. **Register engines** as `EngineUnderTest(name, fn, available, version, notes)`.
   Unavailable engines (missing dependency) are honest stubs: `available=False` and
   the runner skips them — never fake a result. For engines activated by a *lightweight*
   install (pip package, no system binary), detect availability dynamically instead of
   hardcoding `False`: `available=_find_spec_available("rapidocr_onnxruntime")` via
   `importlib.util.find_spec`. This flips the engine on automatically the moment the
   dependency lands, so the same corpus run picks it up without editing the registry.
   Keep `available=False` hardcoded only for heavy-framework stubs (paddleocr/easyocr
   need torch/paddlepaddle) and note in the SKILL what the activation condition is.
3. **Run** `run_bakeoff(engines, fixtures)` → `BakeoffResult` rows with CER/WER,
   duration, char_count, success/error.
4. **Report** CSV + JSON (`report_csv` / `report_json`). Keep both; CSV is the
   human-readable table, JSON the machine-readable artifact.
5. **CLI runner for repeatability** (Cognitive-Loop-OS `scripts/run_bakeoff.py`,
   2026-08-12 #126): a bake-off is only useful if it can be re-run after an
   engine lands or a fixture changes. The CLI exposes
   `--mode ocr|asr|all`, `--fixtures DIR`, `--out DIR`, lists skipped
   (unavailable) engines honestly, and writes timestamped
   `bakeoff-<mode>-<stamp>.{csv,json}` under `.hermes/task-runtime/bakeoff-results/`.
   It imports `load_fixtures` (NOT `enumerate_fixtures` — verify public names
   before writing imports, see `python-testing`), and uses the same registry +
   runner as the tests so the CLI and the test suite evaluate the same engines.
   Prove it with a real run against the corpus (not just `--help`) before
   landing: engine discovery → run → CSV/JSON report is the full path.

## Pitfalls (all validated 2026-08-12)

### `eng+chi_sim` language interleaving inflates CJK CER catastrophically

Tesseract with `lang="eng+chi_sim"` inserts **spaces between Chinese characters**
(the eng model tokenizes by word), so `机器学习是...` comes back as
`机 器 学 习 是 ...`. CER on a clean CJK fixture balloons to **0.8** while the CLI
(`tesseract x.png stdout -l chi_sim`) scores **0.0** on the same image.

- Register **separate per-language engine variants** (`tesseract` = eng,
  `tesseract-chi-sim` = chi_sim) instead of one mixed-language engine.
- Let the bake-off show the language-dependent tradeoff:
  `tesseract`: en_clean CER .0227 / zh_clean 1.0
  `tesseract-chi-sim`: en_clean .0455 / zh_clean **0.0**
- Validate language data first: `tesseract --list-langs` must include every
  `lang=` you use; on Windows set `TESSDATA_PREFIX` to the versioned data dir
  (see `windows-development-environment` skill).

### `or ""` blanks a perfect CER of 0.0 in reports

`"cer": r.cer or ""` writes an empty cell for a **perfect** score because `0.0`
is falsy. Use `r.cer if r.cer is not None else ""` — `None` means "no ground
truth", `0.0` means "flawless"; the report must distinguish them.

### PIL fixture images: CJK-first font order

`ImageFont.truetype("arial.ttf")` **succeeds** on most systems but renders CJK as
blank boxes — OCR then returns empty text and CER=1.0, which looks like an OCR
failure when it is a fixture-generation bug. Try CJK-capable fonts first:

```python
for candidate in ("msyh.ttc", "simhei.ttf", "simsun.ttc", "arial.ttf"):
    try:
        font = ImageFont.truetype(candidate, 20)
        break
    except OSError:
        continue
```

Note `msyh.ttc`/`simsun.ttc` are TrueType *collections* — PIL handles them fine,
Tesseract OCRs the rendered result normally.

### Verify the engine's own output, not just the framework

A bake-off "OK" row only proves the engine ran. Cross-check at least one fixture
against the engine CLI directly (`tesseract x.png stdout -l chi_sim`) to confirm
the framework call path (pytesseract args, env vars) matches the CLI behavior.
In this session the framework's `eng+chi_sim` path scored 0.8 while the CLI
scored 0.0 — only the CLI cross-check exposed the framework bug.

### Activating an ONNX engine: uv pip install must target the run venv

`uv pip install rapidocr-onnxruntime` with no `--python` installs into the
project's `.venv`, NOT the venv that `uv run --frozen --group ci ...` executes
against when `UV_PROJECT_ENVIRONMENT` is set. The dynamic `find_spec` then still
returns `None` and the engine stays off — looks like the detector is broken, but
the package went to the wrong interpreter. Target the run venv explicitly:

```bash
uv pip install --python "D:/.../cognitive-loop-os-ci-venv/Scripts/python.exe" rapidocr-onnxruntime
```

Verify with the SAME interpreter the bake-off uses:
`uv run --frozen ... python -c "import importlib.util; print(importlib.util.find_spec('rapidocr_onnxruntime'))"`
(no need to guess — a direct `find_spec` check tells you which side is wrong).

## Interpreting results: latency vs accuracy tradeoff (validated 2026-08-12)

| Engine | en_clean | en_noisy | zh_clean | avg CER | latency/img |
|---|---|---|---|---|---|
| tesseract (eng) | .0227 | .025 | 1.0 (garbage) | .3492 | ~100ms |
| tesseract-chi-sim | .0455 | .1 | 0.0 (perfect) | .0485 | ~160ms |
| rapidocr (ONNX) | .0227 | **0.0** | **0.0** | **.0076** | ~1.3s |

Read the table, don't just take the column minimum:
- **RapidOCR wins all three fixtures including noisy images** (ONNX-based, no
  torch/paddlepaddle, CPU-friendly) — the default choice for CJK-first corpora.
- Tesseract is 8–13× faster; use it when latency matters more than the last
  CER point, or per-language (`eng` for Latin, `chi_sim` for CJK — never both).
- Publish the tradeoff in the report; a bake-off is a decision tool, not a
  beauty contest. "Engine X has lower CER" is a claim you can make; "engine X is
  better" needs the latency + dependency-cost columns.

## ASR side (validated 2026-08-12, faster-whisper)

### Generating audio fixtures on Windows with no TTS package installed

Windows ships SAPI voices — check what's available, then synthesize WAVs with a
`.ps1` using `System.Speech`:

```powershell
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $synth.GetInstalledVoices()) { $v.VoiceInfo.Name + " | " + $v.VoiceInfo.Culture }
# e.g. "Microsoft Huihui Desktop | zh-CN", "Microsoft Zira Desktop | en-US"
```

Synthesize with `$synth.SelectVoice($Name); $synth.SetOutputToWaveFile($out); $synth.Speak($text)`.
Ground truth goes in the same-stem `.txt` sidecar, and `load_fixtures(dir, "*.wav")`
pairs them — reuse the exact OCR fixture mechanism for audio.

**Pitfall: PowerShell 5.1 + CJK in `.ps1`.** A UTF-8 `.ps1` written without BOM is
parsed as ANSI by Windows PowerShell 5.1, so CJK literals in the script cause
`ParserError: 字符串缺少终止符` / `TerminatorExpectedAtEndOfString`. Two fixes:
write the file as UTF-8 **with BOM**, or keep the script ASCII-only and express
CJK text as `[char]0x...` code-point escapes:

```powershell
$zh = [string]::Join('', @(0x673A,0x5668,0x5B66,0x4E60))  # 机器学习
# or write via [System.IO.File]::WriteAllText with [Text.Encoding]::UTF8
```

Note Git-Bash mangling: `$s` inside a `powershell -Command "...$s..."` string is
expanded by bash before PowerShell sees it — prefer `-File script.ps1`.

### faster-whisper: model download + real numbers (base, CPU int8)

- `pip install faster-whisper`, then first transcribe downloads the model
  (~150MB for `base`) into the HF hub cache; first run includes model load
  (tens of seconds), subsequent runs are fast.
- Results on SAPI-synthesized fixtures (base model, CPU int8):
  `en_clean` CER **0.0**, `en_slow` CER **0.0**, `zh_clean` CER **0.2**.
- **zh CER 0.2 is one traditional-vs-simplified glyph**: `机器` was transcribed
  as `機器`. The base model is traditional-heavy; language auto-detect (zh,
  p=1.00) is correct. This is a model property, not a framework bug — report it
  honestly and consider a post-process 繁→简 pass or a larger/zh-tuned model
  when simplified-Chinese output matters. Always print the raw transcript
  (`segments[].text`) when CER is non-zero — a single misread glyph explains
  most of it.
- `FASTER_WHISPER.available` should be dynamic via
  `find_spec("faster_whisper")`, same pattern as rapidocr.

### Testing optional-heavy-dependency stubs without installing them

`shared/audio_vad.py` (Silero VAD) imports `torch` only at call time. To test
both the unavailable path and the delegation contract without a 2GB torch
install, inject fake modules into `sys.modules`:

```python
torch = types.ModuleType("torch")
hub = types.ModuleType("torch.hub")
hub.load = fake_load
torch.hub = hub
monkeypatch.setitem(sys.modules, "torch", torch)
monkeypatch.setitem(sys.modules, "torchaudio", torchaudio)
```

The fake `utils` tuple must match the real shape
(`(get_speech_timestamps, ...)` — 5 elements), and fake WAV tensors need
`.shape` and `.mean()` for the read path. Cover: unavailable → empty list,
available → delegates to silero, unreadable audio → empty (never crash),
probe returns a bool (never raises).

## Reports as Evidence

Keep the generated corpus + CSV + JSON under the project's evidence/runtime dir
(e.g. `.hermes/task-runtime/bakeoff-corpus/`, `bakeoff-results/`), not in the
source tree. The CSV/JSON are the durable artifact; delete ad-hoc debug scripts.

See `references/h2-ocr-bakeoff-run-20260812.md` for the concrete OCR runs and
results, and `references/h2-asr-bakeoff-run-20260812.md` for the ASR run
(SAPI fixture generation, faster-whisper data, VAD stub tests).

## Vendored ONNX models (Magika-style): inference pitfalls

When an engine under test is a vendored ONNX model (content detection,
embeddings, ASR) rather than an external binary, the pitfalls are different
from language-data issues — see `references/onnx-inference-pitfalls.md`:
- **Double-softmax**: if the ONNX graph already ends in softmax
  (`raw[0].sum() ≈ 1.0`), applying `_softmax` again flattens confident
  predictions (0.889 → 0.011) and every file silently reports `unknown`.
  Probe `raw[0].sum()` and `raw[0].max()` before touching code.
- **Padding token**: short inputs must pad with the config's `padding_token`
  (Magika = 256), never byte 0 (`bytes.ljust(b"\x00")` makes the pad branch
  dead and corrupts features). Assert feature shape from
  `sess.get_inputs()[0].shape` (Magika = beg 1024 + end 1024 = 2048), not a
  hardcoded guess.
- **Coarse label vs format routing**: Magika labels JSON Canvas as `json`; a
  `json → txt` content-format map silently disables the dedicated
  `.canvas` handler. Don't collapse labels that map to multiple handlers —
  fall back to extension detection, and re-run format-routing tests after any
  detector fix (it can change behavior of sibling paths that depended on the
  detector failing).

