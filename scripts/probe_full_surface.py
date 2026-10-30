# SPDX-License-Identifier: MIT
"""全量路由面实测：164 个端点逐条真实 HTTP 探测并落盘登记.

为什么要这个脚本
    本仓的路由面由两张**活表**拼成：``backend.v1.V1_ROUTES``（75 条，其中已含
    ``backend.core.work_surfaces.WORK_SURFACE_ROUTES`` 49 条）与
    ``domains.design.design_lab.http_service.ROUTES``（89 条设计兼容面），合计 164。
    以往文档只写"抽样探活"，没有任何登记能回答"这 164 条各自答了什么"。
    本脚本在**一个真实启动的服务**上逐条实测，把结果写成机器可读登记，
    并由 ``tests/unified/test_v15_route_surface.py`` 据此守卫。

它做什么
    1. 按 ``tests/conftest.py`` 的方式在进程内 ``build_server`` 起真实内核
       （只绑 127.0.0.1、端口 0、Bearer 令牌、Host 固定），工作区落在
       ``.project-local/runs/full-surface/<run>``，绝不碰开发库；
    2. 先用公开 API 造出**服务自己产生的真实状态**（设计项目/简报/方向/方案/条目/
       资产/候选，以及 v1 项目→任务→尝试→包→交接→结果链），把读回到的 id 填进路径；
       确实无法产生真实对象的位置用**与正则完全同形**的合成 id；
    3. 逐条记录：来源表、方法、模式、实际探测路径（或无法构造的原因）、HTTP 状态、
       判定、错误码、响应顶层键；带可选分支的路由额外记录变体路径，一条不漏；
    4. 写 ``.project-local/audit/20261031-fullclosure/routes/surface-register.json``
       与 ``migration/route-surface.csv``。

缺陷的判定规则写死在这里，不由临场判断
    5xx、连接中断/读回异常，以及 404 且错误码恰为内核兜底 ``NOT_FOUND``
    （即这条模式没有命中任何已注册路由）。404 带具名码
    （如 ``ASSISTANCE_PLAN_NOT_FOUND``）是领域拒绝，不是缺陷。
    400/415 的信封类码（键集、Content-Length、Content-Type）说明**探测夹具自己**
    不对，归入"探测夹具限制"并单列，不得算作服务端缺陷。

控制台输出保持纯 ASCII：Windows 控制台是 cp936，直接打印 CJK 有崩溃风险；
中文原因只写进文件。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import re
import secrets
import struct
import sys
import threading
import time
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[1]
for _entry in (str(REPO), str(REPO / "domains" / "design")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from backend.app import build_server  # noqa: E402
from backend.core import binding as binding_rules  # noqa: E402
from backend.core.work_surfaces import WORK_SURFACE_ROUTES  # noqa: E402
from backend.v1 import V1_ROUTES  # noqa: E402
from design_lab import assistance_plan as apl  # noqa: E402
from design_lab import http_service as hs  # noqa: E402
from design_lab import knowledge_library as klib  # noqa: E402
from design_lab import plan_feedback as pf  # noqa: E402
from design_lab import prompt_intelligence as pint  # noqa: E402
from design_lab import rights_review, research_review  # noqa: E402
from design_lab import target_profile as tprof  # noqa: E402

TABLE_V1 = "backend.v1.V1_ROUTES"
TABLE_WORK = "backend.core.work_surfaces.WORK_SURFACE_ROUTES (经 backend.v1.V1_ROUTES 装载)"
TABLE_DESIGN = "domains.design.design_lab.http_service.ROUTES"

#: 内核 dispatch 在路由表里找不到任何匹配时抛的兜底码——它才是"路由没注册"的信号。
KERNEL_NOT_FOUND = "NOT_FOUND"
#: 请求信封层的拒绝：出现即说明探测夹具本身不合规格，不是服务缺陷。
ENVELOPE_CODES = {"INVALID_PROJECT_FIELDS", "INVALID_CONTENT_LENGTH", "JSON_REQUIRED",
                  "INVALID_JSON", "TRANSFER_ENCODING_DENIED", "BODY_TOO_LARGE",
                  "INCOMPLETE_BODY"}

SUCCESS = "成功"
REFUSAL = "领域拒绝"
DEFECT = "缺陷"
FIXTURE = "探测夹具限制"

WORK_ACTIONS = {r.action for r in WORK_SURFACE_ROUTES}


def _ascii(text: Any) -> str:
    """控制台是 cp936，直接打印 CJK 有崩溃风险：所有 stdout 走这一层。"""
    return str(text).encode("ascii", "replace").decode("ascii")


def emit(line: str = "") -> None:
    sys.stdout.write(_ascii(line) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def shift_iso(moment: str, *, seconds: int = 5) -> str:
    try:
        base = datetime.fromisoformat(str(moment).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return now_iso()
    return (base + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------
# 正则模式 → 具体路径：只覆盖本仓两张表实际用到的构造的最小型展开器
# --------------------------------------------------------------------------
class PatternParser:
    """把模式源码解析成节点树，并按从左到右登记全部捕获组。

    支持：字面量与转义、``.``、字符类（含 ``^``、范围、转义）、捕获/非捕获组、
    选择 ``|``（取第一支）、量词 ``? * + {m} {m,n} {m,}``。
    可选组（下限为 0）一律不展开：得到**最短可命中路径**，可选分支另由变体路径补测。
    """

    def __init__(self, src: str) -> None:
        self.src = src
        self.i = 0
        self.next_group = 0
        self.groups: list[tuple[int, str]] = []

    def parse(self) -> tuple[list[tuple], list[tuple[int, str]]]:
        branches = [self._sequence()]
        while self._peek() == "|":
            self.i += 1
            branches.append(self._sequence())
        return branches[0], self.groups

    def _sequence(self) -> list[tuple]:
        items: list[tuple] = []
        while self.i < len(self.src) and self._peek() not in ("|", ")"):
            items.append(self._item())
        return items

    def _item(self) -> tuple:
        atom = self._atom()
        low, high = 1, 1
        ch = self._peek()
        if ch == "?":
            self.i += 1
            low, high = 0, 1
        elif ch == "*":
            self.i += 1
            low, high = 0, None
        elif ch == "+":
            self.i += 1
            low, high = 1, None
        elif ch == "{":
            end = self.src.index("}", self.i)
            body = self.src[self.i + 1:end]
            self.i = end + 1
            if "," in body:
                text_low, text_high = body.split(",", 1)
                low = int(text_low or 0)
                high = int(text_high) if text_high.strip() else None
            else:
                low = high = int(body)
            if high is not None and high < low:
                high = low
        return ("q", atom, low, high)

    def _atom(self) -> tuple:
        ch = self._next()
        if ch == "(":
            capturing = True
            if self._peek() == "?":
                self.i += 1
                nxt = self._peek()
                if nxt == ":":
                    self.i += 1
                    capturing = False
                elif nxt == "P":
                    self.i += 2
                    while self._peek() != ">":
                        self.i += 1
                    self.i += 1
                    capturing = True
            start = self.i
            branches = [self._sequence()]
            while self._peek() == "|":
                self.i += 1
                branches.append(self._sequence())
            gsrc = self.src[start:self.i]
            self._expect(")")
            number = None
            if capturing:
                number = self.next_group
                self.next_group += 1
                self.groups.append((number, gsrc))
            return ("grp", branches, gsrc, number)
        if ch == "[":
            return ("cls", self._class())
        if ch == "\\":
            esc = self._next()
            named = {"d": "0123456789", "w": "abcdefghijklmnopqrstuvwxyz0123456789",
                     "s": " ", "n": "\n"}
            return ("cls", named.get(esc, esc))
        if ch == ".":
            return ("cls", "a")
        return ("lit", ch)

    def _class(self) -> str:
        negate = self._peek() == "^"
        if negate:
            self.i += 1
        chars: list[str] = []
        while True:
            ch = self._next()
            if ch == "\\":
                esc = self._next()
                named = {"d": "0123456789", "w": "abcdefghijklmnopqrstuvwxyz"}
                chars.extend(named.get(esc, esc))
                continue
            if ch == "]":
                break
            if self._peek() == "-" and self._look(1) != "]":
                self.i += 1
                high = self._next()
                if high == "\\":
                    high = self._next()
                chars.extend(chr(code) for code in range(ord(ch), ord(high) + 1))
                continue
            chars.append(ch)
        if not negate:
            return "".join(dict.fromkeys(chars))
        blocked = {c for c in chars if ord(c) < 128}
        return "".join(chr(c) for c in range(32, 127)
                       if chr(c) not in blocked and chr(c) not in "\\")

    def _peek(self) -> str:
        return self.src[self.i] if self.i < len(self.src) else ""

    def _look(self, offset: int) -> str:
        j = self.i + offset
        return self.src[j] if j < len(self.src) else ""

    def _next(self) -> str:
        ch = self.src[self.i]
        self.i += 1
        return ch

    def _expect(self, ch: str) -> None:
        if self._next() != ch:
            raise ValueError("UNBALANCED_PATTERN: " + self.src)


def _class_run(chars: str, count: int, seed: str) -> str:
    if count <= 0 or not chars:
        return ""
    if set(chars) == set("0123456789abcdef"):
        stream = ""
        round_index = 0
        while len(stream) < count:
            stream += hashlib.sha256(("%s|%d" % (seed, round_index)).encode("utf-8")).hexdigest()
            round_index += 1
        return stream[:count]
    return chars[0] * count


def render_pattern(src: str, *, provider: Callable[[str, int], str | None] | None = None,
                   seed: str = "surface") -> tuple[str, list[tuple[int, str]]]:
    """产出可被 ``re.fullmatch`` 命中的具体字符串，以及模式里全部捕获组的登记。"""
    parser = PatternParser(src)
    nodes, groups = parser.parse()

    def walk(items: list[tuple], depth_seed: str) -> str:
        buf: list[str] = []
        for index, node in enumerate(items):
            kind = node[0]
            rep_seed = depth_seed + "#" + str(index)
            if kind == "q":
                atom, low = node[1], node[2]
                if low == 0:
                    continue          # 可选分支：主路径走最短形，变体另测
                text = one(atom, rep_seed)
                buf.append(text * (1 if atom[0] == "grp" else low))
            else:
                buf.append(one(node, rep_seed))
        return "".join(buf)

    def one(atom: tuple, rep_seed: str) -> str:
        kind = atom[0]
        if kind == "lit":
            return atom[1]
        if kind == "cls":
            return _class_run(atom[1], 1, rep_seed)
        if kind == "grp":
            _branches, gsrc, gno = atom[1], atom[2], atom[3]
            if gno is not None and provider is not None:
                value = provider(gsrc, gno)
                if value is not None:
                    return value
            inner = PatternParser(gsrc)
            inodes, _ig = inner.parse()
            return walk(inodes, rep_seed + "(" + gsrc + ")")
        raise ValueError("UNSUPPORTED_ATOM")

    return walk(nodes, seed), groups


def conforming(gsrc: str, label: str) -> str:
    """与给定捕获组模式同形的合成值（无真实对象可用时）."""
    value, _groups = render_pattern(gsrc, provider=None, seed=label)
    return value


def hex_id(label: str, length: int) -> str:
    stream = ""
    round_index = 0
    while len(stream) < length:
        stream += hashlib.sha256(("%s|%d" % (label, round_index)).encode("utf-8")).hexdigest()
        round_index += 1
    return stream[:length]


def pattern_source(route) -> str:
    return route.pattern.pattern if isinstance(route.pattern, re.Pattern) else str(route.pattern)


def table_of(route) -> str:
    if route in WORK_SURFACE_ROUTES:
        return TABLE_WORK
    if any(route is candidate for candidate in V1_ROUTES):
        return TABLE_V1
    return TABLE_DESIGN


# --------------------------------------------------------------------------
# 真实 HTTP 客户端（沿用 tests/conftest.py 的固定传输）
# --------------------------------------------------------------------------
class SurfaceClient:
    def __init__(self, port: int, token: str) -> None:
        self.port = port
        self.token = token

    def request(self, method: str, path: str, body: Any = None, *, host: str | None = None,
                auth: bool = True, timeout: float = 20.0) -> tuple[int | None, Any, str]:
        if not str(path).startswith("/"):
            raise ValueError("request path must be relative to the pinned origin")
        headers = {"Host": host if host is not None else "127.0.0.1:" + str(self.port)}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif method in ("POST", "PUT", "PATCH"):
            payload = b""
            headers["Content-Length"] = "0"
        note = ""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            text = response.read().decode("utf-8", "replace")
            try:
                return response.status, json.loads(text), note
            except json.JSONDecodeError:
                return response.status, {"raw": text[:500]}, note
        except (ConnectionError, OSError) as exc:
            note = type(exc).__name__ + ": " + str(exc)[:180]
            return None, {"error": type(exc).__name__}, note
        finally:
            try:
                connection.close()
            except OSError:
                pass


def dig(payload: Any, pointer: str) -> Any:
    current = payload
    for part in pointer.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def first_string(payload: Any, pointers: list[str]) -> str | None:
    for pointer in pointers:
        value = dig(payload, pointer)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
    return None


# --------------------------------------------------------------------------
# 由 JSON Schema 采样，保证嵌套文档贴合合同
# --------------------------------------------------------------------------
def load_schema(module) -> dict:
    path = Path(module.ENTRY_SCHEMA_PATH if hasattr(module, "ENTRY_SCHEMA_PATH")
                else module.PLAN_SCHEMA_PATH)
    return json.loads(path.read_text(encoding="utf-8"))


def sample_from_schema(node: dict, label: str, root: dict | None = None) -> Any:
    if not isinstance(node, dict):
        return None
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/") and root is not None:
        target: Any = root
        for part in ref[2:].split("/"):
            target = target.get(part) if isinstance(target, dict) else None
        if isinstance(target, dict):
            merged = dict(target)
            merged.update({k: v for k, v in node.items() if k != "$ref"})
            return sample_from_schema(merged, label, root)
    if "const" in node:
        return node["const"]
    if "enum" in node:
        for option in node["enum"]:
            if option is not None:
                return option
        return None
    types = node.get("type")
    if isinstance(types, list):
        types = next((t for t in types if t != "null"), "string")
    if types is None:
        types = "object" if "properties" in node else ("array" if "items" in node else "string")
    if types == "object":
        props = node.get("properties") or {}
        keys = list(node.get("required") or []) or list(props)[:1]
        return {key: sample_from_schema(props[key], label + "." + key, root)
                for key in keys if key in props}
    if types == "array":
        items = node.get("items") or {"type": "string"}
        count = max(int(node.get("minItems") or 0), 1)
        return [sample_from_schema(items, "%s[%d]" % (label, index), root)
                for index in range(count)]
    if types == "string":
        pattern = node.get("pattern")
        if isinstance(pattern, str):
            value, _ = render_pattern(re.sub(r"^\^|\$$", "", pattern), provider=None, seed=label)
            return value
        text = "surface probe " + label.replace(".", " ").replace("_", " ")
        low = int(node.get("minLength") or 1)
        high = node.get("maxLength")
        if high is not None and len(text) > int(high):
            text = text[:int(high)]
        while len(text) < low:
            text += " x"
        return text
    if types in ("integer", "number"):
        return int(node.get("minimum") or 1)
    if types == "boolean":
        return False
    return None


#: 观测集：decomposition.Plan.from_ocr 只接受凸四边形 + text/confidence，且必须落在画布内
#: （本脚本生成的位图是 8x8），空表会被服务按"没有发现任何对象"拒绝。
OCR_DETECTIONS = [{"text": "surface", "confidence": 0.9,
                   "polygon": [[0, 0], [8, 0], [8, 8], [0, 8]]}]


def tiny_png_b64(size: int = 8) -> str:
    width, height = size, size
    raw = b"".join(b"\x00" + b"\x00\x80\xff" * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


# --------------------------------------------------------------------------
# 写路由的请求体（键集与 http_service 里 body(fields=...) 完全一致）
# --------------------------------------------------------------------------
ENTRY_SCHEMA = load_schema(klib)
PLAN_SCHEMA = load_schema(apl)
ENTRY_PROPS = ENTRY_SCHEMA.get("properties") or {}
PLAN_PROPS = PLAN_SCHEMA.get("properties") or {}
RIGHTS_FIELDS = sorted(rights_review.write_fields())
RESEARCH_FIELDS = sorted(research_review.write_fields())
TOKEN_FIELDS = sorted(hs.TOKEN_WRITE_FIELDS)
KNOWLEDGE_FIELDS = {"entry_type", "title", "summary", "domain_tags", "task_tags", "target_tools",
                    "body", "applicability", "limits", "source", "related_capability_ids",
                    "recommended", "created_by", "supersedes"}
KNOWLEDGE_IMPORT_FIELDS = (KNOWLEDGE_FIELDS - {"created_by"}) | {"imported_by"}
KNOWLEDGE_REVISE_FIELDS = (KNOWLEDGE_FIELDS - {"supersedes"}) | {"expected_revision"}


def entry_body(fields: set) -> dict:
    """知识条目写体：嵌套文档按 knowledge-entry-v1 合同采样，键集严格等于 fields。"""
    body: dict[str, Any] = {}
    for key in fields:
        node = ENTRY_PROPS.get(key)
        body[key] = sample_from_schema(node, "entry." + key, ENTRY_SCHEMA) if node else "surface"
    if "title" in fields:
        body["title"] = "surface knowledge entry"
    if "summary" in fields:
        body["summary"] = "probe fixture entry for the full surface register"
    if "supersedes" in fields:
        body["supersedes"] = None
    for who in ("created_by", "imported_by"):
        if who in fields:
            body[who] = "surface-probe"
    if "expected_revision" in fields:
        body["expected_revision"] = 1
    return body


PLAN_CREATE_FIELDS = {"objective", "output_type", "neutral_creative", "brand_constraints",
                      "role_constraints", "lens", "sound", "references", "external_steps",
                      "known_gaps", "limits", "created_by"}
PLAN_REVISE_FIELDS = PLAN_CREATE_FIELDS | {"expected_revision"}


def plan_body(fields: set, *, revision: int = 1) -> dict:
    """方案写体：嵌套文档按 assistance-plan-v1 合同采样；references 用空表避免伪引用。"""
    body: dict[str, Any] = {}
    for key in fields:
        node = PLAN_PROPS.get(key)
        body[key] = sample_from_schema(node, "plan." + key, PLAN_SCHEMA) if node else "surface"
    if "objective" in fields:
        body["objective"] = "surface probe plan objective"
    if "created_by" in fields:
        body["created_by"] = "surface-probe"
    if "references" in fields:
        body["references"] = []
    if "expected_revision" in fields:
        body["expected_revision"] = revision
    return body

RIGHTS_BODY = {"schemaVersion": "design-lab/rights-decision/v1",
               "decision_id": "surface-rights-1", "decision": rights_review.APPROVED,
               "decided_by": "surface-probe", "decided_at": None,
               "license_ref": "surface-license", "territory": "worldwide",
               "use_scope": "internal", "note": "surface probe fixture"}
RESEARCH_BODY = {"finding_id": "surface-finding-1", "claim": "surface probe claim",
                 "confidence": "MEDIUM", "sourceRefs": ["surface-ref"],
                 "notDesignRule": True}


#: DTCG 形态的令牌文档样例（design_layer 的拒绝信息里点名的就是 ``$value`` 口径）。
SAMPLE_TOKEN_DOCUMENT = {"color": {"brand": {"$value": "#123456", "$type": "color"}}}


#: 最小**合同合法**的 RIR：schemaVersion + canvas + 1 个 text 层。
#: adobe_lowering.validate_objects 要求 layers 数在 1..100，空表会在建岗阶段被拒；
#: textPayload 由同一份 schema 采样，避免把字段名写死在这里。
RIR_SCHEMA_PATH = (REPO / "domains" / "design" / "design_lab" / "resources" / "repo"
                  / "design-lab" / "schemas" / "reconstruction"
                  / "reconstruction-ir.schema.json")
RIR_SCHEMA = json.loads(RIR_SCHEMA_PATH.read_text(encoding="utf-8"))


#: 原生 text 层的 id：text_styles 必须**逐一**绑定到它，少一个或多个都被
#: adobe_lowering 以 "unused text style binding" 拒掉。
NATIVE_TEXT_LAYER_ID = "layer-surface-1"
NATIVE_TEXT_STYLES = {NATIVE_TEXT_LAYER_ID: {"font": "surface-font", "size": 12,
                                             "color": "#123456"}}


def _sample_rir() -> dict:
    node = {"id": NATIVE_TEXT_LAYER_ID, "type": "text", "name": "surface layer",
            "opacity": 1.0, "bounds": {"x": 0, "y": 0, "width": 8, "height": 8},
            "inferred": False, "zOrder": 0, "visible": True, "locked": False,
            "blendMode": "normal"}
    text = sample_from_schema(RIR_SCHEMA["$defs"]["textPayload"], "text", RIR_SCHEMA)
    # lower() 只接受 disposition=live 的文本（outlined/hybrid 要另走显式回退，不是本登记的事）
    text["disposition"] = "live"
    node["text"] = text
    return {"schemaVersion": RIR_SCHEMA["properties"]["schemaVersion"]["const"],
            "canvas": {"width": 8, "height": 8, "colorSpace": "srgb"}, "layers": [node]}


SAMPLE_RIR = _sample_rir()




def key(label: str, salt: str = "") -> str:
    """幂等键：image_assets/native_submissions 只接受 ``[A-Za-z0-9_-]{1,64}``，
    所以键里不能有冒号、点或空格——本脚本原来用 ISO 时间戳当键，属于夹具自己不合格。"""
    return (label + "-" + hex_id(salt or label, 12)).replace(":", "-")[:64]


def build_body(action: str, state: dict) -> Any:
    """按路由动作给出请求体；状态类 id 一律读当前 state（探测过程中会被回填）。"""
    stamp = now_iso()
    project = state.get("design_project", "")
    brief = state.get("brief", "")
    direction = state.get("direction", "")
    plan = state.get("plan", "")
    profile = state.get("profile", "")
    entry = state.get("kentry", "")
    asset = state.get("asset", "")
    candidate = state.get("candidate", "surface-candidate-1")
    if action == "_v1_create_project":
        return {"name": "surface-v1-project", "source": "design"}
    if action == "_v1_create_task":
        refs = []
        if project and plan:
            refs = [{"kind": "design_plan_ref", "design_project_id": project, "plan_id": plan}]
        return {"project_id": state.get("v1_project", hex_id("surface-project", 32)),
                "kind": "design", "title": "surface probe task",
                "input_refs": refs,
                "acceptance": {"delivery": "surface", "revision_policy": "LATEST_AT_PACK"},
                "professional_required": False}
    if action == "_v1_create_attempt":
        return {"idempotency_key": key("surface-attempt", stamp)}
    if action == "_v1_build_pack":
        return {}
    if action == "_v1_approve":
        return {"authorization_ref": "g-surface", "expected_version": 1}
    if action == "_v1_declare_handoff":
        return {"claim": "copiedByUser",
                "target_version": state.get("handoff_target", "plan-r1")}
    if action == "_v1_import_result":
        return {"result": design_result_document(state, stamp), "data_origin": "live"}
    if action == "_v1_verify_result":
        return {"axis": "technical"}
    if action == "_work_control_execute":
        return {}
    if action in ("_work_observer_write_refused", "_work_control_write_refused"):
        return {}
    if action == "_create_project":
        return {"name": "surface-compat-project"}
    if action in ("_create_brief", "_revise_brief_scoped", "_revise_brief_by_id"):
        # constraints 是**文本**字段（design_layer._text），goals 才是字符串表；
        # reference_asset_ids 里每个 id 必须是本项目真实资产，空表最稳。
        return {"title": "surface brief", "goals": ["surface goal"],
                "constraints": "surface constraint",
                "reference_asset_ids": ([asset] if asset else []),
                "idempotency_key": key("surface-brief", stamp)}
    if action == "_create_direction":
        # style_notes 是表，color_mood / typography_mood 是文本
        return {"brief_id": brief, "title": "surface direction",
                "style_notes": ["surface style"], "color_mood": "surface color",
                "typography_mood": "surface type", "idempotency_key": key("surface-dir", stamp)}
    if action in ("_revise_direction_scoped", "_revise_direction_by_id"):
        return {"title": "surface direction revised", "style_notes": ["surface style"],
                "color_mood": "surface color", "typography_mood": "surface type",
                "idempotency_key": key("surface-dir-rev", stamp)}
    if action == "_choose_direction":
        return {"actor": "surface probe", "actor_kind": "human",
                "idempotency_key": key("surface-choose", stamp)}
    if action == "_bind_design_system":
        return {"design_system_name": state.get("design_system", "surface-system"),
                "idempotency_key": key("surface-bind", stamp)}
    if action == "_write_tokens":
        return {"actor": "surface probe", "actor_kind": "human",
                "document": SAMPLE_TOKEN_DOCUMENT, "expected_version": 0,
                "idempotency_key": key("surface-tokens", stamp)}
    if action == "_create_target_profile":
        return {"software": "surface-software", "agent": "surface-agent",
                "model": "surface-model", "provider": "surface-provider", "version": "1",
                "entry": tprof.ENTRY_KINDS[0], "task_mode": "surface-mode",
                "actor": "surface probe", "source_ref": "surface-ref", "fields": {}}
    if action == "_validate_target_profile":
        return {"dimensions": {}}
    if action == "_create_assistance_plan":
        return plan_body(PLAN_CREATE_FIELDS)
    if action == "_revise_assistance_plan":
        return plan_body(PLAN_REVISE_FIELDS,
                         revision=int(state.get("plan_revision_n", "1")))
    if action == "_choose_assistance_plan":
        return {"actor": "surface probe", "actor_kind": "human",
                "revision": int(state.get("plan_revision_n", "1"))}
    if action == "_record_plan_feedback":
        return {"outcome": pf.OUTCOMES[0], "target_key": "surface-key",
                "target_model": "surface-model",
                "dimensions": {"clarity": pf.DIMENSION_VERDICTS[0]},
                "issue_timecodes": [], "actor": "surface probe", "note": "surface note",
                "source_ref": "surface-ref", "revision": int(state.get("plan_revision_n", "1"))}
    if action == "_create_knowledge_entry":
        return entry_body(KNOWLEDGE_FIELDS)
    if action == "_import_knowledge_entry":
        return entry_body(KNOWLEDGE_IMPORT_FIELDS)
    if action == "_revise_knowledge_entry":
        return entry_body(KNOWLEDGE_REVISE_FIELDS)
    if action == "_record_knowledge_judgement":
        return {"kind": klib.JUDGEMENT_KINDS[0], "revision": 1, "value": "RECOMMENDED",
                "replaced_by": None, "reason": "surface probe judgement",
                "recorded_by": "surface-probe", "recorded_by_kind": "human"}
    if action == "_rebuild_knowledge_index":
        return {}
    if action == "_record_rights":
        body = dict(RIGHTS_BODY)
        body["decided_at"] = stamp
        return body
    if action == "_record_research":
        return dict(RESEARCH_BODY)
    if action == "_create_knowledge_candidate":
        # assurance/knowledge_feedback.build_candidate 的合同：来源要有可复核摘要、
        # rights 要写门状态与许可、payload 只放方法/教训本体（禁私密字段与绝对路径）。
        return {"candidate_id": key("surface-candidate", stamp),
                "candidate_type": "METHOD",
                "source": {"design_lab_sha": hex_id("surface-candidate-sha", 40),
                           "job_id": "UNUSED", "operation_id": "UNUSED",
                           "evidence_sha256": "sha256:" + hex_id("surface-candidate-ev", 64)},
                "rights": {"rights_gate_state": "CHECKED", "license_id": "surface-license",
                           "contains_client_asset": False,
                           "contains_third_party_asset": False,
                           "redaction_note": "不含客户素材；本夹具只写合成句子"},
                "payload": {"title": "surface candidate",
                            "statement": "surface probe lesson for the route register",
                            "applies_to": ["brand"]},
                "created_at": stamp,
                "revocation_entrypoint": "/api/projects/{id}/knowledge-candidates"}
    if action == "_review_knowledge_candidate":
        return {"decision": "APPROVED", "reviewer_id": "surface-probe",
                "reviewer_kind": "human", "reviewed_at": stamp, "note": "surface note",
                "reason": "surface reason"}
    if action == "_revoke_knowledge_candidate":
        return {"reason": "surface revoke", "revoked_by": "surface-probe", "revoked_at": stamp}
    if action == "_record_jury_verdict":
        return {"schemaVersion": "design-lab/jury-verdict/v1", "kind": "JURY_VERDICT",
                "jury_record_id": key("surface-jury", stamp), "subject_ref": "surface-subject",
                "artifact_sha256": hex_id("surface-artifact", 64),
                "juror": {"id": "surface-probe", "kind": "human",
                          "display_name": "surface probe"},
                "criteria": [{"id": "clarity", "verdict": "PASS", "note": "surface"}],
                "verdict": "PASS", "decided_at": stamp, "supersedes": None,
                "evidence_refs": []}
    if action == "_record_jury_proposal":
        return {"schemaVersion": "design-lab/jury-proposal/v1", "kind": "JURY_PROPOSAL",
                "proposal_id": key("surface-proposal", stamp), "subject_ref": "surface-subject",
                "artifact_sha256": hex_id("surface-artifact", 64),
                "proposer": {"id": "surface-probe", "kind": "human"},
                "criteria": [{"id": "clarity", "verdict": "PASS"}],
                "suggested_verdict": "PASS", "rationale": "surface rationale",
                "created_at": stamp}
    if action == "_import_asset":
        return {"content_base64": tiny_png_b64(), "idempotency_key": key("surface-asset", stamp)}
    if action == "_derive_asset_analysis":
        return {"module": "ocr-surface", "detections": OCR_DETECTIONS,
                "decomposition_id": "surface-decomposition-" + hex_id("decomp", 32)}
    if action == "_reverse_asset_prompt":
        return {"module": "ocr-surface", "detections": OCR_DETECTIONS,
                "decomposition_id": "surface-reversal-" + hex_id("reversal", 32)}
    if action == "_record_model_selection":
        return {"model_id": "UNQUALIFIED_LOCAL", "declared_unused": True,
                "actor": "surface probe", "actor_kind": "human"}
    if action == "_compose_prompt":
        return {"brief_id": brief, "direction_id": direction,
                "target": pint.visual_families()[0]}
    if action == "_review_prompt_result":
        return {"decision": "ACCEPTED", "reviewer": "surface-probe",
                "reviewer_kind": "human", "reviewed_at": stamp, "note": "surface review"}
    if action == "_submit_native_plan":
        # text_styles 必须是对象，并且逐一绑定到 RIR 里的 text 层
        return {"host": "photoshop", "rir": SAMPLE_RIR,
                "text_styles": dict(NATIVE_TEXT_STYLES),
                "idempotency_key": key("surface-plan", stamp)}
    if action == "_submit_task_patch":
        return {"source_attempt_id": state.get("native_attempt", "surface-attempt"),
                "patch": {"ops": []}, "idempotency_key": key("surface-patch", stamp)}
    if action in ("_start_task_run", "_cancel_task"):
        return {"attempt_id": state.get("native_attempt", "surface-attempt")}
    if action == "_create_bundle":
        return {}
    if action == "_preflight_bundle":
        return None
    return None


def design_result_document(state: dict, stamp: str) -> dict:
    """按服务自己固定的打包事实构造一份设计结果文档；缺事实就用同形占位值。"""
    digest = state.get("pinned_digest") or hex_id("surface-plan-digest", 64)
    produced = shift_iso(state.get("handoff_declared_at") or stamp, seconds=5)
    return {
        "schemaVersion": binding_rules.DESIGN_RESULT_SCHEMA_VERSION,
        "resultId": "surface-result-" + hex_id("result" + stamp, 12),
        "summary": "surface probe result for the full route register",
        "taskId": state.get("task", ""),
        "attemptId": state.get("attempt", ""),
        "projectId": state.get("v1_project", ""),
        "designProjectId": state.get("design_project", ""),
        "planId": state.get("plan", ""),
        "planRevision": int(state.get("pack_plan_revision", "1")),
        "contentSha256": digest,
        "producedAt": produced,
        "targetVersion": state.get("handoff_target", "plan-r1"),
        "evidenceRefs": [],
    }


# --------------------------------------------------------------------------
# 捕获组 → 值：真实 id 优先，其次同形合成 id
# --------------------------------------------------------------------------
V1_TASK_ACTIONS = {"_v1_get_task", "_v1_task_completion", "_v1_create_attempt"}
V1_ATTEMPT_ACTIONS = {"_v1_get_attempt", "_v1_build_pack", "_v1_approve",
                      "_v1_declare_handoff", "_v1_import_result"}
V1_RESULT_ACTIONS = {"_v1_get_result", "_v1_verify_result"}

#: 前缀/形态 → 状态键：模式里的捕获组自带的身份提示。
PREFIX_STATE_KEYS: list[tuple[str, str]] = [
    ("bundle-native-", "bundle"),
    ("v-", "bundle_version"),
    ("brief-", "brief"),
    ("direction-", "direction"),
    ("aplan-", "plan"),
    ("tprof-", "profile"),
    ("kentry-", "kentry"),
    ("img-", "asset"),
    ("prompt|reversal", "prompt_result"),
]

#: 主路径之外再测一遍的可选分支：路由动作 → (基础路径) -> 变体路径列表。
VARIANTS_BY_ACTION: dict[str, Callable[[str, dict], list[str]]] = {
    "_list_or_read_assets": lambda base, st: [
        base + "/" + (st.get("asset") or conforming("img-[0-9a-f]{64}", "asset")) + "/content"],
    "_task_detail_or_events": lambda base, st: [base + "/events"],
    "_get_token_document_or_lineage": lambda base, st: [base + "/lineage"],
    "_list_native_assets": lambda base, st: [
        base + "?after=native-" + hex_id("native-asset-cursor", 64)],
    "_list_tasks": lambda base, st: [
        base + "?after=native-job-" + (st.get("native_job") or hex_id("native-job-cursor", 64))],
    "_list_briefs": lambda base, st: [base + "?after=" + (st.get("brief")
                                                          or conforming("brief-[0-9a-f]{32}", "b"))],
    "_list_directions": lambda base, st: [
        base + "?after=" + (st.get("direction") or conforming("direction-[0-9a-f]{32}", "d"))],
    "_list_target_profiles": lambda base, st: [base + "?offset=0&limit=5"],
    "_list_assistance_plans": lambda base, st: [base + "?offset=0&limit=5"],
    "_preflight_bundle": lambda base, st: [base + "?profile=print"],
    "_record_rights": lambda base, st: [base + "?supersedes=surface-rights-1"],
    "_record_research": lambda base, st: [base + "?supersedes=surface-finding-1"],
    "_create_knowledge_candidate": lambda base, st: [base + "?supersedes=surface-candidate-1"],
    "_export_assistance_plan": lambda base, st: [base + "?format=markdown",
                                                 base + "?format=storyboard_csv"],
}

#: 主路径直接补上的查询：不带它该路由只会回答"缺参数"，测不到实际分支。
PRIMARY_QUERY_BY_ACTION: dict[str, str] = {
    "_export_assistance_plan": "?format=markdown",
}


def make_provider(route, state: dict) -> tuple[Callable[[str, int], str | None], dict]:
    psrc = pattern_source(route)
    report = {"real": [], "dummy": []}

    def provider(gsrc: str, gno: int) -> str | None:
        for prefix, key in PREFIX_STATE_KEYS:
            if gsrc.startswith(prefix) or prefix in gsrc:
                value = state.get(key)
                if value:
                    report["real"].append("g%d:%s=%s" % (gno + 1, key, value))
                    return str(value)
                report["dummy"].append("g%d:%s" % (gno + 1, key))
                return None
        if "job-" in gsrc:
            value = state.get("native_job")
            if value:
                report["real"].append("g%d:native_job" % (gno + 1))
                return str(value)
            report["dummy"].append("g%d:native_job" % (gno + 1))
            return None
        if gsrc == "[a-z]+-[a-z0-9]+":
            value = state.get("plan")
            if value:
                report["real"].append("g%d:plan" % (gno + 1))
                return str(value)
            return None
        if gsrc in ("[0-9]+", "[1-9][0-9]{0,8}"):
            return str(state.get("plan_revision_n", "1"))
        if gsrc.startswith("[A-Za-z0-9_.:-]"):
            return str(state.get("candidate_id") or "surface-candidate-1")
        if gsrc.startswith("[a-z0-9][a-z0-9-]"):
            return str(state.get("token_name") or "surface-tokens")
        if gsrc.startswith("[0-9A-Za-z_-]"):
            return "surface-receipt"
        if gsrc == "[0-9a-f]{32}":
            if gno == 0 and psrc.startswith("/api/projects/"):
                value = state.get("design_project")
                if value:
                    report["real"].append("g1:design_project")
                    return str(value)
                report["dummy"].append("g1:design_project")
                return None
            for key, actions in (("task", V1_TASK_ACTIONS), ("attempt", V1_ATTEMPT_ACTIONS),
                                 ("result", V1_RESULT_ACTIONS)):
                if route.action in actions:
                    value = state.get(key)
                    if value:
                        report["real"].append("g%d:%s" % (gno + 1, key))
                        return str(value)
                    report["dummy"].append("g%d:%s" % (gno + 1, key))
                    return None
            return None
        return None

    return provider, report


#: 响应里能回填成真实 id 的字段（动作 → 状态键 → 候选指针）。
#: 指针按**服务实际返回的形状**写（record 都嵌在 'brief'/'plan'/'asset' 这一层里），
#: 不是按字段名的想当然。
HARVEST: dict[str, dict[str, list[str]]] = {
    "_create_project": {"design_project": ["project.id"]},
    "_v1_create_project": {"v1_project": ["project_id"]},
    "_v1_create_task": {"task": ["task_id"]},
    "_v1_create_attempt": {"attempt": ["attempt_id"]},
    "_v1_build_pack": {"pack_plan_revision": ["attempt.pack_ref.plan_revision"],
                       "pinned_digest": ["attempt.pack_ref.plan_content_sha256"]},
    "_v1_declare_handoff": {"handoff_target": ["attempt.handoff.target_version"],
                            "handoff_declared_at": ["attempt.handoff.declared_at"]},
    "_v1_import_result": {"result": ["result.result_id"]},
    "_create_brief": {"brief": ["brief.brief_id", "brief_id"]},
    "_revise_brief_scoped": {"brief": ["brief.brief_id", "brief_id"]},
    "_create_direction": {"direction": ["direction.direction_id", "direction_id"]},
    "_create_assistance_plan": {"plan": ["plan.plan_id", "plan_id"],
                                "plan_revision_n": ["revision", "plan.revision"]},
    "_revise_assistance_plan": {"plan_revision_n": ["revision", "plan.revision"]},
    "_create_target_profile": {"profile": ["profile.profile_id", "profile_id"]},
    "_create_knowledge_entry": {"kentry": ["entry.knowledge_entry_id", "knowledge_entry_id"]},
    "_import_asset": {"asset": ["asset.id", "asset_id"]},
    "_compose_prompt": {"prompt_result": ["result_id", "composition_id", "id"]},
    "_reverse_asset_prompt": {"reversal_result": ["result_id", "reversal_id", "id"]},
    "_create_knowledge_candidate": {"candidate_id": ["candidate_id", "candidate.candidate_id"]},
    "_record_rights": {"rights_id": ["decision_id"]},
    "_record_research": {"finding_id": ["finding_id"]},
    "_write_tokens": {"token_name": ["name", "token_name"]},
    "_submit_native_plan": {"native_job": ["task_id", "job_id", "attempt.job_id"],
                            "native_attempt": ["attempt_id", "attempt.attempt_id"]},
    "_create_bundle": {"bundle": ["bundle_id", "bundleId", "id"],
                       "bundle_version": ["version_id", "versionId", "version"]},
}


def harvest(action: str, payload: Any, state: dict) -> list[str]:
    updates: list[str] = []
    for key, pointers in HARVEST.get(action, {}).items():
        if not isinstance(payload, dict):
            continue
        value = first_string(payload, pointers)
        if value:
            state[key] = value
            updates.append(key)
    return updates


# --------------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------------
def extract_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("error", "code", "status", "reason_code"):
        value = payload.get(key)
        if isinstance(value, str) and value and value not in ("ERROR", "OK"):
            return value
    return ""


def envelope_keys(payload: Any) -> list[str]:
    return sorted(payload) if isinstance(payload, dict) else []


def classify(status: Any, payload: Any, note: str) -> tuple[str, bool, str, str]:
    """返回 (判定, 是否缺陷, 错误码, 原因)."""
    code = extract_code(payload)
    if status is None:
        return DEFECT, True, code, ("连接中断或读回异常：%s；服务未给出任何 HTTP 响应"
                                    % (note or "未指明异常"))
    if status >= 500:
        return DEFECT, True, code, ("服务端错误 %s：路由已注册但处理链抛出 5xx，"
                                    "错误码 %s" % (status, code or "无"))
    if 200 <= status < 300:
        return SUCCESS, False, code, "成功 %s：读到 2xx 响应" % status
    if status == 404 and code == KERNEL_NOT_FOUND:
        return DEFECT, True, code, ("路由未注册：404 且错误码是内核兜底 NOT_FOUND，"
                                    "说明该模式没有命中任何已注册路由")
    if code in ENVELOPE_CODES:
        return FIXTURE, False, code, ("探测夹具限制：%s 是请求信封层拒绝（键集/长度/类型），"
                                      "说明本脚本的夹具不合规格，不是服务端缺陷" % code)
    if 400 <= status < 500:
        return REFUSAL, False, code, ("领域拒绝 %s：带具名错误码 %s，由合同或人工门作出"
                                      % (status, code or "无具名码"))
    return DEFECT, True, code, "非预期状态 %s（既非 2xx、非 4xx 具名拒绝、也非 5xx）" % status


# --------------------------------------------------------------------------
# 探测过程
# --------------------------------------------------------------------------
class SurfaceProber:
    def __init__(self, client: SurfaceClient) -> None:
        self.client = client
        self.state: dict[str, str] = {}
        self.seed_log: list[dict[str, Any]] = []
        self.rows: list[dict[str, Any]] = []

    # -- 造状态 -------------------------------------------------------------
    def seed_step(self, name: str, action: str, method: str, path: str, body: Any = None) -> None:
        status, payload, note = self.client.request(method, path, body)
        updates = harvest(action, payload, self.state)
        self.seed_log.append({"step": name, "action": action, "method": method, "path": path,
                              "status": status, "code": extract_code(payload),
                              "captured": updates, "transport_note": note})
        emit("  seed %-22s %-6s %-52s -> %s %s" % (_ascii(name), method, _ascii(path)[:52],
                                                   status, _ascii(extract_code(payload))))

    def seed(self) -> None:
        emit("[seed] 用公开 API 造出服务自己产生的真实状态")
        self.seed_step("design_project", "_create_project", "POST", "/api/projects",
                       build_body("_create_project", self.state))
        scoped = "/api/projects/" + self.state.get("design_project", "")
        self.seed_step("target_profile", "_create_target_profile", "POST", "/api/target-profiles",
                       build_body("_create_target_profile", self.state))
        self.seed_step("knowledge_entry", "_create_knowledge_entry", "POST",
                       "/api/knowledge-entries",
                       build_body("_create_knowledge_entry", self.state))
        self.seed_step("brief", "_create_brief", "POST", scoped + "/briefs",
                       build_body("_create_brief", self.state))
        self.seed_step("direction", "_create_direction", "POST", scoped + "/directions",
                       build_body("_create_direction", self.state))
        self.seed_step("assistance_plan", "_create_assistance_plan", "POST",
                       scoped + "/assistance-plans",
                       build_body("_create_assistance_plan", self.state))
        self.seed_step("asset", "_import_asset", "POST", scoped + "/assets",
                       build_body("_import_asset", self.state))
        self.seed_step("prompt", "_compose_prompt", "POST", scoped + "/prompts",
                       build_body("_compose_prompt", self.state))
        self.seed_step("knowledge_candidate", "_create_knowledge_candidate", "POST",
                       scoped + "/knowledge-candidates",
                       build_body("_create_knowledge_candidate", self.state))
        token_name = self.state.get("token_name", "surface-tokens")
        self.seed_step("tokens", "_write_tokens", "POST",
                       scoped + "/design-system-tokens/" + token_name,
                       build_body("_write_tokens", self.state))
        self.seed_step("native_plan", "_submit_native_plan", "POST", scoped + "/native-plans",
                       build_body("_submit_native_plan", self.state))
        self.seed_step("v1_project", "_v1_create_project", "POST", "/api/v1/projects",
                       build_body("_v1_create_project", self.state))

    # -- 逐路由探测 ---------------------------------------------------------
    def probe_route(self, route, table: str) -> dict[str, Any]:
        psrc = pattern_source(route)
        provider, report = make_provider(route, self.state)
        construction = ""
        path = None
        note = ""
        try:
            if route.exact:
                path = psrc
                construction = "固定路径（exact）"
            else:
                path, groups = render_pattern(psrc, provider=provider,
                                              seed=table + route.method + psrc)
                if PRIMARY_QUERY_BY_ACTION.get(route.action):
                    path += PRIMARY_QUERY_BY_ACTION[route.action]
                if report["real"] and not report["dummy"]:
                    construction = "真实 id（服务自己产生并读回）：" + ", ".join(report["real"])
                elif report["real"]:
                    construction = ("混合：真实 id " + ", ".join(report["real"])
                                    + "；同形合成 id " + ", ".join(report["dummy"]))
                elif report["dummy"]:
                    construction = ("同形合成 id（无真实对象可产生）："
                                    + ", ".join(report["dummy"]))
                else:
                    construction = "同形合成 id（模式无捕获组）"
        except Exception as exc:  # noqa: BLE001 - 构造失败必须登记而不是吞掉
            construction = "无法构造：" + type(exc).__name__ + " " + str(exc)[:160]
            note = construction

        status: Any = None
        payload: Any = None
        transport = ""
        if path is not None:
            body = build_body(route.action, self.state) if route.method != "GET" else None
            status, payload, transport = self.client.request(route.method, path, body)
            captured = harvest(route.action, payload, self.state)
            if captured:
                construction += "；本次响应回填 " + ", ".join(captured)
        verdict, defect, code, reason = classify(status, payload, transport)
        if path is None:
            verdict, defect = FIXTURE, False
        row = {
            "table": table,
            "route_key": "%s|%s|%s" % (table, route.method, psrc),
            "method": route.method,
            "pattern": psrc,
            "handler": route.action,
            "path": path,
            "constructed": path is not None,
            "construction": construction,
            "http_status": status,
            "error_code": code,
            "verdict": verdict,
            "defect": defect,
            "reason": reason,
            "envelope_keys": envelope_keys(payload),
            "transport_note": transport or note,
            "variants": [],
        }
        if path is not None and route.action in VARIANTS_BY_ACTION:
            for variant in VARIANTS_BY_ACTION[route.action](path, self.state):
                v_status, v_payload, v_transport = self.client.request(
                    route.method, variant,
                    build_body(route.action, self.state) if route.method != "GET" else None)
                v_verdict, v_defect, v_code, v_reason = classify(v_status, v_payload, v_transport)
                row["variants"].append({"path": variant, "http_status": v_status,
                                        "error_code": v_code, "verdict": v_verdict,
                                        "defect": v_defect, "reason": v_reason,
                                        "envelope_keys": envelope_keys(v_payload)})
        self.rows.append(row)
        return row

    def run(self, routes: list[tuple]) -> None:
        for route, table in routes:
            row = self.probe_route(route, table)
            emit("  %-6s %-58s -> %s %s [%s]" % (
                row["method"], _ascii(row["path"] if row["path"] else "<未构造>")[:58],
                row["http_status"], _ascii(row["error_code"]), _ascii(row["verdict"])))


def enumerate_routes() -> list[tuple]:
    """从两张活表现数，绝不抄任何文档里的数字。"""
    listed: list[tuple] = []
    v1_keys = {id(route) for route in WORK_SURFACE_ROUTES}
    for route in V1_ROUTES:
        listed.append((route, TABLE_WORK if id(route) in v1_keys else TABLE_V1))
    for route in hs.ROUTES:
        listed.append((route, TABLE_DESIGN))
    return listed


# --------------------------------------------------------------------------
# 落盘
# --------------------------------------------------------------------------
CSV_COLUMNS = ["路由表来源", "方法", "路径模式", "具体探测路径", "构造方式", "HTTP状态",
               "判定", "错误码", "响应顶层键", "缺陷", "可选分支变体", "备注"]


def summary(rows: list[dict]) -> dict:
    by_verdict: dict[str, int] = {}
    by_table: dict[str, int] = {}
    for row in rows:
        by_verdict[row["verdict"]] = by_verdict.get(row["verdict"], 0) + 1
        by_table[row["table"]] = by_table.get(row["table"], 0) + 1
    defects = [{"route_key": r["route_key"], "method": r["method"], "pattern": r["pattern"],
                "path": r["path"], "http_status": r["http_status"], "error_code": r["error_code"],
                "handler": r["handler"], "reason": r["reason"]}
               for r in rows if r["defect"]]
    unconstructed = [{"route_key": r["route_key"], "construction": r["construction"]}
                     for r in rows if not r["constructed"]]
    return {"enumerated": len(rows), "by_verdict": by_verdict, "by_table": by_table,
            "defects": defects, "unconstructed": unconstructed,
            "variant_paths_probed": sum(len(r["variants"]) for r in rows)}


def write_register(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                               sort_keys=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    import csv as _csv
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", encoding="utf-8", newline="")
    try:
        writer = _csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([
                row["table"], row["method"], row["pattern"],
                row["path"] if row["path"] is not None else "未构造",
                row["construction"],
                "" if row["http_status"] is None else row["http_status"],
                row["verdict"], row["error_code"], "|".join(row["envelope_keys"]),
                "是" if row["defect"] else "否",
                " ; ".join("%s->%s/%s" % (v["path"], v["http_status"], v["verdict"])
                           for v in row["variants"]),
                row["reason"],
            ])
    finally:
        handle.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--workspace", default=".project-local/runs/full-surface/run1",
                        help="一次性工作区（相对仓库根），绝不使用开发库")
    parser.add_argument("--register",
                        default=".project-local/audit/20261031-fullclosure/routes/"
                                "surface-register.json")
    parser.add_argument("--csv", default="migration/route-surface.csv")
    parser.add_argument("--skip-seed", action="store_true", help="调试用：不造状态")
    parser.add_argument("--fresh", action="store_true",
                        help="先删除本脚本自己的 runs/full-surface 工作区，保证可从零复现")
    args = parser.parse_args(argv)

    workspace = (REPO / args.workspace).resolve()
    if str(workspace) != str(REPO) and not str(workspace).startswith(str(REPO) + "\\"):
        raise SystemExit("REFUSED: workspace must stay inside the repository")
    if args.fresh:
        allowed_root = str(REPO / ".project-local" / "runs" / "full-surface") + "\\"
        if not str(workspace).startswith(allowed_root):
            raise SystemExit("REFUSED: --fresh only wipes .project-local/runs/full-surface/*")
        if workspace.exists():
            import shutil
            shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("# surface probe scratch workspace\n", encoding="utf-8")
    token = secrets.token_hex(32)
    emit("[boot] workspace=%s" % _ascii(str(workspace)))
    httpd, context = build_server(workspace, token, 0)
    client = SurfaceClient(httpd.server_port, token)
    emit("[boot] listening 127.0.0.1:%d" % httpd.server_port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    prober = SurfaceProber(client)
    try:
        routes = enumerate_routes()
        emit("[enumerate] total=%d (backend.v1=%d, work_surface=%d, design=%d)" % (
            len(routes), sum(1 for _r, t in routes if t == TABLE_V1),
            sum(1 for _r, t in routes if t == TABLE_WORK),
            sum(1 for _r, t in routes if t == TABLE_DESIGN)))
        if len(routes) != 164:
            raise SystemExit("REFUSED: enumerated %d routes, expected 164 from the live tables"
                             % len(routes))
        if not args.skip_seed:
            prober.seed()
        emit("[probe] 逐条实测")
        prober.run(routes)
    finally:
        httpd.shutdown()
        try:
            context["unified"].close()
            context["work"].close()
        except Exception:  # noqa: BLE001 - 关闭失败不影响登记
            pass

    rows = prober.rows
    stats = summary(rows)
    payload = {
        "schemaVersion": "ai-work-lab/surface-register/v1",
        "generated_at": now_iso(),
        "workspace": str(workspace),
        "server": "backend.app.build_server (in-process, 127.0.0.1, port 0, bearer)",
        "enumeration": {
            "backend.v1.V1_ROUTES": len(V1_ROUTES),
            "backend.core.work_surfaces.WORK_SURFACE_ROUTES": len(WORK_SURFACE_ROUTES),
            "domains.design.design_lab.http_service.ROUTES": len(hs.ROUTES),
            "total": len(V1_ROUTES) + len(hs.ROUTES),
            "note": "V1_ROUTES 本身即 table + WORK_SURFACE_ROUTES，75 已含 49，不得重复相加",
        },
        "summary": stats,
        "seed_log": prober.seed_log,
        "rows": rows,
    }
    register_path = (REPO / args.register).resolve()
    csv_path = (REPO / args.csv).resolve()
    write_register(register_path, payload)
    write_csv(csv_path, rows)
    emit("[write] %s" % _ascii(str(register_path)))
    emit("[write] %s" % _ascii(str(csv_path)))
    emit("[result] enumerated=%d success=%d refusal=%d defect=%d fixture=%d unconstructed=%d "
         "variants=%d" % (
             stats["enumerated"], stats["by_verdict"].get(SUCCESS, 0),
             stats["by_verdict"].get(REFUSAL, 0), stats["by_verdict"].get(DEFECT, 0),
             stats["by_verdict"].get(FIXTURE, 0), len(stats["unconstructed"]),
             stats["variant_paths_probed"]))
    for defect in stats["defects"]:
        emit("  DEFECT %s %s -> %s %s" % (_ascii(defect["method"]),
                                          _ascii(str(defect["path"])[:90]),
                                          defect["http_status"], _ascii(defect["error_code"])))
    return 1 if stats["unconstructed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())


