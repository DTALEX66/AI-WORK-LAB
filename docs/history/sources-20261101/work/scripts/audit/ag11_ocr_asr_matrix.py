"""AG-11: measure the OCR and ASR matrix instead of re-verifying that weights exist.

The 2026-09-28 model-governance run measured one mixed zh/en page and one 4.49 s clip,
and AG-11 records that the other cells — plain zh, scanned, PDF, table, page order, and
ASR quality — were never covered. This tool covers them against material that already
exists on this machine, through a runtime that already exists too (LM Studio serving the
registered vision model, and the registered faster-whisper weights in-process on CPU).

Design rules the register gate checks afterwards:

* every declared cell ends up either MEASURED with numbers, or NOT_RUN with a stated
  reason — an absent cell is a failure, not a silent gap;
* ground truth is mechanical: probes for the PDF cell are read out of the same PDF's text
  layer, the rendered cells are built from the strings being checked, and the ASR cell is
  scored by character error rate against the phrase that synthesised the wav;
* the vendor ASR wavs have no transcript, so they are reported as transcripts with unknown
  quality rather than being dressed up as a pass.

Usage: python scripts/audit/ag11_ocr_asr_matrix.py [--out PATH] [--skip-asr]
"""
from __future__ import annotations

import argparse
import base64
import difflib
import io
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / ".project-local" / "artifacts" / "model-governance-20260928" / "fixtures"
LIBRARY = Path(os.environ.get("WORK_LAB_MODEL_LIBRARY", r"D:\All projects\Model library"))
DEFAULT_OUT = REPO / ".project-local" / "artifacts" / "ag11-matrix" / "evidence.json"
BASE_URL = os.environ.get("WORK_LAB_VISION_BASE_URL", "http://localhost:1234/v1")
VISION_MODEL = "qwen2.5-vl-7b-instruct"
WHISPER_DIR = LIBRARY / "whisper" / "faster-whisper-large-v3-turbo"
SPEECH_PHRASE = "本地模型治理由工作实验室统一负责"
PAGE_PROBES = ("WORK-LAB", "Qwen3.5-4B", "Qwen3.8-27B", "Qwen3.8", "Reranker",
               "本地模型治理", "共享模型库", "只保存一份", "嵌入模型", "关注度", "OCR")
FONT_CANDIDATES = (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\Deng.ttf")
REQUEST_TIMEOUT = 420


def http_json(url: str, payload: dict | None, timeout: int) -> tuple[dict, float]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback only
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body or "{}"), round(time.perf_counter() - start, 2)


def png_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def ocr_image(raw: bytes, prompt: str) -> tuple[str, float]:
    payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64,"
                             + base64.b64encode(raw).decode("ascii")}}]}],
        "temperature": 0.0,
        "max_tokens": 900,
    }
    data, seconds = http_json(f"{BASE_URL}/chat/completions", payload, REQUEST_TIMEOUT)
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    return text.strip(), seconds


def probe_hits(text: str, probes: tuple[str, ...] | list[str]) -> dict:
    found = [probe for probe in probes if probe in text]
    missing = [probe for probe in probes if probe not in found]
    return {"probes": len(probes), "hits": len(found), "hit_rate": round(len(found) / max(len(probes), 1), 3),
            "found": found, "missing": missing}


def character_error_rate(reference: str, hypothesis: str) -> float:
    reference_chars = [c for c in reference if not c.isspace()]
    hypothesis_chars = [c for c in hypothesis if not c.isspace()]
    if not reference_chars:
        return 1.0
    matcher = difflib.SequenceMatcher(a=reference_chars, b=hypothesis_chars, autojunk=False)
    correct = sum(block.size for block in matcher.get_matching_blocks())
    return round(1.0 - correct / len(reference_chars), 4)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class Recorder:
    def __init__(self) -> None:
        self.cells: list[dict] = []

    def measured(self, cell_id: str, kind: str, input_ref: str, ground_truth: str, **fields) -> None:
        self.cells.append({"id": cell_id, "kind": kind, "input": input_ref,
                           "groundTruth": ground_truth, "status": "MEASURED", **fields})

    def not_run(self, cell_id: str, kind: str, reason: str) -> None:
        self.cells.append({"id": cell_id, "kind": kind, "status": "NOT_RUN", "reason": reason})

    def failed(self, cell_id: str, kind: str, exc: Exception) -> None:
        self.cells.append({"id": cell_id, "kind": kind, "status": "FAILED",
                           "error": f"{type(exc).__name__}: {exc}"[:300]})


def serve_check() -> dict:
    data, _ = http_json(f"{BASE_URL}/models", None, 20)
    ids = [entry.get("id") for entry in data.get("data") or []]
    require(VISION_MODEL in ids, f"{VISION_MODEL} not served; visible: {ids}")
    return {"servedModels": ids}


def cell_mixed(recorder: Recorder) -> None:
    raw = (FIXTURES / "page-zh-en.png").read_bytes()
    text, seconds = ocr_image(raw, "用 OCR 逐行输出这张图片里的全部文字，保持原样，不要翻译或补全。")
    hits = probe_hits(text, list(PAGE_PROBES))
    recorder.measured("ocr-mixed-zh-en-page", "ocr", str(FIXTURES / "page-zh-en.png"),
                      "11 probe strings taken from the fixture generator",
                      seconds=seconds, characters=len(text), **hits)


def cell_scanned(recorder: Recorder) -> None:
    from PIL import Image, ImageFilter  # type: ignore
    image = Image.open(FIXTURES / "page-zh-en.png").convert("RGB")
    small = image.resize((max(1, image.width * 5 // 10), max(1, image.height * 5 // 10)))
    buffer = io.BytesIO()
    small.save(buffer, format="JPEG", quality=32)
    degraded = Image.open(buffer).convert("RGB").filter(ImageFilter.GaussianBlur(0.6))
    degraded = degraded.resize((image.width, image.height))
    text, seconds = ocr_image(png_bytes(degraded),
                              "这是低质量扫描件。用 OCR 逐行输出可见文字，看不清的用 ? 代替。")
    hits = probe_hits(text, list(PAGE_PROBES))
    recorder.measured("ocr-scanned-degraded", "ocr", "page-zh-en.png rescaled 0.5x + JPEG q32 + blur",
                      "same 11 probes as the clean page",
                      seconds=seconds, characters=len(text), **hits)


def cell_plain_language(recorder: Recorder, which: str, probes: list[str]) -> None:
    raw = (FIXTURES / "page-zh-en.png").read_bytes()
    prompt = ("Extract the visible text exactly as printed." if which == "en"
              else "逐行输出图片里的中文文字，保持原样。")
    text, seconds = ocr_image(raw, prompt)
    hits = probe_hits(text, probes)
    recorder.measured(f"ocr-{which}-prompt", "ocr", "page-zh-en.png",
                      f"probes checked case-sensitively against a {which}-language prompt",
                      seconds=seconds, characters=len(text), **hits)


def cell_pdf(recorder: Recorder) -> None:
    import pypdfium2 as pdfium  # type: ignore
    document = pdfium.PdfDocument(str(FIXTURES / "governance.pdf"))
    page = document[0]
    bitmap = page.render(scale=150 / 72)
    raw = png_bytes(bitmap.to_pil().convert("RGB"))
    text_layer = str(page.get_textpage().get_text_range()).strip()
    probes = [line.strip() for line in text_layer.splitlines() if len(line.strip()) >= 4][:8]
    require(probes, "the PDF text layer produced no probe strings")
    ocr_text, seconds = ocr_image(raw, "用 OCR 逐行输出这一页的全部文字，保持原样。")
    hits = probe_hits(ocr_text, probes)
    recorder.measured("ocr-pdf-page", "ocr", "governance.pdf page 1 rendered at 150 dpi",
                      "probes read mechanically from the same page's text layer",
                      seconds=seconds, characters=len(ocr_text),
                      pdf_text_layer_characters=len(text_layer), **hits)


def build_table_image():
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    require(font_path is not None, f"no CJK font found among {FONT_CANDIDATES}")
    rows = [["模型", "角色", "运行时"],
            ["qwen3-embedding-0.6b", "嵌入", "lmstudio"],
            ["qwen3-reranker-0.6b", "重排", "lmstudio"],
            ["faster-whisper", "语音识别", "进程内"],
            ["qwen2.5-vl-7b", "光学识别", "lmstudio"]]
    image = Image.new("RGB", (900, 340), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 28)
    for y in range(0, 340, 68):
        draw.line((0, y, 900, y), fill=(60, 60, 60), width=2)
    for x in (0, 380, 620, 900):
        draw.line((x, 0, x, 340), fill=(60, 60, 60), width=2)
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row):
            left = (0 if col_index == 0 else 380 if col_index == 1 else 620) + 12
            draw.text((left, row_index * 68 + 18), cell, fill="black", font=font)
    probes = [value for row in rows for value in row]
    return png_bytes(image), probes


def cell_table(recorder: Recorder) -> None:
    raw, probes = build_table_image()
    text, seconds = ocr_image(raw, "这是一张表格。按行输出每个单元格的文字，行内用 | 分隔。")
    hits = probe_hits(text, probes)
    recorder.measured("ocr-table", "ocr", "synthetic 5x3 CJK table rendered with the system font",
                      "the exact cell strings that were drawn", seconds=seconds,
                      cells=len(probes), **hits)


def cell_page_order(recorder: Recorder) -> None:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    require(font_path is not None, "no CJK font available to render the pages")
    pages = [("第一页甲 ALPHA", "marker-first"), ("第二页乙 BRAVO", "marker-second"),
             ("第三页页 CHARLIE", "marker-third")]
    font = ImageFont.truetype(font_path, 42)
    encoded = []
    for line, _ in pages:
        image = Image.new("RGB", (700, 220), "white")
        ImageDraw.Draw(image).text((40, 80), line, fill="black", font=font)
        encoded.append(png_bytes(image))
    payload = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content":
                      [{"type": "text", "text": "按顺序逐页输出每页文字，页与页之间用 --- 分隔，保持原样。"}]
                      + [{"type": "image_url",
                          "image_url": {"url": "data:image/png;base64,"
                                          + base64.b64encode(raw).decode("ascii")}}
                         for raw in encoded]}],
        "temperature": 0.0, "max_tokens": 700,
    }
    data, seconds = http_json(f"{BASE_URL}/chat/completions", payload, REQUEST_TIMEOUT)
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    positions = [text.find(name) for name, _ in pages]
    ordered = all(position >= 0 for position in positions) and positions == sorted(positions)
    recorder.measured("ocr-page-order", "ocr", "three rendered pages in one request",
                      "each page's unique heading string, in the given order",
                      seconds=seconds, pages=len(pages), found_positions=positions,
                      probes=len(pages), hits=sum(1 for p in positions if p >= 0),
                      hit_rate=round(sum(1 for p in positions if p >= 0) / len(pages), 3),
                      order_preserved=bool(ordered))


def cells_asr(recorder: Recorder) -> None:
    from faster_whisper import WhisperModel  # type: ignore
    require(WHISPER_DIR.is_dir(), f"no whisper model dir at {WHISPER_DIR}")
    model = WhisperModel(str(WHISPER_DIR), device="cpu", compute_type="int8")

    wav = FIXTURES / "speech-zh.wav"
    with wave.open(str(wav), "rb") as handle:
        seconds_audio = handle.getnframes() / handle.getframerate()
    start = time.perf_counter()
    segments, _info = model.transcribe(str(wav), language="zh", beam_size=1)
    transcript = "".join(segment.text.strip() for segment in segments)
    took = round(time.perf_counter() - start, 2)
    recorder.measured("asr-fixture-zh-cer", "asr", str(wav),
                      f"the synthesised phrase {SPEECH_PHRASE!r}",
                      audio_seconds=round(seconds_audio, 2), transcribe_seconds=took,
                      real_time_factor=round(took / seconds_audio, 2),
                      transcript=transcript,
                      character_error_rate=character_error_rate(SPEECH_PHRASE, transcript),
                      probes=1, hits=1 if SPEECH_PHRASE in transcript else 0,
                      hit_rate=1.0 if SPEECH_PHRASE in transcript else 0.0)

    vendor = LIBRARY / "sherpa-onnx" / "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23" / "test_wavs"
    names = sorted(p.name for p in vendor.glob("*.wav")) if vendor.is_dir() else []
    if not names:
        recorder.not_run("asr-vendor-wavs", "asr", f"no vendor test wavs under {vendor}")
        return
    results = {}
    for name in names[:3]:
        path = vendor / name
        with wave.open(str(path), "rb") as handle:
            duration = handle.getframerate() and handle.getnframes() / handle.getframerate()
        began = time.perf_counter()
        segments, _info = model.transcribe(str(path), language="zh", beam_size=1)
        text = " ".join(segment.text.strip() for segment in segments)
        results[name] = {"audio_seconds": round(duration, 2),
                         "transcribe_seconds": round(time.perf_counter() - began, 2),
                         "transcript": text}
    recorder.cells.append({
        "id": "asr-vendor-wavs", "kind": "asr", "status": "MEASURED_NO_TRUTH",
        "input": str(vendor), "runs": results,
        "groundTruth": "none — the vendor ships these wavs without transcripts, so "
                       "no character error rate is claimable from them",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-asr", action="store_true")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    recorder = Recorder()
    print("cells=", end="", flush=True)

    environment = {}
    try:
        environment = serve_check()
    except Exception as exc:  # noqa: BLE001 - the whole OCR half depends on it
        for cell in ("ocr-mixed-zh-en-page", "ocr-scanned-degraded", "ocr-zh-prompt",
                     "ocr-en-prompt", "ocr-pdf-page", "ocr-table", "ocr-page-order"):
            recorder.not_run(cell, "ocr", f"vision server unavailable: {type(exc).__name__}: {exc}")

    if not any(cell["id"] == "ocr-mixed-zh-en-page" and cell["status"] == "NOT_RUN"
               for cell in recorder.cells):
        runners = [
            ("ocr-mixed-zh-en-page", cell_mixed),
            ("ocr-scanned-degraded", cell_scanned),
            ("ocr-zh-prompt", lambda rec: cell_plain_language(
                rec, "zh", ["本地模型治理", "共享模型库", "只保存一份", "嵌入模型"])),
            ("ocr-en-prompt", lambda rec: cell_plain_language(
                rec, "en", ["WORK-LAB", "Qwen3.5-4B", "Reranker", "OCR"])),
            ("ocr-pdf-page", cell_pdf),
            ("ocr-table", cell_table),
            ("ocr-page-order", cell_page_order),
        ]
        for cell_id, runner in runners:
            try:
                runner(recorder)
            except Exception as exc:  # noqa: BLE001 - one broken cell must not hide the rest
                recorder.failed(cell_id, "ocr", exc)

    if args.skip_asr:
        recorder.not_run("asr-fixture-zh-cer", "asr", "--skip-asr given")
        recorder.not_run("asr-vendor-wavs", "asr", "--skip-asr given")
    else:
        try:
            cells_asr(recorder)
        except Exception as exc:  # noqa: BLE001
            recorder.failed("asr", "asr", exc)
            recorder.not_run("asr-vendor-wavs", "asr", f"asr unavailable: {type(exc).__name__}")

    cells = recorder.cells
    summary = {
        "schemaVersion": "work-lab/ag11-ocr-asr-matrix/v1",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "visionEndpoint": BASE_URL, "visionModel": VISION_MODEL,
        "endpointInventory": environment,
        "whisperModelDir": str(WHISPER_DIR),
        "cells": cells,
        "counts": {
            "declared": len(cells),
            "measured": sum(1 for c in cells if c["status"].startswith("MEASURED")),
            "not_run": sum(1 for c in cells if c["status"] == "NOT_RUN"),
            "failed": sum(1 for c in cells if c["status"] == "FAILED"),
        },
        "ocrHitRates": [c.get("hit_rate") for c in cells if c["kind"] == "ocr"
                        and c["status"] == "MEASURED"],
        "asrCharacterErrorRate": next((c.get("character_error_rate") for c in cells
                                       if c["id"] == "asr-fixture-zh-cer"), None),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    for cell in cells:
        extra = (f" hits={cell.get('hits')}/{cell.get('probes')} rate={cell.get('hit_rate')}"
                 f" cer={cell.get('character_error_rate')} {cell.get('seconds') or cell.get('transcribe_seconds')}s"
                 if cell["status"].startswith("MEASURED") else f" {cell.get('reason', cell.get('error', ''))[:70]}")
        print(f"\n  {cell['id']:<24} {cell['status']:<18}{extra}", end="")
    print(f"\nSUMMARY {summary['counts']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
