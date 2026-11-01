# SPDX-License-Identifier: MIT
"""V24: two capability rows that carried no assertion at all.

`migration/capability-family-register.csv` recorded `05#L21|design-domain` and
`05#L28|research` as UNVERIFIED/GAP-adjacent with the honest note 「本仓没有对应断言，数字未经复算」.
Both clauses are machine-checkable, so this file checks them:

* the domain-pack projection reports what is on disk, in order, with the counts derived in the
  call -- and never a validation verdict the repository's own checker did not deliver;
* research material is data only, no runtime path imports it, and the declared dependencies gain
  no online-collection client.

The planted checker in the second node is what makes the first node's `NOT_CHECKED` assertion
worth anything: a projection that hard-coded "not checked" would pass the real-tree node and fail
this one.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
if str(TARGET_ROOT / "domains" / "design") not in sys.path:
    sys.path.insert(0, str(TARGET_ROOT / "domains" / "design"))

from design_lab import domain_packs as dp  # noqa: E402


def _tracked(prefix: str | None) -> list[str]:
    argv = ["git", "ls-files", "-z"] + ([prefix] if prefix is not None else [])
    out = subprocess.run(argv, cwd=str(TARGET_ROOT), capture_output=True, timeout=300)
    assert out.returncode == 0, out.stderr[-400:]
    return [p.decode("utf-8", "surrogateescape") for p in out.stdout.split(b"\0") if p]


def test_domain_pack_projection_reports_the_disk_and_invents_no_verdict():
    """登记行 05#L21|design-domain：目录数、逐包资格与合计都由这一次调用现算。

    证明：投影列出的条目恰好等于盘面上的包目录（顺序一致，既不漏也不凭空多）；`counts.packs`
    等于该长度、`byValidation` 各类相加也等于它；本树的仓库自带校验脚本 *不在*（checker.state
    为 UNAVAILABLE），因此每一包都必须是 NOT_CHECKED 并带上那句"校验器没跑"的 note——
    没有一个 VALIDATES 是被顺手填上的；每个条目的身份字段逐字来自该包自己的 manifest，
    manifest 里没有 `domain` 的条目必须答 null，而不是被默认成任何字符串（v1 包不许假装是 v2）。
    没证明：任何真实宿主/CI 跑过那份校验器；「13 个领域包资格分别标记」里的"标记"在本树只有
    NOT_CHECKED 这一格被真正走出，其余三格由下一个节点用植入的校验器证明。
    """
    document = dp.build()
    root = dp.packaged_root()
    on_disk = sorted(path.name for path in (root / dp.PACK_ROOT_REL).iterdir() if path.is_dir())
    assert on_disk, "盘面上没有领域包目录，本节点的断言需要按现读重写"

    entries = document["packs"]
    assert [entry["directory"] for entry in entries] == on_disk, on_disk
    assert document["counts"]["packs"] == len(on_disk), document["counts"]
    assert sum(document["counts"]["byValidation"].values()) == len(on_disk)
    assert document["checker"]["state"] == "UNAVAILABLE", document["checker"]
    assert document["counts"]["byValidation"][dp.VALIDATES] == 0, document["counts"]
    assert all(entry["validation"] == dp.NOT_CHECKED for entry in entries), entries[:2]
    assert all("checker" in (entry["note"] or "") for entry in entries), entries[:2]
    assert document["validationVocabulary"] == ["VALIDATES", "INVALID", "UNREADABLE",
                                                "NOT_CHECKED"]

    for entry in entries:
        manifest_path = root / dp.PACK_ROOT_REL / entry["directory"] / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for field, key in (("pack_id", "packId"), ("version", "version"),
                           ("domain", "domain"), ("schema_version", "manifestSchemaVersion")):
            declared = manifest.get(field)
            assert entry[key] == (declared if isinstance(declared, str) and declared else None), \
                (entry["directory"], field, declared, entry[key])
    defaulted = [entry["directory"] for entry in entries
                 if not (root / dp.PACK_ROOT_REL / entry["directory"] / "manifest.json").is_file()]
    assert all((entry["packId"], entry["domain"]) == (None, None)
               for entry in entries if entry["directory"] in defaulted), defaulted


def test_the_pack_verdict_is_the_checkers_and_an_unreadable_pack_is_never_dropped(tmp_path):
    """植入反证：校验器给出的结论必须原样进报表，读不到的包必须留在列表里并被标 UNREADABLE。

    临时根里造四个包：清单正常的两个（其中一个被植入的校验器拒掉）、一个清单不是 JSON、
    一个根本没有清单。断言分别落在 VALIDATES / INVALID（带校验器自己写的那句理由）/
    UNREADABLE（两种读不到清单的情形，且身份字段保持 null）。若投影把 NOT_CHECKED 写死、
    自己编理由，或把读不到的包静默跳过，这个节点立刻红。
    """
    packs = tmp_path / "design-lab" / "domain-packs"
    for name in ("good", "rejected", "bad-json", "no-manifest"):
        (packs / name).mkdir(parents=True)
    for name in ("good", "rejected"):
        (packs / name / "manifest.json").write_text(json.dumps({
            "pack_id": name, "version": "0.1.0", "display_name": name.title() + " Pack",
            "domain": name, "schema_version": "design-lab/domain-pack/v2"}), encoding="utf-8")
    (packs / "bad-json" / "manifest.json").write_text("{ this is not json", encoding="utf-8")
    scripts = tmp_path / "design-lab" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "verify_domain_pack_v2.py").write_text(
        "def validate(pack_dir):\n"
        "    if pack_dir.name == 'good':\n"
        "        return True, []\n"
        "    return False, ['planted rejection for ' + pack_dir.name]\n", encoding="utf-8")

    document = dp.build(tmp_path)
    by_name = {entry["directory"]: entry for entry in document["packs"]}
    assert sorted(by_name) == ["bad-json", "good", "no-manifest", "rejected"], document["packs"]
    assert document["counts"]["byValidation"] == {dp.VALIDATES: 1, dp.INVALID: 1,
                                                  dp.UNREADABLE: 2, dp.NOT_CHECKED: 0}
    assert by_name["good"]["validation"] == dp.VALIDATES, by_name["good"]
    # the verdict is the checker's own text, copied without local opinion
    assert by_name["rejected"]["validation"] == dp.INVALID, by_name["rejected"]
    assert by_name["rejected"]["validationErrors"] == ["planted rejection for rejected"], \
        by_name["rejected"]
    assert by_name["rejected"]["validationErrorCount"] == 1, by_name["rejected"]
    # a manifest that cannot be read never reaches the checker: it is UNREADABLE and named,
    # and its identity fields stay null instead of being defaulted
    assert by_name["bad-json"]["validation"] == dp.UNREADABLE, by_name["bad-json"]
    assert by_name["bad-json"]["validationErrors"] == ["manifest.json is not valid JSON"]
    assert (by_name["bad-json"]["packId"], by_name["bad-json"]["domain"]) == (None, None)
    assert by_name["no-manifest"]["validation"] == dp.UNREADABLE, by_name["no-manifest"]
    assert by_name["no-manifest"]["validationErrors"] == ["manifest.json is absent"]
    assert document["checker"]["state"] != "UNAVAILABLE", document["checker"]


def test_research_material_is_data_that_no_runtime_path_imports(tmp_path):
    """登记行 05#L28|research：「资料不是运行事实」与「不新增在线采集依赖」都是可查的。

    证明：research/ 下的跟踪文件全是数据（本树实测只有 JSON，没有任何 .py，因此运行时不可能
    从这里 import 到一个模块）；仓库里除 research/ 自己以外没有任何 .py 的 import 语句指向它；
    候选分类学能解析、条目非空、条目键集合一致，条目数由这次读取现算而不是抄登记；
    项目声明的依赖里没有 HTTP/网络采集客户端（requests / httpx / aiohttp / urllib3 / socket 类）。
    没证明：任何联网检索能力存在（09 分期表 L30 的 P3 检索本就未做，本行也不声称它做了）；
    分类学里每条资料的内容正确性（那是人审的范围）。
    """
    tracked = _tracked("research")
    assert tracked, "research/ 下没有跟踪文件，本节点的断言需按现读重写"
    assert all(path.endswith(".json") for path in tracked), tracked
    assert not [path for path in tracked if path.endswith(".py")], tracked

    # only an import of the top-level `research` package counts: `from .assurance import
    # research_store` names a different module and must not be reported as a false positive
    importer = re.compile(r"^(?:import|from)\s+research(?:\.[\w.]+)*\b")
    importers = []
    for path in _tracked(None):
        if not path.endswith(".py") or path.startswith("research/"):
            continue
        try:
            lines = (TARGET_ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if importer.match(stripped):
                importers.append("%s: %s" % (path, stripped))
    assert importers == [], importers[:5]
    # and the same rule proves the predicate can bite: a planted import of research is found
    planted = tmp_path / "runtime_module.py"
    planted.write_text("import research.candidates\n", encoding="utf-8")
    assert importer.match(planted.read_text(encoding="utf-8").strip()), "谓词抓不到植入的导入"
    assert not importer.match("from .assurance import research_store")

    document = json.loads((TARGET_ROOT / "research/candidates/CANDIDATE-TAXONOMY.json")
                          .read_text(encoding="utf-8"))
    assert document["schemaVersion"] == "design-lab/candidate-taxonomy/v1"
    entries = document["entries"]
    assert isinstance(entries, list) and entries, document.keys()
    shape = sorted(entries[0])
    off_shape = [index for index, item in enumerate(entries) if sorted(item) != shape]
    assert off_shape == [], ("taxonomy 条目形状不一致，计数与列名不能再按统一结构读", off_shape[:5])
    assert len(entries) > 100, len(entries)

    declared = (TARGET_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", declared, re.S | re.M)
    assert block, "pyproject 里没有 dependencies 数组，本条断言需按现读重写"
    # only the quoted requirement specs count: the array carries explanatory comments too
    names = [re.split(r"[<>=!;\[]", item)[0].strip().lower()
             for item in re.findall(r'"([^"]+)"', block.group(1))]
    online_clients = sorted({name for name in names
                             if name in ("requests", "httpx", "aiohttp", "urllib3",
                                         "selenium", "playwright", "socketio")})
    assert online_clients == [], (names, online_clients)
    assert names, names


RIR_COPIES = ("design-lab/schemas/reconstruction/reconstruction-ir.schema.json",
              "domains/design/design_lab/resources/repo/design-lab/schemas/reconstruction/"
              "reconstruction-ir.schema.json",
              "packages/contracts/schemas-design/reconstruction/reconstruction-ir.schema.json")


def test_rir_contract_is_one_document_in_three_places_and_refuses_what_it_must(tmp_path):
    """登记行 05#L23|design-reconstruction：合同本身可查，人审那一半不假称查过。

    证明：RIR 合同的三份副本（来源仓那份、打包资源那份、对外发布的那份）逐字节相同，所以
    "发布合同 == 产品用的那份"不是一句话；产品按 `design_lab.reconstruction` 这个名字导入它，
    而实现只有一份（`contracts.__file__` 落在 packages/capabilities/reconstruction 下）；
    安装态下不给出项目根就直接被拒（不允许把 raster 路径按导入猜测的根解析）；
    `validate_rir({}, project_root=...)` 报出的正是 schema 自己声明的第一个必填字段名
    （错误信息来自合同，不是测试编的）；`NaN` 在进入任何字段检查之前就被拒（非有限数不是合法 JSON，
    不能被读成 null）；路径政策的每一类坏输入——绝对、上级穿越、反斜杠、URI scheme、空串——
    都被 `_require_project_relative` 具名拒绝，而一条干净的相对路径确实解析在项目根内，
    证明这条规则不是"什么都拒"。
    没证明：一份真实 RIR 能通过整份合同（本仓没有可复用的合法 RIR 样本；raster 节点只有在合法文档里
    才会走到同一个路径函数，这条调用链由 contracts.py 的调用点唯一决定）；
    「结构与视觉规格分开验收」需人审，本行不声称那条已完成。
    """
    import hashlib

    from design_lab.reconstruction import contracts

    # the product imports it as `design_lab.reconstruction`; the file itself lives in
    # packages/capabilities/reconstruction (the package path is aliased, not duplicated),
    # so there is one implementation and not a second authority
    assert Path(contracts.__file__).as_posix().endswith(
        "packages/capabilities/reconstruction/contracts.py"), contracts.__file__

    digests = set()
    for relative in RIR_COPIES:
        path = TARGET_ROOT / relative
        assert path.is_file(), path
        digests.add(hashlib.sha256(path.read_bytes()).hexdigest())
    assert len(digests) == 1, digests
    schema = json.loads((TARGET_ROOT / RIR_COPIES[0]).read_text(encoding="utf-8"))
    assert schema["required"], sorted(schema)

    # the installed spelling refuses to guess where the project is: without an explicit root it
    # would resolve raster paths against whatever the import machinery thinks the root is
    with pytest.raises(contracts.ContractError, match="requires an explicit project root"):
        contracts.validate_rir({})
    with pytest.raises(contracts.ContractError) as missing:
        contracts.validate_rir({}, project_root=tmp_path)
    assert schema["required"][0] in str(missing.value), str(missing.value)

    with pytest.raises(contracts.ContractError, match="non-finite"):
        contracts.validate_rir({"layers": [float("nan")]}, project_root=tmp_path)

    for bad in ("/etc/passwd", "../outside.png", "C:\\layers\\a.png", "https://host/a.png",
                "a/../b.png", ""):
        with pytest.raises(contracts.ContractError):
            contracts._require_project_relative(bad, "node 'n' raster.path", tmp_path)
    resolved = contracts._require_project_relative("layers/a.png", "node 'n' raster.path", tmp_path)
    assert resolved.is_relative_to(tmp_path.resolve()), resolved
