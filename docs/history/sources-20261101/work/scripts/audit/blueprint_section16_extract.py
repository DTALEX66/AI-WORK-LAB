"""Dump the blueprint docx section-16 candidate table as UTF-8 JSON, with row keys.

Selected by its header row, not by position: the document carries a contents list near the
top, so "the first table after a paragraph starting with 16." is not the candidate pool.
Row keys are 16.NN in document order over the data rows.
"""
import json
import pathlib
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SRC = pathlib.Path(r"D:\All projects\Record\02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx")
OUT = pathlib.Path(".project-local/runs/convergence-20261007-c/section16.json")
HEADER = ["候选/家族", "有边界的角色", "触发条件与验收"]

with zipfile.ZipFile(SRC) as z:
    root = ET.fromstring(z.read("word/document.xml"))


def text_of(el):
    return "".join(t.text or "" for t in el.iter(f"{W}t")).strip()


matches = []
for tbl in root.iter(f"{W}tbl"):
    rows = [[text_of(tc) for tc in tr.findall(f"{W}tc")]
            for tr in tbl.findall(f"{W}tr")]
    if rows and rows[0] == HEADER:
        matches.append(rows)

if len(matches) != 1:
    print(f"SECTION16_TABLE_AMBIGUOUS matches={len(matches)} expected=1")
    sys.exit(2)

data = matches[0][1:]
payload = {
    "sourcePath": str(SRC),
    "header": HEADER,
    "dataRowCount": len(data),
    "rows": [{"row": f"16.{i + 1:02d}", "candidate": r[0], "role": r[1],
              "trigger": r[2]} for i, r in enumerate(data)],
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
written = json.loads(OUT.read_text(encoding="utf-8"))
print(f"WROTE {OUT} bytes={OUT.stat().st_size} dataRows={written['dataRowCount']}")
for r in written["rows"]:
    print(f"  {r['row']}  {r['candidate']}")
sys.exit(0 if written["dataRowCount"] == 19 else 1)
