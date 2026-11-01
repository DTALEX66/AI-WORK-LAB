# Patch/Write Tools: Backslash-Escape Mangles Windows Paths (validated 2026-09-02)

When a `patch`/`write` replacement payload contains a literal Windows path,
backslash-escape sequences inside it get decoded **before** the write:

- `D:\All projects\DSH\resources\app.asar.unpacked\package.json`
  → the `\r` in `\resources` becomes a carriage return, and CRLF normalization
  turns it into a real newline → the path is SPLIT across two lines on disk
  (`...DSH` + newline + `esources\app.asar...`).
- A follow-up `patch` whose `old_string` spans that broken line then FAILS to
  match (the on-disk line break is CRLF, so a `\n`-joined old_string never
  matches), yet the tool may still report success — the file is unchanged.

Dangerous sequences in Windows paths: `\r`, `\n`, `\t`, `\b`, `\f`, `\"`, `\\`
(valid JSON/string escapes). `\d`, `\A`, `\a` are not escapes and pass through.

## Rules

1. **In edit payloads, write Windows paths with forward slashes**
   (`D:/All projects/DSH/...`) — markdown/code accept them, and no escape
   decoding can fire.
2. If backslashes are unavoidable (code snippets), double them (`D:\\All ...`)
   so decoding yields a literal single backslash.
3. **After any patch that wrote a `\x`-containing path, verify at byte level**:
   `python -c "import pathlib; d=pathlib.Path('<f>').read_bytes(); i=d.find('版本'.encode()); print(repr(d[i:i+120]))"`
   — look for `\\r`/`\\n` bytes in the middle of a path (repr shows CR as `\\r`).
4. Fixing a mangled file: a text patch may keep failing (old_string can't span
   the embedded CRLF) — go **byte-level**: read bytes, `bytes.replace` the bad
   segment (`b"DSH\\r\\nesources"` → `b"DSH\\resources"`), write bytes back.
5. Python `open().write()` inside execute_code does NOT have this problem —
   escapes only decode in the string literal you typed; use raw strings
   (`r"D:\..."`) or doubled backslashes there.
