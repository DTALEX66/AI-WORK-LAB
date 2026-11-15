# SPDX-License-Identifier: MIT
"""Publish changed register bytes using a disposable project-local staging file."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def publish_bytes(path: Path, payload: bytes) -> bool:
    """Leave identical files untouched; stage different bytes under .project-local."""
    path = Path(path)
    try:
        if path.read_bytes() == payload:
            return False
    except FileNotFoundError:
        pass

    scratch = ROOT / ".project-local" / "runs" / "register-write"
    scratch.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix="register-", suffix=".tmp", dir=scratch)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    except OSError as error:
        raise OSError("REGISTER_PUBLISH_FAILED; staged file retained at %s: %s"
                      % (temporary, error)) from error
    return True
