# SPDX-License-Identifier: MIT
"""DL-TP-R2-013: LocalStateStore initializer."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .paths import resolve_paths
from .state_resources import state_schema

DDL = state_schema('design-lab-state-v1.sql')


def init_db(db_path: Path, *, project_root=None) -> sqlite3.Connection:
    db_path = resolve_paths(project_root=project_root).database_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript(DDL.read_text(encoding='utf-8'))
    conn.commit()
    return conn


def schema_version(conn: sqlite3.Connection) -> str:
    cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='operation_intent'")
    return 'v1' if cur.fetchone() else 'EMPTY'
