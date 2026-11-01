#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-A: DesignCommand validation (capability-based, tool-agnostic).

领域要求 capability；runtime 决定 adapter。命令验证不依赖具体工具/模型。
"""
from __future__ import annotations


# 已声明 capabilities（与 adapter-registry capability 语义对齐的领域能力）
KNOWN_CAPABILITIES: set[str] = {
    "image.layer.create", "image.layer.mask", "image.selection.subject",
    "image.adjustment.curves", "image.text.create", "image.export.raster",
    "image.composite", "typography.layout", "image.mask", "export.raster",
    "vector.path", "vector.shape", "vector.text", "vector.export",
    "document.create", "document.page", "layout.frame", "layout.style",
    "motion.composition", "motion.keyframe", "motion.render",
    "video.sequence", "video.clip", "video.export",
    "pdf.preflight", "pdf.export", "photo.process", "photo.export",
    "gen.media", "gen.edit", "gen.variation", "gen.reference",
    "analysis.design_critique", "reasoning.long_context", "vision.design_critique",
    "embedding.multimodal", "image.generate", "image.edit",
}


def validate_command(cmd: dict) -> list[str]:
    errs: list[str] = []
    if not cmd.get("command_id"):
        errs.append("command_id required")
    if cmd.get("schemaVersion") != "design-lab/design-command/v1":
        errs.append("schemaVersion must be design-lab/design-command/v1")
    cap = cmd.get("capability", "")
    if not cap:
        errs.append("capability required")
    elif cap not in KNOWN_CAPABILITIES:
        errs.append(f"unknown capability: {cap}")
    if not cmd.get("document"):
        errs.append("document required (artifact:// or object ref)")
    if not cmd.get("project_id"):
        errs.append("project_id required")
    return errs


def is_tool_name(capability: str) -> bool:
    """capability 不得是具体工具名（provider/adapter 中立性铁律）。"""
    banned = {"photoshop", "illustrator", "indesign", "figma", "blender",
              "comfyui", "minimax", "deepseek", "claude", "gpt", "firefly"}
    low = capability.lower()
    return any(b in low for b in banned)
