"""WORK orchestration: collectors, durable worker, ledger read models and projections.

Migrated from WORK-LAB under the F01 finding. This package imports nothing at
`import domains.work.orchestration` time — every module is loaded by the consumer that
needs it, because the default posture of this repository's read path is zero automatic
execution (no subprocess, no user-directory scan, no network, no host launch). The
explicit, default-off door for the probing modules is `probe.py`.
"""
