# SPDX-License-Identifier: MIT
"""AI-WORK-LAB unified backend package.

Composition of the two migrated sources:
* domains/design/design_lab  - the DESIGN-LAB loopback service (89-route /api surface)
* domains/work/workflow_core - the WORK-LAB repair-pack lifecycle (record/approve/declare/outcome)
* backend.v1                 - the unified /api/v1 envelope (Task/Attempt/Result/Verification)
"""
__version__ = "0.1.0-alpha.0+fusion.r1"
