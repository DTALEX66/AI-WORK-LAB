#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host E3 probe (Batch F-4) — detect a real host run surface, launch nothing.

This script answers one narrow question with no side effects: *is there a real,
authorised host run surface on this machine right now?* It deliberately does NOT
start Photoshop, Illustrator or any GUI, does not talk to a network, and does not
treat an installed application, a LaunchAgent entry or our own UXP adapter package
as proof that a host run happened.

The only positive signal is an explicitly configured bridge entry
(``DL_HOST_E3_ENDPOINT``, non-empty): that is the operator declaring that a real
host is reachable and authorised for an E3 fixture session. Everything else is
reported as detail, never as presence.

Usage:
    python design-lab/scripts/host_e3_probe.py

Output contract (one line, machine-parsed):
    HOST_E3_PROBE=<HOST_PRESENT|HOST_ABSENT> details=...

Exit code is always 0: a probe reports state, it does not pass or fail a gate.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENDPOINT_ENV = "DL_HOST_E3_ENDPOINT"

# Adapter packages we own. Their presence shows scaffolding, NOT a host run.
ADAPTER_PACKAGES = (
    ("photoshop-reconstruction", REPO / "integrations/hosts/adobe/photoshop-reconstruction"),
    ("illustrator", REPO / "integrations/hosts/adobe/illustrator"),
)

NOTE = ("探针只读环境变量与适配器包目录，绝不启动宿主软件/GUI；"
        "HOST_PRESENT 仅由显式授权的桥接入口 DL_HOST_E3_ENDPOINT 触发，"
        "适配器包存在或应用已安装都不算宿主运行面。")


def package_state(root: Path) -> str:
    """'present' when the package directory has at least one entry, else 'absent'."""
    try:
        return "present" if root.is_dir() and any(root.iterdir()) else "absent"
    except OSError:
        return "absent"


def probe(env: dict | None = None) -> tuple[str, str]:
    """(verdict, details). Never launches anything."""
    environment = os.environ if env is None else env
    endpoint = (environment.get(ENDPOINT_ENV) or "").strip()
    endpoint_state = "set" if endpoint else "unset"
    packages = ",".join(f"{name}:{package_state(root)}" for name, root in ADAPTER_PACKAGES)
    verdict = "HOST_PRESENT" if endpoint else "HOST_ABSENT"
    details = (f"endpoint={endpoint_state};adapter_packages={packages};"
               f"host_launched=false;network_used=false")
    return verdict, details


def main(argv=None) -> int:
    verdict, details = probe()
    print(f"HOST_E3_PROBE={verdict} details={details}")
    print(f"HOST_E3_PROBE_DETAIL={NOTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
