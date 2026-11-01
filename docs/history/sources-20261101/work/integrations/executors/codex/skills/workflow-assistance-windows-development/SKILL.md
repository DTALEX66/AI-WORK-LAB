---
name: workflow-assistance-windows-development
description: "Use when diagnosing Windows shell, path, encoding or process failures."
---

# Windows development

Identify the actual shell and executable before diagnosing. Distinguish PowerShell,
cmd, Git Bash/MSYS and WSL. Use native Windows paths for native Python programs,
quoted literal paths for filesystem actions and argument arrays where available.

Classify parsing, MSYS conversion, encoding, CRLF, missing executable and lock
failures before retrying. Read actual listeners/process identity before starting
or stopping a service; a recycled PID is not proof of ownership.

Only for the matching symptom, read [Windows details](references/windows-details.md).
For Python, discover the project test entry and interpreter/package pairing before
running or installing anything. Use project-local caches and temporary directories.
Optional missing tools do not prove a product defect.
