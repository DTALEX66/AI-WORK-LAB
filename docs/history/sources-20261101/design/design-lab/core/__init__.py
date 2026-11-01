#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-A: design kernel entry (public API surface).

内核只暴露 contracts 与轻量状态机；不依赖具体模型/工具/宿主。
"""
from .project_state import DesignProject, ProjectTransitionError, load_project, STAGES, TRANSITIONS
from .commands import validate_command, KNOWN_CAPABILITIES, is_tool_name
from .user_modes import MODE_SEMANTICS, mode_semantics, requires_human_approval, quality_gate_auto, VALID_MODES

__all__ = [
    "DesignProject", "ProjectTransitionError", "load_project", "STAGES", "TRANSITIONS",
    "validate_command", "KNOWN_CAPABILITIES", "is_tool_name",
    "MODE_SEMANTICS", "mode_semantics", "requires_human_approval", "quality_gate_auto", "VALID_MODES",
]
