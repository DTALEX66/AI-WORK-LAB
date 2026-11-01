"""Per-verb evidence for the adapter interface: which verbs a client actually answers, read-only.

The capability ladder in `adapter_capability_projection.py` answers what a CLIENT is (declared, installed,
observed). It cannot answer the interface question the register still names open: of the verbs the adapter
contract declares, which ones does this client answer? Without that, "capable" is a claim about a client and
not about an interface.

This probe closes exactly that half, and only the half that can be closed without a side effect:

  * the verb list is DISCOVERED, never assumed — `client-adapter.schema.json#properties.interface.const` is
    the authority, cross-checked against that schema's `operations` enum and
    `capability-matrix.json#interface_contract`; any disagreement raises (see
    `adapter_capability_projection.contract_verb_vocabulary`);
  * a verb is MET only when a read-only call answered it and the row names the command, the exit code and a
    digest of what came back. The only argv shapes this probe will run are version / help / inventory
    (`READ_ONLY_FLAGS`), re-checked by `read_only_guard` at the moment of the call;
  * write verbs and execution verbs are REFUSED BEFORE ATTEMPTED, not faked: `apply` and `rollback` would
    mutate a real user configuration, `invoke` spends a provider call and carries a prompt off this machine,
    `plan` drafts a mutation, `observe` on GitHub is `gh run list` (a network request), and `--version` on
    the GUI clients opens a window instead of answering. A refusal is recorded as NOT_PROBED with its
    concrete reason, because an honest NOT_PROBED is worth more than a fabricated MET;
  * an answer that is only a self-report is not credited either: the vendored adapters' `observe()` answers
    `status=OBSERVED` with `events=[]` and `observed_at=null`, which is a completion claim with nothing
    readable back, so the row says NOT_PROBED with `attempted=true` and names the missing readback;
  * `NOT_SUPPORTED` is always a declaration, never a measurement, so the row names the declaration it rests
    on (the per-client `operations` lists and `policy_projection.*_supported`) at SYNTHETIC level. Where the
    two disagree — a client whose `operations` carries `apply` while `apply_supported` is false — the row
    names the drift instead of picking a winner;
  * an unresolvable entry point is reported as ENTRY_NOT_RESOLVED, the way the entry probe record already
    does for three clients, and the paths that were checked are listed so a reader can see what "unresolved"
    actually covered.

Nothing here writes inside the repository except `.project-local/runs/qoder-agent-verbs/` (`--out` refuses
any other path), and the tracked audit record is only ever extended by hand afterwards.

Usage:
    python adapter_verb_probe.py --client hermes [--out <scratch>.json]
    python adapter_verb_probe.py --all [--out <scratch>.json]
Exit: 0 when every requested client produced rows that pass the projection's own verb validator; 2 when a
client id is unknown, the verb vocabulary disagrees, or a row would over-claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO = SCRIPTS_DIR.parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import adapter_capability_projection as projection  # noqa: E402

SCRATCH_ROOT = ".project-local/runs/qoder-agent-verbs"
TIMEOUT_SECONDS = 20
# The whole of what this probe is willing to run: a version line, a usage page, an inventory listing.
READ_ONLY_FLAGS = ("--version", "-V", "--help", "-h", "help")
NEVER_ATTEMPTED = {
    "apply": "拒绝尝试：apply 会对真实用户配置写入。即使当前实现答 UNSUPPORTED，一个已实现 apply 的版本"
             "会被这次调用真的写下去，所以本探针不给自己这个权限。",
    "rollback": "拒绝尝试：rollback 是对真实用户配置的写回，属于破坏性动作，本探针一律不触发。",
    "invoke": "拒绝尝试：invoke 是一次真实执行——付费 provider 调用、提示词送出本机、并发起网络请求。",
    "plan": "拒绝尝试：plan 的产物是一张针对真实用户配置的待审批变更草稿；本探针不生成任何写入计划。",
    "observe": "拒绝尝试：observe 需要已接通的会话读回或一次出网查询，本探针禁止网络。",
}
# A `policy_projection` flag is a per-verb declaration. Only these four map onto interface verbs; `readback`
# and `drift` name operations OUTSIDE the contract and are reported as vocabulary drift, never adjudicated.
POLICY_FLAGS = {"detect": "detect_supported", "plan": "plan_supported", "apply": "apply_supported",
                "rollback": "rollback_supported"}
POLICY_FLAGS_OUTSIDE_CONTRACT = ("readback_supported", "drift_supported")


def now_iso() -> str:
    """Same +0800 wall-clock form the tracked executor probe record uses."""
    return time.strftime("%Y-%m-%dT%H:%M:%S+0800", time.gmtime(time.time() + 8 * 3600))


def read_only_guard(argv: list[str]) -> str | None:
    """Refuse, at the moment of the call, anything that is not `entry <read-only flag>`."""
    if len(argv) < 2:
        return "EMPTY_COMMAND"
    if argv[-1] not in READ_ONLY_FLAGS:
        return f"NOT_A_READ_ONLY_FLAG {argv[-1]!r} (allowed: {', '.join(READ_ONLY_FLAGS)})"
    # the callable is always the argument right before the flag, both for `[exe, --help]` and for the
    # `["cmd.exe", "/d", "/c", wrapper, --help]` form the repo's codex wrapper needs.
    entry = argv[-2]
    if not Path(str(entry)).is_file():
        return f"ENTRY_NOT_EXECUTABLE {entry!r}"
    return None


def run_read_only(argv: list[str]) -> dict[str, Any]:
    """One short-lived read: no shell, no write capability, and no network by construction of the argv."""
    refusal = read_only_guard(argv)
    if refusal:
        return {"invoked": False, "reason": refusal}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
                              encoding="utf-8", errors="replace", shell=False)
    except FileNotFoundError as exc:
        return {"invoked": False, "reason": f"ENTRY_NOT_EXECUTABLE {exc!r}"}
    except subprocess.TimeoutExpired:
        return {"invoked": True, "exitCode": None, "reason": f"PROBE_TIMEOUT_{TIMEOUT_SECONDS}s"}
    except OSError as exc:
        return {"invoked": False, "reason": f"PROBE_OS_ERROR {exc!r}"}
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return {"invoked": True, "exitCode": proc.returncode,
            "outputSha256": hashlib.sha256(out.encode("utf-8", errors="replace")).hexdigest(),
            "outputLines": len(lines), "firstLine": (lines[0] if lines else "")[:160]}


def failure_text(probe: dict[str, Any]) -> str:
    return str(probe.get("reason") or f"exit={probe.get('exitCode')}")


def _lookup(name: str) -> str | None:
    return shutil.which(name) or shutil.which(f"{name}.exe")


def _desktop_shortcut(fragment: str) -> list[str]:
    desktop = Path.home() / "Desktop"
    return sorted(str(item) for item in desktop.glob(f"*{fragment}*.lnk"))


def resolve_entry(client_id: str) -> dict[str, Any]:
    """Resolve only declared entry points, and record every path that was checked.

    A GUI client's executable may well exist: this proves existence with a file test and still refuses to
    launch it, because `--version` on an Electron/Tauri binary opens a window instead of answering. A
    desktop shortcut is recorded as a shortcut, not as an entry point: reading its target means running
    cscript, and the target is a GUI program this probe does not start.
    """
    home = Path.home()
    checked: list[str] = []
    if client_id == "hermes":
        root = Path(os.environ.get("HERMES_HOME") or (home / "AppData" / "Local" / "hermes"))
        exe = root / "bin" / "hermes.exe"
        checked.append(f"HERMES_HOME|default -> {exe}")
        return {"argv": [str(exe)] if exe.is_file() else None, "kind": "cli", "form": "executable",
                "entryExists": exe.is_file(), "checked": checked}
    if client_id == "codex":
        wrapper = REPO / "packages" / "client-neutral-core" / "bin" / "codex.cmd"
        checked.append(f"repo canonical wrapper -> {wrapper}")
        # cmd.exe is required to run a .cmd; the flag stays its own argument so the space in the repo path
        # can never be reinterpreted by a shell.
        return {"argv": ["cmd.exe", "/d", "/c", str(wrapper)] if wrapper.is_file() else None,
                "kind": "cli-wrapper", "form": "repo-wrapper", "entryExists": wrapper.is_file(),
                "checked": checked}
    if client_id == "github":
        found = _lookup("gh")
        checked.append(f"PATH gh|gh.exe -> {found}")
        return {"argv": [found] if found else None, "kind": "cli", "form": "path-executable",
                "entryExists": bool(found), "checked": checked}
    if client_id == "deepseek-harness":
        exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "DeepSeek Harness" / \
            "DeepSeek Harness.exe"
        checked.append(f"LOCALAPPDATA vendor default -> {exe}")
        return {"argv": None, "kind": "gui", "form": "executable", "entryExists": exe.is_file(),
                "checked": checked}
    declared = {
        # both strings are taken verbatim from config/adapter-registry.json#entries[].provenance
        # .version_readback — declared, not guessed — and only tested for existence; nothing is launched.
        "cc-switch": r"D:\Programs\CC Switch\cc-switch.exe",
        "open-design": str(home / "AppData" / "Local" / "Programs" / "Open Design" / "Open Design.exe"),
    }.get(client_id)
    if declared:
        checked.append(f"registry-declared executable -> {declared}")
        return {"argv": None, "kind": "gui", "form": "executable",
                "entryExists": Path(declared).is_file(), "checked": checked}
    fragment = client_id.replace("-", " ")
    shortcut = _desktop_shortcut(fragment) or _desktop_shortcut(fragment.replace("code", "Code")) \
        or _desktop_shortcut(client_id.replace("-", ""))
    path_hit = _lookup(client_id.replace("-", ""))
    checked.append(f"desktop shortcut *{fragment}*.lnk -> {shortcut or 'no match'}")
    checked.append(f"PATH {client_id.replace('-', '')} -> {path_hit}")
    form = "desktop-shortcut" if shortcut and not path_hit else ("executable" if path_hit else "absent")
    kind = "gui" if client_id == "openhuman" else "none"
    return {"argv": None, "kind": kind, "form": form, "entryExists": bool(shortcut or path_hit),
            "checked": checked}


def _entry_facts(entry: dict[str, Any]) -> tuple[str, str]:
    """(the clause a row may state, the entry-resolution enum) for an entry point that was not run."""
    kind, form, exists = entry["kind"], entry["form"], entry["entryExists"]
    if entry["argv"]:
        return ("入口已解析，本探针也确实以只读方式调用过它（见 checkedPaths）", "RESOLVED")
    if kind == "gui" and exists and form == "executable":
        return ("GUI 客户端：入口文件存在性已实测（见 checkedPaths），但 --version 是启动窗口而不是作答，"
                "本探针不启动 GUI", "ENTRY_PRESENT_LAUNCH_REFUSED")
    if exists and form == "desktop-shortcut":
        return ("桌面快捷方式存在（见 checkedPaths），但其 TargetPath 需要 cscript 解析、目标又是一个 "
                "GUI 程序；本探针既不解析快捷方式目标也不启动 GUI",
                "SHORTCUT_PRESENT_TARGET_NOT_RESOLVED")
    if kind == "none":
        return ("NOT_PROBED_DECLARATIVE_ONLY：该 support_level 没有声明任何 live 入口点，"
                "PATH 与桌面快捷方式实测均无（见 checkedPaths）", "NO_DECLARED_ENTRY")
    if exists:
        return ("入口存在但没有可用的只读作答形式（见 checkedPaths）", "ENTRY_PRESENT_LAUNCH_REFUSED")
    return ("ENTRY_NOT_RESOLVED：本机没有该客户端的可解析入口（见 checkedPaths）", "ENTRY_NOT_RESOLVED")


def load_adapter(client_id: str) -> tuple[Any, list[str]]:
    """The vendored adapter object and the ADAPTERS keys this tree actually has. Importing runs nothing."""
    try:
        import real_adapters
    except Exception as exc:  # noqa: BLE001 — an unimportable adapter is a finding, not a crash
        return None, [f"IMPORT_FAILED {exc!r}"]
    return real_adapters.ADAPTERS.get(client_id), sorted(real_adapters.ADAPTERS)


def _row(verb: str, state: str, *, evidence_level: str, reason: str | None = None,
         source: str | None = None, attempted: bool, basis: str | None = None,
         command: list[str] | None = None, probe: dict[str, Any] | None = None,
         declared_in: dict[str, bool] | None = None, drift: str | None = None,
         entry_resolution: str | None = None, checked: list[str] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"verb": verb, "state": state, "evidenceLevel": evidence_level,
                           "source": source, "reason": reason, "attempted": attempted,
                           "probedAt": now_iso()}
    if basis:
        row["basis"] = basis
    if command:
        row["command"] = [str(part) for part in command]
    if probe:
        if probe.get("exitCode") is not None:
            row["exitCode"] = probe["exitCode"]
        if probe.get("outputSha256"):
            row["outputDigest"] = probe["outputSha256"]
        if probe.get("outputLines") is not None:
            row["outputLines"] = probe["outputLines"]
        row["detail"] = probe.get("firstLine") or probe.get("reason") or ""
    if declared_in is not None:
        row["declaredIn"] = dict(declared_in)
    if drift:
        row["declaresDrift"] = drift
    if entry_resolution:
        row["entryResolution"] = entry_resolution
    if checked:
        row["checkedPaths"] = checked
    return row


def _refused(verb: str, reason: str, *, adapter_declaration: str | None,
             declared_in: dict[str, bool], entry: dict[str, Any]) -> dict[str, Any]:
    full = reason or NEVER_ATTEMPTED[verb]
    if adapter_declaration:
        full = f"{full}（另记：{adapter_declaration}；那是本仓库实现的声明，不是客户端的拒绝）"
    _clause, resolution = _entry_facts(entry)
    return _row(verb, "NOT_PROBED", evidence_level="NO_EVIDENCE", reason=full, attempted=False,
                basis="探针政策：只读 version/help/inventory 之外一律不触发", declared_in=declared_in,
                entry_resolution=resolution, checked=entry["checked"])


def _declared_absent(verb: str, client_id: str, *, declared_in: dict[str, bool], flag: str | None,
                     flag_value: Any) -> dict[str, Any]:
    source = (f"config/adapter-registry.json#entries[{client_id}].operations + "
              f"config/capability-matrix.json#clients[{client_id}].operations 均不含 {verb}")
    if flag and not flag_value:
        source += f" + config/adapter-registry.json#entries[{client_id}].policy_projection.{flag}=false"
    drift = None
    if flag and flag_value:
        drift = (f"两份 operations 清单都不含 {verb}，但 policy_projection.{flag}={flag_value}："
                 "verb 声明与 policy_projection 声明矛盾。此处按接口的每客户端声明（operations）记"
                 " NOT_SUPPORTED，并把矛盾原样留着，不替 owner 选真值")
    return _row(verb, "NOT_SUPPORTED", evidence_level="SYNTHETIC", source=source,
                reason="该动词不在该客户端的任何声明动词集合里"
                       + ("，且 policy_projection 同步否证" if flag and not flag_value else "")
                       + "：这是声明层面的缺失，本机没有测量成分。",
                attempted=False, basis="声明否证", declared_in=declared_in, drift=drift)


def probe_client(client_id: str, *, registry_entry: dict[str, Any], matrix_entry: dict[str, Any] | None,
                 verbs: tuple[str, ...]) -> dict[str, Any]:
    """One client, one row per contract verb, each adjudicated from a named source or a named refusal."""
    adapter, adapter_keys = load_adapter(client_id)
    entry = resolve_entry(client_id)
    registry_ops = [str(op) for op in registry_entry.get("operations") or []]
    matrix_ops = [str(op) for op in (matrix_entry or {}).get("operations") or []]
    policy = registry_entry.get("policy_projection") or {}
    self_report = adapter.capabilities() if adapter is not None else None
    unsupported = [str(op) for op in ((self_report or {}).get("unsupported_operations") or [])]
    adapter_declaration = None
    if unsupported:
        adapter_declaration = (f"real_adapters.py::{type(adapter).__name__}.capabilities() 自报 "
                               f"unsupported_operations={unsupported}")

    declared_runtime = (matrix_entry or {}).get("runtime_adapter")
    adapter_drift = None
    if declared_runtime and adapter is None:
        adapter_drift = (f"config/capability-matrix.json 声明 runtime_adapter={declared_runtime}，"
                         f"但 real_adapters.ADAPTERS 实测键为 {adapter_keys}：该 adapter 在本树不可调用")

    rows: list[dict[str, Any]] = []
    for verb in verbs:
        declared = {"adapter-registry": verb in registry_ops, "capability-matrix": verb in matrix_ops}
        any_declared = any(declared.values())
        flag = POLICY_FLAGS.get(verb)
        flag_value = policy.get(flag) if flag else None

        # 1. a verb no per-client declaration grants
        if not any_declared:
            rows.append(_declared_absent(verb, client_id, declared_in=declared, flag=flag,
                                         flag_value=flag_value))
            continue

        # 2. a verb the more specific declaration denies (drift named, not resolved)
        if flag_value is False:
            drift = None
            if any_declared:
                drift = (f"operations 声明含 {verb}，但 policy_projection.{flag}=false：两份在册声明矛盾，"
                         "此处按更具体的那条记 NOT_SUPPORTED 并保留矛盾，不替 owner 选真值")
            rows.append(_row(
                verb, "NOT_SUPPORTED", evidence_level="SYNTHETIC",
                source=f"config/adapter-registry.json#entries[{client_id}].policy_projection.{flag}=false",
                reason="本仓库为该客户端登记的 policy_projection 明确声明此动词不支持；没有测量成分。",
                attempted=False, basis="声明否证", declared_in=declared, drift=drift))
            continue

        # 3. declared and not denied — can a read-only call answer it?
        if verb in ("apply", "rollback", "invoke", "plan"):
            rows.append(_refused(verb, NEVER_ATTEMPTED[verb], adapter_declaration=adapter_declaration,
                                 declared_in=declared, entry=entry))
            continue

        if verb == "observe":
            if client_id == "github":
                row = _refused(verb, "拒绝尝试：GitHubAdapter.observe() 的源码实测执行 "
                                     "`gh run list --limit 3`，即一次出网请求；本探针禁止网络。",
                               adapter_declaration=None, declared_in=declared, entry=entry)
                row["ref"] = "packages/client-neutral-core/scripts/real_adapters.py:171-179"
                rows.append(row)
            elif adapter is None:
                reason = ("observe 未被建立：本探针要记这个动词，需要一次已接通的会话读回或一次只读查询，"
                          "而网络被禁止；本树也没有该客户端可调用的 vendored adapter"
                          + (f"（{adapter_drift}）" if adapter_drift else "") + "。")
                rows.append(_refused(verb, reason, adapter_declaration=None,
                                     declared_in=declared, entry=entry))
            else:
                observed = adapter.observe({})
                events = observed.get("events") or []
                digest = hashlib.sha256(json.dumps(observed, sort_keys=True).encode("utf-8")).hexdigest()
                if events and observed.get("observed_at"):
                    rows.append(_row(
                        verb, "MET", evidence_level="INTEGRATED",
                        source=f"real_adapters.py::{type(adapter).__name__}.observe() -> "
                               f"{len(events)} events observed_at={observed.get('observed_at')}",
                        reason="进程内只读调用返回了带时间戳的事件读回。", attempted=True,
                        basis=f"source={observed.get('source')}",
                        probe={"exitCode": 0, "outputSha256": digest, "outputLines": len(events)}))
                else:
                    rows.append(_row(
                        verb, "NOT_PROBED", evidence_level="NO_EVIDENCE",
                        reason="已调用进程内 adapter.observe({}) ：返回 status=OBSERVED 但 events=[] 且 "
                               "observed_at=null —— 这是自报完成，没有任何可读回的观测，按「自报 ≠ PASS」"
                               "不记 MET。",
                        attempted=True,
                        basis=f"observe() 实测返回 {json.dumps(observed, ensure_ascii=False)}；"
                              f"digest={digest[:16]}",
                        declared_in=declared))
            continue

        if verb == "detect":
            if not entry["argv"]:
                clause, resolution = _entry_facts(entry)
                rows.append(_row(verb, "NOT_PROBED", evidence_level="NO_EVIDENCE",
                                 reason=f"{clause}，因此 detect 记 NOT_PROBED 而非 MET。",
                                 attempted=False, declared_in=declared, entry_resolution=resolution,
                                 checked=entry["checked"]))
                continue
            argv = entry["argv"] + ["--version"]
            probe = run_read_only(argv)
            if probe.get("invoked") and probe.get("exitCode") == 0:
                rows.append(_row(verb, "MET", evidence_level="INTEGRATED",
                                 source=f"read-only version readback: {' '.join(argv)}",
                                 reason="只读版本读回成功返回：detect 动词的一次真实作答，不含任何写入。",
                                 attempted=True, basis=str(probe.get("firstLine")), command=argv,
                                 probe=probe, declared_in=declared, entry_resolution="RESOLVED"))
            else:
                rows.append(_row(verb, "NOT_PROBED", evidence_level="NO_EVIDENCE",
                                 reason=f"入口已解析，但只读命令未给出可用作答：{failure_text(probe)}",
                                 attempted=True, command=argv, probe=probe, declared_in=declared,
                                 entry_resolution="PROBE_FAILED"))
            continue

        # capabilities: the client's own read-only inventory first; the vendored adapter's self-report is
        # never credited as the client answering.
        probe: dict[str, Any] | None = None
        argv: list[str] | None = None
        if entry["argv"]:
            argv = entry["argv"] + ["--help"]
            probe = run_read_only(argv)
            if probe.get("invoked") and probe.get("exitCode") == 0 and probe.get("outputLines"):
                rows.append(_row(
                    verb, "MET", evidence_level="INTEGRATED",
                    source=f"read-only inventory readback: {' '.join(argv)}",
                    reason="客户端以只读 usage/清单形式作答。这是人类可读的命令清单，不是机器可读的能力合同，"
                           "卡片不得据此推断其它动词成立。",
                    attempted=True,
                    basis=f"{probe.get('outputLines')} 行清单；首行 {probe.get('firstLine')}",
                    command=argv, probe=probe, declared_in=declared, entry_resolution="RESOLVED"))
                continue
            clause = f"只读清单调用未给出可用作答：{failure_text(probe)}"
            resolution = "PROBE_FAILED"
        else:
            clause, resolution = _entry_facts(entry)
        if self_report is not None:
            rows.append(_row(
                verb, "NOT_PROBED", evidence_level="NO_EVIDENCE",
                reason=f"客户端侧未作答（{clause}）；本仓库 adapter.capabilities() 自报 "
                       f"operations={self_report.get('operations')} —— 自报清单不是客户端的作答，不记 MET。",
                attempted=True, basis="real_adapters.capabilities() 自报", declared_in=declared,
                entry_resolution=resolution))
            continue
        rows.append(_row(
            verb, "NOT_PROBED", evidence_level="NO_EVIDENCE",
            reason=f"没有可作答的只读入口：{clause}；本树也没有该客户端的 vendored adapter"
                   + (f"（{adapter_drift}）" if adapter_drift else "") + "。",
            attempted=False, declared_in=declared, entry_resolution=resolution))

    errors = projection.validate_verb_evidence(rows, verbs=verbs)
    if errors:
        raise ValueError(f"{client_id}: probe produced rows its own validator refuses: {errors}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {"client": client_id, "displayName": registry_entry.get("display_name") or client_id,
            "adapterVendored": adapter is not None, "adapterDeclared": declared_runtime,
            "adapterDrift": adapter_drift, "entryKind": entry["kind"], "entryExists": entry["entryExists"],
            "checkedPaths": entry["checked"], "adapterSelfReport": adapter_declaration,
            "stateCounts": counts, "verbs": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", help="one declared adapter id")
    parser.add_argument("--all", action="store_true", help="every entry in the adapter registry")
    parser.add_argument("--out", default=None, help="scratch path for the produced block")
    args = parser.parse_args()

    try:
        verbs = projection.contract_verb_vocabulary(REPO)
    except (ValueError, OSError) as exc:
        print(f"ADAPTER_VERB_PROBE_NOT_RUN VERB_VOCABULARY {exc}", file=sys.stderr)
        return 2

    registry, _conformance, matrix = projection.load_inputs(REPO)
    entries = {str(item.get("id")): item for item in registry.get("entries") or []}
    if args.client:
        if args.client not in entries:
            print(f"UNKNOWN_CLIENT {args.client!r}; declared: {', '.join(entries)}", file=sys.stderr)
            return 2
        targets = [args.client]
    elif args.all:
        targets = list(entries)
    else:
        print("either --client or --all is required", file=sys.stderr)
        return 2

    results = []
    for client_id in targets:
        matrix_entry = next((item for item in list(matrix.get("clients") or [])
                             + list(matrix.get("manifest_only_clients") or [])
                             if str(item.get("id")) == client_id), None)
        try:
            results.append(probe_client(client_id, registry_entry=entries[client_id],
                                        matrix_entry=matrix_entry, verbs=verbs))
        except Exception as exc:  # noqa: BLE001 — a failed client is a finding, not a silent zero
            print(f"{client_id}: PROBE_ABORTED {exc!r}", file=sys.stderr)
            return 2

    counts: dict[str, int] = {}
    for result in results:
        for state, value in result["stateCounts"].items():
            counts[state] = counts.get(state, 0) + value
    block = {
        "schemaVersion": "work-lab/adapter-verb-probe/v1",
        "at": now_iso(),
        "tool": "packages/client-neutral-core/scripts/adapter_verb_probe.py",
        "readOnly": True,
        "network": False,
        "verbVocabulary": {
            "verbs": list(verbs),
            "source": "packages/contracts/schemas/workflow/client-adapter.schema.json"
                      "#properties.interface.const",
            "crossChecksAgreed": ["schema.operations.enum", "capability-matrix#interface_contract"],
            "declaredPerClientFrom": ["config/adapter-registry.json#entries[].operations",
                                      "config/capability-matrix.json#clients[].operations",
                                      "config/adapter-registry.json#entries[].policy_projection"],
            "contractVerbsWithNoPolicyFlag": ["capabilities", "invoke", "observe"],
            "policyFlagsNamingVerbsOutsideTheContract": list(POLICY_FLAGS_OUTSIDE_CONTRACT),
        },
        "policy": {
            "attempted": "只读 version/help/inventory 子进程调用，以及进程内纯计算的 capabilities()/observe()",
            "neverAttempted": ["apply", "invoke", "plan", "rollback"],
            "neverAttemptedWhere": "这些动词在任何客户端、任何配置下都不被本探针触发",
            "refusedPerClient": {"observe": "GitHubAdapter.observe() 出网；无 vendored adapter 的客户端无只读"
                                            "会话读回源——两者都记 NOT_PROBED 并写明拒绝理由"},
            "neverAttemptedReason": "写入真实用户配置、付费 provider 调用、把提示词送出本机、网络请求、"
                                    "启动 GUI 窗口",
            "timeoutSeconds": TIMEOUT_SECONDS,
            "allowedFlags": list(READ_ONLY_FLAGS),
        },
        "counts": {"clients": len(results), **counts},
        "results": results,
        "note": ("MET means this probe ran a read-only call that the row names and the client answered it. "
                 "NOT_SUPPORTED is a named declaration, never a measurement. NOT_PROBED is either a refusal "
                 "this probe holds itself to or an answer that carries too little to be credited — `reason` "
                 "says which and `attempted` says whether a call was made. No verb row climbs the "
                 "seven-layer ladder: it can make a card honest, it cannot make a client MET above "
                 "Installed."),
    }

    print("verbs=" + ",".join(verbs))
    for result in results:
        print(f"{result['client']:18} " + " ".join(
            f"{row['verb']}={row['state']}" for row in result["verbs"]))
    print("ADAPTER_VERB_PROBE_DONE " + json.dumps(block["counts"], ensure_ascii=False))

    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = REPO / out
        if not str(out).startswith(str(REPO / SCRATCH_ROOT)):
            print(f"REFUSED_WRITE_OUTSIDE_SCRATCH {out}", file=sys.stderr)
            return 2
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")
        print("block -> " + out.relative_to(REPO).as_posix())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
