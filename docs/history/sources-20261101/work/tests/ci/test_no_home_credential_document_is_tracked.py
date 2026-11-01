"""No home-owned credential-class document may sit in the tracked tree of a PUBLIC repository.

The project rule is explicit -- never commit credentials, `.env` files or auth stores -- and the
2026-09-30 audit archive import carried `reports/audit-archive/20260930/hermes/config.yaml`, a copy
of the user's live Hermes Home config, into a repository whose GitHub visibility is PUBLIC. A
value-shape scan of that file found zero secret-shaped values, so nothing was leaked *as measured*;
what was leaked is the config document itself, which AGENTS.md treats as mixed-ownership and
never-promotable. That is the exposure this test refuses to let grow again.

Two separate judgements are pinned here, because conflating them is how a false alarm and a real
leak both get waved through:
  * NAME class -- a tracked path whose exact basename is a credential/config-store kind. These must
    equal the declared exception set exactly, so a stale exception fails as loudly as a new one.
  * VALUE class -- secret-shaped bytes inside a tracked blob. The scanner that answers this is
    probed against planted shapes, because a zero-count instrument that has never been shown to
    fire proves nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "audit"))

CREDENTIAL_NAME_CLASS = re.compile(
    r"(?i)(^|/)(\.env|[^/]*\.env\.[a-z]+|config\.yaml|credentials(\.json)?|secrets?(\.json)?|"
    r"auth(\.json|\.yaml|\.store)?|id_rsa[a-z_]*|[^/]*\.(pem|pfx|p12|key|keystore|jks))$"
)

# Every member must be a project-authored document or an owner-registered exposure. The reason
# column is the audit trail: an exception without a reason is how a leak becomes permanent state.
DECLARED_EXCEPTIONS: dict[str, str] = {
    "config/config.yaml": "authored here; the project's own declared config document, "
                          "checked by the config-diff gate",
    "config/.env.template": "authored here; placeholder vocabulary only, never a live value",
    "reports/audit-archive/20260930/hermes/config.yaml": "EXPOSURE, pending owner decision -- "
        "imported copy of the user's Hermes Home config; value-shape scan reports 0 matches "
        "(.project-local/artifacts/SECRET_SHAPE_SCAN_HEAD.json), removal is owner-gated because "
        "the file is an archived audit member",
}


def tracked_paths() -> list[str]:
    raw = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True).stdout
    return [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]


class NameClassIsExactlyDeclared(unittest.TestCase):
    def test_tracked_credential_named_files_are_the_declared_set(self) -> None:
        found = {p for p in tracked_paths() if CREDENTIAL_NAME_CLASS.search(p)}
        extra = sorted(found - set(DECLARED_EXCEPTIONS))
        missing = sorted(set(DECLARED_EXCEPTIONS) - found)
        self.assertEqual([], extra, f"new credential-class document tracked: {extra}")
        self.assertEqual([], missing, f"declared exception no longer tracked; delete the line: {missing}")

    def test_every_exception_carries_a_reason(self) -> None:
        for path, reason in DECLARED_EXCEPTIONS.items():
            self.assertGreaterEqual(len(reason), 40, f"{path}: exception reason too thin to audit")

    def test_the_name_class_rejects_the_shapes_it_exists_to_reject(self) -> None:
        """A guard that cannot fire guards nothing: each shape must be refused on its own."""
        for probe in [".env", "config/.env", "secrets.json", "credentials.json", "auth.json",
                      "id_rsa", "server.pem", "client.pfx", "keystore.jks", "tls.key",
                      "hermes/home/config.yaml"]:
            self.assertTrue(CREDENTIAL_NAME_CLASS.search(probe), f"name class missed {probe}")

    def test_the_name_class_does_not_refuse_ordinary_source_on_a_word_collision(self) -> None:
        """The coarse substring matcher over-matches; this class must not refuse a real app."""
        for keep in ["apps/token-monitor/src/main.js", "docs/current/workflow-assistance/"
                     "workflow/token-monitor.md", "config/adapter-registry.json",
                     "packages/client-neutral-core/scripts/canonical_store.py"]:
            self.assertFalse(CREDENTIAL_NAME_CLASS.search(keep), f"name class over-refused {keep}")


class ValueScannerIsCompetent(unittest.TestCase):
    """The 0-match result is only evidence if the instrument demonstrably fires on real shapes."""

    def setUp(self) -> None:
        import tracked_secret_shape_scan as tool
        self.tool = tool

    def test_planted_secret_shapes_are_detected(self) -> None:
        """Shapes are assembled at runtime, never spelled as literals in this file.

        GitHub's push protection scans the added lines of every commit in a push and rejected one
        of my pushes over a *fake* Slack token written here. A planted literal that a real scanner
        cannot tell from a real credential is a liability the repository should not carry, so each
        value is concatenated from parts: the scanner still sees the shape in the string it is
        handed, and no blob in this repository's history ever contains a matchable token.
        """
        planted = {
            "github-pat": "token: " + "ghp_" + "A" * 36,
            "openai-key": 'api_key = "sk-' + "a" * 34 + '"',
            "anthropic-key": "key: " + "sk-ant-" + "a" * 30,
            "aws-access-key": "aws_access_key_id = " + "AKIA" + "ABCD1234EFGH5678",
            "private-key-block": "-----BEGIN RSA " + "PRIVATE KEY-----" + "\nMIIEow",
            "jwt": "authorization: " + "eyJhbGciOiJIUzI1NiIs" + "." + "eyJzdWIiOiIxMjM0NTY3ODkw"
                   + "." + "abcDEF123456",
            "bearer-token": "Authorization: " + "Bearer " + "abc123." * 5,
            "secret-assignment": "password: " + "Sup3rS3cr3tValue123",
            "slack-token": "xoxb" + "-" + "123456789012" + "-" + "abcdefghijklmnop",
            "google-api-key": "AIza" + "SySya" * 6,
        }
        for name, text in planted.items():
            with self.subTest(shape=name):
                self.assertTrue(self.tool.scan_text(text), f"{name}: planted value not detected")
        # and the source of this very file must not contain a matchable token
        own_text = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual([], self.tool.scan_text(own_text),
                         "this fixture carries a matchable credential literal")

    def test_prose_about_credentials_is_not_reported_as_one(self) -> None:
        prose = ("The password field is documented as `password: <your-api-key>`, and the "
                 "api_key = 'example-placeholder' form is shown in the README. token handling "
                 "is described in the auth store section.")
        self.assertEqual([], self.tool.scan_text(prose))

    def test_a_scoped_tree_scan_reports_its_own_coverage(self) -> None:
        """The tool must publish how many files it actually read, not just what it found."""
        out = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "audit" / "tracked_secret_shape_scan.py"),
             "--scope", "config", "--out",
             ".project-local/runs/qoder-20261007-a/secret_scan_from_test.json"],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, out.returncode, out.stdout + out.stderr)
        lines = [ln for ln in out.stdout.splitlines() if ln.startswith("SECRET_SHAPE_SCAN")]
        self.assertTrue(lines, "tool printed no coverage receipt line")
        receipt = dict(kv.split("=") for kv in lines[0].split()[1:])
        self.assertGreater(int(receipt["scanned"]), 0, "scan read nothing and claimed a clean tree")


class BackupSuffixClassIsExactlyDeclared(unittest.TestCase):
    """Turn register row D2's prose ("0 tracked .bak") into a measurement that can go red.

    D2 was closed as vacuous on a 2026-09-23 scan, and the tree gained a tracked `.bak` on
    2026-09-30 (`reports/audit-archive/.../config.toml.bak`, added by d43d07a7). The claim rotted
    because nothing recomputed it; this recomputes it on every gate run, and a stale exception
    fails just as loudly as a new one.
    """

    BACKUP_CLASS = re.compile(r"(?i)\.(bak|orig|backup)$")
    DECLARED_EXCEPTIONS: dict[str, str] = {
        "reports/audit-archive/20260930/openhuman/users/6a6776fa283c66ca5cfe7f36/config.toml.bak":
            "archived audit member, not stray build residue; deleting it is an owner decision "
            "(row D2 is OPEN pending that call)",
    }

    def test_tracked_backup_named_files_are_the_declared_set(self) -> None:
        found = {p for p in tracked_paths() if self.BACKUP_CLASS.search(p)}
        extra = sorted(found - set(self.DECLARED_EXCEPTIONS))
        gone = sorted(set(self.DECLARED_EXCEPTIONS) - found)
        self.assertEqual([], extra, f"new backup file tracked: {extra}")
        self.assertEqual([], gone, f"backup exception no longer tracked; delete the line: {gone}")

    def test_the_backup_class_fires_on_the_shapes_it_names(self) -> None:
        for probe in ["a/settings.json.bak", "x/y.rs.orig", "z/report.backup"]:
            self.assertTrue(self.BACKUP_CLASS.search(probe), probe)
        for keep in ["a/bake.rs", "orig/lane.ts", "package.json"]:
            self.assertFalse(self.BACKUP_CLASS.search(keep), keep)


if __name__ == "__main__":
    unittest.main()
