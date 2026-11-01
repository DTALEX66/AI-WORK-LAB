# SPDX-License-Identifier: MIT
"""Pure authorization and three-run qualification contracts for Illustrator host read-back."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "design-lab"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


class AdobeReadbackTests(unittest.TestCase):
    def test_expired_authorization_blocks_before_host_launch(self) -> None:
        from reconstruction.adobe_readback import AuthorizationExpired, verify_launch_authorization

        expired = {"jobId": "adobe-test", "expiresAt": "2000-01-01T00:00:00Z", "approved": True}
        with self.assertRaises(AuthorizationExpired):
            verify_launch_authorization(expired, "adobe-test")

    def test_three_clean_readbacks_are_required_for_runtime_qualification(self) -> None:
        from reconstruction.adobe_readback import HostRun, qualify_host

        now = datetime.now(timezone.utc).isoformat()
        run = HostRun("PASS", "a" * 64, "b" * 64, (), now)

        self.assertEqual(qualify_host((run, run)).state, "PARTIAL")
        self.assertEqual(qualify_host((run, run, run)).state, "PASS")


if __name__ == "__main__":
    unittest.main()
