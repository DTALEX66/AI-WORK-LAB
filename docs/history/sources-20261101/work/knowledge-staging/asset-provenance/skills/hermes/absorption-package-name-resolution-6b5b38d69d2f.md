---
name: absorption-package-name-resolution
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/absorption-package-name-resolution/SKILL.md
---

---
name: absorption-package-name-resolution
description: Resolve misspelled PyPI names in absorption queues.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [absorption, queue, pypi, package-resolution, adapter, sleep-mode]
    related_skills: [sleep-mode, agent-workflow-fortress]
---

# Absorption Queue: Package Name Resolution

When an autonomous sleep-mode queue or absorption task specifies a PyPI package name and `pip install <name>` fails with "No matching distribution found," do not skip the task or file it as blocked. Follow this resolution pattern.

## Resolution workflow

1. **Try the exact name.** `pip install <name>` — if it fails, note the exact error.

2. **Try near-miss variants.** Common PyPI misspellings and close matches encountered in practice:

   | Queue name | Likely real package | Comment |
   |---|---|---|
   | `readabilipipe` | `readabilipy` (v0.3.0) | Mozilla Readability Python wrapper |
   | `newspaper` | `newspaper4k` or `newspaper3k` | `newspaper4k` is the current fork |
   | `goose` | `goose3` | Python 3 port of Goose |
   | `boilerpipe` | `boilerpy3` | Python 3 port of Boilerpipe |
   | `tika` | `tika-python` | Apache Tika Python client |
   | `markdownify` | `markdownify` (exists) or `html2text` | Check both |
   | `readability` | `readability-lxml` or `readabilipy` | Two separate implementations |

3. **Install + smoke test.** Install the resolved candidate, verify it imports, check the API surface with `dir()` and `inspect.signature()`. If it can't do what the task needs, try the next candidate.

4. **Document the resolution.** In the cycle evidence, record the original queue name and the actual installed package. Add a `name_resolution` field:

   ```json
   "name_resolution": {
     "queue_name": "readabilipipe",
     "resolved_package": "readabilipy",
     "resolved_version": "0.3.0",
     "justification": "Closest match on PyPI; provides Mozilla Readability content extraction"
   }
   ```

5. **Never fake the package.** If no real package provides the described capability after 3 reasonable candidates, mark the adapter as `UNAVAILABLE` with an appropriate registry entry. Do not create a stub.

## When to abort

After 3 reasonable near-miss candidates without a match, file the task as `blocked: unknown_package` and move to the next dependency-ready task. Do not spend more than one cycle per missing package.

## Edge cases

- **Package is a brand name, not a PyPI name:** `pip install <name>` as first test.
- **Package was renamed:** Check the newer package's README for rename documentation.
- **No public Python package exists** (system binary, Node-only tool): Classify UNAVAILABLE.
- **Package exists but is unimportable** (wrong Python version, missing native extensions): Classify UNAVAILABLE with blocker.

## Verification checklist

- [ ] `pip install <exact-name>` attempted and failed
- [ ] 3 near-miss candidates tested
- [ ] Resolution logged in cycle evidence
- [ ] Nothing faked — installed or classified UNAVAILABLE
