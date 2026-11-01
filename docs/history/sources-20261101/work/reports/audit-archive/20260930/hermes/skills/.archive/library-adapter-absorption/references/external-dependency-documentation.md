# External Dependency Documentation & Sync

## When

User asks for comprehensive external dependency documentation with download links,
synced to both local (OS configuration directory) and cloud (GitHub repo).

## Target locations

| Location | Path | Purpose |
|---|---|---|
| **OS config root** (local) | `D:\All projects\OS configuration\EXTERNAL_DEPENDENCIES.md` | Local reference, stays outside project repo |
| **Project repo** (cloud) | `docs/environment/EXTERNAL_DEPENDENCIES.md` | Committed to project, visible on GitHub |

Both copies must be kept in sync. The OS configuration directory is itself a Git repo
(`DTALEX66/OS-configuration`), so changes there are also pushed to a remote.

## Document structure

Cover these sections with exact download links:

1. **Environment variables** — session-level, not registry. Document each with its value
   and purpose. Example: `UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT`, `HERMES_HOME`.

2. **System tools** (must install) — each with version, download URL, install method,
   and verification command. Examples: Python, uv, Tesseract, FFmpeg, Git, Node.

3. **Python packages** — grouped by purpose (core runtime, data, database, logging,
   format engines, LLM provider, ADOPT-absorbed, CI/test). Pull from
   `pyproject.toml` + `uv.lock`.

4. **Vendored assets** — third-party source/model files copied directly into the repo.
   Each with source URL, version, license, location in repo, and license file pointer.
   Examples: PDF.js, Magika ONNX model.

5. **External API services** — no install needed but require network. List URL,
   authentication requirement, and rate limits. Examples: Crossref, DataCite,
   OpenAlex, Wikidata.

6. **Local services** — port, start command, purpose. Examples: FastAPI :8000,
   FlClashCore :7890.

7. **Toolchain paths** — show directory tree of scoop-managed toolchains.

8. **From-scratch installation checklist** — numbered steps from zero to running.

9. **GitHub repo description note** — the GitHub "About" description field is
   effectively fixed (hard to change through automation). Document what it currently
   says and note "后期更新绕开它" (future updates work around it). The description
   in `app/main.py` title is the canonical product name.

## Sync workflow

```bash
# 1. Write to project repo
write_file docs/environment/EXTERNAL_DEPENDENCIES.md

# 2. Copy to OS config (two-way sync)
cp docs/environment/EXTERNAL_DEPENDENCIES.md "D:/All projects/OS configuration/EXTERNAL_DEPENDENCIES.md"

# 3. Commit both repos
git add docs/environment/EXTERNAL_DEPENDENCIES.md && git commit -m "docs: ..." && git push
cd "D:/All projects/OS configuration" && git add EXTERNAL_DEPENDENCIES.md && git commit -m "docs: ..." && git push
```

## Update rules

- Any new system tool, model file, or external API must be registered here
- `pyproject.toml` dependency changes auto-reflect in `uv.lock`; this doc syncs manually
- Review quarterly or on major version upgrades
