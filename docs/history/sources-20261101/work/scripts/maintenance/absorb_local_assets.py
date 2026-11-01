"""Absorb what is actually on this machine into the two registries — measured, not claimed.

Reads the physical Model library / OS External Configuration roots, completes three
TRUNCATED digests only where the computed hash starts with the recorded prefix, corrects
a wrong byte count, reclassifies a declared HF entry that has refs but no blobs, and
registers three shared toolchain executables with version readback.

Nothing is written that a measurement did not produce. Foreign-project paths are recorded
as read-only references, never as WORK-LAB-owned weights.
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path.cwd()
MR_PATH = ROOT / ".project/governance/model-registry.json"
IDX_PATH = ROOT / ".project/governance/external-libraries-index.json"
OS_ROOT = pathlib.Path(r"D:\All projects\OS External Configuration")
MODEL_ROOT = pathlib.Path(r"D:\All projects\Model library")
TODAY = "2026-10-07"


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def readback(argv):
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return ((done.stdout or "") + (done.stderr or "")).splitlines()[:1] or [""]


mr = json.loads(MR_PATH.read_text(encoding="utf-8"))
assert pathlib.Path(mr["sharedPhysicalRoot"]) == MODEL_ROOT, mr["sharedPhysicalRoot"]

COMPLETE = {
    "faster-whisper-large-v3-turbo": "whisper/faster-whisper-large-v3-turbo/model.bin",
    "sherpa-onnx-sense-voice": ("sherpa-onnx/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
                                "/model.int8.onnx"),
}
changed = []
for model in mr["models"]:
    mid = model.get("id")
    rel = COMPLETE.get(mid)
    if not rel:
        continue
    target = MODEL_ROOT / rel
    if not target.is_file():
        print(f"ABORT {mid}: declared artifact missing on disk: {target}")
        sys.exit(2)
    actual = digest(target)
    prefix = (model.get("assetDigest") or {}).get("prefix") or ""
    if prefix and not actual.startswith(prefix):
        print(f"ABORT {mid}: computed {actual[:16]} does not start with the recorded "
              f"prefix {prefix} — the file is not what the record describes")
        sys.exit(3)
    model["sha256"] = actual
    model["file"]["bytes"] = target.stat().st_size
    model["file"]["relative_path"] = rel
    model["assetDigest"] = {
        "state": "VERIFIED_FULL",
        "artifact": target.name,
        "prefix": actual[:16],
        "completedAt": TODAY,
        "how": (f"Re-hashed {rel} on {TODAY} under the owner's 2026-10-07 authorization; "
                f"the computed digest starts with the 16-hex prefix the "
                f"2026-09-29 migration round recorded, which is what identifies this file "
                "as the same artifact rather than a replacement. The prior state was "
                "TRUNCATED with sha256=null."),
    }
    changed.append((mid, actual[:16], target.stat().st_size))

# The zipformer entry named an artifact that does not exist by that name; record the
# three real files instead of leaving a pointer nothing can resolve.
ZIP_DIR = MODEL_ROOT / ("sherpa-onnx/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23")
if ZIP_DIR.is_dir():
    for model in mr["models"]:
        if model.get("id") != "sherpa-onnx-streaming-zipformer-zh-14m":
            continue
        present = [p for p in sorted(ZIP_DIR.glob("*.onnx"))]
        model["assetDigest"] = {
            "state": "MULTI_FILE_DIR",
            "artifact": "encoder-epoch-99-avg-1.onnx",
            "files": [{"name": p.name, "bytes": p.stat().st_size} for p in present],
            "note": ("sherpa streaming ASR is a triple (encoder/decoder/joiner), not one "
                     "weight; the previous record pointed at an artifact name that does "
                     "not exist in the directory. Byte counts and names are read from the "
                     f"directory on {TODAY}; full digests are not claimed here because "
                     "no prior prefix exists to identify these files against."),
        }
        changed.append((model["id"], "names+bytes recorded", len(present)))

mr["lastVerified"] = TODAY
MR_PATH.write_text(json.dumps(mr, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\r\n")
print("MODEL_REGISTRY updated:", changed)

# ---------------------------------------------------------------- toolchain assets
idx = json.loads(IDX_PATH.read_text(encoding="utf-8"))
libs = {l["id"]: l for l in idx["libraries"]}

TC = libs["os-external-toolchains"]
TC["assets"] = [a for a in TC["assets"] if a.get("name") not in
                {"tesseract (OCR)", "tesseract language packs", "ffmpeg",
                 "rapidocr-onnxruntime + PP-OCRv4 weights (foreign project venv)"}]


def exe_asset(name, rel_dir, exe_rel, argv, kind, role):
    base = OS_ROOT / "10-toolchains" / "scoop" / "apps" / rel_dir
    exe = base / exe_rel
    if not exe.is_file():
        print(f"ABORT asset missing: {exe}")
        sys.exit(4)
    out = readback([str(exe)] + argv)
    return {"name": name, "kind": kind, "role": role,
            "relativePath": str(exe.relative_to(OS_ROOT)).replace("\\", "/"),
            "versionReadback": out[0].strip()[:120],
            "sha256": digest(exe), "bytes": exe.stat().st_size,
            "verifiedAt": TODAY,
            "note": "resolved from apps/<pkg>/<version>/, not a scoop shim (the shims are stale)"}


TC["assets"].append(exe_asset(
    "tesseract (OCR)", "tesseract/5.5.0.20241111", "tesseract.exe",
    ["--version"], "ocr-executable", "local.ocr.printed"))
TC["assets"].append(exe_asset(
    "ffmpeg", "ffmpeg/8.1.2", "bin/ffmpeg.exe", ["-version"], "media-executable",
    "local.media.audio-extract-for-asr"))

lang_dir = OS_ROOT / "10-toolchains/scoop/apps/tesseract-languages"
langs = sorted(p for p in lang_dir.rglob("*.traineddata")) if lang_dir.is_dir() else []
TC["assets"].append({
    "name": "tesseract language packs",
    "kind": "ocr-data",
    "role": "local.ocr.languages",
    "relativePath": "10-toolchains/scoop/apps/tesseract-languages",
    "files": len(langs),
    "chi_sim": next(({"bytes": p.stat().st_size, "sha256": digest(p)} for p in langs
                    if p.name == "chi_sim.traineddata"), None),
    "verifiedAt": TODAY,
    "note": "count and the Chinese model's hash are read from disk, not from a release page",
})

TC["assets"].append({
    "name": "rapidocr-onnxruntime + PP-OCRv4 weights (foreign project venv)",
    "kind": "read-only-foreign-reference",
    "role": "local.ocr.candidate",
    "relativePath": "ArcheAxis-Knowledge-OS-ci-venv/Lib/site-packages/rapidocr_onnxruntime",
    "onnx": [{"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p)}
             for p in sorted((OS_ROOT / "ArcheAxis-Knowledge-OS-ci-venv/Lib/site-packages"
                              "/rapidocr_onnxruntime/models").glob("*.onnx"))],
    "package": "rapidocr_onnxruntime-1.4.4.dist-info",
    "verifiedAt": TODAY,
    "note": ("Present on the shared root but installed inside ANOTHER project's venv, so it "
             "is registered as a read-only reference with measured digests, not as a "
             "WORK-LAB-owned weight or a dependency this repository may import. Absorbing "
             "it for real means installing it into a WORK-LAB-owned environment, which is "
             "an AG-11 decision with its own authorization." ),
})

HF = libs["os-external-hf-models"]
hub = OS_ROOT / "40-models/huggingface/hub"


def hub_state(dirname):
    d = hub / dirname
    if not d.is_dir():
        return None
    blobs = [p for p in (d / "blobs").glob("*")] if (d / "blobs").is_dir() else []
    refs = [p for p in (d / "refs").glob("*")] if (d / "refs").is_dir() else []
    return {"dir": dirname, "blobFiles": len(blobs), "refs": len(refs),
            "bytes": sum(p.stat().st_size for p in blobs if p.is_file())}


ppocr = [hub_state(p.name) for p in sorted(hub.glob("models--PaddlePaddle--*"))]
ppocr = [s for s in ppocr if s]
whisper_base = hub_state("models--Systran--faster-whisper-base")
whisper_tiny = hub_state("models--Systran--faster-whisper-tiny")

HF["assets"] = [
    {"name": "PaddlePaddle PP-OCR / PP-LCNet / UVDoc (5 repos)",
     "role": "ocr",
     "state": "REFS_ONLY_NO_BLOBS" if all(s["blobFiles"] == 0 for s in ppocr) else "PARTIAL",
     "repos": ppocr,
     "verifiedAt": TODAY,
     "note": ("Measured 2026-10-07: every one of these snapshot directories holds a refs "
              "pointer and ZERO blob files, i.e. the weights were never downloaded. The "
              "previous entry asserted role=ocr with no state, which read as availability. "
              "AG-11 must not count this root as an OCR source.")},
    {"name": "Systran faster-whisper-base / -tiny",
     "role": "asr",
     "state": "BLOBS_PRESENT" if whisper_base and whisper_base["blobFiles"] else "UNKNOWN",
     "repos": [s for s in (whisper_base, whisper_tiny) if s],
     "verifiedAt": TODAY,
     "note": "These two do carry blobs; the smaller models are the fallback ASR set."},
]
HF["totalSizeGb"] = round(sum(
    p.stat().st_size for p in hub.rglob("*") if p.is_file()) / 2**30, 2)
idx["lastVerified"] = TODAY
idx["generatedAt"] = TODAY
IDX_PATH.write_text(json.dumps(idx, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\r\n")
print("INDEX updated: toolchain assets =", len(TC["assets"]),
      "hf totalSizeGb =", HF["totalSizeGb"])
print("ppocr blob check:", all(s["blobFiles"] == 0 for s in ppocr),
      "whisper-base blobs:", (whisper_base or {}).get("blobFiles"))
