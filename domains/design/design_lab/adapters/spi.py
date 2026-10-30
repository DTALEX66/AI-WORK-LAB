# SPDX-License-Identifier: MIT
"""DL-TP-R2-004: Adapter SPI (type + lifecycle contracts).

Categories: HostAdapter / ProviderAdapter / ConnectorAdapter / FormatAdapter /
BinaryDistributionAdapter. Lifecycle: probe -> prepare -> execute -> observe ->
readback -> rollback. Delivery split: create / validate / publish / deliver.
"""
from __future__ import annotations
from abc import ABC, abstractmethod

ADAPTER_TYPES = ("host", "provider", "connector", "format", "binary")

LIFECYCLE = ("probe", "prepare", "execute", "observe", "readback", "rollback")

ERROR_KINDS = ("permission", "version", "host_busy", "revision_conflict", "modal", "timeout", "license", "readback_mismatch")


class AdapterBase(ABC):
    """All adapters expose version, type, and lifecycle entrypoints."""
    adapter_id: str
    adapter_type: str
    version: str

    @abstractmethod
    def probe(self, ctx: dict) -> dict:
        ...
    @abstractmethod
    def prepare(self, ctx: dict) -> dict:
        ...
    @abstractmethod
    def execute(self, envelope: dict) -> dict:
        ...
    @abstractmethod
    def observe(self, ctx: dict) -> dict:
        ...
    @abstractmethod
    def readback(self, ctx: dict) -> dict:
        ...
    @abstractmethod
    def rollback(self, ctx: dict) -> dict:
        ...

class HostAdapter(AdapterBase):
    adapter_type = "host"

class ProviderAdapter(AdapterBase):
    adapter_type = "provider"

class ConnectorAdapter(AdapterBase):
    adapter_type = "connector"

class FormatAdapter(AdapterBase):
    adapter_type = "format"

class BinaryDistributionAdapter(AdapterBase):
    adapter_type = "binary"

