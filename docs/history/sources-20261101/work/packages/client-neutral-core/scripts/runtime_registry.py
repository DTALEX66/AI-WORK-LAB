"""Local model runtime registry and per-runtime adapters (WL3-330 / MR-06).

Discovery, health, capability, and usage mapping for local model runtimes —
Ollama, llama.cpp, faster-whisper, ComfyUI endpoint, DeepSeek provider, and
Codex executor. Each adapter implements only the applicable slice of
discovery / health / capabilities / invoke-plan / usage mapping.

Contract rules (taskpack §10 / MR-06 acceptance):

- An uninstalled runtime is reported ABSENT and never triggers installation.
- A non-loopback endpoint is rejected fail-closed.
- Ports/paths come from discovery or machine overlay; never hard-coded
  defaults that bypass discovery.
- Unknown runtime version is UNKNOWN (not invented).
- ComfyUI adapter is observe/reference-only by default.
- Codex adapter never requires an OpenAI API key.
- Never reads credentials, never scans other drives, never starts a runtime.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "workflow/runtime-registry/v1"
EVIDENCE_UNVERIFIED = "UNVERIFIED"
EVIDENCE_OBSERVED = "OBSERVED"

# Fail-closed: only loopback is acceptable for local runtimes.
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _probe_executable(names: list[str]) -> tuple[str | None, str | None]:
    """Find an executable by name on PATH. Returns (path, version) or (None, None)."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path, None
    return None, None


def _probe_version(cmd: list[str], timeout: int = 8) -> str | None:
    """Run a version probe; any failure yields UNKNOWN (None), never a guess."""
    try:
        result = subprocess.run(
            cmd, text=True, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode != 0:
            return None
        text = (result.stdout or result.stderr or "").strip()
        return text.splitlines()[0] if text else None
    except (OSError, subprocess.SubprocessError):
        return None


def _http_json(url: str, timeout: int = 5) -> dict[str, Any] | None:
    """GET a JSON endpoint; returns None on any failure (health = UNHEALTHY)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None


def _port_listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _validate_loopback(endpoint: str | None) -> tuple[bool, str]:
    """Reject any non-loopback endpoint fail-closed."""
    if not endpoint:
        return True, "no endpoint (ABSENT)"
    scheme, _, rest = endpoint.partition("://")
    if rest.startswith("["):
        host, _, port = rest[1:].partition("]")
        if port.startswith(":"):
            port = port[1:]
    else:
        host, _, port = rest.partition(":")
    host = host.strip("[]").lower()
    if host not in _LOOPBACK_HOSTS:
        return False, f"non-loopback endpoint rejected: {endpoint!r}"
    if port:
        try:
            p = int(port.split("/")[0])
            if not (1 <= p <= 65535):
                return False, f"invalid port: {port}"
        except ValueError:
            return False, f"invalid port: {port}"
    return True, "loopback bound"


def _base_registry(runtime_id: str, kind: str, discovery_method: str,
                   bind_scope: str, resource_class: str,
                   evidence_state: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_id": runtime_id,
        "kind": kind,
        "discovery_method": discovery_method,
        "bind_scope": bind_scope,
        "resource_class": resource_class,
        "evidence_state": evidence_state,
    }


# ---------------------------------------------------------------------------
# Ollama adapter
# ---------------------------------------------------------------------------
OLLAMA_DEFAULT_PORT = 11434


def discover_ollama(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """Discover the Ollama runtime: executable, version, port, health.

    Port comes from machine overlay or live probe; the default constant is only
    a fallback for the health check when nothing is declared.
    """
    overlay = machine_overlay or {}
    declared_port = overlay.get("ollama_port")
    exe, _ = _probe_executable(["ollama"])
    if not exe:
        return _base_registry(
            "ollama", "ollama", "executable-probe", "unknown", "gpu.heavy", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["gguf"],
            "supported_modalities": ["text", "vision", "embedding"],
            "health_probe": None,
            "health_state": "ABSENT",
            "launch_mode": "system-service",
            "auto_start_policy": "never",
            "process_ownership": "user-external",
            "unload_contract": "ollama stop <model>",
            "stop_contract": None,
            "rollback_contract": None,
        }

    version = _probe_version([exe, "--version"])
    port = declared_port if isinstance(declared_port, int) else OLLAMA_DEFAULT_PORT
    ok, detail = _validate_loopback(f"http://127.0.0.1:{port}")
    if not ok:
        return _base_registry(
            "ollama", "ollama", "executable-probe", "unknown", "gpu.heavy", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": exe,
            "detected_version": version,
            "version_state": "DETECTED" if version else "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["gguf"],
            "supported_modalities": ["text", "vision", "embedding"],
            "health_probe": None,
            "health_state": "UNHEALTHY",
            "launch_mode": "system-service",
            "auto_start_policy": "never",
            "process_ownership": "user-external",
            "unload_contract": "ollama stop <model>",
            "stop_contract": None,
            "rollback_contract": None,
            "bind_scope": "unknown",
            "health_detail": detail,
        }

    data = _http_json(f"http://127.0.0.1:{port}/api/version")
    health_state = "HEALTHY" if data and data.get("version") else "UNHEALTHY"
    return _base_registry(
        "ollama", "ollama", "executable-probe", "loopback", "gpu.heavy", EVIDENCE_OBSERVED,
    ) | {
        "executable_identity": exe,
        "detected_version": version,
        "version_state": "DETECTED" if version else "UNKNOWN",
        "endpoint": f"http://127.0.0.1:{port}",
        "supported_formats": ["gguf"],
        "supported_modalities": ["text", "vision", "embedding"],
        "health_probe": f"GET /api/version on 127.0.0.1:{port}",
        "health_state": health_state,
        "launch_mode": "system-service",
        "auto_start_policy": "never",
        "process_ownership": "user-external",
        "unload_contract": "ollama stop <model>",
        "stop_contract": None,
        "rollback_contract": None,
    }


def ollama_models(endpoint: str | None) -> list[dict[str, Any]]:
    """List installed Ollama models (usage mapping input). Empty on any failure."""
    if not endpoint:
        return []
    data = _http_json(endpoint.rstrip("/") + "/api/tags", timeout=8)
    if not data:
        return []
    models: list[dict[str, Any]] = []
    for item in data.get("models", []):
        models.append({
            "name": item.get("name"),
            "size_bytes": item.get("size"),
            "modified_at": item.get("modified_at"),
            "digest": item.get("digest"),
            "family": (item.get("details") or {}).get("family"),
        })
    return models


# ---------------------------------------------------------------------------
# llama.cpp adapter (sidecar-only, never auto-started)
# ---------------------------------------------------------------------------
def discover_llama_cpp(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """llama.cpp is a sidecar runtime; never auto-start, report presence only."""
    overlay = machine_overlay or {}
    exe, _ = _probe_executable(["llama-server", "llama-cli", "llama-cli.exe"])
    declared = overlay.get("llama_cpp_executable")
    if declared and isinstance(declared, str) and Path(declared).is_file():
        exe = declared
    if not exe:
        return _base_registry(
            "llama-cpp", "llama-cpp", "executable-probe", "unknown", "gpu.heavy", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["gguf"],
            "supported_modalities": ["text"],
            "health_probe": None,
            "health_state": "ABSENT",
            "launch_mode": "managed-sidecar",
            "auto_start_policy": "never",
            "process_ownership": "unknown",
            "unload_contract": None,
            "stop_contract": "RuntimeSupervisor terminates only its own PID tree",
            "rollback_contract": None,
        }
    version = _probe_version([exe, "--version"])
    return _base_registry(
        "llama-cpp", "llama-cpp", "executable-probe", "unknown", "gpu.heavy", EVIDENCE_OBSERVED,
    ) | {
        "executable_identity": exe,
        "detected_version": version,
        "version_state": "DETECTED" if version else "UNKNOWN",
        "endpoint": None,
        "supported_formats": ["gguf"],
        "supported_modalities": ["text"],
        "health_probe": None,
        "health_state": "UNKNOWN",
        "launch_mode": "managed-sidecar",
        "auto_start_policy": "never",
        "process_ownership": "unknown",
        "unload_contract": None,
        "stop_contract": "RuntimeSupervisor terminates only its own PID tree",
        "rollback_contract": None,
    }


# ---------------------------------------------------------------------------
# faster-whisper adapter (ASR, cpu.heavy)
# ---------------------------------------------------------------------------
def discover_faster_whisper(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """faster-whisper is a Python package; report presence via import, never install."""
    overlay = machine_overlay or {}
    import_ok = False
    try:
        import faster_whisper  # noqa: F401
        import_ok = True
    except Exception:
        import_ok = False
    if not import_ok:
        return _base_registry(
            "faster-whisper", "faster-whisper", "executable-probe", "unknown", "cpu.heavy", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["ct2", "bin"],
            "supported_modalities": ["audio"],
            "health_probe": None,
            "health_state": "ABSENT",
            "launch_mode": "managed-sidecar",
            "auto_start_policy": "never",
            "process_ownership": "unknown",
            "unload_contract": None,
            "stop_contract": "RuntimeSupervisor terminates only its own PID tree",
            "rollback_contract": None,
        }
    return _base_registry(
        "faster-whisper", "faster-whisper", "executable-probe", "unknown", "cpu.heavy", EVIDENCE_OBSERVED,
    ) | {
        "executable_identity": "faster_whisper (python import)",
        "detected_version": None,
        "version_state": "UNKNOWN",
        "endpoint": None,
        "supported_formats": ["ct2", "bin"],
        "supported_modalities": ["audio"],
        "health_probe": "import faster_whisper",
        "health_state": "HEALTHY",
        "launch_mode": "managed-sidecar",
        "auto_start_policy": "never",
        "process_ownership": "unknown",
        "unload_contract": None,
        "stop_contract": "RuntimeSupervisor terminates only its own PID tree",
        "rollback_contract": None,
    }


# ---------------------------------------------------------------------------
# ComfyUI endpoint adapter (observe/reference-only)
# ---------------------------------------------------------------------------
COMFYUI_DEFAULT_PORT = 8188


def discover_comfyui(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """ComfyUI is observe/reference-only: never start, stop, or reconfigure.

    A declared loopback capability endpoint is health-probed; anything else is
    UNAVAILABLE/ABSENT.
    """
    overlay = machine_overlay or {}
    declared = overlay.get("comfyui_endpoint")
    if not declared:
        return _base_registry(
            "comfyui", "comfyui", "declared-overlay", "unknown", "gpu.heavy", EVIDENCE_UNVERIFIED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["safetensors", "ckpt"],
            "supported_modalities": ["image", "video"],
            "health_probe": None,
            "health_state": "ABSENT",
            "launch_mode": "external",
            "auto_start_policy": "never",
            "process_ownership": "user-external",
            "unload_contract": None,
            "stop_contract": None,
            "rollback_contract": None,
        }
    ok, detail = _validate_loopback(declared)
    if not ok:
        return _base_registry(
            "comfyui", "comfyui", "declared-overlay", "unknown", "gpu.heavy", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": ["safetensors", "ckpt"],
            "supported_modalities": ["image", "video"],
            "health_probe": None,
            "health_state": "UNHEALTHY",
            "launch_mode": "external",
            "auto_start_policy": "never",
            "process_ownership": "user-external",
            "unload_contract": None,
            "stop_contract": None,
            "rollback_contract": None,
            "health_detail": detail,
        }
    data = _http_json(declared.rstrip("/") + "/system_stats", timeout=5)
    health_state = "HEALTHY" if data else "UNHEALTHY"
    return _base_registry(
        "comfyui", "comfyui", "declared-overlay", "loopback", "gpu.heavy", EVIDENCE_OBSERVED,
    ) | {
        "executable_identity": None,
        "detected_version": None,
        "version_state": "UNKNOWN",
        "endpoint": declared,
        "supported_formats": ["safetensors", "ckpt"],
        "supported_modalities": ["image", "video"],
        "health_probe": "GET /system_stats on declared loopback endpoint",
        "health_state": health_state,
        "launch_mode": "external",
        "auto_start_policy": "never",
        "process_ownership": "user-external",
        "unload_contract": None,
        "stop_contract": None,
        "rollback_contract": None,
    }


# ---------------------------------------------------------------------------
# DeepSeek provider adapter (cloud; egress-gated)
# ---------------------------------------------------------------------------
def discover_deepseek(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """DeepSeek is a cloud provider binding; only declared in machine overlay.

    Health is UNKNOWN without a probe — never invented, never calls the paid
    API from discovery.
    """
    overlay = machine_overlay or {}
    declared = bool(overlay.get("deepseek_binding"))
    return _base_registry(
        "deepseek-api", "deepseek-api", "declared-overlay", "unknown", "none", EVIDENCE_UNVERIFIED,
    ) | {
        "executable_identity": None,
        "detected_version": None,
        "version_state": "UNKNOWN",
        "endpoint": None,
        "supported_formats": [],
        "supported_modalities": ["text"],
        "health_probe": None,
        "health_state": "UNKNOWN" if declared else "ABSENT",
        "launch_mode": "external",
        "auto_start_policy": "never",
        "process_ownership": "user-external",
        "unload_contract": None,
        "stop_contract": None,
        "rollback_contract": None,
        "egress": "approval_required" if declared else None,
    }


# ---------------------------------------------------------------------------
# Codex executor adapter (never requires an OpenAI API key)
# ---------------------------------------------------------------------------
def discover_codex(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """Codex is an agent executor; discovery never touches API keys or auth.

    The adapter reports the wrapper executable when present; health is
    UNKNOWN because probing would start the executor.
    """
    overlay = machine_overlay or {}
    exe, _ = _probe_executable(["codex"])
    declared = overlay.get("codex_executable")
    if declared and isinstance(declared, str) and Path(declared).is_file():
        exe = declared
    if not exe:
        return _base_registry(
            "codex-exec", "codex-exec", "executable-probe", "unknown", "none", EVIDENCE_OBSERVED,
        ) | {
            "executable_identity": None,
            "detected_version": None,
            "version_state": "UNKNOWN",
            "endpoint": None,
            "supported_formats": [],
            "supported_modalities": ["text"],
            "health_probe": None,
            "health_state": "ABSENT",
            "launch_mode": "external",
            "auto_start_policy": "never",
            "process_ownership": "user-external",
            "unload_contract": None,
            "stop_contract": None,
            "rollback_contract": None,
        "requires_openai_api_key": False,
        }
    return _base_registry(
        "codex-exec", "codex-exec", "executable-probe", "unknown", "none", EVIDENCE_OBSERVED,
    ) | {
        "executable_identity": exe,
        "detected_version": None,
        "version_state": "UNKNOWN",
        "endpoint": None,
        "supported_formats": [],
        "supported_modalities": ["text"],
        "health_probe": None,
        "health_state": "UNKNOWN",
        "launch_mode": "external",
        "auto_start_policy": "never",
        "process_ownership": "user-external",
        "unload_contract": None,
        "stop_contract": None,
        "rollback_contract": None,
        "requires_openai_api_key": False,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
ADAPTERS: dict[str, Any] = {
    "ollama": discover_ollama,
    "llama-cpp": discover_llama_cpp,
    "faster-whisper": discover_faster_whisper,
    "comfyui": discover_comfyui,
    "deepseek-api": discover_deepseek,
    "codex-exec": discover_codex,
}


def discover_all(machine_overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    """Discover every registered runtime. Pure read-only; no side effects."""
    return {
        "schema_version": SCHEMA_VERSION,
        "discovered_at": None,
        "runtimes": {
            runtime_id: discover(machine_overlay)
            for runtime_id, discover in sorted(ADAPTERS.items())
        },
    }


if __name__ == "__main__":
    print(json.dumps(discover_all(), ensure_ascii=False, indent=2, default=str))
