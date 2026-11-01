"""Model catalog snapshot builder (WL3-330 / MR-02+05 extension).

Reads the live Ollama runtime and builds a standard model catalog that the
task-level resolver (MR-08) and client projections consume. Pure metadata
(never weights); maps installed Ollama models to logical capability roles.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/model-catalog/v1"

# Logical role mapping: installed model -> capability claims (taskpack §9)
_ROLE_MAP: dict[str, dict[str, Any]] = {
    "qwen3:4b": {"role": "local.general.fast", "modality": ["text"],
                 "capabilities": ["text", "summarize"], "family": "qwen3",
                 "quality_state": "OK", "lifecycle": "ACTIVE", "locality": "local"},
    "qwen3:8b": {"role": "local.general.fast", "modality": ["text"],
                 "capabilities": ["text", "summarize", "reasoning"], "family": "qwen3",
                 "quality_state": "OK", "lifecycle": "ACTIVE", "locality": "local"},
    "qwen2.5-coder:7b": {"role": "local.code.readonly", "modality": ["text"],
                          "capabilities": ["code.read", "code.review", "text"],
                          "family": "qwen2.5-coder", "quality_state": "OK",
                          "lifecycle": "ACTIVE", "locality": "local"},
    "qwen3-coder:30b-a3b-q4_K_M": {"role": "local.code.readonly", "modality": ["text"],
                                      "capabilities": ["code.read", "code.review", "code.write", "text"],
                                      "family": "qwen3-coder", "quality_state": "OK",
                                      "lifecycle": "ACTIVE", "locality": "local"},
    "qwen2.5vl:7b": {"role": "local.vision.ocr", "modality": ["vision", "text"],
                      "capabilities": ["vision", "ocr", "text"], "family": "qwen2.5vl",
                      "quality_state": "OK", "lifecycle": "ACTIVE", "locality": "local"},
    "qwen3-embedding:0.6b": {"role": "local.embedding", "modality": ["embedding"],
                              "capabilities": ["embedding"], "family": "qwen3-embedding",
                              "quality_state": "OK", "lifecycle": "ACTIVE", "locality": "local"},
    "qwen3-reranker:latest": {"role": "local.reranker", "modality": ["reranker"],
                              "capabilities": ["rerank"], "family": "qwen3",
                              "quality_state": "OK", "lifecycle": "ACTIVE", "locality": "local"},
}


def _ollama_tags(endpoint: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    try:
        with urllib.request.urlopen(endpoint.rstrip("/") + "/api/tags", timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"models": []}


def build_catalog(endpoint: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    data = _ollama_tags(endpoint)
    installed = {m.get("name"): m for m in data.get("models", [])}
    models: dict[str, Any] = {}
    for name, meta in installed.items():
        role_info = _ROLE_MAP.get(name)
        if not role_info:
            continue
        details = meta.get("details") or {}
        models[name] = {
            "asset_id": name.replace(":", "-").replace(".", "-"),
            "display_name": name,
            "family": role_info["family"],
            "architecture_status": "CONFIRMED" if details.get("family") else "UNVERIFIED",
            "modality": role_info["modality"],
            "format": "gguf",
            "quantization": details.get("quantization_level"),
            "size_bytes": meta.get("size"),
            "storage_mode": "managed",
            "owner": "user-shared",
            "lifecycle": role_info["lifecycle"],
            "quality_state": role_info["quality_state"],
            "locality": role_info["locality"],
            "role": role_info["role"],
            "capabilities": role_info["capabilities"],
            "runtime_candidates": ["ollama"],
            "ui_frozen": True,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "endpoint": endpoint,
        "model_count": len(models),
        "models": models,
    }


if __name__ == "__main__":
    print(json.dumps(build_catalog(), ensure_ascii=False, indent=2))
