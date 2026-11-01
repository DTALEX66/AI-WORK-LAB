# SPDX-License-Identifier: MIT
"""Source-checkout bridge to the single existing reconstruction implementation.

Wheel builds replace this bridge with the canonical package initializer and
include its modules directly. No repository path is needed after installation.
This bridge is retired when the canonical implementation migrates into src.
"""
from pathlib import Path

_source = Path(__file__).resolve().parents[3] / 'packages' / 'capabilities' / 'reconstruction'
if _source.is_dir() and (_source / 'adobe_job.py').is_file():
    __path__.append(str(_source))
