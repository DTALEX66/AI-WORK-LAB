---
name: workflow-assistance-github-delivery
description: "Use when delivering a GitHub PR, release or exact-SHA CI verdict."
---

# GitHub delivery

Read the actual branch, HEAD, dirty paths and remote target. Preserve user work and
stage only the task's changes. Commit, push, PR, merge and release follow the current
task grant; do not request the same grant repeatedly.

Use Git for local identity and the native GitHub client/API for remote readback.
Do not print credentials. Fetch/read the target before relying on remote state.
Bind required checks to the delivered SHA; failed, cancelled, missing and required
skipped checks cannot pass. After squash merge, verify the actual merge commit on
main rather than requiring the old PR head to be an ancestor.

Keep IMPLEMENTED_LOCAL, TESTED_LOCAL, BRANCH_PUBLISHED, CI_VERIFIED_EXACT_SHA,
MERGED_MAIN and INSTALLED_RUNTIME_VERIFIED distinct. A release URL or version is
not proof of installed behavior. Use exact paths/SHAs/URLs as evidence.
