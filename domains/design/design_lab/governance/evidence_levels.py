# SPDX-License-Identifier: MIT
"""The E0-E5 evidence ladder, authored once.

Five modules spelled this ladder independently (the assurance plane, the media
boundary, and three standalone verifiers), so a sixth level or a renamed one
could be added in one place and silently disagree with the other four. Runtime
code imports the tuple; the verifiers bootstrap ``src`` on ``sys.path`` and
derive their list/set/pattern from the same bytes instead of a hand copy.
"""
from __future__ import annotations

EVIDENCE_LEVELS = ("E0", "E1", "E2", "E3", "E4", "E5")
