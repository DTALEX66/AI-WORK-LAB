---
name: local-model-runtime-deployment
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/mlops/local-model-runtime-deployment/SKILL.md
---

---
name: local-model-runtime-deployment
description: "Use when deploying local AI runtimes (ComfyUI, MiniMax H3)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [comfyui, model-download, modelscope, vram, deployment, china-network, video-generation]
    related_skills: [comfyui, windows-development-environment, windows-portable-toolchain-boundaries]
    category: mlops
---

# Local Model Runtime Deployment

## When to Use

- User asks to deploy/install a local generative-AI runtime on this Windows
  machine: ComfyUI (portable), MiniMax H3, SD/Flux, Wan, or similar model
  weights.
- User asks to deploy/install a local **agent runtime** (a coding-agent harness
  you install from source and run as a loopback Web UI / headless CLI, e.g.
  DeepSeek Harness). See `references/agent-runtime-deepseek-harness.md` for the
  pinned CLI/env/build/isolation recipe.
- User asks to download large model weights (>1 GB) and you must decide
  source, verify integrity, and place them in the right runtime directories.
- Hardware-feasibility questions: "can this GPU run model X?"
- Project adapter tasks that go from E0 placeholder to E3 runtime evidence
  (e.g. DESIGN-LAB DL-CFY-* / DL-H3-* adapters).

## Golden rule: research the community BEFORE declaring hardware insufficient

User's hard correction (verbatim): **"先去调研，其他人是怎么配置的，别老自己想"**
— do NOT conclude "can't run on this GPU" from model size or your own
reasoning. 8 GB VRAM was judged insufficient for MiniMax H3 by raw spec
reasoning; the community runs it via CPU offload. Before any feasibility
verdict, search:

- ComfyUI GitHub issues/discussions: `api.github.com/search/issues?q=<model>+vram+repo:Comfy-Org/ComfyUI`
- ModelScope model-page discussions (国内可达) and README files
- Dedicated accelerator/Turbo repos (e.g. `xmarre/ComfyUI-Spectrum-MiniMax-H3`)

Only after finding (or failing to find) community evidence do you state a
feasibility verdict, and always cite the evidence.

## Hardware truth: use nvidia-smi for VRAM, NOT Win32_VideoController

`Get-CimInstance Win32_VideoController` reports `AdapterRAM` in a bogus 32-bit
unit (an 8 GB RTX 5060 reported "4 GB"). Always confirm real VRAM with:

```bash
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
```

Also check system RAM (`Get-CimInstance Win32_ComputerSystem
TotalPhysicalMemory`) — with large weights + CPU offload, RAM is the real
binding constraint (41 GB of H3 weights fits a 64 GB box).

## China-network download recipes (user rule: never use the user's VPN proxy for bulk downloads — 浪费流量; prefer domestic mirrors when slow)

- HuggingFace direct AND `hf-mirror.com` often **time out** from CN networks.
  **ModelScope (modelscope.cn) is fast (30+ MB/s)** and hosts official
  repackages (e.g. `Comfy-Org/MiniMax-H3`, `lightx2v/Minimax-h3-Turbo`).
- GitHub release downloads DO work direct (3 MB/s class) but need integrity
  verification (below).
- File-list API (returns JSON `Data.Files[]` with `Name`/`Size`):
  ```
  https://modelscope.cn/api/v1/models/{owner}/{name}/repo/files?Revision=master&Root={subdir}
  ```
- Download URL:
  ```
  https://modelscope.cn/models/{owner}/{name}/resolve/master/{subdir}/{file}
  ```
- ModelScope model pages are a SPA — if you need rendered content
  (README, file sizes, license), use the API above or the browser tool.

## Large-download integrity discipline (validated 2026-08-14)

A 2 GB `.7z` downloaded with a single `curl -sL` can finish with the WRONG
size (server Content-Length 2133107036 vs local 2134737244) and
`7z x` fails with **"Can't open as archive"** — the transfer was corrupted
mid-flight, not a bad archive. Protocol:

1. Record the server's Content-Length first:
   `curl -sIL <url> | grep -i content-length` (follow redirects with -L).
2. Download with resume + retries:
   `curl -sL -C - --retry 3 --retry-delay 5 -o <dest> <url>`.
3. After download, compare final size to Content-Length; mismatch = corrupt.
4. Integrity-test archives BEFORE extracting: `7z t <archive>` (rc=0 = OK).
   `7z x` "Can't open as archive" on a magic-valid header = truncated file,
   NOT a bad download URL.
5. Re-download instead of hoping; the first corrupt 2 GB took the same wall
   time as a clean one.

Also: **execute_code sandbox can return HTTP 206 with 0 bytes transferred
for large downloads** (network restriction inside the sandbox). Use the
terminal (guard-wrapped) for real bulk downloads; verify actual bytes landed.

### Background download launch: only guard-wrapped terminal background works (validated 2026-08-14)

All three "clever" ways to background a multi-GB download fail:
- `threading.Thread` inside execute_code — dies when the sandbox exits.
- `subprocess.Popen(creationflags=DETACHED_PROCESS)` — process stays alive
  but curl stalls at 0 bytes (sandbox network restriction applies).
- A downloader script run directly by execute_code — same sandbox limit.

The reliable pattern: write the downloader script under the project's
`.hermes/task-runtime/` (guard-allowed path), have it write output to the
external root (outside the repo), and launch it as
`terminal(background=true, notify_on_complete=true)` via the guard wrapper:
`python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python .hermes/task-runtime/downloader.py`.
Then **do not babysit it** — work on parallel deliverables (evidence docs,
registry sync, other PRs) and let the completion notification arrive.

Also: a corrupt large file may be locked by a leftover curl process —
`tasklist | grep curl`, `taskkill /F /PID` before deleting it.

## MiniMax H3 on 8 GB VRAM — supported, via CPU offload

Key facts (evidence trail in `references/minimax-h3-low-vram.md`):

- ComfyUI issue #15251 confirms 8 GB VRAM (RTX 3060 Ti class) + partial CPU
  offloading is a supported scenario; the VAE device-mismatch bug was fixed
  upstream ("Fixed in the recent update").
- Official Comfy-Org/MiniMax-H3 README: prefer **int8_convrot** over
  fp8_scaled when PyTorch is cu130 (our portable ships torch cu130);
  nvfp4 text encoder does NOT require a Blackwell GPU.
- Minimal workable set ≈ 41 GB weights (fits 64 GB RAM with weights resident):
  `minimax_h3_fl2va_pruned_int8_convrot` (20.97 GB) +
  `qwen3vl_32b_minimax_h3_nvfp4_awq` (14.61 GB) +
  `minimax_h3_video_vae_fp16` (4.85 GB) + `minimax_h3_audio_vae_fp32` (0.56 GB).
- Model placement:
  `models/diffusion_models/`, `models/text_encoders/`, `models/vae/`.
  Workflows: `Comfy-Org/workflow_templates/templates/video_minimax_h3_{i2v,t2v,r2v}.json`.
- Accelerators for low VRAM: `xmarre/ComfyUI-Spectrum-MiniMax-H3`
  (training-free, ~45% fewer transformer evals) and Turbo variants
  (`lightx2v/Minimax-h3-Turbo`, 4-step/8-step, 1.3–1.8 GB DiT).

## Governance: keep SOURCE_REGISTRY in sync with actual state (validated 2026-08-14)

When a source's real status changes (e.g. ai-product-os frontend moved to
quarantine and its source externalized out of Git), the SOURCE_REGISTRY entry
must be updated to match: `integration_mode: vendor-adapt` → `quarantine`,
`status: adopt-now` → `review-required`, plus rollback/windows notes. Registry
drift vs reality is a governance gap caught by audits. Edit the JSON with
`patch` (targeted line changes) — NEVER re-serialize with `json.dumps`, which
normalizes indentation and turns a 6-line fix into a 4000-line diff.

## Project experience ledger: capture lessons in-repo as LESSONS.md

User request pattern: "总结项目经验错误问题修复方案，固化到本项目". After a
long multi-PR session, write `project-memory/LESSONS.md` (project root for
DESIGN-LAB; path may vary per repo) with entries in the fixed shape
「问题 → 根因 → 修复 → 防复发」, grouped by theme (runtime deployment,
governance, discipline, git/delivery). Two hard user constraints:
- **Scope to THIS project only** — user explicitly rejects cross-project
  content ("WORK LAB不要"): do NOT include other projects' overlay/config
  lessons, and do not even name the other project in the doc (remove it from
  the header scope note AND from example text).
- Ship it as a normal PR (branch → CI → squash merge), same as any doc change.

## ComfyUI Portable specifics

- Windows Portable build: download from Comfy-Org/ComfyUI releases
  (`ComfyUI_windows_portable_nvidia.7z`, ~2 GB), extract with 7-Zip
  (`D:\All projects\OS External Configuration\toolchains\scoop\shims\7z.exe`).
- Layout: `ComfyUI_windows_portable/{python_embeded,ComfyUI,run_nvidia_gpu.bat}`.
- Verify: `python_embeded/python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"`
  (portable ships torch cu130 with CUDA enabled).
- Launch headless: `python_embeded/python.exe -s main.py --port 8188
  --disable-auto-launch` from the ComfyUI dir; health check
  `curl http://127.0.0.1:8188/system_stats` → devices[] shows cuda:0 + VRAM.
- Keep the runtime under the external dependency root (e.g.
  `D:\All projects\Design External Configuration\toolchains\comfyui`), NOT
  inside a Git repo — consistent with project external-dependency policy.
- **User may name a NEW external root for a specific project** (e.g. DESIGN-LAB
  uses `D:\All projects\Design External Configuration` while ArcheAxis uses
  `OS External Configuration`). Ask/confirm the exact root before downloading;
  do not assume the shared one.

### Model-library migration: move weights to a shared model root (validated 2026-08-16)

When the user names a shared local model library (e.g. `D:\All projects\Model
library`) and asks to move a project's large model weights into it, do NOT
copy-and-delete tens of GB. Pattern that worked for DESIGN-LAB's MiniMax H3
(39.55 GB across 4 files):

1. **Subdirectory per runtime** — ComfyUI gets its own exclusive subdir
   `Model library/ComfyUI/{diffusion_models,text_encoders,vae}`. Future tools
   get sibling subdirs.
2. **Same-drive move = atomic rename** — `shutil.move` on the same drive falls
   back to `os.rename`, instant (no 39 GB copy). First probe `127.0.0.1:8188`;
   abort if ComfyUI is listening.
3. **Head/tail hash, not full sha256** — a full sha256 over 39 GB is minutes
   per file. Same-drive rename cannot change bytes, so verify size + sha256 of
   the first and last 1 MB only. Full hash is only needed for cross-drive copy.
4. **extra_model_paths.yaml keeps ComfyUI working** — write it next to
   `main.py` so ComfyUI finds the moved weights without copying them back:
   ```yaml
   model_library:
     base_path: D:/All projects/Model library/ComfyUI
     diffusion_models: diffusion_models
     text_encoders: text_encoders
     vae: vae
   ```
5. **Do NOT move ComfyUI's bundled components** — `vae_approx/` (taesd
   `*.safetensors`) and the `put_*_here` 0-byte placeholders ship with ComfyUI
   and are not user weights; leave them in the default `models/` tree.
6. **Write a migration manifest** to the project's ignored
   `.hermes/task-runtime/` (per-file src/dst/size/head+tail hash) as evidence.

### Daemon-launcher trap: subprocess.run(timeout=N) kills the whole tree (validated 2026-08-14)

A wrapper script that starts the daemon with
`subprocess.run([...], timeout=120)` does NOT keep it alive forever — at N
seconds Python raises TimeoutExpired and **kills the entire child process
tree, including the ComfyUI server**. Symptom: everything works for ~2
minutes (health checks pass, models recognized), then the background wrapper
reports `exit code 1` + TimeoutExpired and the port goes dead. This bit
twice in one session. For any long-running daemon use `subprocess.Popen`
with NO timeout + `proc.wait()`, log to a file, and use
`creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`:

```python
with open(LOG, 'w', encoding='utf-8') as logf:
    proc = subprocess.Popen([str(py), '-s', 'main.py', '--port', '8188',
                             '--disable-auto-launch'],
                            cwd=str(comfy), env=env,
                            stdout=logf, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    proc.wait()   # no timeout — daemon stays up
```

Verify the fix by waiting PAST the old timeout point (135 s) and re-checking
`/system_stats` — if it still answers, the daemon survived.

## Verify model recognition via ComfyUI API (beyond /system_stats, validated 2026-08-14)

`/system_stats` proves the runtime is up, but NOT that the downloaded models
are loadable. After placing weights, restart ComfyUI and probe the API:

```python
# 1. Nodes registered — full scan and grep; node names are NOT guessable
#    ("MiniMaxH3" alone does not exist):
GET http://127.0.0.1:8188/object_info            # → ~849 nodes
#    MiniMax H3: EmptyMiniMaxH3LatentAV, MiniMaxH3ImageToVideo,
#    MiniMaxH3ReferenceToVideo, MiniMaxH3SigmaShift, MinimaxTextToVideoNode

# 2. Model files actually visible to each loader:
GET http://127.0.0.1:8188/object_info/UNETLoader   # input.unet_name → [filenames]
GET http://127.0.0.1:8188/object_info/CLIPLoader   # input.clip_name
GET http://127.0.0.1:8188/object_info/VAELoader    # input.vae_name
```

All three loaders must list your downloaded files — that is the E3 "models
recognized" evidence, distinct from "runtime started".

## E0→E3 upgrade: verifier gates may hardcode E0 state (validated 2026-08-14)

When an adapter legitimately reaches E3, a gate that requires the evidence
README to declare `E0 placeholder (no execution)` will FAIL — the gate was
written for the pre-runtime state. Symptom: `VERIFY_<TOOL>_GATE=FAIL
findings=1` with `EVIDENCE: must declare E0 placeholder`. Fix the gate to
accept both states: `has_e0 OR (has_e3 AND evidence/E3-*.md present)`, and
update the gate's success message to reflect the actual state (E0 vs E3).
Always run the full verify chain + tests after upgrading a manifest, before
opening the PR.

## Verification checklist

- [ ] VRAM measured with nvidia-smi (never Win32_VideoController.AdapterRAM)
- [ ] Feasibility verdict cites community evidence, not raw spec reasoning
- [ ] Downloads matched server Content-Length; `.7z` passed `7z t` before extract
- [ ] Bulk downloads ran via terminal (guard-wrapped), not execute_code sandbox
- [ ] Runtime launched and `/system_stats` reports cuda device
- [ ] Adapter evidence updated (E0 → E3 with runtime version + task IDs)
