# Windows / Git Bash JSONL append reference

## Trigger

Use when appending a computed JSONL activity/event entry from a Windows Git Bash terminal, especially when the entry contains Chinese text, Windows paths, quotes, or backslashes.

## Failure pattern

A direct `python -c` command with an interpolated JSON string can be rewritten by shell quoting before Python receives it. Typical symptoms include an unterminated Python string, missing quotes, or shell commands accidentally executed from JSON text. Treat that as a failed append; do not infer that the ledger changed.

## Safe recipe

1. Build the entry as a Python dict.
2. Serialize with `json.dumps(entry, ensure_ascii=False, separators=(",", ":"))`.
3. Encode the resulting UTF-8 line with `base64.b64encode`.
4. Pass only the ASCII base64 token through the shell.
5. Decode in a short Python command and append bytes with `Path(path).open("ab")`.
6. Read the ledger again, select the final line, parse it with `json.loads`, and verify the event, run ID, task, and timestamp.

This preserves prior lines and avoids shell interpretation of the JSON payload. It does not authorize overwriting a ledger or writing secrets/raw logs into it.

## Alternative: temp-script pattern (preferred under project-data-boundary)

When `hermes-project-data.py` wrapper blocks shell chaining and heredocs, use a temp Python script:

1. Use `write_file` to create `.hermes/sleep-mode/append_entry.py` with the entry as a Python dict.
2. Run: `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- .venv/Scripts/python .hermes/sleep-mode/append_entry.py`
3. Clean up: `rm .hermes/sleep-mode/append_entry.py` through the wrapper.
4. Verify by reading the ledger.

## Known limitations of base64 approach under wrapper

The base64 recipe works in a plain Windows terminal session but can silently fail (exit code -1 with empty output) when run through `hermes-project-data.py` wrapper on Windows Git Bash. The exact failure is intermittent and depends on quoting depth. If base64 append produces no output and exit code -1, fall back to the temp-script pattern above.

## Evidence requirements

Record separately:

- command construction failure, if any;
- whether the target file size/line count changed;
- final-line JSON parse result;
- exact project-local path;
- no-secret/redaction check.
