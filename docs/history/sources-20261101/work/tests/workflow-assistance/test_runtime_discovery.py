"""Contract tests for the local model runtime registry (WL3-330 / MR-06).

Covers the taskpack §20.3 runtime/resource matrix for the discovery layer:
Ollama absent/healthy, non-loopback rejection, unknown version, ComfyUI
observe-only, Codex never requires an API key, faster-whisper absence.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

import runtime_registry as registry


class RuntimeRegistryTests(unittest.TestCase):
    def test_schema_version_is_v1(self) -> None:
        entry = registry._base_registry("x", "ollama", "executable-probe", "loopback", "gpu.heavy", "OBSERVED")
        self.assertEqual(entry["schema_version"], "workflow/runtime-registry/v1")

    # -- loopback validation ------------------------------------------------
    def test_non_loopback_endpoint_rejected(self) -> None:
        ok, detail = registry._validate_loopback("http://0.0.0.0:11434")
        self.assertFalse(ok)
        self.assertIn("non-loopback", detail)
        ok2, _ = registry._validate_loopback("http://192.168.1.10:11434")
        self.assertFalse(ok2)

    def test_loopback_endpoints_accepted(self) -> None:
        for endpoint in ("http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434"):
            ok, _ = registry._validate_loopback(endpoint)
            self.assertTrue(ok, endpoint)

    def test_invalid_port_rejected(self) -> None:
        ok, detail = registry._validate_loopback("http://127.0.0.1:99999")
        self.assertFalse(ok)
        self.assertIn("port", detail)

    # -- Ollama absent ------------------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value=None)
    def test_ollama_absent_when_no_executable(self, _which: mock.Mock) -> None:
        entry = registry.discover_ollama()
        self.assertEqual(entry["health_state"], "ABSENT")
        self.assertEqual(entry["executable_identity"], None)
        self.assertEqual(entry["auto_start_policy"], "never")
        self.assertIsNone(entry["endpoint"])

    # -- Ollama healthy -----------------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value="C:/ollama/ollama.exe")
    @mock.patch("runtime_registry._probe_version", return_value="ollama version is 0.32.13")
    @mock.patch("runtime_registry._http_json", return_value={"version": "0.32.13"})
    def test_ollama_healthy(self, _http, _ver, _which) -> None:
        entry = registry.discover_ollama()
        self.assertEqual(entry["health_state"], "HEALTHY")
        self.assertEqual(entry["bind_scope"], "loopback")
        self.assertEqual(entry["version_state"], "DETECTED")
        self.assertEqual(entry["endpoint"], "http://127.0.0.1:11434")

    # -- Ollama unhealthy (executable present, API down) ---------------------
    @mock.patch("runtime_registry.shutil.which", return_value="C:/ollama/ollama.exe")
    @mock.patch("runtime_registry._probe_version", return_value="ollama version is 0.32.13")
    @mock.patch("runtime_registry._http_json", return_value=None)
    def test_ollama_unhealthy_when_api_down(self, _http, _ver, _which) -> None:
        entry = registry.discover_ollama()
        self.assertEqual(entry["health_state"], "UNHEALTHY")
        self.assertEqual(entry["endpoint"], "http://127.0.0.1:11434")

    # -- unknown version stays UNKNOWN --------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value="C:/ollama/ollama.exe")
    @mock.patch("runtime_registry._probe_version", return_value=None)
    @mock.patch("runtime_registry._http_json", return_value={"version": "0.32.13"})
    def test_ollama_unknown_version_not_invented(self, _http, _ver, _which) -> None:
        entry = registry.discover_ollama()
        self.assertEqual(entry["version_state"], "UNKNOWN")
        self.assertIsNone(entry["detected_version"])

    # -- port from machine overlay -------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value="C:/ollama/ollama.exe")
    @mock.patch("runtime_registry._probe_version", return_value="v0.32.13")
    @mock.patch("runtime_registry._http_json", return_value={"version": "0.32.13"})
    def test_ollama_declared_port_wins(self, _http, _ver, _which) -> None:
        entry = registry.discover_ollama({"ollama_port": 21434})
        self.assertEqual(entry["endpoint"], "http://127.0.0.1:21434")

    # -- llama.cpp ----------------------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value=None)
    def test_llama_cpp_absent_no_install(self, _which) -> None:
        entry = registry.discover_llama_cpp()
        self.assertEqual(entry["health_state"], "ABSENT")
        self.assertEqual(entry["auto_start_policy"], "never")
        self.assertEqual(entry["launch_mode"], "managed-sidecar")

    @mock.patch("runtime_registry.shutil.which", return_value="C:/llama/llama-server.exe")
    @mock.patch("runtime_registry._probe_version", return_value="build 1234")
    def test_llama_cpp_detected(self, _ver, _which) -> None:
        entry = registry.discover_llama_cpp()
        self.assertEqual(entry["health_state"], "UNKNOWN")  # never probe live model
        self.assertEqual(entry["version_state"], "DETECTED")

    # -- ComfyUI observe/reference-only --------------------------------------
    def test_comfyui_absent_without_declared_endpoint(self) -> None:
        entry = registry.discover_comfyui()
        self.assertEqual(entry["health_state"], "ABSENT")
        self.assertEqual(entry["launch_mode"], "external")
        self.assertEqual(entry["auto_start_policy"], "never")

    def test_comfyui_non_loopback_declared_rejected(self) -> None:
        entry = registry.discover_comfyui({"comfyui_endpoint": "http://0.0.0.0:8188"})
        self.assertEqual(entry["health_state"], "UNHEALTHY")
        self.assertIsNone(entry["endpoint"])

    @mock.patch("runtime_registry._http_json", return_value={"system": "ok"})
    def test_comfyui_declared_loopback_healthy(self, _http) -> None:
        entry = registry.discover_comfyui({"comfyui_endpoint": "http://127.0.0.1:8188"})
        self.assertEqual(entry["health_state"], "HEALTHY")
        self.assertEqual(entry["bind_scope"], "loopback")

    # -- faster-whisper ------------------------------------------------------
    @mock.patch.dict("sys.modules", {"faster_whisper": None})
    def test_faster_whisper_absent(self) -> None:
        entry = registry.discover_faster_whisper()
        self.assertEqual(entry["health_state"], "ABSENT")

    # -- DeepSeek ------------------------------------------------------------
    def test_deepseek_absent_without_binding(self) -> None:
        entry = registry.discover_deepseek({})
        self.assertEqual(entry["health_state"], "ABSENT")

    def test_deepseek_declared_egress_approval_required(self) -> None:
        entry = registry.discover_deepseek({"deepseek_binding": True})
        self.assertEqual(entry["health_state"], "UNKNOWN")  # never probe paid API
        self.assertEqual(entry["egress"], "approval_required")

    # -- Codex ---------------------------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value=None)
    def test_codex_absent(self, _which) -> None:
        entry = registry.discover_codex()
        self.assertEqual(entry["health_state"], "ABSENT")
        self.assertFalse(entry["requires_openai_api_key"])

    @mock.patch("runtime_registry.shutil.which", return_value="C:/codex/codex.exe")
    def test_codex_never_requires_api_key(self, _which) -> None:
        entry = registry.discover_codex()
        self.assertEqual(entry["health_state"], "UNKNOWN")  # probing would start it
        self.assertFalse(entry["requires_openai_api_key"])

    # -- discover_all --------------------------------------------------------
    @mock.patch("runtime_registry.shutil.which", return_value=None)
    def test_discover_all_is_read_only_and_complete(self, _which) -> None:
        result = registry.discover_all()
        self.assertEqual(result["schema_version"], "workflow/runtime-registry/v1")
        self.assertEqual(
            set(result["runtimes"]),
            {"ollama", "llama-cpp", "faster-whisper", "comfyui", "deepseek-api", "codex-exec"},
        )

    # -- ollama_models usage mapping ------------------------------------------
    @mock.patch("runtime_registry._http_json", return_value={
        "models": [{"name": "qwen3:4b", "size": 1024, "digest": "abc", "details": {"family": "qwen3"}}],
    })
    def test_ollama_models_mapping(self, _http) -> None:
        models = registry.ollama_models("http://127.0.0.1:11434")
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["name"], "qwen3:4b")
        self.assertEqual(models[0]["family"], "qwen3")

    @mock.patch("runtime_registry._http_json", return_value=None)
    def test_ollama_models_empty_on_failure(self, _http) -> None:
        self.assertEqual(registry.ollama_models("http://127.0.0.1:11434"), [])


if __name__ == "__main__":
    unittest.main()
