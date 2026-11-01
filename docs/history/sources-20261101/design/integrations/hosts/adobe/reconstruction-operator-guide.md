# Reconstruction host qualification operator guide

This guide is for a human-approved, single Adobe host session. It does not grant unattended application control.

1. Start Illustrator from its official installation and open the approved job for the current Git SHA.
2. Confirm the job root is inside the run-owned project evidence directory; reject paths outside it.
3. Run the allowlisted assembly operations only. Save AI, export SVG and PNG, reopen the saved AI, then record the read-back hash.
4. Repeat three clean runs. Record each deterministic preview hash, read-back hash, run SHA, host version and residue result.
5. Only after all six golden cases and Illustrator runs pass may an operator assemble a `reconstruction-evidence/v1` file and invoke `verify_reconstruction_release.py`.

Local unit tests, static JSX/UXP inspection, a successful export without re-open/read-back, or a run bound to another SHA never qualify `installedRuntimeVerified`.
