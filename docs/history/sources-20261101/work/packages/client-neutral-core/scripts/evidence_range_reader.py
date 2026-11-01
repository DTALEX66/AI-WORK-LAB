"""Precise byte-range reads on large evidence artifacts (REQ-RANGE-20261007 / blueprint SoL row).

The evidence chain already carries a sha256 per artifact and a cost budget, but the only way to look at a
large log was to read it whole or show a prefix (`_truncate(limit=4000)`-style). A prefix is not a slice:
a reader cannot tell where it stopped, whether more exists, or whether the bytes they were shown still
belong to the digest that was recorded.

This module reads an exact interval and reports enough identity to trust it:

* the handle must resolve inside a declared evidence surface — an absolute path outside the repository, a
  path that is inside the repository but not evidence, a credential-shaped name, a missing file, a
  directory, and an unreadable file are each their own typed failure, never an empty success;
* the caller may pin the expected whole-file digest; the reader then MEASURES the file itself and compares
  its own measurement against that pin — a caller-supplied "actual" digest is never the basis of a verdict,
  because comparing one caller input with another proves only that the caller repeated itself. A mismatch is
  DIGEST_MISMATCH and returns NO content, because showing bytes from a file that is not the recorded one is
  worse than showing nothing;
* `sliceDigest` is a digest of exactly the bytes returned, so an interval can be cited without shipping
  the whole artifact;
* cost is measured and reported (bytes read against file size), because the point of the feature is that a
  slice of a large log is cheap, and that claim has to be checkable.

Read-only by construction: there is no write path here, it never follows a handle out of the project, and
it never serves a file that the project's own boundary calls configuration, credentials, or a session store.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import sys

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from path_text import inside_root, path_is_anchored  # noqa: E402
from typing import Any

SCHEMA_VERSION = "worklab/evidence-range-result/v1"
MAX_LIMIT = 4 * 1024 * 1024          # 4 MiB per read; larger requests are refused, not silently capped
DEFAULT_LIMIT = 64 * 1024
DIGEST_HEX_LENGTH = 64
# Verifying an identity means hashing the whole artifact, so an expected_digest costs one full read.
# That is bounded on purpose: past this size the reader says it cannot verify instead of reading a
# multi-gigabyte log to answer a range request. Unmeasurable names itself; it never becomes a pass.
WHOLE_HASH_MAX_BYTES = 16 * 1024 * 1024
WHOLE_HASH_CHUNK_BYTES = 1 * 1024 * 1024

STATUS_OK = "OK"
STATUS_OUT_OF_RANGE = "OUT_OF_RANGE"
REFUSALS = {
    "HANDLE_REQUIRED": "handle 为空：没有句柄就没有对象。",
    "ABSOLUTE_PATH_REQUIRED": "handle 必须是绝对路径；相对路径会随调用者的工作目录改变所指文件。",
    "OUT_OF_BOUNDARY": "handle 解析到本仓库之外，只读投影不跨越项目边界。",
    "OUT_OF_EVIDENCE_SURFACE": "handle 不在声明的证据目录内：项目内部本身就是敏感的，边界不等于许可。",
    "SENSITIVE_NAME": "handle 指向凭证、配置、会话库或密钥类文件，读取投影在任何边界内都不提供这类内容。",
    "UNRESOLVABLE": "handle 无法解析，按失败关闭处理。",
    "NOT_A_FILE": "handle 不指向普通文件（不存在、目录或特殊文件）。",
    "UNREADABLE": "handle 存在但读不了；这是实测到的失败，不是没有内容。",
    "LIMIT_TOO_LARGE": f"单次读取上限 {MAX_LIMIT} 字节，超限拒绝而不是静默截断。",
    "DIGEST_MISMATCH": "期望摘要与读取器实测的整文件摘要不符：返回的字节不属于被记录的那份产物，因此不返回内容。",
    "DIGEST_SHAPE": "expected_digest 必须是 64 位十六进制 sha256。",
    "IDENTITY_TOO_LARGE_TO_MEASURE": (
        f"核对身份需要实测整文件摘要，而文件超过 {WHOLE_HASH_MAX_BYTES} 字节上限："
        "身份未核验，因此不返回内容；这不是读取失败，也不是通过。"),
}

# `.project-local/artifacts` and `.project-local/runs` are what the boundary declaration names as evidence
# and runtime surfaces. Everything else inside the repository is source, configuration, or a local database:
# staying inside the Git root is a spill rule, not a reading licence.
DEFAULT_EVIDENCE_ROOTS = (".project-local/artifacts", ".project-local/runs")

# The owner's no-read law is about kinds of content, so it is enforced by name as well as by directory: a
# restored pre-install backup sits under an evidence root and still contains another tool's config.
#
# Matching is per delimited word, not per substring, because a substring test over-refuses real evidence:
# `02_SCOPE_SUPERSESSION_MAP.md` was being refused for containing "session", and a stylesheet called
# `design-tokens.css` for containing "token". Both are project files with nothing credential about them.
SENSITIVE_PREFIXES = (".env",)
SENSITIVE_SUFFIXES = (".env", ".sqlite", ".sqlite3", ".db", ".key", ".pem", ".pfx", ".pkcs12",
                      "config.yaml", "config.yml", ".credentials", "login data", "id_rsa")
SENSITIVE_WORDS = frozenset({
    "credential", "credentials", "secret", "secrets", "token", "auth", "auth_store", "cookie", "cookies",
    "password", "passwords", "passwd", "session", "sessions", "private_key", "keystore", "browser_data",
    "history", "sqlite", "sqlite3", "db", "p12", "pkcs12",
})

# Kept as the coarse vocabulary for callers that describe the rule in prose; the matcher below is the law.
SENSITIVE_NAME_TOKENS = tuple(sorted(SENSITIVE_WORDS | {"config.yaml", ".env", ".sqlite", ".db", ".key",
                                                        ".pem", "id_rsa", "canonical.sqlite"}))
_NAME_SPLIT = re.compile(r"[^a-z0-9]+")


def name_is_sensitive(resolved: Path, exempt: tuple[str, ...] = ()) -> bool:
    """True when any path segment names a credential, session, cookie, auth or config-store kind.

    `exempt` removes exact tokens from the judgement -- the control plane's config diff is the one operation
    whose legitimate subject IS a configuration document, and it answers only key-path questions.
    """
    for part in resolved.parts:
        lowered = part.lower()
        if lowered in exempt:
            continue
        if lowered.startswith(SENSITIVE_PREFIXES):
            return True
        if lowered.endswith(SENSITIVE_SUFFIXES):
            return True
        if any(word in SENSITIVE_WORDS for word in _NAME_SPLIT.split(lowered) if word):
            return True
    return False


BOUNDARY_DECLARATION = ".project/governance/project-data-boundary.json"
_BOUNDARY_ROOT_KEYS = ("canonicalEvidenceRoot", "taskArtifactsRoot", "runtimeRoot")


def declared_evidence_roots(root: Path) -> tuple[str, ...]:
    """Read the evidence surfaces from the boundary declaration instead of hardcoding a second opinion.

    A missing or unreadable declaration falls back to the narrow default, never to "everything in the
    repository": an absent authority is a reason to refuse, not to allow.
    """
    try:
        document = json.loads((Path(root) / BOUNDARY_DECLARATION).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return DEFAULT_EVIDENCE_ROOTS
    declared = tuple(str(document[key]) for key in _BOUNDARY_ROOT_KEYS if document.get(key))
    return declared or DEFAULT_EVIDENCE_ROOTS


def _sha256_slice(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _measure_whole_digest(path: Path, size: int) -> str | None:
    """Hash the whole artifact, or return None when the reader refuses to.

    Only called when a caller asked for identity verification, so the full read is the caller's own price,
    not something the cheap range path pays.
    """
    if size > WHOLE_HASH_MAX_BYTES:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(WHOLE_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(*, expected: str | None, measured: str | None, size: int | None) -> dict[str, Any]:
    """The identity block, and the only place its provenance vocabulary is spelled.

    `wholeDigest` is ever a measurement made by this reader, never a value the caller supplied: an earlier
    shape put a caller argument in this field and the interface then compared it with another caller
    argument and called the result AGREE.
    """
    if measured:
        source = "measured-by-reader"
    elif expected:
        source = "not-measurable"
    else:
        source = "not-requested"
    return {
        "expectedDigest": expected,
        "wholeDigest": measured,
        "sizeBytes": size,
        "digestSource": source,
        "verified": bool(expected and measured and measured == expected),
    }


def _refusal(code: str, *, handle: str, detail: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "REFUSED",
        "reason_code": code,
        "reason": REFUSALS[code] + (f" 细节：{detail}" if detail else ""),
        "handle": handle,
        "content": None,
        "cost": {"bytesRead": 0, "fileSize": None, "wholeFileWasRead": False},
    }


def read_range(*, handle: str, root: Path, offset: int = 0, limit: int = DEFAULT_LIMIT,
               expected_digest: str | None = None,
               evidence_roots: tuple[str, ...] = DEFAULT_EVIDENCE_ROOTS) -> dict[str, Any]:
    """Read `limit` bytes at `offset` from a declared evidence artifact inside this project.

    `evidence_roots` are relative to `root` and default to the surfaces the boundary declaration names as
    evidence and runtime storage. Passing an explicit tuple narrows the surface; passing () refuses
    everything, because an unset surface is not the same as an unrestricted one.

    `expected_digest` is the ONLY identity input: the reader measures the file itself and refuses to return
    bytes when its measurement disagrees. There is deliberately no parameter for the caller to supply the
    file's "actual" digest — that input could only ever be compared against another caller input, and an
    identity check whose both sides come from the same untrusted party is not a check.
    """
    # Containment is decided from TEXT first (path_text), because `resolve()`/`is_relative_to` consult the
    # host: on the Linux runner a Windows-shaped handle has no drive, so posixpath reads it as relative and
    # anchors it inside this project -- the verdict then depends on which machine asks. The resolved real path
    # is still computed, but ONLY ever to add a refusal (a symlink that climbs out of the project), never to
    # grant one, so no host can make an outside file look inside.
    root_declared = Path(str(root))
    if not handle or not str(handle).strip():
        return _refusal("HANDLE_REQUIRED", handle=str(handle))
    if not path_is_anchored(handle):
        return _refusal("ABSOLUTE_PATH_REQUIRED", handle=str(handle))
    inside, root_lex, cand_lex = inside_root(handle, root_declared)
    if not inside:
        return _refusal("OUT_OF_BOUNDARY", handle=str(handle),
                        detail=f"{cand_lex} 不在 {root_lex} 之内")
    path = Path(str(handle))
    if name_is_sensitive(path):
        # Named before the surface test: a credential-looking path is refused even when it sits in an
        # evidence root, so a restored backup cannot be read just because it was filed under artifacts/.
        return _refusal("SENSITIVE_NAME", handle=str(handle), detail=path.name)
    if not evidence_roots or not any(inside_root(handle, root_declared / relative)[0]
                                     for relative in evidence_roots):
        return _refusal("OUT_OF_EVIDENCE_SURFACE", handle=str(handle), detail=cand_lex)
    try:
        real = path.resolve()
    except OSError as error:
        return _refusal("UNRESOLVABLE", handle=str(handle), detail=type(error).__name__)
    real_inside, _, real_lex = inside_root(real, root_declared)
    if not real_inside:
        return _refusal("OUT_OF_BOUNDARY", handle=str(handle),
                        detail=f"realpath {real_lex} 逃出了 {root_lex}（链接或重定向），只读投影不跟出项目")
    if not path.is_file():
        return _refusal("NOT_A_FILE", handle=str(handle))
    if limit <= 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": STATUS_OUT_OF_RANGE,
            "reason_code": "LIMIT_NON_POSITIVE",
            "reason": "limit 必须为正数；0 或负数不是一次读取。",
            "handle": str(handle),
            "content": None,
            "cost": {"bytesRead": 0, "fileSize": None, "wholeFileWasRead": False},
        }
    if limit > MAX_LIMIT:
        return _refusal("LIMIT_TOO_LARGE", handle=str(handle), detail=f"requested={limit}")

    size = path.stat().st_size
    if offset < 0:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": STATUS_OUT_OF_RANGE,
            "reason_code": "OFFSET_NEGATIVE",
            "reason": "offset 不能为负。",
            "handle": str(handle),
            "content": None,
            "cost": {"bytesRead": 0, "fileSize": size, "wholeFileWasRead": False},
        }
    if offset >= size:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": STATUS_OUT_OF_RANGE,
            "reason_code": "OFFSET_PAST_END",
            "reason": f"offset {offset} 已超过文件长度 {size}；这是空区间，不是读失败。",
            "handle": str(handle),
            "content": None,
            "cost": {"bytesRead": 0, "fileSize": size, "wholeFileWasRead": False},
        }

    measured: str | None = None
    if expected_digest is not None:
        if len(expected_digest) != DIGEST_HEX_LENGTH or any(
                character not in "0123456789abcdefABCDEF" for character in expected_digest):
            return _refusal("DIGEST_SHAPE", handle=str(handle), detail=expected_digest[:16])
        try:
            measured = _measure_whole_digest(path, size)
        except OSError as error:
            return _refusal("UNREADABLE", handle=str(handle), detail=type(error).__name__)
        if measured is None:
            result = _refusal("IDENTITY_TOO_LARGE_TO_MEASURE", handle=str(handle),
                              detail=f"size={size} > {WHOLE_HASH_MAX_BYTES}")
            result["cost"]["fileSize"] = size
            result["identity"] = _identity(expected=expected_digest, measured=None, size=size)
            return result
        if measured != expected_digest:
            result = _refusal("DIGEST_MISMATCH", handle=str(handle),
                              detail=f"expected={expected_digest[:12]}… measured={measured[:12]}…")
            result["cost"]["fileSize"] = size
            result["identity"] = _identity(expected=expected_digest, measured=measured, size=size)
            return result

    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(limit)
    except OSError as error:
        return _refusal("UNREADABLE", handle=str(handle), detail=type(error).__name__)

    end = offset + len(data)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_OK,
        "reason_code": "READ_OK",
        "reason": "按精确区间读取。",
        "handle": str(path),
        "offset": offset,
        "limit": limit,
        "bytesRequested": min(limit, size - offset),
        "endOffset": end,
        "eofReached": end >= size,
        "content": data.decode("utf-8", errors="replace"),
        "sliceDigest": _sha256_slice(data),
        "identity": _identity(expected=expected_digest, measured=measured, size=size),
        "cost": {"bytesRead": len(data), "fileSize": size,
                 "wholeFileWasRead": end >= size and offset == 0 and len(data) == size},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handle", required=True, help="absolute path inside this repository")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--expected-digest", default=None)
    parser.add_argument("--evidence-root", action="append", default=None,
                        help="relative evidence surface; defaults to the boundary declaration")
    parser.add_argument("--json", action="store_true", help="print the full typed result")
    args = parser.parse_args(argv)
    roots = tuple(args.evidence_root) if args.evidence_root else declared_evidence_roots(args.root)
    result = read_range(handle=args.handle, root=args.root, offset=args.offset, limit=args.limit,
                        expected_digest=args.expected_digest, evidence_roots=roots)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"status={result['status']} reason={result['reason_code']} "
              f"bytes={result['cost']['bytesRead']}/{result['cost']['fileSize']}")
        if result["content"] is not None:
            print(result["content"], end="")
    return 0 if result["status"] == STATUS_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
