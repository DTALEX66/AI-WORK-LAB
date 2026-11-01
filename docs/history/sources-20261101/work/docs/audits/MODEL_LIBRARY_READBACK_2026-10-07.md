# Model library readback — 2026-10-07

- Root: `D:\All projects\Model library`
- Checked at: `2026-10-06T20:30:56Z`
- Method: `sha256 over the full bytes of each file as it sits on this machine`
- Command: `python scripts/audit/model_library_readback.py` (receipt: `.project-local/artifacts/model-library-readback.json`)
- Gate: `python scripts/ci/verify_model_registry_integrity.py` (AG-05g refuses a byte claim with no recorded basis)

## Why this pass existed

`.project/governance/model-registry.json` carried a 64-hex `sha256` for nine of ten models and health words like `DOWNLOADED_HASH_VERIFIED`, while nothing recorded what those digests were digests *of*, or when anyone last recomputed them. The integrity gate checked the shape of each value and passed. A copied-back upstream hash and a locally recomputed digest were therefore indistinguishable in the machine authority — the same defect class ERR-125 caught in the recovered-source registry, one layer down.

## What was measured

| Model | Status | Presence | Bytes | Digest recomputed |
|---|---|---|---:|---|
| qwen3.5-4b | active | `VERIFIED_FILE` | 2,740,937,888 | matches the recorded sha256 |
| qwen3.8-27b-ud-iq4_xs | active | `VERIFIED_FILE` | 14,252,845,984 | matches the recorded sha256 |
| qwen3-embedding-0.6b | active | `VERIFIED_FILE` | 639,150,592 | matches the recorded sha256 |
| qwen3-reranker-0.6b | active | `VERIFIED_FILE` | 494,879,360 | matches the recorded sha256 |
| qwen2.5-vl-7b-instruct | active | `VERIFIED_FILE` | 4,683,072,032 | matches the recorded sha256 |
| faster-whisper-large-v3-turbo | active | `VERIFIED_FILE` | 1,617,884,929 | matches the recorded sha256 |
| sherpa-onnx-sense-voice | standby | `VERIFIED_FILE` | 239,233,841 | matches the recorded sha256 |
| sherpa-onnx-streaming-zipformer-zh-14m | standby | `VERIFIED_DIR` | 81,340,658 | no single-file digest (directory-backed) |
| qwen3-8b | RETIRED_PENDING_DECISION | `VERIFIED_BLOB_CONTENT_ADDRESS` | 5,225,374,496 | matches the recorded sha256 |
| qwen3-coder-30b-a3b | RETIRED_PENDING_DECISION | `VERIFIED_BLOB_CONTENT_ADDRESS` | 18,556,688,736 | matches the recorded sha256 |

Total bytes accounted for: **48,531,408,516 B (45.20 GiB)** across 10 entries; nine digests were recomputed and matched, one model is a 12-file directory and now carries a per-file manifest instead of one truncated prefix claim.

## The two RETIRED_PENDING_DECISION weights are present, and they cost

- **qwen3-8b** — `ollama/blobs/sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f` (5,225,374,496 B), tag(s) registry.ollama.ai/library/qwen3/8b; the blob hashes to its own file name, which is ollama's content address, so presence and integrity are both proven. The registry now records the retained bytes next to the pending decision, because a decision that is left open over gigabytes of disk is not free.
- **qwen3-coder-30b-a3b** — `ollama/blobs/sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a` (18,556,688,736 B), tag(s) registry.ollama.ai/library/qwen3-coder/30b-a3b-q4_K_M; the blob hashes to its own file name, which is ollama's content address, so presence and integrity are both proven. The registry now records the retained bytes next to the pending decision, because a decision that is left open over gigabytes of disk is not free.

## Leftover files, re-checked

- `runtimes-tmp/reranker-dl.gguf` — recheck `PRESENT` at `2026-10-06T20:30:56Z`: reranker GGUF download leftover; qwen3-reranker is already served by Ollama.
  Observed 494,879,360 B, full digest `a18ae2a5f553fe02…` recorded in the registry; duplicate tested: **True**, byte duplicate of: None.
  Action kept: REGISTERED_NOT_DELETED — deletion is not justified: the file is not a byte duplicate of any registered model (measured 2026-10-07)
- `ollama/blobs/sha256-81fb60c7…-partial (+16 zero-length part files)` — recheck `UNRESOLVABLE_AS_WRITTEN` at `2026-10-06T20:30:56Z`: abandoned `ollama pull qwen3.
  Action kept: REGISTERED_NOT_DELETED — pure partial-download residue, safe to reclaim once the user confirms
- `ollama/blobs/sha256-a99b7f834d754b88f122d865f32758ba9f0994a83f8363df2c1e71c17605a025` — recheck `PRESENT` at `2026-10-06T20:30:56Z`: Ollama weight layer for the qwen2.
  Observed 5,969,233,408 B, full digest `a99b7f834d754b88…` recorded in the registry; duplicate tested: **True**, byte duplicate of: None.
  Action kept: REGISTERED_NOT_DELETED — this is another runtime's content-addressed store; WORK-LAB registers what it finds and does not delete outside the project r

Three things this pass settled:

1. The `runtimes-tmp/reranker-dl.gguf` leftover is **the same byte length as the registered reranker but a different full digest**, so it is not a duplicate. The owner rule allows deletion only against a confirmed duplicate, so deleting it is not justified and the record now says why instead of implying consent.
2. The `ollama/blobs/sha256-81fb60c7…-partial (+16 zero-length part files)` record was written as prose: the path field contains an ellipsis and a count, so no tool can open it. It is now marked `UNRESOLVABLE_AS_WRITTEN`. No blob beginning `81fb60c7` exists in the store on 2026-10-07 and no deletion of it is recorded in this session, so the honest verdict is that the 3,389,971,840 B figure cannot be verified as written — not that it was proven absent.
3. A 5,969,233,408 B ollama weight layer for the `qwen2.5vl/7b` family belonged to **no registry entry at all**. It is registered now, with its content address verified, and left in place: it is another runtime's store and WORK-LAB does not delete outside the project root without an owner decision.

## Limits kept honest

- None of this is verified on the CI runner. It has no weight root, and AGENTS.md says a skipped required job fails the aggregate, so the readback is recorded local evidence with its tool, date and basis, and the gate checks the claim's internal consistency only.
- The readback reads a machine-local path outside this repository, one-directionally. Nothing was moved, renamed, downloaded or deleted in the library.
- A model resolving to a directory is not one artifact: the zipformer entry now carries twelve per-file digests, and the earlier single `TRUNCATED` prefix claim about one of its files stays as history rather than being silently replaced.
- No tool in `.project/governance/source-ledger.json` was installed. That file's rows are deliberately REFERENCE-only with written trigger conditions (`docs/current/workflow-assistance/workflow/wloss-reference-decisions.md`), and the compatibility policy records no licence allowlist, so nothing was silently adopted on a licence assumption either.

