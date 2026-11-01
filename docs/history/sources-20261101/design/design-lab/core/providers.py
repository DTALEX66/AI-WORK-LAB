#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P2-I: Provider SPI — capability-level abstraction.

业务代码只依赖 capability id（如 reasoning.long_context / vision.design_critique），
绝不直接调用 deepseek_v3() / gpt_x() / minimax_x()。
"""
from __future__ import annotations

KNOWN_CAPABILITIES = {
    "reasoning.long_context", "vision.design_critique", "embedding.multimodal",
    "image.generate", "image.edit", "gen.variation", "analysis.design_critique",
    "classification.fast", "rule_extraction.small",
    # DL 组件在线核实（2026-08-17）：可并入的能力域
    "vision.encoding", "image.segment", "image.detect.open_vocab",
    "document.ocr", "document.layout", "quality.aesthetic_score",
}

PROVIDER_ID_PATTERN = "provider:"  # 本地/网关端点引用前缀


def validate_provider(decl: dict) -> list[str]:
    errs: list[str] = []
    if decl.get("schemaVersion") != "design-lab/provider-capability/v1":
        errs.append("schemaVersion must be design-lab/provider-capability/v1")
    caps = decl.get("capabilities", [])
    if not caps:
        errs.append("capabilities required")
    for c in caps:
        if c not in KNOWN_CAPABILITIES:
            errs.append(f"unknown capability: {c}")
    if not decl.get("endpoint_ref", "").startswith(PROVIDER_ID_PATTERN):
        errs.append("endpoint_ref must use provider: reference (no absolute paths)")
    return errs


def contains_absolute_path(decl: dict) -> bool:
    ref = decl.get("endpoint_ref", "")
    return ("C:" in ref or "D:" in ref or ref.startswith("/") or "\\" in ref)
