"""Pins the pure decision surface of scripts/audit/entry_baseline_readback.py.

The real-machine readback (registry/desktop/.lnk on disk) is never touched here — these
tests feed synthetic resolution dicts and synthetic shell-link bytes into the two pure
functions (decide, parse_lnk) and assert the exact fail-closed verdicts, so the projection
cannot drift from the contract vocabulary while nobody is watching. Negative controls are
first-class tests: two install locations, a dead shortcut target, an IconLocation reset to
the temp install directory (the NSIS trap) and a surface with no install at all must never
come out green or silently disappear.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import struct
import unittest
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "entry_baseline_readback.py"
LIVE_PROBE = ROOT / "scripts" / "audit" / "executor_live_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("entry_baseline_readback", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_module()

TEMP_ROOTS = ["C:\\Users\\X\\AppData\\Local\\Temp"]


def good_shortcut(**over):
    sc = {"lnk_path": "C:\\Users\\X\\Desktop\\App.lnk",
          "target": "C:\\Users\\X\\AppData\\Local\\Programs\\App\\app.exe",
          "target_exists": True, "working_dir": "C:\\Users\\X\\AppData\\Local\\Programs\\App",
          "working_dir_exists": True, "icon": "C:\\Users\\X\\AppData\\Local\\Programs\\App\\app.exe",
          "icon_named": True, "icon_exists": True, "arguments": ""}
    sc.update(over)
    return sc


class VocabularyTests(unittest.TestCase):
    def test_verdict_spelling_comes_from_the_contract_schema(self) -> None:
        enum, source = MODULE.load_location_vocabulary()
        self.assertIn("software-installation-identity.schema.json", source)
        for name in ("SINGLE_VERIFIED", "SINGLE_UNVERIFIED", "DUAL_INSTALLATION",
                     "LOCATION_DRIFT", "MISSING_EXPECTED_INSTALL", "NOT_INSTALLED", "OS_MANAGED"):
            self.assertIn(name, enum, f"{name} is not spelled the same in the contract enum")

    def test_entry_not_resolved_matches_the_probe_vocabulary(self) -> None:
        # ENTRY_NOT_RESOLVED lives in scripts/audit/executor_live_probe.py, not in the
        # schema enum; the audit row may use it ONLY as that same literal.
        self.assertIn("ENTRY_NOT_RESOLVED", LIVE_PROBE.read_text(encoding="utf-8"))
        self.assertEqual("ENTRY_NOT_RESOLVED", MODULE.ENTRY_NOT_RESOLVED)

    def test_no_verdict_outside_the_enum_plus_the_probe_state(self) -> None:
        enum, _ = MODULE.load_location_vocabulary()
        allowed = set(enum) | {MODULE.ENTRY_NOT_RESOLVED}
        cases = [
            {"readback_error": "boom"},
            {"os_managed": True},
            {"relocation_requested": True},
            {"install_roots": ["C:\\a", "D:\\b"], "require_desktop": True},
            {"install_roots": [], "require_desktop": True, "expected_roots": []},
            {"install_roots": [], "expected_roots": ["C:\\declared"], "require_desktop": True},
            {"require_desktop": False, "cli_resolved": True, "cli_paths": ["C:\\gh\\gh.exe"]},
            {"require_desktop": True, "shortcut": good_shortcut(), "wscript_agree": True},
            {"require_desktop": True, "shortcut": good_shortcut(target_exists=False),
             "install_roots": ["D:\\elsewhere"]},
            {"require_desktop": True, "shortcut": good_shortcut(icon=TEMP_ROOTS[0] + "\\nsD.tmp\\a.exe"),
             "temp_roots": TEMP_ROOTS, "install_roots": [str(PureWindowsPath(good_shortcut()["target"]).parent)]},
        ]
        for res in cases:
            res.setdefault("temp_roots", TEMP_ROOTS)
            res.setdefault("install_roots", [])
            verdict = MODULE.decide(res)["verdict"]
            self.assertIn(verdict, allowed, f"verdict {verdict!r} escaped the contract vocabulary")


class NegativeControlTests(unittest.TestCase):
    def test_two_install_locations_are_never_single_verified(self) -> None:
        out = MODULE.decide({"install_roots": ["D:\\Programs\\App", "C:\\Users\\X\\AppData\\Local\\Programs\\App"],
                             "require_desktop": True, "temp_roots": TEMP_ROOTS})
        self.assertNotEqual("SINGLE_VERIFIED", out["verdict"])
        self.assertEqual("DUAL_INSTALLATION", out["verdict"])

    def test_dead_shortcut_target_is_never_single_verified(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": [], "expected_roots": [],
                             "shortcut": good_shortcut(target_exists=False)})
        self.assertNotEqual("SINGLE_VERIFIED", out["verdict"])
        self.assertEqual("NOT_INSTALLED", out["verdict"])

    def test_dead_target_while_an_install_exists_is_drift(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": ["D:\\Programs\\App"],
                             "shortcut": good_shortcut(target_exists=False)})
        self.assertEqual("LOCATION_DRIFT", out["verdict"])

    def test_temp_icon_location_is_drift_not_ignored(self) -> None:
        out = MODULE.decide({"require_desktop": True,
                             "temp_roots": TEMP_ROOTS,
                             "install_roots": ["C:\\Users\\X\\AppData\\Local\\Programs\\App"],
                             "shortcut": good_shortcut(icon=TEMP_ROOTS[0] + "\\nsA1B2\\app.exe")})
        self.assertEqual("LOCATION_DRIFT", out["verdict"])
        self.assertIn("IconLocation", out["reason"])

    def test_temp_target_is_drift(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": [],
                             "shortcut": good_shortcut(target=TEMP_ROOTS[0] + "\\nsZ\\app.exe")})
        self.assertEqual("LOCATION_DRIFT", out["verdict"])

    def test_uninstalled_surface_reports_not_installed_not_absent(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": [], "expected_roots": []})
        self.assertEqual("NOT_INSTALLED", out["verdict"])

    def test_declared_expected_location_absent_is_missing_expected_install(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": [], "expected_roots": ["C:\\Users\\X\\AppData\\Local\\Programs\\App"]})
        self.assertEqual("MISSING_EXPECTED_INSTALL", out["verdict"])

    def test_invented_launcher_convicts(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                             "install_roots": ["C:\\Users\\X\\AppData\\Local\\Programs\\App"],
                             "invented_launcher": True,
                             "shortcut": good_shortcut(target="C:\\Windows\\System32\\wscript.exe")})
        self.assertEqual("LOCATION_DRIFT", out["verdict"])

    def test_parser_disagreement_downgrades(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS, "wscript_agree": False,
                             "install_roots": ["C:\\Users\\X\\AppData\\Local\\Programs\\App"],
                             "shortcut": good_shortcut()})
        self.assertNotEqual("SINGLE_VERIFIED", out["verdict"])
        self.assertEqual("SINGLE_UNVERIFIED", out["verdict"])

    def test_named_missing_icon_is_unverified_not_green(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS, "wscript_agree": True,
                             "install_roots": [],
                             "shortcut": good_shortcut(icon="C:\\gone\\icon.ico", icon_exists=False)})
        self.assertEqual("SINGLE_UNVERIFIED", out["verdict"])

    def test_readback_failure_is_entry_not_resolved(self) -> None:
        out = MODULE.decide({"readback_error": "HKCU unreadable in this sandbox", "temp_roots": TEMP_ROOTS})
        self.assertEqual("ENTRY_NOT_RESOLVED", out["verdict"])

    def test_installed_but_no_desktop_shortcut_is_unverified(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS, "shortcut": None,
                             "install_roots": ["C:\\Programs\\App"]})
        self.assertEqual("SINGLE_UNVERIFIED", out["verdict"])


class PositiveTests(unittest.TestCase):
    def test_clean_single_chain_verifies(self) -> None:
        out = MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS, "wscript_agree": True,
                             "install_roots": ["C:\\Users\\X\\AppData\\Local\\Programs\\App"],
                             "shortcut": good_shortcut()})
        self.assertEqual("SINGLE_VERIFIED", out["verdict"])
        self.assertEqual(good_shortcut()["target"], out["canonical_candidate"])

    def test_cli_surface_verifies_from_path(self) -> None:
        out = MODULE.decide({"require_desktop": False, "temp_roots": TEMP_ROOTS,
                             "cli_resolved": True, "cli_paths": ["C:\\Program Files\\GitHub CLI\\gh.exe"]})
        self.assertEqual("SINGLE_VERIFIED", out["verdict"])

    def test_os_managed_and_relocation_states_reachable(self) -> None:
        self.assertEqual("OS_MANAGED", MODULE.decide({"os_managed": True})["verdict"])
        self.assertEqual("RELOCATION_REQUESTED", MODULE.decide({"relocation_requested": True})["verdict"])


# ---------------------------------------------------------------------------
# synthetic [MS-SHLLINK] bytes for the hand parser (no real files, no registry)
# ---------------------------------------------------------------------------
def build_lnk(target: str, working_dir: str, arguments: str, uni: bool,
              icon: str | None = None, with_idlist: bool = True) -> bytes:
    flags = 0x00000010 if uni else 0x00000000
    if with_idlist:
        flags |= 0x00000001
    header = struct.pack("<I", 0x4C) + bytes.fromhex("0114020000000000c000000000000046") \
        + struct.pack("<I", flags) + b"\x00" * (76 - 4 - 16 - 4)
    body = b""
    if with_idlist:
        # one 6-byte item (size includes its own u16) followed by the 0x0000 terminator
        body += b"\x06\x00" + b"\xef\xbe\xad\xde" + b"\x00\x00"
    # LinkInfo
    if uni:
        lbp = target.encode("utf-16-le") + b"\x00\x00"
    else:
        lbp = target.encode(MODULE.ansi_codec(), errors="replace") + b"\x00"
    volid = b"\x15\x00\x00\x00" + b"\x03\x00\x00\x00" + b"V" * 13
    lbp_off = 28 + len(volid)
    li_len = lbp_off + len(lbp)
    # 28-byte LinkInfo header (6 u32 + 4 zero pad), then VolumeID, then LocalBasePath
    link_info = struct.pack("<IIIIII", li_len, 28, 1, len(volid), lbp_off, 0) + b"\x00" * 4 \
        + volid + lbp
    body += link_info
    # StringData: Name(0), RelativePath(0), WorkingDirectory, CommandArguments
    def counted(s: str) -> bytes:
        if uni:
            return struct.pack("<H", len(s)) + s.encode("utf-16-le")
        return struct.pack("<H", len(s)) + s.encode(MODULE.ansi_codec(), errors="replace")
    body += counted("") + counted("") + counted(working_dir) + counted(arguments)
    if icon is not None:
        loc = icon.encode("utf-16-le") + b"\x00\x00"
        # block: [u32 size][u32 signature][u32 flags][UTF-16 location + NUL]
        block = struct.pack("<II", 12 + len(loc), 0xA0000007) + b"\x00" * 4 + loc
        body += block
    return header + body


class LnkParserTests(unittest.TestCase):
    def test_ansi_target_wd_and_args(self) -> None:
        raw = build_lnk("C:\\Tools\\app.exe", "C:\\Tools", "--flag", uni=False)
        out = MODULE.parse_lnk(raw)
        self.assertTrue(out["parse_ok"], out["parse_error"])
        self.assertEqual("C:\\Tools\\app.exe", out["target_path"])
        self.assertEqual("C:\\Tools", out["working_directory"])
        self.assertEqual("--flag", out["arguments"])

    def test_utf16_target_wd_and_icon(self) -> None:
        raw = build_lnk("C:\\Tools\\App Gui.exe", "C:\\Tools", "",
                        uni=True, icon="C:\\Tools\\App Gui.exe,0")
        out = MODULE.parse_lnk(raw)
        self.assertTrue(out["parse_ok"], out["parse_error"])
        self.assertEqual("C:\\Tools\\App Gui.exe", out["target_path"])
        self.assertEqual("C:\\Tools", out["working_directory"])
        self.assertEqual("C:\\Tools\\App Gui.exe,0", out["icon_location"])

    def test_truncated_file_fails_closed(self) -> None:
        out = MODULE.parse_lnk(b"\x4c\x00\x00\x00" + b"\x00" * 30)
        self.assertFalse(out["parse_ok"])
        self.assertIsNotNone(out["parse_error"])

    def test_bad_header_rejected(self) -> None:
        out = MODULE.parse_lnk(b"NOPE" + b"\x00" * 100)
        self.assertFalse(out["parse_ok"])
        self.assertIn("header", (out["parse_error"] or "").lower())



class PlatformIndependenceTests(unittest.TestCase):
    """The decision surface must give the same verdict on a Linux runner as on the box it describes.

    CI failed 2 + 1 here while this Windows box passed 22/22, because two call sites folded Windows-shaped
    strings through the PLATFORM Path: on Linux `Path("C:\\a\\b.exe").parent` is `.` and
    `Path("C:\\dir") / "x.exe"` is `C:\\dir/x.exe`. The behaviour test pins the verdict across spellings
    that mean the same Windows location, and the static test refuses any `Path(` inside the pure surface --
    so a regression convicts on either runner, not only on the one that is not Windows.
    """

    PURE_SURFACE = ("decide", "_norm", "_in_temp", "parse_lnk")

    def _decide(self, shortcut_over=None, roots=None):
        sc = good_shortcut(**(shortcut_over or {}))
        return MODULE.decide({"require_desktop": True, "temp_roots": TEMP_ROOTS,
                              "install_roots": list(roots or []), "expected_roots": [],
                              "shortcut": sc, "wscript_agree": True})["verdict"]

    def test_the_same_windows_location_verdicts_the_same_however_it_is_spelled(self) -> None:
        backslash = "C:\\Users\\X\\AppData\\Local\\Programs\\App"
        forward = "C:/Users/X/AppData/Local/Programs/App"
        upper = "C:\\USERS\\X\\APPDATA\\LOCAL\\PROGRAMS\\APP"
        base = self._decide(roots=[backslash])
        self.assertEqual("SINGLE_VERIFIED", base,
                         f"a clean single chain must verify before spelling is discussed: {base}")
        for label, root in (("forward-slash", forward), ("upper-case", upper)):
            self.assertEqual(base, self._decide(roots=[root]),
                             f"the {label} spelling of the same Windows install changed the verdict; the "
                             "decision surface is reading the runner's path flavour, not the domain")
        dead = self._decide(shortcut_over={"target_exists": False}, roots=[])
        self.assertEqual("NOT_INSTALLED", dead)
        self.assertEqual(dead, self._decide(shortcut_over={"target_exists": False,
                                                           "target": "C:/Users/X/AppData/Local/Programs/App/app.exe"},
                                            roots=[]),
                         "a dead target stays a dead target whatever the separator")

    def test_the_pure_surface_never_asks_the_platform_how_to_read_a_windows_path(self) -> None:
        tree = ast.parse((ROOT / "scripts/audit/entry_baseline_readback.py")
                         .read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in self.PURE_SURFACE:
                for call in ast.walk(node):
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                            and call.func.id == "Path"):
                        offenders.append(f"{node.name}:{call.lineno}")
        self.assertEqual([], offenders,
                         f"these call sites in the pure decision surface use the platform Path and will "
                         f"diverge on a non-Windows runner: {offenders}; use PureWindowsPath")


class AnsiCodecPortabilityTests(unittest.TestCase):
    """The gate must run on the runner, not only on the machine that wrote it (cloud audit W03).

    `mbcs` exists on Windows and raises LookupError on the Linux runner. The instrument and this fixture
    now read one decision from `ansi_codec()`; these tests are what keeps it that way, and they name the
    reading assumption on a non-Windows host instead of pretending the byte was decoded authoritatively.
    """

    def test_the_codec_is_decided_in_one_place_and_never_spelled_at_a_call_site(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        spelled = [node.lineno for node in ast.walk(tree)
                   if isinstance(node, ast.Constant) and node.value == "mbcs"]
        in_helper = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "ansi_codec":
                in_helper = {n.lineno for n in ast.walk(node)
                             if isinstance(n, ast.Constant) and n.value == "mbcs"}
        self.assertEqual(sorted(spelled), sorted(in_helper),
                         f"the codec is spelled outside ansi_codec() at lines {sorted(set(spelled) - in_helper)};"
                         " a second spelling is the platform-specific bug coming back")
        self.assertEqual(len(spelled), 1, f"expected exactly one `mbcs` literal, found {len(spelled)}")
        # the fixture is the other half of the same decision: it must ask the instrument what the codec
        # is, or the two sides agree only by luck on the host that wrote them
        fixture = Path(__file__).read_text(encoding="utf-8")
        self.assertIn('target.encode(MODULE.ansi_codec()', fixture,
                      "build_lnk spells the ANSI codec itself again -- that is the W03 failure shape")
        self.assertIn('s.encode(MODULE.ansi_codec()', fixture, "the counted-string half drifted")
        # constructed, not written out: a literal needle would appear in this file's own source and the
        # assertion would convict itself for containing the thing it forbids
        bare = "encode(" + chr(34) + "mbcs" + chr(34)
        self.assertEqual(0, fixture.count(bare), "a bare ANSI spelling came back into the fixture")

    def test_the_ansi_fixture_round_trips_through_the_host_that_reads_it(self) -> None:
        raw = build_lnk("C:\\Tools\\app.exe", "C:\\Tools", "--flag", uni=False)
        out = MODULE.parse_lnk(raw)
        self.assertTrue(out["parse_ok"], out["parse_error"])
        self.assertEqual("C:\\Tools\\app.exe", out["target_path"])
        self.assertEqual("--flag", out["arguments"])
        self.assertEqual(MODULE.ansi_codec(), out["ansiCodec"],
                         "the parse result must say which codec produced these strings")

    def test_the_non_windows_reader_names_its_assumption(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows has a system ANSI codepage; the fallback basis is a non-Windows claim")
        self.assertEqual("cp1252", MODULE.ansi_codec())
        out = MODULE.parse_lnk(build_lnk("C:\\a.exe", "C:\\", "", uni=False))
        self.assertIn("assumed", out["ansiCodecBasis"], out)

    @unittest.skipUnless(os.name == "nt", "the system codepage only exists on Windows")
    def test_windows_uses_the_system_codepage_and_claims_no_assumption(self) -> None:
        self.assertEqual("mbcs", MODULE.ansi_codec())
        out = MODULE.parse_lnk(build_lnk("C:\\Tools\\app.exe", "C:\\Tools", "", uni=False))
        self.assertTrue(out["parse_ok"], out["parse_error"])
        self.assertNotIn("ansiCodecBasis", out,
                         "a Windows read uses this machine's own ANSI codepage; calling that 'assumed' "
                         "would understate it. Only the fallback host has to warn.")

    def test_the_fallback_codec_cannot_read_a_codepage_936_path(self) -> None:
        """Why `ansiCodecBasis` is a warning and not a nicety: cp1252 has no answer for a Chinese path.

        Asserted against the codecs themselves rather than as a round trip of a non-ASCII shortcut,
        because whether `应用` survives depends on the machine's ANSI codepage -- a fact about the box,
        not a contract of this repository. A test that passed here and failed on an en-US host would be
        measuring the keyboard layout instead of the code.
        """
        with self.assertRaises(UnicodeEncodeError):
            "应用".encode("cp1252")
        self.assertEqual("应用", "应用".encode("cp936").decode("cp936"))


    def test_the_fallback_branch_is_exercisable_on_every_host(self) -> None:
        """The Linux path is proven here, not deferred to the runner.

        `os.name` is the whole decision, so swapping the module's `os` binding runs the non-Windows
        branch on a Windows box -- which is what makes the W03 fix checkable before a push instead of
        discovering the shape of the fallback from a CI log.
        """
        import types
        original = MODULE.os
        try:
            MODULE.os = types.SimpleNamespace(name="posix")
            self.assertEqual("cp1252", MODULE.ansi_codec())
            out = MODULE.parse_lnk(build_lnk("C:\\a.exe", "C:\\", "", uni=False))
            self.assertTrue(out["parse_ok"], out["parse_error"])
            self.assertEqual("C:\\a.exe", out["target_path"])
            self.assertIn("assumed", out["ansiCodecBasis"], out)
        finally:
            MODULE.os = original
        self.assertEqual("mbcs" if os.name == "nt" else "cp1252", MODULE.ansi_codec(),
                         "the swap must not outlive the test")


if __name__ == "__main__":
    unittest.main()
