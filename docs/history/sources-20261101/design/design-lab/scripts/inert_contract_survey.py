#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-INERT-SURVEY: turn "nothing implements this" into a decision a person can actually make.

`design-lab/config/contract-bindings.json` carries thirty contracts marked INERT. Since commit
6fa40276 the bindings gate RE-MEASURES that claim on every run (INERT_BUT_NAMED_BY_PRODUCT), which
proved the claim true -- but a true negative is still not a decision. Wire it or retire it is a
product call, and a product call needs the facts beside it: which table already carries this
activity, who writes that table, what a retirement would touch, what a wiring would have to add.

This script computes those facts from the repository and writes them into
`docs/audits/INERT-CONTRACT-SURVEY-<date>.md` inside a fenced JSON block, so the document is a
generated artifact and not a hand-typed table:

    python design-lab/scripts/inert_contract_survey.py           # write
    python design-lab/scripts/inert_contract_survey.py --check   # read-only drift check

Rules it applies, stated because they are judgement calls a reviewer may disagree with:
  * A schema overlaps a table when at least a third of its declared top-level property names are
    columns of that table. One third is a floor for "this is plausibly the same activity written
    twice", not a measurement of anything in the product; every hit reports its own coverage, so a
    reviewer can see a 34% match and reject it.
  * `writers` are product sources holding an INSERT/UPDATE/DELETE against that table; `readers` are
    product sources selecting from it. Both are found in code text, never in comments, for the same
    reason the object-model gate stopped trusting prose on 2026-10-08.
  * A retirement is reported COHERENT only when nothing else in the ledger or the route inventory
    references the schema. That is a check that the option exists, not a recommendation to take it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'design-lab' / 'scripts'))

from verify_contract_bindings import LEDGER_REL, product_corpus  # noqa: E402

SQL_DIR = ROOT / 'design-lab/schemas/state'
DOC_DIR = ROOT / 'docs/audits'
DOC_NAME = 'INERT-CONTRACT-SURVEY-2026-10-08.md'
DOC_REL = f'docs/audits/{DOC_NAME}'
CREATE = re.compile(r'CREATE TABLE(?: IF NOT EXISTS)?\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*;', re.S)
RESERVED = {'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'CONSTRAINT'}
WRITE_RE = re.compile(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-zA-Z0-9_]+)', re.I)
READ_RE = re.compile(r'\b(FROM|JOIN)\s+([a-zA-Z0-9_]+)', re.I)
OVERLAP_FLOOR = 1.0 / 3.0


def sql_tables(root: Path = ROOT) -> dict[str, list[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted((root / SQL_DIR.relative_to(ROOT)).glob('*.sql')):
        for match in CREATE.finditer(path.read_text(encoding='utf-8')):
            name, body = match.group(1), match.group(2)
            columns = set()
            for line in body.split('\n'):
                line = line.split('--')[0].strip().rstrip(',')
                if not line:
                    continue
                first = line.split()[0].upper()
                if first in RESERVED:
                    continue
                columns.add(line.split()[0].lower())
            found.setdefault(name, set()).update(columns)
    return {name: sorted(columns) for name, columns in found.items()}


def table_users(corpus: dict[str, str]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Where each table is written and read, from executable text only.

    SQL lives inside Python string literals, so "executable text" here means: drop lines whose first
    token is a `#` comment. That is deliberately narrower than raw text and wider than an AST, because
    the string holding the statement is the fact being sought.
    """
    writers: dict[str, set[str]] = {}
    readers: dict[str, set[str]] = {}
    for rel, text in corpus.items():
        code = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('#'))
        for verb, table in WRITE_RE.findall(code):
            writers.setdefault(table.lower(), set()).add(rel)
        for _verb, table in READ_RE.findall(code):
            readers.setdefault(table.lower(), set()).add(rel)
    return ({name: sorted(v) for name, v in writers.items()},
            {name: sorted(v) for name, v in readers.items()})


def schema_fields(path: Path) -> list[str]:
    """The schema's declared top-level property names, or None when the file is not on disk.

    A contract row whose file has gone is exactly the case a survey must keep reporting instead of
    crashing on: the ledger still carries the claim, and the sheet is where that disagreement shows.
    """
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding='utf-8'))
    props = doc.get('properties') or {}
    return sorted(name.lower() for name in props)


def classify(row: dict, tables: dict, writers: dict, readers: dict, corpus: dict,
             ledger: dict) -> dict:
    schema_rel = row['schema']
    name = Path(schema_rel).name
    declared = schema_fields(ROOT / schema_rel)
    if declared is None:
        return {'schema': schema_rel, 'version': row.get('version'), 'fields': 0,
                'best_table': None, 'overlap': 0.0, 'matched_fields': [], 'table_writers': [],
                'table_readers': [], 'state': 'SCHEMA_FILE_ABSENT', 'thin_match': False,
                'retire_coherent': False,
                'retire_targets': [f'{LEDGER_REL}:{name} row'],
                'route_references': [route['route'] for route in ledger.get('routes', [])
                                     if route.get('schema') == schema_rel],
                'reason': (row.get('reason') or '').strip()}
    comparable = [field for field in declared if field not in ('schemaversion', '$schema')]
    best_name, best_hits, best_ratio = None, [], 0.0
    for table, columns in sorted(tables.items()):
        hits = [field for field in comparable if field in columns]
        if not comparable:
            continue
        ratio = len(hits) / len(comparable)
        if ratio > best_ratio:
            best_name, best_hits, best_ratio = table, hits, ratio
    writes = sorted(writers.get(best_name, [])) if best_name else []
    reads = sorted(readers.get(best_name, [])) if best_name else []
    # A two-property schema reaches the floor on ONE shared column. That is worth showing rather
    # than hiding: `thin_match` says which rows are labelled by a single name in common.
    thin_match = bool(best_name) and len(best_hits) <= 1 and len(comparable) <= 3
    if best_name and best_ratio >= OVERLAP_FLOOR:
        state = 'TABLE_WRITES_THIS_ACTIVITY' if writes else 'TABLE_EXISTS_UNWRITTEN'
    elif best_name and writes:
        # a table that is really written but shares only a few names: adjacent, not a duplicate
        state = 'ADJACENT_TABLE_WRITTEN'
    else:
        state = 'NO_STATE_COUNTERPART'
    route_refs = [route['route'] for route in ledger.get('routes', [])
                  if route.get('schema') == schema_rel]
    other_rows = [other['schema'] for other in ledger.get('contracts', [])
                  if other is not row and other.get('schema') == schema_rel]
    schema_exists = (ROOT / schema_rel).is_file()
    return {
        'schema': schema_rel,
        'version': row.get('version'),
        'fields': len(comparable),
        'best_table': best_name,
        'overlap': round(best_ratio, 3),
        'matched_fields': best_hits,
        'table_writers': writes,
        'table_readers': reads,
        'state': state,
        'thin_match': thin_match,
        'retire_coherent': not route_refs and not other_rows and schema_exists,
        'retire_targets': [schema_rel, f'{LEDGER_REL}:{name} row'],
        'route_references': route_refs,
        'reason': (row.get('reason') or '').strip(),
    }


def build(root: Path = ROOT) -> dict:
    ledger = json.loads((root / LEDGER_REL).read_text(encoding='utf-8'))
    inert = [row for row in ledger['contracts'] if row.get('status') == 'INERT']
    corpus = product_corpus(root)
    tables = sql_tables(root)
    writers, readers = table_users(corpus)
    rows = [classify(row, tables, writers, readers, corpus, ledger) for row in inert]
    counts: dict[str, int] = {}
    for entry in rows:
        counts[entry['state']] = counts.get(entry['state'], 0) + 1
    return {'schemaVersion': 'design-lab/inert-contract-survey/v1',
            'inertRows': len(inert), 'contracts': len(ledger['contracts']),
            'productFiles': len(corpus), 'tables': len(tables),
            'stateCounts': counts, 'rows': rows}


MARKDOWN = '''# INERT 合同普查（生成物，勿手改）

由 `design-lab/scripts/inert_contract_survey.py` 计算生成；重跑：
`python design-lab/scripts/inert_contract_survey.py`，只读校验：加 `--check`。
本页的每个数字都来自仓库本身（schema 属性、`design-lab/schemas/state/*.sql` 的表列、产品源码中
对该表的写入/读取语句），不是从任何 reason 文案抄来的。

判定规则（可反对，但必须显式反对）：一个 schema 与某张表"重叠"，当且仅当它声明的顶层属性名中
至少 1/3 是该表的列。这个三分之一是"大概是同一件事被声明了两次"的门槛，不是产品里的某个测量值；
每行都给出自己的 overlap 与命中的字段名，34% 的匹配可以被 reviewer 直接否掉。

分类含义：
  * `TABLE_WRITES_THIS_ACTIVITY` —— 有产品代码在写这张表：这条 INERT 声明的很可能是同一事物的第二种形状。
  * `TABLE_EXISTS_UNWRITTEN` —— 表在 SQL 里声明了，但没有任何产品代码写它：形状对得上，实现也没有。
  * `ADJACENT_TABLE_WRITTEN` —— 有被写的表但字段重合不足三分之一：相邻，不是重复。
  * `NO_STATE_COUNTERPART` —— 没有任何表对得上。
  * `SCHEMA_FILE_ABSENT` —— 账本还声明着这条合同，文件已经不在仓里：既谈不上接线，退役也要先说明。

标注 `（thin）` 的行：schema 声明的属性 ≤3 且只有 1 个名字与表重合 —— 门槛在这种情况下会被单个
同名列达到，判断请配合 `matched_fields` 一起看，不要只看分类词。

`retire_coherent` 只说明"退役这条在账本与路由清单里没有连带引用"，即该选项可执行，不表示建议执行。

下面这段 JSON 是本页的可校验部分：`--check` 会重算并与此块逐字节比较，改了代码没重跑就是红的。

```json
{json_block}
```

## 一览表

| schema | 声明字段 | 最相近表 | 重合 | 谁在写这张表 | 分类 | 退役可执行 |
|---|---|---|---|---|---|---|
{table_rows}
'''


def render(document: dict) -> str:
    lines = []
    for entry in document['rows']:
        writers = ', '.join(path.split('/')[-1] for path in entry['table_writers'][:3]) or '—'
        lines.append(f"| `{Path(entry['schema']).name}` | {entry['fields']} | "
                     f"{entry['best_table'] or '—'} | {entry['overlap']:.2f} | {writers} | "
                     f"{entry['state']}{'（thin）' if entry.get('thin_match') else ''} | "
                     f"{'是' if entry['retire_coherent'] else '否'} |")
    body = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    return (MARKDOWN.replace('{json_block}', body)
            .replace('{table_rows}', '\n'.join(lines)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--stdout', action='store_true')
    args = parser.parse_args(list(argv) if argv is not None else None)

    document = build()
    text = render(document)
    if args.stdout:
        print(text)
        return 0
    target = ROOT / DOC_REL
    if args.check:
        if not target.is_file():
            print(f'INERT_SURVEY=FAIL missing {DOC_REL}')
            return 1
        current = target.read_text(encoding='utf-8')
        if current != text:
            print(f'INERT_SURVEY=FAIL stale {DOC_REL} -- the survey was computed from code that has '
                  'moved; re-run without --check')
            return 1
        print(f'INERT_SURVEY=OK rows={document["inertRows"]} states='
              + ','.join(f'{key}={value}' for key, value in sorted(document['stateCounts'].items())))
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8', newline='\n')
    written = (ROOT / DOC_REL).read_text(encoding='utf-8')
    if written != text:
        print('INERT_SURVEY=FAIL the written bytes are not what was computed')
        return 1
    print(f'INERT_SURVEY=WROTE {DOC_REL} rows={document["inertRows"]} '
          f'tables={document["tables"]} productFiles={document["productFiles"]} '
          f'states={document["stateCounts"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
