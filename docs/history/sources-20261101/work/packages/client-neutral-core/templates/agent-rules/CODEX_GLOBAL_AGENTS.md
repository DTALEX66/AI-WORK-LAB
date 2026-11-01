# Global Codex baseline

- Work in the current Git project. If there is no Git project, stay read-only and ask before creating files.
- Read the project `AGENTS.md` files before editing. Project rules are more specific and take precedence over this baseline.
- Keep temporary files, caches, logs, test environments, and generated artifacts inside the current project's declared ignored runtime directory. WORK-LAB uses `.project-local/`; other projects define their own boundary. Do not use the user profile, desktop, system temp, or another project for task data without explicit authorization.
- Do not access `E:\` unless the user explicitly authorizes the exact path and operation in the current request.
- Do not read or reveal credentials, `.env` files, auth stores, private keys, browser data, or tokens.
- Do not delete user data, overwrite existing instruction files, run destructive Git commands, publish, push, create pull requests, or make global/system changes without explicit approval.
- Keep changes small, run the relevant checks, and distinguish verified behavior from structural inspection.
- When a project provides a Hermes workflow launcher or task contract, use that project-local mechanism; do not assume Hermes exists for unrelated projects.
