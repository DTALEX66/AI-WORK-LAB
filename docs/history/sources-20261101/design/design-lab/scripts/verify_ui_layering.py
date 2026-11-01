#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep the Workbench's stacking order in a declared table, and prove the table is the CSS.

DESIGN.md §2 records the gap as "12 z-index 处且无层级表 → 新增层层必须先进表再使用".
Nothing in this repository checked that, so a new layer could be introduced anywhere and the
rule was a sentence. This verifier makes it machine-readable:

  * every `z-index` in the UI sources must read a `var(--layer-*)` token -- a bare number is
    a layer nobody named;
  * every token used must be declared in `:root`, every `--layer-*` declared must be in the
    table, and the table's value must equal the declaration (so a hand-written table entry
    cannot drift from the stylesheet);
  * the selectors the table attributes to a layer must be the selectors that actually carry
    it, or the table goes stale instead of quietly wrong.

Usage:
    python design-lab/scripts/verify_ui_layering.py                 # check
    python design-lab/scripts/verify_ui_layering.py --write          # (re)generate the table
    python design-lab/scripts/verify_ui_layering.py --css <path> --table <path>   # for tests
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "apps" / "workbench" / "style.css"
TABLE = ROOT / "design-lab" / "config" / "ui-layering.json"

RULE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}", re.S)
ZINDEX = re.compile(r"(?:^|[;{\s])z-index\s*:\s*(var\(\s*(--layer-[a-z0-9-]+)\s*\)|-?\d+)")
# Layer tokens live in `:root`. Scanning the block (rather than matching a fixed separator
# pattern over the whole file) keeps packed and per-line declarations equivalent, and avoids
# the overlap trap where consuming one `;` hides the next declaration from the same regex.
ROOT_BLOCK = re.compile(r":root\s*\{([^}]*)\}", re.S)
LAYER_TOKEN = re.compile(r"(--layer-[a-z0-9-]+)\s*:\s*(-?\d+)")

# Names and purposes are authored; the numbers and selectors are measured. `--write` takes
# the value from the stylesheet, so a name can be wrong in prose but a value cannot be wrong
# at all -- the check below compares them.
NAMES = {
    "-3": ("canvas-grid", "画布底纹网格：所有内容的下方，不参与交互"),
    "-2": ("canvas-ambient", "环境光晕与其伪元素：底纹之上、面板之下"),
    "0": ("flow-figure", "流程图 SVG 画布：面板内部的基准层"),
    "2": ("flow-node", "流程图节点：基准画布之上，只在 .flow 内部比较"),
    "50": ("topbar", "壳层顶栏：与路由面板同文档流，靠相对定位"),
    "60": ("nav-rail", "宽屏固定侧栏：盖住内容列，不盖住浮层"),
    "88": ("drawer", "离屏抽屉族（工作区抽屉与窄屏侧栏）：导航之上、遮罩之下"),
    "90": ("scrim", "模态遮罩：压住抽屉与页面，接受点击关闭"),
    "95": ("palette", "命令面板：遮罩之上的可输入浮层"),
    "110": ("toast", "瞬时通知：所有浮层之上，不接收焦点"),
    "200": ("skip-link", "键盘跳转链：仅在聚焦时出现，必须高于一切"),
}


def strip_comments(text: str) -> str:
    """Blank CSS comments but keep line numbers: prose mentions `z-index:65` and must not
    be counted as a declaration (that is how the original 12-row count was made)."""
    return re.sub(r"/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def measure(css_text: str) -> list[dict]:
    rows = []
    for match in RULE.finditer(css_text):
        selector = " ".join(match.group("selector").split()).lstrip(", ")
        for hit in ZINDEX.finditer(match.group("body")):
            token = hit.group(2)
            rows.append({"selector": selector,
                         "raw": hit.group(1),
                         "token": token,
                         "literal": None if token else hit.group(1),
                         "line": css_text[:match.start()].count("\n") + 1})
    return rows


def declared_tokens(css_text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for block in ROOT_BLOCK.finditer(css_text)
            for m in LAYER_TOKEN.finditer(block.group(1))}


def load_table(path: Path) -> dict:
    if not path.is_file():
        return {"schemaVersion": "design-lab/ui-layering/v1", "layers": []}
    return json.loads(path.read_text(encoding="utf-8"))


def build_table(rows: list[dict], tokens: dict[str, str], previous: dict) -> dict:
    """Group the measured declarations by token.

    Values and selectors come from the stylesheet; `name`/`purpose` are authored in NAMES and
    survive a regeneration if a human has already edited them, because the prose is the
    owner's to decide while the number is the machine's to verify.
    """
    existing = {layer.get("token"): layer for layer in previous.get("layers", [])}
    layers = []
    for name, value in sorted(tokens.items(), key=lambda kv: int(kv[1])):
        carried = [r["selector"] for r in rows if r["token"] == name]
        prior = existing.get(name, {})
        authored = NAMES.get(value, (name.removeprefix("--layer-"), ""))
        layers.append({
            "token": name,
            "value": int(value),
            "selectors": sorted(set(carried)),
            "usedBy": len(carried),
            "name": prior.get("name") or authored[0],
            "purpose": prior.get("purpose") or authored[1],
            # `note` is the human/measurement field: it survives a regeneration because a
            # rendered observation cannot be re-derived from the stylesheet.
            "note": prior.get("note"),
        })
    return {"schemaVersion": "design-lab/ui-layering/v1",
            "measuredBy": "design-lab/scripts/verify_ui_layering.py --write",
            "source": "apps/workbench/style.css (:root + every z-index declaration)",
            "status": "proposed-for-owner-acceptance",
            "rule": "新增层层必须先在此表登记；界面源文件里的 z-index 一律 var(--layer-*)",
            "layers": layers}


def check(css_text: str, table: dict) -> list[str]:
    rows = measure(css_text)
    tokens = declared_tokens(css_text)
    problems = []
    for row in rows:
        if row["literal"] is not None:
            problems.append(f"LITERAL-ZINDEX {row['selector']} (style.css:{row['line']}) "
                            f"= {row['literal']} -- declare a layer instead of a number")
        elif row["token"] not in tokens:
            problems.append(f"UNDECLARED-TOKEN {row['selector']} uses {row['token']} "
                            "which :root does not define")
    used = {r["token"] for r in rows if r["token"]}
    for token, value in tokens.items():
        if token not in used:
            problems.append(f"UNUSED-TOKEN {token}:{value} is declared but carries nothing")
        listed = next((l for l in table.get("layers", []) if l.get("token") == token), None)
        if listed is None:
            problems.append(f"TABLE-MISSING-LAYER {token} -- the table must name every layer")
        elif str(listed.get("value")) != value:
            problems.append(f"TABLE-VALUE-DRIFT {token}: {value} "
                            f"but the table says {listed.get('value')}")
    for layer in table.get("layers", []):
        token = layer.get("token")
        if token not in tokens:
            problems.append(f"TABLE-STALE-LAYER {token} -- no longer declared in :root")
            continue
        expected = sorted({r["selector"] for r in rows if r["token"] == token})
        actual = sorted(layer.get("selectors", []))
        if expected != actual:
            problems.append(f"TABLE-SELECTOR-DRIFT {token}: table says {actual} "
                            f"but the stylesheet applies it to {expected}")
        if not (layer.get("purpose") or "").strip():
            problems.append(f"UNDOCUMENTED-LAYER {token} -- a layer nobody explains")
    if not table.get("layers"):
        problems.append("TABLE_EMPTY: run design-lab/scripts/verify_ui_layering.py --write")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--css", default=str(CSS))
    parser.add_argument("--table", default=str(TABLE))
    args = parser.parse_args()

    css_path, table_path = Path(args.css), Path(args.table)
    css_text = strip_comments(css_path.read_text(encoding="utf-8"))
    rows = measure(css_text)
    tokens = declared_tokens(css_text)

    if args.write:
        table = build_table(rows, tokens, load_table(table_path))
        table_path.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
        print(f"UI_LAYERING=WRITTEN {table_path.name} layers={len(table['layers'])} "
              f"declarations={len(rows)}")
        return 0

    problems = check(css_text, load_table(table_path))
    values = sorted({int(v) for v in tokens.values()})
    print(f"UI_LAYERING scope={css_path.name} declarations={len(rows)} "
          f"layers={len(tokens)} values={values}")
    for problem in problems:
        print("UI_LAYERING=FAIL " + problem)
    if problems:
        return 1
    print("UI_LAYERING=PASS every layer is named, measured from the stylesheet, and the "
          "table matches the rules that carry it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
