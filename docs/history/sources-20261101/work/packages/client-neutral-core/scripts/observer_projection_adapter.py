"""Read-only Observer adapter over the Workflow-owned Telemetry Ledger."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from telemetry_ledger import TelemetryLedger


class WorkflowProjectionAdapter:
    def __init__(self, ledger_path: Path) -> None:
        self._ledger = TelemetryLedger(ledger_path)
        self.path = self._ledger.path

    def snapshot(self) -> dict[str, Any]:
        return self._ledger.projection()

    def events_after(self, event_id: str | None = None) -> list[dict[str, Any]]:
        """Return an immutable reconnect window after the Observer cursor."""
        events = self.snapshot()["events"]
        if not event_id:
            return events
        for index, event in enumerate(events):
            if event.get("event_id") == event_id:
                return events[index + 1:]
        return events

    def append(self, *_: Any, **__: Any) -> None:
        raise PermissionError("Observer projection adapter is read-only")
