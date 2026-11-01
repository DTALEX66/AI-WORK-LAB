# Windows Validated Cases

Companion reference for `windows-development-environment`. The SKILL.md keeps
the core selection/quoting/resolution strategies; these detailed case studies
(marked "(validated …)" in the original) live here so they can be read on
demand without bloating the always-loaded skill body.

---

## 1. Shell and encoding — detailed cases

### CJK in ASCII-only PowerShell scripts

PowerShell 5.1 can misparse UTF-8 scripts containing CJK when launched from Git-Bash. Prefer an ASCII-only `.ps1`, or save the script as UTF-8 with BOM before retrying. Keep explanations in Markdown rather than embedding large non-ASCII blocks in PowerShell source.

When a `.ps1` must stay ASCII-only but needs CJK **text** (e.g. synthesizing a Chinese audio fixture via System.Speech without a TTS package), express the CJK as code-point escapes instead of literals:

```powershell
$zh = [string]::Join('', @(0x673A,0x5668,0x5B66,0x4E60))  # 机器学习
# or write it out via [System.IO.File]::WriteAllText($p, $zh, [Text.Encoding]::UTF8)
```

Also: `powershell -Command "...$s..."` from Git-Bash expands `$s` as a **bash** variable before PowerShell sees it — a `$synth = New-Object ...` inline command breaks. Put the script in a file and run `powershell -ExecutionPolicy Bypass -File script.ps1` instead. Check available SAPI voices with a short `.ps1`:

```powershell
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $synth.GetInstalledVoices()) { $v.VoiceInfo.Name + " | " + $v.VoiceInfo.Culture }
```

Check touched text files before upload:

```bash
python -c "from pathlib import Path; p=Path('script.ps1'); b=p.read_bytes(); print('utf8', end=' '); b.decode('utf-8'); print('ok', 'crlf', b'\r\n' in b)"
git diff --check
```

Do not normalize unrelated historical files merely to remove noise; check the current change set.

## 2. Executable resolution — detailed cases

### Launching a GUI exe with spaces from Git-Bash (use PowerShell, not `cmd start`)

Do NOT launch a desktop GUI exe from Git-Bash with `cmd.exe /d /s /c "start \"\" \"C:\path with spaces\app.exe\""`. Git-Bash mangles the nested quotes and the `\"\"` title-argument pairing, so `start` mis-parses and Windows pops a spurious **"Windows 找不到 '\' 文件"** dialog (it treats a stray `\` as the file to open). This is a launch-command quoting bug, NOT an app fault.

Launch the GUI with PowerShell `Start-Process` (handles paths-with-spaces and the working dir correctly):

```bash
powershell.exe -NoProfile -Command "Start-Process -FilePath 'D:\Programs\Open Design\Open Design.exe' -WorkingDirectory 'D:\Programs\Open Design'"
```

Then verify it actually came up, don't assume:

```bash
sleep 8
tasklist | grep -i "Open Design"          # expect the main + renderer + gpu processes
# GUI readiness: capture the app window via computer_use and read its AX tree
# (a `windows: []` / empty window_title on the process does NOT mean it failed;
#  the window renders on a later capture).
```

The same rule applies to any Electron/CEF desktop app launched from a project checkout (Open Design, OpenHuman, Hermes desktop, CC Switch): prefer `Start-Process` and confirm by process tree + a window snapshot rather than by the exit of the launch command.

## 3. Paths and Git-Bash — detailed cases

### Bash wrapper scripts: two silent breakers (validated 2026-08-12)

A project-local bash wrapper (e.g. `scripts/ci/run_tests.sh` that fixes `--basetemp` and env vars, then `exec uv run ... pytest`) hits two silent traps:

1. **`pwd` returns an MSYS path (`/d/All projects/...`) that Windows Python/uv cannot parse.** `$(cd ... && pwd)` inside git-bash gives `/d/...`; passing that as `--basetemp=` or any path argument to a Windows-native program makes it fail or silently ignore the argument (pytest reports `collected 0 items` with a correct-looking rootdir). Fix: derive the Windows path with `pwd -W` (or `cygpath -w`), normalize backslashes to forward slashes, and use that for every path handed to Windows programs; keep the MSYS path only for bash `cd`.
2. **A leading `--` is passed through as an argument when bash invokes a non-builtin script.** `bash scripts/run_tests.sh -- -x --collect-only` does NOT strip the `--`: `"$@"` becomes `(--, -x, --collect-only)` and the script's `pytest ... "$@"` then treats `--` as a file-path separator — pytest reports `ERROR: file or directory not found: -x` and collects 0 items. Fix: strip a leading `--` inside the script before forwarding: `if [ "${1:-}" = "--" ]; then shift; fi` — then both `run_tests.sh -x ...` and `run_tests.sh -- -x ...` work.

Debug wrapper failures with `bash -x script.sh` — the final expanded command line exposes both traps immediately.

### Native Windows git cannot open MSYS-style `/tmp/...` paths

In Git-Bash, `/tmp` maps to `C:\Users\<user>\AppData\Local\Temp`, but `git apply /tmp/x.patch` (and other native-git path args) fails with `can't open patch ... No such file or directory` because native git does not translate the MSYS path. `ls`/`cp` work with `/tmp/...` (they're shell builtins / MSYS-aware), but `git` is not. When staging a saved patch between worktrees, pass the Windows-native form: `git apply "C:/Users/<user>/AppData/Local/Temp/x.patch"` (or `$(cygpath -w /tmp/x.patch)`), and copy support files with `cp` then reference them by their Windows path.

Avoid Windows redirection `>NUL` in Git-Bash: it can create a real repository file named `NUL`. Use `>/dev/null 2>&1` for Bash commands, or keep `NUL` inside a deliberately quoted `cmd.exe /c` command.

### Backticks in `git commit -m` are command substitution in Bash

Git-Bash executes backticks inside double-quoted `-m` strings. A commit message like `git commit -m "report_csv blanked perfect CER 0.0 (falsy \`or \"\"\`)"` runs `or` as a shell command and silently swallows the quoted text — the message lands in the repo truncated/mangled. When a commit message contains backtick-worthy content (code spans, `or`-style tokens), either:
- write the message to a file and use `git commit -F msg.txt` (most reliable), or
- avoid backticks entirely in the `-m` string (use plain quotes/plain prose).

After committing, `git log -1 --format=%B` and read the full message before pushing — truncation is silent and irreversible once merged.

## 5. Local Windows servers — detailed cases

### Stale uvicorn/FastAPI child still serving OLD code

When a FastAPI server is started via a wrapper process (e.g. `python -m app.runtime_entrypoint core` that itself launches uvicorn), killing the wrapper (`process kill`) frequently leaves the **detached uvicorn child alive**. It keeps listening on the port AND — if the app takes a runtime/database lock at startup — keeps holding that lock. Symptoms that are easy to misread:

- A **new startup fails** with `RuntimeError: database operator requires the app to be offline` (the lock is held by the zombie child).
- The port still answers, but the answer comes from **stale code**: a route added after the child started returns `422` (the `Literal[...]` path-param validation rejects the new value) while the same request via TestClient against current source returns `200`. The response `workspace=200` can be true while a new sub-route 422s — both are the zombie, not a real code bug.
- `curl` to a *newly added* asset/route returns an error even though you just added it — this does NOT mean your edit is wrong; it means you are talking to an old process.

Diagnose by PID, not by port memory — find who actually LISTENs, then confirm that pid still belongs to a process this task started. Stop order: ask that process to exit normally first; forceful termination is a **recovery step of last resort**, is limited to processes this task created, and requires explicit authorization. A forceful kill is **never** evidence that native task cancellation works. Once forceful termination is the authorized step (use `taskkill /F /PID`, NOT `taskkill //PID` which Git-Bash mangles into an invalid option):

```bash
netstat -ano | grep ':8000' | grep LISTEN          # last column = pid
taskkill /F /PID <pid>
sleep 2
netstat -ano | grep ':8000' | grep LISTEN || echo PORT_FREE
```

If that last-resort step itself fails (or the pid is a detached child you want to clean without knowing it), kill by port with PowerShell in one line — validated 2026-08-13, and it survives Git-Bash quoting where `cmd //c "taskkill /PID ..."` silently runs the wrong thing:

```bash
powershell.exe -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force }"
# then verify the port is actually free:
netstat -ano | grep ':8000' | grep LISTEN || echo PORT_FREE
```

Then start fresh from current source. If a runtime/lock guard still complains after the port is free, check for the lock file / stale pid before assuming the code is wrong. Prefer `notify_on_complete=true` on the background server launch so you learn when the wrapper exits, and always re-verify readiness with a health check + a request against a *newly added* route before trusting the restart.

For several projects, probe the page title or a known health endpoint on each candidate port before opening a browser preview. Do not use an old screenshot or stale tab as evidence that the current project is running.

- For Git-Bash commands with non-ASCII JSON, write the payload to a UTF-8 file and pass `curl -d @file`; do not rely on inline shell encoding.

## 7. Git changes and upload hygiene — validated cases

### Provenance / digest hashes on Windows use CRLF-normalized bytes (validated 2026-08-13)

A repo that records file hashes (skill provenance, checksum manifests, state files) must compute them from **CRLF→LF normalized bytes**, or Windows CRLF checkouts will never match Linux LF hashes. `check_skill_provenance.py` style validators do:

```python
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
hashlib.sha256(data).hexdigest()
```

After editing any tracked file covered by a hash manifest, regenerate the hash with the SAME normalization (plain `sha256(file_bytes)` gives a different value on CRLF files) and run the provenance gate. Symptom: `source SHA drift: <name>` with no content change visible in diff.

### gh CLI uninstalled: git credential helper points at a dead path (validated 2026-08-13)

After `gh` is uninstalled (or its scoop install moved), a leftover global git config `credential.https://github.com.helper = !'C:\...\gh.exe' auth git-credential` breaks every push with `could not read Username`. The Windows Credential Manager still holds valid credentials; the dead helper shadows it.

Fix at the repo level (do not edit global config without asking):

```bash
git config credential.https://github.com.helper 'manager'
git config credential.https://gist.github.com.helper 'manager'
git push   # now authenticates via the Credential Manager
```

For REST API calls, the Credential Manager does NOT return a plaintext token via `git credential fill` (interactive), so use `git credential fill` piped to curl only when it returns a `password=` line (do not print it):

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | grep '^password=' | cut -d= -f2-)
curl -s -H "Authorization: Bearer ***" "https://api.github.com/repos/OWNER/REPO"
unset TOKEN
```

Note: `host=github.com` works for api.github.com too; `host=api.github.com` has no stored credential.

### Anonymous GitHub API rate limit (60/hr) vs authenticated (5000/hr)

Bulk check-run / PR-status polling with anonymous `curl` exhausts the 60/hr core limit fast; responses then come back as `403 rate limit exceeded` with empty JSON. Authenticate every repeated API call (see token snippet above); check remaining quota with the authenticated request: `curl -s https://api.github.com/rate_limit -H "Authorization: Bearer ***"`.

### Rebase + force-push: CI push-event run fails on `before` sha (validated 2026-08-13)

After `git rebase` + `--force-with-lease`, the GitHub **push** workflow run can fail in a `git diff "$BEFORE_SHA" "$HEAD_SHA"` step (e.g. gate-plan's "Discover changed paths") because `github.event.before` is the pre-rebase sha that no longer exists in the branch history. The **pull_request** run for the same head stays green. Do NOT treat the push-run failure as a code bug:

- Read PR mergeState from the pull_request run's check-runs only.
- If branch protection requires `aggregate` and the stale push run blocks it, push an empty commit (`git commit --allow-empty -m "ci: retrigger"`) to supersede the failed push run, or merge via REST with the pull_request check green.

Before editing:

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel
```

Before staging:

```bash
git status --short
git diff --check
git diff --stat
```

Stage explicit paths only. Never stage `.env`, `auth.json`, databases, logs, caches, virtual environments, browser state, or generated runtime evidence. A clean local test is not release evidence; use the repository's canonical quality gate and verify CI against the exact commit SHA.

### Stale exported env vars redirect project DB/runtime paths

The Hermes terminal session persists exported environment variables across calls. A variable exported by an earlier run (e.g. `export COGNITIVE_DATA_DIR=/tmp/mfx-browser-smoke` from a previous smoke run) silently redirects the project's runtime path resolution — the app then opens/validates a different SQLite database, and `migrate` or server startup fails with confusing downstream errors (`phase4 research schema migration is pending`, `no such module: vec0`, or writes landing in the temp dir). The DB path looks wrong only if you check `python -c "from shared import storage; print(storage.DB_PATH)"`.

Diagnose and fix:

```bash
echo "COGNITIVE_DATA_DIR=${COGNITIVE_DATA_DIR-unset}"
unset COGNITIVE_DATA_DIR        # or export -n COGNITIVE_DATA_DIR
python -c "from shared import storage; print(storage.DB_PATH)"  # re-check the resolved path
```

When launching project servers from bash, explicitly `env -u COGNITIVE_DATA_DIR` (and `-u PYTHONPATH`) so a stray export cannot hijack the run. `env -u` on the command line beats relying on `unset` having taken effect in a long-lived session.

### Convention gate `--source head` checks git HEAD, not the working tree (validated 2026-08-13)

A repo convention checker invoked as `check_repository_conventions.py --source head` validates the **committed HEAD objects**, not the dirty working tree. Editing a file on disk does not change what the gate sees until the change is committed — so a gate that "failed locally" can pass immediately after commit+push of the identical fix, and vice versa. When a CI convention gate fails while your local `--source head` run passes, suspect a BOM/encoding difference introduced at write time (see below) rather than assuming CI parity.

### utf-8-sig / encoding='utf-8-sig' writes inject a UTF-8 BOM that convention gates reject (validated 2026-08-13)

`Path.write_text(..., encoding='utf-8-sig')` writes a leading `EF BB BF` BOM even when the original file had none. A repo convention gate that forbids BOMs (`unexpected-bom: UTF-8 BOM is prohibited`) then fails on files you merely touched. Symptom: your edit is correct, but CI/lint reports `unexpected-bom` on files whose content diff looks clean. Fix: read with `utf-8-sig` (tolerant) but **write with plain `utf-8`** (or `write_bytes` after stripping a leading `\xef\xbb\xbf`). Verify with `head -c 3 file | xxd` — must NOT be `ef bb bf`.

### `no such module: vec0` during migrate/fingerprint with sqlite-vec (validated 2026-08-12)

A project using the `sqlite-vec` extension can fail migrations with `sqlite3.OperationalError: no such module: vec0` even though `import sqlite_vec` succeeds: the extension is loaded **per-connection** (`conn.enable_load_extension(True); sv.load(conn)`), and a schema-fingerprint routine that opens a plain `sqlite3.connect` then `SELECT *` over every table hits `vec0` virtual tables without the module loaded. The vector rows are derived from a companion `<table>_id_map` table anyway, so the correct fix is to **skip virtual tables in the fingerprint** and let the id-map table carry the fingerprint:

```python
declared = str(item["sql"] or "")
if "USING vec0" in declared or "VIRTUAL TABLE" in declared:
    continue  # rows derived from *_id_map; can't SELECT without extension
```

Symptoms to recognize: migrate succeeds on a fresh DB then startup fails with a confusing `phase4 ... schema migration is pending` / `no such module: vec0` traceback pointing at `migration_runner`/`index_manifest` fingerprint code. The fix is in the fingerprint routine, not in the migration SQL.

### `uv pip install` without `--python` targets the wrong venv (validated 2026-08-12)

With `UV_PROJECT_ENVIRONMENT` set, `uv run --frozen` executes against that venv, but a bare `uv pip install <pkg>` installs into the **project `.venv`** instead. The package then cannot be imported by the same `uv run` command: `find_spec('<pkg>')` returns `None`, and anything keyed off it (e.g. an engine's `available` flag) silently stays off. This looks like the detector is broken when the real problem is two different interpreters.

```bash
# wrong: goes to project .venv
uv pip install rapidocr-onnxruntime
# right: target the venv uv run actually uses
uv pip install --python "D:/All projects/OS configuration/cognitive-loop-os-ci-venv/Scripts/python.exe" rapidocr-onnxruntime
# verify with the SAME interpreter the run uses:
uv run --frozen --group ci python -c "import importlib.util; print(importlib.util.find_spec('rapidocr_onnxruntime'))"
```

`uv pip show <pkg>` prints the `Location:` — compare it against `uv run --frozen python -c "import sys; print(sys.prefix)"` before assuming the install landed where the run looks.

### 混用裸 `pip install` 会绕过 `uv.lock` 导致 pydantic-core 漂移崩溃 (validated 2026-08-14)

uv 管理的项目（hermes-agent 等）用 `uv.lock` 精确锁定依赖。**裸 `pip install` 不读 `uv.lock`，会装 PyPI 最新版并静默覆盖锁定版本**。2026-08-14 Hermes desktop 后端启动崩溃的根因正是这个：某操作混用 pip，把 `pydantic-core` 从锁定的 2.46.4 升级到 2.48.0，而 `pydantic 2.13.4` 对 pydantic-core 是**精确绑定**（`Requires-Dist: pydantic-core==2.46.4`，`==` 不是 `>=`，二者编译期紧耦合），版本不匹配 → FastAPI 导入即崩 → 后端起不来（报错表面像"依赖缺失"，实为版本漂移）。

诊断看证据、不猜（查 dist-info 的安装器 + 锁文件对比）：

```bash
# 1. 谁装的（uv 还是 pip）—— INSTALLER 文件写明了安装器
cat venv/Lib/site-packages/pydantic_core-*/dist-info/INSTALLER
# 2. 锁文件版本 vs 实际版本
grep -A2 'name = "pydantic-core"' uv.lock | grep version
python -c "import pydantic_core; print(pydantic_core.__version__)"
# 3. pydantic 声明要哪个 core（精确绑定 ==）
grep 'pydantic-core' venv/Lib/site-packages/pydantic-*/dist-info/METADATA
```

修复用 uv 恢复锁定版本，不要再用 pip 覆盖：

```bash
uv sync                        # 或 uv pip install pydantic-core==2.46.4
```

教训：uv 管理的项目里，任何依赖安装/升级都走 `uv sync` / `uv pip install`，**禁止裸 `pip install`**（它绕过锁文件，漂移是静默的，直到运行时崩溃才暴露）。

### pytesseract OCR skips: TESSDATA_PREFIX must point at the versioned dir (validated 2026-08-12)

On this machine, scoop installs language data under a **versioned** directory and there is NO `tesseract-languages/current` symlink. The stale default `TESSDATA_PREFIX=/c/Users/ALEX/scoop/apps/tesseract-languages/current` makes pytesseract fail with `Error opening data file .../tessdata/eng.traineddata` and OCR tests **skip silently** (they do not fail). Fix: set the env var to the actual data dir and export it for the pytest run:

```bash
export TESSDATA_PREFIX="D:/All projects/OS configuration/toolchains/scoop/apps/tesseract-languages/4.1.0"
tesseract --list-langs   # sanity: should print eng
# then run pytest with TESSDATA_PREFIX=... in the env (env -u PYTHONPATH TESSDATA_PREFIX=... uv run ...)
```

Verify the real data location with `find "D:/All projects/OS configuration/toolchains/scoop/apps" -maxdepth 4 -name "eng.traineddata"`. A skipped OCR test is a sign to check this env var, not evidence the OCR path is fine.
