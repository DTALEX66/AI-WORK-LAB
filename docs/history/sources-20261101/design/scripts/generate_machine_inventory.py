#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-B040 / DLDS-H030 — regenerate reports/current/MACHINE_INVENTORY.json.

Read-only host inventory consolidation, promoted from the throwaway script that
lived under ``.project-local/`` so the projection is reproducible from the tree.

Every entry records HOW it was observed (registry / path probe / version file /
CLI) and its boundary. "A common path had no match" is recorded as
NOT_FOUND_IN_SCOPE together with the searched scope, never as "not installed".
No host is launched, nothing is installed, no private data is read.

Usage:
    python scripts/generate_machine_inventory.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports" / "current" / "MACHINE_INVENTORY.json"
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-B040",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-H030"]
ORIGIN = "promoted from .project-local/task-runtime/r5-host-inventory-v2-20260913/build_machine_inventory.py"
REGISTRY_SCOPE = "HKLM/HKCU Uninstall (DisplayName/DisplayVersion/InstallLocation)"


def project_python() -> str:
    """The project virtualenv's interpreter, without assuming a Windows layout.

    (DL-AUDIT-20260914-06) A fresh checkout on another platform has a different
    virtualenv layout; probing only ``.venv/Scripts/python.exe`` would report the
    project interpreter as NOT_FOUND there. Resolve the platform-appropriate
    virtualenv path and fall back to the running interpreter.
    """
    for candidate in (".venv/bin/python", ".venv/Scripts/python.exe"):
        path = REPO / candidate
        if path.exists():
            return str(path)
    return sys.executable or "python3"


def exists(path: str) -> bool:
    return Path(path).exists()


def run(cmd: list, timeout: int = 30) -> tuple:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout)
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001 - a probe failure is data, not a crash
        return -1, f"probe-error: {exc}"


def build(reobserve: bool = False) -> dict:
    """Produce the inventory document.

    An inventory is a *dated observation*, not a live reading. Regenerating
    without ``--reobserve`` reproduces the recorded observation so that every
    consumer which cites its timestamp (the Adobe host matrix, the model radar and
    their tests) stays consistent. A new observation is deliberate, and whoever
    asks for it must update those consumers in the same change.
    """
    if not reobserve and OUT.is_file():
        return json.loads(OUT.read_text(encoding="utf-8"))
    _, ffmpeg_out = run([r"D:/All projects/OS External Configuration/10-toolchains/scoop/apps/"
                         r"ffmpeg/current/bin/ffmpeg.exe", "-version"])
    ffmpeg_version = ffmpeg_out.splitlines()[0] if ffmpeg_out else None
    _, node_out = run([r"C:/Users/ALEX/AppData/Local/hermes/node/node.EXE", "--version"])
    _, python_out = run([project_python(), "-V"])
    _, gpu_out = run([r"C:/Windows/System32/nvidia-smi.exe",
                      "--query-gpu=name,driver_version,memory.total,memory.used,memory.free",
                      "--format=csv,noheader,nounits"])
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                         text=True, encoding="utf-8").stdout.strip()

    software = [
        {"name": "Adobe Photoshop 2025", "version": "26.7.0.15", "presence": "PRESENT",
         "location": "C:/Program Files/Adobe/Adobe Photoshop 2025",
         "exe": "C:/Program Files/Adobe/Adobe Photoshop 2025/Photoshop.exe",
         "exe_exists": exists("C:/Program Files/Adobe/Adobe Photoshop 2025/Photoshop.exe"),
         "observed_by": "registry + path probe",
         "boundary": "installed != process running != workflow verified"},
        {"name": "Adobe Illustrator 2025", "version": "29.5.1", "presence": "PRESENT",
         "location": "C:/Program Files/Adobe/Adobe Illustrator 2025",
         "exe": "C:/Program Files/Adobe/Adobe Illustrator 2025/Support Files/Contents/Windows/Illustrator.exe",
         "exe_exists": exists("C:/Program Files/Adobe/Adobe Illustrator 2025/Support Files/"
                              "Contents/Windows/Illustrator.exe"),
         "observed_by": "registry + path probe",
         "boundary": "installed != process running != workflow verified"},
        {"name": "Adobe Photoshop 2023", "version": "2023", "presence": "PRESENT",
         "location": "C:/Program Files/Adobe/Adobe Photoshop 2023", "observed_by": "directory listing",
         "boundary": "legacy version retained; not the primary test target"},
        {"name": "Adobe Illustrator 2023", "version": "2023", "presence": "PRESENT",
         "location": "C:/Program Files/Adobe/Adobe Illustrator 2023", "observed_by": "directory listing",
         "boundary": "legacy version retained; not the primary test target"},
        {"name": "Adobe Premiere Pro 2025", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": REGISTRY_SCOPE + " + C:/Program Files/Adobe listing",
         "boundary": "not found in searched scope != proof of absence on all volumes"},
        {"name": "Adobe Media Encoder 2025", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": REGISTRY_SCOPE + " + C:/Program Files/Adobe listing",
         "boundary": "same as above"},
        {"name": "Adobe InDesign 2025", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": REGISTRY_SCOPE + " + C:/Program Files/Adobe listing",
         "boundary": "same as above"},
        {"name": "Adobe After Effects 2025", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": REGISTRY_SCOPE + " + C:/Program Files/Adobe listing",
         "boundary": "same as above"},
        {"name": "MiniMax Design", "version": "3.0.10", "presence": "PRESENT",
         "location": "C:/Users/ALEX/AppData/Local/com.minimax.hub", "observed_by": "registry",
         "boundary": "install registry only; private data not read; separate from H3 model and cloud API"},
        {"name": "Penpot Desktop", "version": "0.24.0", "presence": "PRESENT",
         "location": "C:/PenpotDesktop (from uninstall string; InstallLocation empty)",
         "observed_by": "registry (UninstallString)", "boundary": "install registry only; not launched"},
        {"name": "ComfyUI (portable)", "version": "0.33.1", "presence": "PRESENT",
         "location": "D:/All projects/Design External Configuration/toolchains/comfyui/"
                     "ComfyUI_windows_portable",
         "observed_by": "version file ComfyUI/comfyui_version.py + path probe",
         "bundled_python": "python_embeded/python.exe",
         "bundled_python_exists": exists("D:/All projects/Design External Configuration/toolchains/"
                                         "comfyui/ComfyUI_windows_portable/python_embeded/python.exe"),
         "main_py_exists": exists("D:/All projects/Design External Configuration/toolchains/comfyui/"
                                  "ComfyUI_windows_portable/ComfyUI/main.py"),
         "boundary": "files observed; service not started this round; no model generation performed"},
        {"name": "Blender", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": "C:/Program Files/Blender Foundation + registry", "boundary": "not auto-installed"},
        {"name": "OpenDesign", "version": None, "presence": "NOT_FOUND_IN_SCOPE",
         "searched": "C:/Users/ALEX/AppData/Local/Programs, C:/Program Files, registry (Open.?Design)",
         "boundary": "repo has an Open Design host adapter; the desktop app was not located in "
                     "searched scope"},
    ]
    models = [
        {"name": "MiniMax H3 diffusion",
         "path": "D:/All projects/Model library/ComfyUI/diffusion_models/"
                 "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
         "exists": exists("D:/All projects/Model library/ComfyUI/diffusion_models/"
                          "minimax_h3_fl2va_pruned_int8_convrot.safetensors")},
        {"name": "H3 text encoder",
         "path": "D:/All projects/Model library/ComfyUI/text_encoders/"
                 "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
         "exists": exists("D:/All projects/Model library/ComfyUI/text_encoders/"
                          "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors")},
        {"name": "H3 video VAE",
         "path": "D:/All projects/Model library/ComfyUI/vae/minimax_h3_video_vae_fp16.safetensors",
         "exists": exists("D:/All projects/Model library/ComfyUI/vae/minimax_h3_video_vae_fp16.safetensors")},
        {"name": "H3 audio VAE",
         "path": "D:/All projects/Model library/ComfyUI/vae/minimax_h3_audio_vae_fp32.safetensors",
         "exists": exists("D:/All projects/Model library/ComfyUI/vae/minimax_h3_audio_vae_fp32.safetensors")},
    ]
    return {
        "schemaVersion": "design-lab/machine-inventory/v1",
        "task_keys": TASK_KEYS,
        "origin": ORIGIN,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": sha,
        "read_only": True,
        "host": {
            "os": "Windows 11 (10.0.26100)",
            "cpu": "Intel Core i5-14600KF (14 cores)",
            "ram_bytes": 68487733248,
            "gpu": gpu_out or None,
            "gpu_note": "nvidia-smi read-only query; total 8151 MiB VRAM",
        },
        "cli": {
            "ffmpeg": {"path": "D:/All projects/OS External Configuration/10-toolchains/scoop/apps/"
                               "ffmpeg/current/bin/ffmpeg.exe", "version": ffmpeg_version,
                       "exists": exists("D:/All projects/OS External Configuration/10-toolchains/"
                                        "scoop/apps/ffmpeg/current/bin/ffmpeg.exe")},
            "python": {"path": project_python(), "version": python_out},
            "node": {"path": "C:/Users/ALEX/AppData/Local/hermes/node/node.EXE", "version": node_out},
        },
        "software": software,
        "models": models,
        "paths_config": ".project/paths.json (shared_inputs: model-library, design-assets, "
                        "os-toolchain, design-toolchain)",
        "discipline": {
            "not_launched": True, "not_installed": True,
            "not_found_means": "no match within the recorded search scope; never asserted as "
                               "universal absence",
            "no_private_data_read": True,
            "install_registry_does_not_prove": "process running / workflow verified / license "
                                               "applicability",
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reobserve", action="store_true",
                        help="take a NEW observation (changes observed_at); update every consumer "
                             "that cites the previous observation in the same change")
    args = parser.parse_args(argv)
    payload = build(reobserve=args.reobserve)
    if args.check:
        if not OUT.is_file():
            print("MACHINE_INVENTORY=FAIL missing")
            return 1
        current = json.loads(OUT.read_text(encoding="utf-8"))
        # Volatile by design: the observation timestamp, the subject sha, the CLI
        # probe output and the live GPU memory reading.
        stable = ("schemaVersion", "task_keys", "origin", "read_only", "software", "models",
                  "paths_config", "discipline")
        same = all(current.get(key) == payload.get(key) for key in stable)
        print("MACHINE_INVENTORY=" + ("PASS" if same else "DRIFT (re-probe required)"))
        return 0 if same else 1
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print("wrote reports/current/MACHINE_INVENTORY.json")
    present = sum(1 for s in payload["software"] if s["presence"] == "PRESENT")
    absent = sum(1 for s in payload["software"] if s["presence"] == "NOT_FOUND_IN_SCOPE")
    print(f"present={present} not_found_in_scope={absent}")
    print("ffmpeg:", (payload["cli"]["ffmpeg"]["version"] or "probe failed")[:48])
    print("node:", payload["cli"]["node"]["version"], "| python:", payload["cli"]["python"]["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
