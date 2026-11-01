#!/usr/bin/env python3
"""Local Windows token monitor for JSON/JSONL usage logs.

The monitor only counts explicit provider usage fields. It never estimates token
counts from characters and never displays raw log lines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

MODEL_KEYS = ("model", "model_name", "modelName")
REQUEST_KEYS = ("request_id", "requestId", "id")
TIMESTAMP_KEYS = ("timestamp", "created", "created_at", "time")
_JSON_START = re.compile(r"\{")


@dataclass(frozen=True)
class UsageRecord:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model: str
    request_id: str
    timestamp: str
    source: str = "provider_usage"

    @property
    def exact(self) -> bool:
        return self.input_tokens is not None or self.output_tokens is not None or self.total_tokens is not None


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    records: int = 0
    unrecognized_lines: int = 0
    by_model: dict[str, "UsageTotals"] = field(default_factory=dict)

    def add(self, record: UsageRecord) -> None:
        input_value = record.input_tokens or 0
        output_value = record.output_tokens or 0
        total_value = record.total_tokens
        if total_value is None:
            total_value = input_value + output_value
        self.input_tokens += input_value
        self.output_tokens += output_value
        self.total_tokens += total_value
        self.records += 1
        model = record.model or "(unknown model)"
        if model not in self.by_model:
            self.by_model[model] = UsageTotals()
        child = self.by_model[model]
        child.input_tokens += input_value
        child.output_tokens += output_value
        child.total_tokens += total_value
        child.records += 1


def _as_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _first_text(data: dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and isinstance(value, (str, int, float)):
            return str(value)
    return default


def _token_value(data: dict[str, Any], names: tuple[str, ...]) -> int | None:
    for name in names:
        value = _as_nonnegative_int(data.get(name))
        if value is not None:
            return value
    return None


def _usage_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        token_values = {
            "input": _token_value(value, ("prompt_tokens", "input_tokens")),
            "output": _token_value(value, ("completion_tokens", "output_tokens")),
            "total": _token_value(value, ("total_tokens",)),
        }
        if any(item is not None for item in token_values.values()):
            yield value
        for child in value.values():
            yield from _usage_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _usage_dicts(child)


def parse_usage_payload(payload: Any, *, source: str = "provider_usage") -> list[UsageRecord]:
    """Extract explicit usage records from a decoded JSON payload.

    We intentionally do not infer tokens from text, byte length, or model name.
    """
    if not isinstance(payload, (dict, list)):
        return []
    root = payload if isinstance(payload, dict) else {}
    records: list[UsageRecord] = []
    seen: set[tuple[int | None, int | None, int | None, str, str]] = set()
    for usage in _usage_dicts(payload):
        values = {
            "input": _token_value(usage, ("prompt_tokens", "input_tokens")),
            "output": _token_value(usage, ("completion_tokens", "output_tokens")),
            "total": _token_value(usage, ("total_tokens",)),
        }
        # Prefer the nearest parent/root metadata when usage is nested in a response.
        model = _first_text(usage, MODEL_KEYS) or _first_text(root, MODEL_KEYS, "unknown")
        request_id = _first_text(usage, REQUEST_KEYS) or _first_text(root, REQUEST_KEYS)
        timestamp = _first_text(usage, TIMESTAMP_KEYS) or _first_text(root, TIMESTAMP_KEYS)
        key = (values["input"], values["output"], values["total"], model, request_id)
        if key in seen:
            continue
        seen.add(key)
        total = values["total"]
        if total is None and values["input"] is not None and values["output"] is not None:
            total = values["input"] + values["output"]
        records.append(
            UsageRecord(
                input_tokens=values["input"],
                output_tokens=values["output"],
                total_tokens=total,
                model=model,
                request_id=request_id,
                timestamp=timestamp,
                source=source,
            )
        )
    return records


def decode_log_line(line: str) -> Any | None:
    """Decode JSONL or a timestamp/prefix followed by a JSON object."""
    text = line.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_START.search(text)
        if not match:
            return None
        try:
            return json.loads(text[match.start() :])
        except json.JSONDecodeError:
            return None


def parse_log_line(line: str) -> list[UsageRecord]:
    payload = decode_log_line(line)
    return parse_usage_payload(payload) if payload is not None else []


class LogTail:
    """Read only appended lines and handle truncation/file rotation."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.identity: tuple[int, int] | None = None

    def read_new_lines(self) -> list[str]:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return []
        identity = (getattr(stat, "st_dev", 0), stat.st_ino)
        if self.identity != identity or stat.st_size < self.offset:
            self.offset = 0
            self.identity = identity
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self.offset)
                lines = handle.readlines()
                self.offset = handle.tell()
        except (FileNotFoundError, PermissionError, OSError):
            return []
        return lines


class UsageMonitor:
    def __init__(self, path: Path) -> None:
        self.tail = LogTail(path)
        self.totals = UsageTotals()
        self._seen_fingerprints: set[str] = set()

    def poll(self) -> int:
        records_added = 0
        for line in self.tail.read_new_lines():
            records = parse_log_line(line)
            if not records:
                if line.strip():
                    self.totals.unrecognized_lines += 1
                continue
            fingerprint_base = line.strip().encode("utf-8", errors="replace")
            for index, record in enumerate(records):
                fingerprint = hashlib.sha256(fingerprint_base + str(index).encode()).hexdigest()
                if fingerprint in self._seen_fingerprints:
                    continue
                self._seen_fingerprints.add(fingerprint)
                self.totals.add(record)
                records_added += 1
        return records_added


def default_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "hermes" / "logs" / "agent.log"
    return Path.home() / ".local" / "share" / "hermes" / "logs" / "agent.log"


def run_self_test() -> int:
    import project_temp

    with project_temp.fixture_root(prefix='monitor-selftest-') as raw:
        path = Path(raw) / "agent.log"
        path.write_text(
            json.dumps({"model": "test-model", "usage": {"prompt_tokens": 11, "completion_tokens": 7}})
            + "\n"
            + json.dumps({"model": "test-model", "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}})
            + "\nnot usage\n",
            encoding="utf-8",
        )
        monitor = UsageMonitor(path)
        if monitor.poll() != 2:
            raise AssertionError("expected two usage records")
        if monitor.totals.input_tokens != 14 or monitor.totals.output_tokens != 9 or monitor.totals.total_tokens != 23:
            raise AssertionError(f"unexpected totals: {monitor.totals}")
        if monitor.totals.unrecognized_lines != 1:
            raise AssertionError("expected one unrecognized line")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"usage": {"total_tokens": 4}}) + "\n")
        if monitor.poll() != 1 or monitor.totals.total_tokens != 27:
            raise AssertionError("append polling failed")
    print("TOKEN_MONITOR_SELF_TEST_PASS")
    return 0


def run_gui(path: Path, poll_ms: int) -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        print(f"Tkinter is unavailable: {exc}", file=sys.stderr)
        return 2

    class App:
        COLORS = {
            "bg": "#0d0f18",
            "surface": "#151925",
            "surface_alt": "#1c2130",
            "border": "#292f43",
            "text": "#f4f4f5",
            "muted": "#9298ad",
            "purple": "#9b7cff",
            "purple_dark": "#6d4ee6",
            "cyan": "#38d9e9",
            "green": "#42d392",
            "orange": "#f7b955",
            "red": "#fb7185",
        }

        def __init__(self, root: Any) -> None:
            self.root = root
            self.monitor = UsageMonitor(path)
            self.running = False
            self.styles = ttk.Style(root)
            try:
                self.styles.theme_use("clam")
            except tk.TclError:
                pass
            self.configure_styles()
            root.title("Hermes Token Monitor")
            root.geometry("980x650")
            root.minsize(820, 560)
            root.configure(bg=self.COLORS["bg"])
            root.columnconfigure(0, weight=1)
            root.rowconfigure(3, weight=1)

            header = tk.Frame(root, bg=self.COLORS["bg"], padx=26, pady=22)
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(1, weight=1)
            mark = tk.Canvas(header, width=42, height=42, bg=self.COLORS["bg"], highlightthickness=0)
            mark.grid(row=0, column=0, rowspan=2, padx=(0, 13))
            mark.create_oval(4, 4, 38, 38, fill=self.COLORS["purple_dark"], outline="")
            mark.create_oval(13, 13, 29, 29, fill=self.COLORS["cyan"], outline="")
            tk.Label(header, text="HERMES", bg=self.COLORS["bg"], fg=self.COLORS["muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="sw")
            tk.Label(header, text="Token Monitor", bg=self.COLORS["bg"], fg=self.COLORS["text"], font=("Segoe UI", 22, "bold")).grid(row=1, column=1, sticky="nw")
            self.badge = tk.Label(header, text="●  IDLE", bg=self.COLORS["surface_alt"], fg=self.COLORS["muted"], padx=12, pady=6, font=("Segoe UI", 9, "bold"))
            self.badge.grid(row=0, column=2, rowspan=2, sticky="e")

            source = tk.Frame(root, bg=self.COLORS["surface"], padx=16, pady=14, highlightbackground=self.COLORS["border"], highlightthickness=1)
            source.grid(row=1, column=0, padx=26, pady=(0, 14), sticky="ew")
            source.columnconfigure(1, weight=1)
            tk.Label(source, text="数据源", bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=(0, 12))
            self.path_var = tk.StringVar(value=str(path))
            self.path_entry = tk.Entry(source, textvariable=self.path_var, bg=self.COLORS["surface_alt"], fg=self.COLORS["text"], insertbackground=self.COLORS["text"], relief="flat", font=("Segoe UI", 10))
            self.path_entry.grid(row=0, column=1, ipady=8, sticky="ew")
            ttk.Button(source, text="选择文件", style="Ghost.TButton", command=self.choose_file).grid(row=0, column=2, padx=(10, 8))
            self.toggle = ttk.Button(source, text="▶  开始监控", style="Accent.TButton", command=self.toggle_monitor)
            self.toggle.grid(row=0, column=3)

            stats = tk.Frame(root, bg=self.COLORS["bg"], padx=26)
            stats.grid(row=2, column=0, sticky="ew")
            self.labels: dict[str, tk.StringVar] = {}
            cards = (("input", "输入 Tokens", self.COLORS["purple"], "PROMPT / INPUT"), ("output", "输出 Tokens", self.COLORS["cyan"], "COMPLETION / OUTPUT"), ("total", "总 Tokens", self.COLORS["green"], "EXACT USAGE"), ("records", "请求次数", self.COLORS["orange"], "REQUESTS"), ("unknown", "未识别行", self.COLORS["red"], "NO USAGE"))
            for column, (key, title, color, caption) in enumerate(cards):
                stats.columnconfigure(column, weight=1)
                card = tk.Frame(stats, bg=self.COLORS["surface"], padx=15, pady=13, highlightbackground=self.COLORS["border"], highlightthickness=1)
                card.grid(row=0, column=column, padx=(0 if column == 0 else 6, 0), sticky="ew")
                tk.Frame(card, bg=color, height=3).pack(fill="x", side="top", pady=(0, 10))
                tk.Label(card, text=caption, bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
                var = tk.StringVar(value="0")
                self.labels[key] = var
                tk.Label(card, textvariable=var, bg=self.COLORS["surface"], fg=color, font=("Segoe UI", 19, "bold")).pack(anchor="w", pady=(3, 0))
                tk.Label(card, text=title, bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w")

            body = tk.Frame(root, bg=self.COLORS["surface"], padx=18, pady=16, highlightbackground=self.COLORS["border"], highlightthickness=1)
            body.grid(row=3, column=0, padx=26, pady=(16, 14), sticky="nsew")
            body.columnconfigure(0, weight=1)
            body.rowconfigure(1, weight=1)
            title_row = tk.Frame(body, bg=self.COLORS["surface"])
            title_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            tk.Label(title_row, text="模型用量排行", bg=self.COLORS["surface"], fg=self.COLORS["text"], font=("Segoe UI", 13, "bold")).pack(side="left")
            tk.Label(title_row, text="仅显示日志中明确的真实 usage", bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(side="right")
            self.table = ttk.Treeview(body, columns=("model", "input", "output", "total", "records"), show="headings", style="Dashboard.Treeview")
            for key, heading, width in (("model", "模型", 300), ("input", "输入", 120), ("output", "输出", 120), ("total", "总计", 120), ("records", "请求数", 100)):
                self.table.heading(key, text=heading)
                self.table.column(key, width=width, anchor="e" if key != "model" else "w")
            self.table.grid(row=1, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.table.yview)
            scrollbar.grid(row=1, column=1, sticky="ns", padx=(8, 0))
            self.table.configure(yscrollcommand=scrollbar.set)
            self.empty = tk.Label(body, text="还没有检测到 usage\n开始监控后，真实 token 数据会出现在这里", bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("Segoe UI", 11), justify="center")
            self.empty.place(relx=0.5, rely=0.58, anchor="center")
            self.status = tk.StringVar(value="就绪 · 不会读取文件，直到点击“开始监控”")
            footer = tk.Frame(root, bg=self.COLORS["bg"], padx=26, pady=12)
            footer.grid(row=4, column=0, sticky="ew")
            tk.Label(footer, text="●", textvariable=None, bg=self.COLORS["bg"], fg=self.COLORS["purple"], font=("Segoe UI", 10)).pack(side="left")
            tk.Label(footer, textvariable=self.status, bg=self.COLORS["bg"], fg=self.COLORS["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        def configure_styles(self) -> None:
            c = self.COLORS
            self.styles.configure("Accent.TButton", background=c["purple_dark"], foreground="white", borderwidth=0, padding=(14, 8), font=("Segoe UI", 9, "bold"))
            self.styles.map("Accent.TButton", background=[("active", c["purple"]), ("disabled", c["border"])])
            self.styles.configure("Ghost.TButton", background=c["surface_alt"], foreground=c["text"], borderwidth=0, padding=(12, 8), font=("Segoe UI", 9))
            self.styles.map("Ghost.TButton", background=[("active", c["border"])])
            self.styles.configure("Dashboard.Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"], borderwidth=0, rowheight=34, font=("Segoe UI", 10))
            self.styles.configure("Dashboard.Treeview.Heading", background=c["surface_alt"], foreground=c["muted"], relief="flat", font=("Segoe UI", 9, "bold"))
            self.styles.map("Dashboard.Treeview", background=[("selected", c["purple_dark"])], foreground=[("selected", "white")])
            self.styles.configure("Vertical.TScrollbar", background=c["surface_alt"], troughcolor=c["surface"], borderwidth=0, arrowsize=12)

        def choose_file(self) -> None:
            selected = filedialog.askopenfilename(title="选择 Hermes 日志", filetypes=(("日志文件", "*.log *.jsonl *.json"), ("所有文件", "*.*")))
            if selected:
                self.path_var.set(selected)

        def toggle_monitor(self) -> None:
            if self.running:
                self.running = False
                self.toggle.configure(text="▶  开始监控")
                self.badge.configure(text="●  PAUSED", fg=self.COLORS["orange"])
                self.status.set("已暂停 · 日志不会继续读取")
                return
            selected = Path(self.path_var.get()).expanduser()
            self.monitor = UsageMonitor(selected)
            self.running = True
            self.toggle.configure(text="Ⅱ  暂停监控")
            self.badge.configure(text="●  LIVE", fg=self.COLORS["green"])
            self.status.set(f"实时监控中 · {selected}")
            self.tick()

        def tick(self) -> None:
            if not self.running:
                return
            self.monitor.poll()
            totals = self.monitor.totals
            self.labels["input"].set(f"{totals.input_tokens:,}")
            self.labels["output"].set(f"{totals.output_tokens:,}")
            self.labels["total"].set(f"{totals.total_tokens:,}")
            self.labels["records"].set(str(totals.records))
            self.labels["unknown"].set(str(totals.unrecognized_lines))
            for item in self.table.get_children():
                self.table.delete(item)
            for model, values in sorted(totals.by_model.items()):
                self.table.insert("", "end", values=(model, values.input_tokens, values.output_tokens, values.total_tokens, values.records))
            if totals.records:
                self.empty.place_forget()
            else:
                self.empty.place(relx=0.5, rely=0.58, anchor="center")
            self.root.after(poll_ms, self.tick)

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地 Hermes 实时 Token Monitor；只统计日志中的真实 usage 字段")
    parser.add_argument("--file", type=Path, default=default_log_path(), help="JSON/JSONL 日志路径；默认指向 Hermes agent.log")
    parser.add_argument("--poll-ms", type=int, default=500, help="轮询间隔，默认 500ms")
    parser.add_argument("--self-test", action="store_true", help="运行无 GUI 自检")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()
    if args.poll_ms < 100:
        parser.error("--poll-ms must be >= 100")
    return run_gui(args.file, args.poll_ms)


if __name__ == "__main__":
    raise SystemExit(main())
