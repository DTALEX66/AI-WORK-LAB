# SPDX-License-Identifier: MIT
"""Scoped, project-owned process environment for repository test entrypoints."""
from contextlib import contextmanager
import os
import sys
import tempfile
import uuid

from .paths import resolve_paths


@contextmanager
def project_test_environment(namespace):
    """Prepare valid local temp/cache roots before discovery; restore on exit.

    This controls this Python process and inherited child settings, not native
    applications' private scratch policies. Retain run directories for audit.
    """
    layout = resolve_paths()
    values = layout.child_environment(namespace, uuid.uuid4().hex)
    values['TMPDIR'] = values['TEMP']
    # Validate every target before creating any. Use the central reparse and
    # selected-root policy, including existing cache descendants.
    directories = {layout.checked_path(value) for key, value in values.items()
                   if key != 'PROJECT_LOCAL_ROOT'}
    for directory in sorted(directories, key=str):
        layout.checked_path(directory).mkdir(parents=True, exist_ok=True)
    values['PYTHONDONTWRITEBYTECODE'] = '1'
    previous = {key: os.environ.get(key) for key in values}
    previous_temp = tempfile.tempdir
    previous_bytecode = sys.dont_write_bytecode
    try:
        os.environ.update(values)
        # tempfile may have cached an earlier caller's directory before entry.
        tempfile.tempdir = values['TEMP']
        sys.dont_write_bytecode = True
        yield layout
    finally:
        tempfile.tempdir = previous_temp
        sys.dont_write_bytecode = previous_bytecode
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
