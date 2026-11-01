from __future__ import annotations
import sys
from pathlib import Path

SENSITIVE_NAMES = {".env", "auth.json", "credentials.json", "cookies.json"}

def check(root: Path) -> list[str]:
    failures: list[str] = []
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.name == ".git" and path != root / ".git":
            failures.append(f"nested git: {path}")
        if path.is_file() and path.name.lower() in SENSITIVE_NAMES:
            failures.append(f"sensitive filename: {path.relative_to(root)}")
    return failures

if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    failures = check(root)
    if failures:
        for item in failures:
            print(item)
        raise SystemExit(1)
    print("SECURITY_PATH_CHECK=PASS")
