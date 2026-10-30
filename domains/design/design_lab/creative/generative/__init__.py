# SPDX-License-Identifier: MIT
"""DESIGN-LAB generative runtime contracts (Deep Adaptation Wave D).

DL-P0-080 workflow provider, DL-P0-081 partial re-execution, DL-P0-090 remote
provider record structure and DL-P0-091 model-as-external-asset. Everything in
this package is structural: it validates graphs and records, plans minimal
re-execution and fails closed. It never dispatches a generation, never holds a
credential and never claims inference evidence it did not measure.
"""
from __future__ import annotations

from .errors import GenerativeError
from . import model_assets, partial_execution, remote_provider, workflow_provider

__all__ = [
    "GenerativeError", "model_assets", "partial_execution", "remote_provider",
    "workflow_provider",
]
