# SPDX-License-Identifier: MIT
"""DL-TP-R2-004: Adapter SPI contract tests."""
from __future__ import annotations
import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(SRC))

class AdapterSPITests(unittest.TestCase):
    def test_types_and_lifecycle(self):
        from design_lab.adapters.spi import ADAPTER_TYPES, LIFECYCLE, ERROR_KINDS
        self.assertEqual(len(ADAPTER_TYPES), 5)
        self.assertIn('execute', LIFECYCLE)
        self.assertIn('readback_mismatch', ERROR_KINDS)

    def test_host_adapter_type(self):
        from design_lab.adapters.spi import HostAdapter
        self.assertEqual(HostAdapter.adapter_type, 'host')

if __name__ == '__main__':
    unittest.main()
