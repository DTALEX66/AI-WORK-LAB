#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-B: user mode control semantics over the kernel workflow.

模式决定披露度与自动化度（V42-0203 五模式），不改变能力面。
"""
from __future__ import annotations

# mode -> (disclosure, control, auto_quality_gate, human_approval_points)
MODE_SEMANTICS: dict[str, dict] = {
    "guided":     {"disclosure": "high",   "control": "low",    "auto_quality_gate": False, "human_approval_points": ("direction", "critique", "preflight")},
    "copilot":    {"disclosure": "high",   "control": "medium", "auto_quality_gate": False, "human_approval_points": ("critique", "preflight")},
    "director":   {"disclosure": "medium", "control": "high",   "auto_quality_gate": True,  "human_approval_points": ("preflight",)},
    "method":     {"disclosure": "medium", "control": "high",   "auto_quality_gate": True,  "human_approval_points": ("preflight",)},
    "production": {"disclosure": "low",    "control": "high",   "auto_quality_gate": True,  "human_approval_points": ()},
}

VALID_MODES = set(MODE_SEMANTICS)


def mode_semantics(mode: str) -> dict | None:
    return MODE_SEMANTICS.get(mode)


def requires_human_approval(mode: str, stage: str) -> bool:
    sem = MODE_SEMANTICS.get(mode)
    if not sem:
        raise ValueError(f"unknown mode: {mode}")
    return stage in sem["human_approval_points"]


def quality_gate_auto(mode: str) -> bool:
    return MODE_SEMANTICS[mode]["auto_quality_gate"]
