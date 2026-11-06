# SPDX-License-Identifier: MIT
"""V24: two capability rows that carried no assertion at all.

`migration/capability-family-register.csv` recorded `05#L21|design-domain` and
`05#L28|research` as UNVERIFIED/GAP-adjacent with the honest note 「本仓没有对应断言，数字未经复算」.
Both clauses are machine-checkable, so this file checks them:

* the domain-pack projection reports what is on disk, in order, with the counts derived in the
  call -- and never a validation verdict the repository's own checker did not deliver;
* research material is data only, no runtime path imports it, and the declared dependencies gain
  no online-collection client.

The two nodes read each other: the first runs the repository's own checker over the real tree and
shows that no pack is left `NOT_CHECKED` there any more, the second plants a synthetic checker into
a temporary root and shows that a `VALIDATES` / `INVALID` / `UNREADABLE` verdict is only ever the
checker's own. Both directions are therefore closed -- neither "nothing was checked" nor
"everything passes" can be hard-coded into the projection.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

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
    """登记行 05#L21|design-domain：仓库自带的校验脚本此刻真的在跑，结论由它给、计数由这次调用现算。

    证明（六面，全部按本树现读，任一不成立即红）：
    1 校验器在场且被载入：`checker.state` 为 LOADED、`checker.note` 为 None，而它点名的那个相对
      路径按模块自己的方式（打包资源根 + `CHECKER_REL`）解析出来确实是一个位于该根之下的真实文件，
      所以"我用了仓库自带的校验器"不是报表的自我声明。
    2 已经没有包停在 NOT_CHECKED（`byValidation.get(NOT_CHECKED, 0) == 0`）；与此同时
      `validationVocabulary` 仍然把 NOT_CHECKED 列在词表里。词表是"这个发射器会说哪四种话"的声明，
      不是这一次的读数：某一格这次没出现，不等于可以把它从词表里抹掉。
    3 数目对得上：`counts.packs` == 条目数 == 盘面上的包目录数，`byValidation` 各类相加仍是它。
    4 结论从不裸奔：每一条 VALIDATES 的 `validationErrorCount` 都是 0，每一条 INVALID/UNREADABLE 的
      `validationErrorCount` 都 > 0 且 `validationErrors` 非空——没有理由就没有结论，反之亦然。
    5 一条具名的真实发现：`minigame-design` 是 INVALID，`validationErrorCount` 为 11，第一条点名
      缺少的 `domain` 属性，其余每条都是 `files.*` 声明缺失（按形状核对，不逐字抄那 11 条串）。
    6 防漂移：这份随包发布的校验脚本的当前摘要，必须等于 `migration/copies.json`（迁移工具自己写的
      台账）为它记下的 `sha256_target`。将来有人悄悄改过 shipped 校验器，这里会红，而不是继续报绿。
    没证明：`VALIDATES` 只是"本仓这些文件的结构对不对"的 E1 结构陈述——不是任何真实宿主跑过一次，
    不是设计质量判定，不是被接受的领域能力，也不是真人（E4）验收；13 个包里 12 个通过这件事，
    对这 12 个包设计得好不好没有任何说法。本节点也没有修任何东西：`minigame-design` 的 manifest
    内容我没动过一个字节，让它继续 INVALID 正是校验器在尽责，把它改好是 owner 的设计工作，
    不在这里用断言抹平，也不在这里替它补 `domain`。词表里 UNREADABLE 那一格由下一个节点用植入的
    假包证明——本树现在没有读不到的包，所以这一格在本节点是空的，不是被跳过的。
    """
    import hashlib

    document = dp.build()
    root = dp.packaged_root()
    on_disk = sorted(path.name for path in (root / dp.PACK_ROOT_REL).iterdir() if path.is_dir())
    assert on_disk, "盘面上没有领域包目录，本节点的断言需要按现读重写"

    entries = document["packs"]
    by_validation = document["counts"]["byValidation"]
    assert [entry["directory"] for entry in entries] == on_disk, on_disk

    # (1) the checker the report says it used is a real file under the root it resolved
    checker = document["checker"]
    assert checker["path"] == dp.CHECKER_REL.as_posix(), checker
    assert checker["state"] == "LOADED", checker
    assert checker["note"] is None, checker
    shipped_checker = root / dp.CHECKER_REL
    assert shipped_checker.is_file(), \
        f"{dp.CHECKER_REL.as_posix()} 并不在打包资源根下，checker.state=LOADED 是空话：{root}"
    assert shipped_checker.resolve().is_relative_to(root.resolve()), shipped_checker

    # (2) an empty result cell vs a still-declared vocabulary word -- two different things
    assert by_validation.get(dp.NOT_CHECKED, 0) == 0, \
        ("校验器已载入（state=LOADED），却仍有包停在 NOT_CHECKED：那条结论不是校验器给的，"
         "而是投影自己写的", by_validation, checker)
    assert dp.NOT_CHECKED in document["validationVocabulary"], \
        ("本树已不再产生 NOT_CHECKED，但发射器仍然必须能说出这一格：词表是能力声明，不是本次读数",
         document["validationVocabulary"])
    assert document["validationVocabulary"] == ["VALIDATES", "INVALID", "UNREADABLE", "NOT_CHECKED"]

    # (3) every number in the report is this call's count of the disk
    assert document["counts"]["packs"] == len(entries) == len(on_disk), \
        (document["counts"], len(entries), len(on_disk))
    assert sorted(by_validation) == sorted(dp.VALIDATION_STATES), by_validation
    assert sum(by_validation.values()) == len(on_disk), (by_validation, len(on_disk))

    # (4) a verdict is never delivered without its reason, and never with an invented one
    assert all(entry["validation"] in dp.VALIDATION_STATES for entry in entries), \
        [(entry["directory"], entry["validation"]) for entry in entries]
    passed_with_errors = [entry["directory"] for entry in entries
                          if entry["validation"] == dp.VALIDATES
                          and entry["validationErrorCount"] != 0]
    assert passed_with_errors == [], ("报成 VALIDATES 却带着非零错误计数", passed_with_errors)
    verdict_without_reason = [entry["directory"] for entry in entries
                              if entry["validation"] in (dp.INVALID, dp.UNREADABLE)
                              and not (entry["validationErrorCount"] > 0
                                       and entry["validationErrors"])]
    assert verdict_without_reason == [], ("给了否定结论却没有校验器自己那句理由的包", verdict_without_reason)

    # (5) the one real finding on this tree, named, with the checker's own reasons
    rejected = [entry for entry in entries if entry["validation"] == dp.INVALID]
    assert [entry["directory"] for entry in rejected] == ["minigame-design"], \
        ("本树应当只有 minigame-design 被仓库自带的校验脚本拒掉",
         [entry["directory"] for entry in rejected])
    pack = rejected[0]
    assert pack["packId"] == "minigame-design", pack
    assert pack["manifestSchemaVersion"] == "workflow/domain-pack/v1", pack
    assert pack["validationErrorCount"] == 11, \
        ("校验器给 minigame-design 的错误条数变了：本条按现读改写，别把它凑回 11",
         pack["validationErrorCount"], pack["validationErrors"][:1])
    assert pack["validationErrorCount"] <= dp.MAX_ERRORS, \
        ("条数已超出投影的列举上限，下面的完整性判断不再成立，需按现读改写",
         pack["validationErrorCount"], dp.MAX_ERRORS)
    assert len(pack["validationErrors"]) == pack["validationErrorCount"], \
        ("列出的就该是全部理由，而不是被截断的前段", pack["validationErrors"])
    assert pack["note"] is None, ("条数未超上限却带上了截断说明", pack["note"])
    first, rest = pack["validationErrors"][0], pack["validationErrors"][1:]
    assert "'domain'" in first and "required" in first.lower(), \
        ("第一条应当点名 v1 清单缺少的那个 domain 属性", first)
    pattern = r"manifest missing files\.[a-z0-9_]+ declaration"
    undeclared_files = [error for error in rest if not re.fullmatch(pattern, error)]
    assert undeclared_files == [], ("其余每条都该是缺一个 files.* 声明", undeclared_files[:3])
    assert len(rest) == pack["validationErrorCount"] - 1, len(rest)

    # (6) the shipped validator is still the bytes the migration ledger recorded for it
    ledger = json.loads((TARGET_ROOT / "migration" / "copies.json").read_text(encoding="utf-8"))
    checker_tail = dp.CHECKER_REL.as_posix()
    records = [record for group in ledger["copies"] for record in (group.get("records") or [])
               if record["target"].replace("\\", "/").endswith(checker_tail)]
    assert len(records) == 1, ("迁移台账里这条校验脚本的记录必须唯一",
                               [record["target"] for record in records])
    record = records[0]
    assert record["sha256_source"] == record["sha256_target"], \
        ("台账自己就没记下逐字节复制，之后的摘要比较就不再证明任何东西", record)
    current_digest = hashlib.sha256(shipped_checker.read_bytes()).hexdigest()
    assert current_digest == record["sha256_target"], \
        ("随包发布的校验器已被改动：上面每一条 VALIDATES 都是按这份新字节说的，"
         "而台账记录的仍是迁移时那一份", checker_tail, current_digest, record["sha256_target"])

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
    undeclared_domain = [entry["directory"] for entry in entries if entry["domain"] is None]
    assert undeclared_domain == ["minigame-design"], \
        ("清单没声明 domain 的包必须答 null，不许被默认成任何字符串（v1 不许假装是 v2）", undeclared_domain)


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


#: The legal RIR sample and the raster bytes it needs, both migrated byte-for-byte.
RIR_SAMPLE = "tests/fixtures/reconstruction/uikit-conformance-2026-09-28/input.rir.json"
FLAT_PNG = "tests/fixtures/reconstruction/flat-64.png"
#: what build_photoshop_job says about the shapes below -- copied from measured refusals, and
#: asserted rather than paraphrased so a change in wording has to be a decision, not drift.
RECT_GATE = "rounded or parameterized rect unsupported"
REMAP_GATE = "raster remapping/alpha requires explicit preprocessed asset"


def _nodes_of(document: dict) -> list[dict]:
    def walk(node):
        yield node
        for child in node.get("children") or []:
            yield from walk(child)

    return [node for layer in document["layers"] for node in walk(layer)]


def _sample() -> dict:
    return json.loads((TARGET_ROOT / RIR_SAMPLE).read_text(encoding="utf-8"))


def _stage(tmp_path: Path, raster_rel: str) -> tuple[Path, Path]:
    """A project root with the marker the path policy insists on, and a run root inside it."""
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    (project / "AGENTS.md").write_text("# 测试项目标记（不是交付物）\n", encoding="utf-8")
    run_dir = project / ".project-local" / "task-runtime" / "kit-raster"
    run_dir.mkdir(parents=True, exist_ok=True)
    asset = project / PurePosixPath(raster_rel)
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes((TARGET_ROOT / FLAT_PNG).read_bytes())
    return project, run_dir


def test_a_migrated_rir_sample_passes_the_contract_with_a_raster_node():
    """登记行 05#L23 的「本仓没有一份能过整份合同的合法 RIR 样本」被一份迁入的字节否证。

    证明：
    * 样本与栅格夹具的当前摘要逐字等于 `migration/copies.json` 为它们记下的 `sha256_target`
      （台账记的是复制时的摘要，所以这里同时证明"逐字节迁入"与"此后没被人改过"）；
    * 未改动的样本过本仓的 `validate_rir`：schema、非有限数、身份字段全过，并且它含
      **恰好一个** `type=raster` 节点——这一句是让"raster 那一支被走过"成为可失败断言的关键，
      否则合同过了九个纯矢量节点也能被说成"栅格链路验证过"；
    * 样本的清单版本、画布与该 raster 的声明路径按现读钉住（v1、64×64、
      `.hermes/task-runtime/.../texture-chip.png`），并且那个 PNG **在本仓并不存在**：
      来源仓里它也只在 `.hermes` 运行时目录、从未进 Git。这条负面断言写在这里是为了防止以后
      有人拿一个凭空造的 PNG 冒充"原件"。
    没证明：栅格字节被任何宿主读过（没有）；这份样本是本项目产生的（它是迁入的来源仓审计工件）；
    清单的 domain 字段有值——v1 清单没声明，读回里它是 null。
    """
    from design_lab.reconstruction import contracts
    import hashlib
    from pathlib import PurePosixPath

    ledger = json.loads((TARGET_ROOT / "migration" / "copies.json").read_text(encoding="utf-8"))
    for relative in (RIR_SAMPLE, FLAT_PNG):
        # 台账记的是复制那台机器上的绝对目标路径，一份克隆的根不一样，所以按结尾取这一条，
        # 并要求它唯一——同一个夹具留下两条记录时，「逐字节迁入」就重新变成了含糊话。
        records = [record for group in ledger["copies"]
                   for record in (group.get("records") or [])
                   if record["target"].replace("\\", "/").endswith("/" + relative)]
        assert len(records) == 1, ("迁移台账里这份夹具的记录必须唯一",
                                   relative, [record["target"] for record in records])
        record = records[0]
        assert record["sha256_source"] == record["sha256_target"], \
            ("台账自己就没记下逐字节复制，之后的摘要比较就不再证明任何东西", relative, record)
        on_disk = hashlib.sha256((TARGET_ROOT / relative).read_bytes()).hexdigest()
        assert on_disk == record["sha256_target"], (
            "迁入字节已被改动，之后每条按它下的结论都要重算", relative, on_disk,
            record["sha256_target"])

    document = _sample()
    contracts.validate_rir(document, project_root=TARGET_ROOT)
    rasters = [node for node in _nodes_of(document) if node.get("type") == "raster"]
    assert len(rasters) == 1, ("raster 支没有被真正走到：文档里的栅格节点数不是 1",
                               [node.get("id") for node in rasters])
    node = rasters[0]
    assert document["schemaVersion"] == "design-lab/reconstruction-ir/v1", document
    assert (document["canvas"]["width"], document["canvas"]["height"]) == (64, 64), document["canvas"]
    declared = node["raster"]["path"]
    assert declared.startswith(".hermes/task-runtime/"), declared
    assert not (TARGET_ROOT / PurePosixPath(declared)).exists(), (
        "样本声明的原件 PNG 竟然在本仓存在——它从不在来源仓的 Git 里，这里出现的是谁放的？")


def test_relative_and_absolute_project_roots_reach_the_same_raster_verdict(tmp_path):
    """同一条合法 raster.path，根写成相对还是绝对必须给同一个答案。

    这条是为一个归因错位写的：`_require_project_relative` 把 `project_root` 原样留下，
    却拿 `resolve()` 之后的绝对路径去和它比 inclusion，于是 `Path(".")` 当根时**任何**合法路径
    都被判"逃逸"，理由还是「reparse resolution escapes outside the project」——说的是一件没
    发生的事（与 §15.21 修掉的「包行读不到」说成「没绑指纹」同一类）。同文件的兄弟函数
    `plan_to_rir` 早就 `resolve()` 了，所以同一个特性里两处对"根"的归一化不一致。

    证明：
    * 三种写法（`Path(".")`、`Path(".").resolve()`、裸字符串 `"."`）在同一份未改动样本上
      结论一致，都是过——这一条在修复之前是红的；
    * 那句拒绝消息现在说得通：`layers/./x.png`、`layers//x.png`、`a/../b.png` 各自被
      「parent traversal and dot segments are forbidden」具名拒掉。此前只有 `..` 被拒，
      `.` 与空段被 PurePosixPath 归一化吃掉而静默通过，消息与实际行为不符；
    * 逃逸那一支仍有真主人：直接给 `_path_is_within` 一个真在项目外的绝对路径，它返回 False，
      所以那句话不是永远不成立的死代码；
    * 反斜杠那条也照旧被具名拒掉（不是被 schema 抢先），且一个含制表符的名字**仍然通过**——
      本节点把它当实测事实记下来，不声称策略覆盖控制字符。
    没证明：宿主对含制表符路径的行为；`.hermes` 那类隐藏目录前缀是否应当被允许（策略今天不管）。
    """
    from design_lab.reconstruction import contracts
    import os

    document = _sample()
    here = Path(os.getcwd())
    assert here == TARGET_ROOT, ("这条要在仓库根下跑，否则相对根的语义测不到东西", str(here))
    for root in (Path("."), Path(".").resolve(), "."):
        contracts.validate_rir(document, project_root=root)

    for sneaky in ("layers/./x.png", "layers//x.png", "a/../b.png", "../up.png"):
        with pytest.raises(contracts.ContractError, match="dot segments are forbidden"):
            contracts._require_project_relative(sneaky, "raster.path", TARGET_ROOT)
    with pytest.raises(contracts.ContractError, match="backslash paths are forbidden"):
        contracts._require_project_relative("layers" + chr(92) + "x.png", "raster.path", TARGET_ROOT)
    tabbed = contracts._require_project_relative("layers" + chr(9) + "x.png", "raster.path",
                                                 TARGET_ROOT)
    assert tabbed.name.startswith("layers\t"), repr(tabbed.name)

    outside = contracts._path_is_within(Path("C:/Windows/win.ini"), TARGET_ROOT.resolve())
    assert outside is False, ("逃逸判定恒真或恒假，那句 escapes 就成了装饰", outside)


def test_the_raster_path_reports_the_gates_a_real_document_actually_hits(tmp_path):
    """栅格节点在合法文档里走产品自己的函数，撞上的门按各自的名字报出来。

    三段都是现测的结论，不是挑了好听的那一段：
    ① 迁入的样本原样交给 `build_photoshop_job` 得到 `rounded or parameterized rect unsupported`
      ——它先在一个带参数 rect 上被拒，所以**不能**声称这条链撞的是 raster 门；
    ② 把文档收成只留那个 raster 节点（仍是合法 RIR）后得到 `raster remapping/alpha requires
      explicit preprocessed asset`——样本的 raster 带一条 sourceMappings，产品拒绝未预处理的
      重映射，这是真实门槛而不是缺口；
    ③ 再清掉 sourceMappings、把 crop 物成 PNG 实际尺寸、并把栅格放进 run root 之内，构建被接受，
      产出一个 `asset-texture-chip` 资源且路径落在 run root 里——这一句就是登记原先说"未被端到端
      演示"的那一半。
    两份派生文档都被断言为"与迁入字节不同"，样本本身在磁盘上一个字节没动。
    没证明：任何真实宿主执行过这个 job（没有拉起 Photoshop，也没写它的文档）；派生文档是设计成品
    （它们是测试构造）；`validate_objects` 适用于 Photoshop 形状（不适用，本节点因此不调用它）。
    """
    import copy
    from PIL import Image
    from design_lab.reconstruction import contracts
    from design_lab.reconstruction import adobe_job

    with Image.open(TARGET_ROOT / FLAT_PNG) as image:
        width, height = image.size
    sample = _sample()
    declared = [n for n in _nodes_of(sample) if n.get("type") == "raster"][0]["raster"]["path"]

    def expect_refusal(document, project, run_dir, message):
        with pytest.raises(adobe_job.AdobeJobError) as refused:
            adobe_job.build_photoshop_job(document, run_dir, text_styles={}, project_root=project)
        assert str(refused.value) == message, str(refused.value)

    project, run_dir = _stage(tmp_path, declared)
    expect_refusal(copy.deepcopy(sample), project, run_dir, RECT_GATE)

    solo = copy.deepcopy(sample)
    solo["layers"] = [[n for n in _nodes_of(sample) if n.get("type") == "raster"][0]]
    solo["layers"][0]["zOrder"] = 0
    contracts.validate_rir(solo, project_root=project)
    expect_refusal(solo, project, run_dir, REMAP_GATE)

    inside = ".project-local/task-runtime/kit-raster/layers/texture-chip.png"
    accepted = copy.deepcopy(solo)
    raster = accepted["layers"][0]["raster"]
    raster.update({"path": inside, "sourceMappings": [],
                   "crop": {"x": 0, "y": 0, "width": width, "height": height}})
    accepted["layers"][0]["bounds"] = {"x": 0, "y": 0, "width": width, "height": height}
    staged = project / PurePosixPath(inside)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes((TARGET_ROOT / FLAT_PNG).read_bytes())
    contracts.validate_rir(accepted, project_root=project)
    job = adobe_job.build_photoshop_job(accepted, run_dir, text_styles={}, project_root=project)
    assets = job.get("assets") or []
    assert [asset["id"] for asset in assets] == ["asset-texture-chip"], assets
    asset_path = Path(assets[0]["path"])
    assert run_dir.resolve() in asset_path.resolve().parents or asset_path.resolve() == run_dir.resolve(), (
        "资源路径不在 run root 之内，前面那句「落进 run root」是空话", str(asset_path))
    assert asset_path.is_file() and asset_path.stat().st_size == (TARGET_ROOT / FLAT_PNG).stat().st_size
    assert job["schemaVersion"], job

    assert json.dumps(accepted, sort_keys=True) != json.dumps(sample, sort_keys=True), (
        "派生文档与迁入样本逐字相同，那它就不是派生文档")
    assert _sample() == json.loads((TARGET_ROOT / RIR_SAMPLE).read_text(encoding="utf-8")), (
        "测试把迁入的样本改了")


DOMAIN_PACKS_DIR = ("domains/design/design_lab/resources/repo/design-lab/domain-packs")


def test_the_deferred_domain_pack_names_the_elements_this_tree_actually_lacks():
    """「要真人写设计内容」has to say which elements, and stay in step with the disk.

    The deferral used to exist only as a sentence in the entry, with a hand-typed count that was
    wrong twice over: the pack's tracked copies are 9 records rather than 18 path strings, and the
    elements missing from the directory are six, not five -- `handoff_contract` was left out, so
    the human queue was shorter than reality. The checker's own verdict is the authority here, so
    this node compares the register's enumeration against the files that are absent, using the
    element-to-filename map a compliant pack publishes. Add one of those files and this goes red
    with the new list: the deferral is a pointer at measured absence, not a permanent excuse.
    """
    entries = {e["id"]: e for e in json.loads(
        (TARGET_ROOT / "migration/deferral-register.json").read_text(encoding="utf-8-sig"))["entries"]}
    gate = entries["design.minigame_domain_pack"]

    reference = json.loads((TARGET_ROOT / DOMAIN_PACKS_DIR / "uiux-design/manifest.json")
                           .read_text(encoding="utf-8"))
    elements = reference["files"]
    pack_dir = TARGET_ROOT / DOMAIN_PACKS_DIR / "minigame-design"
    absent = sorted(name for name, relative in elements.items() if not (pack_dir / relative).exists())
    assert absent, ("参照包 uiux-design 的元素若也落在 minigame-design 里，下面的对照就没有意义")

    enumerated = [group.split("、") for group in re.findall(r"（([^）]*)）", gate["lift_condition"])]
    candidates = [group for group in enumerated if set(group) <= set(elements)]
    assert len(candidates) == 1, ("延期条款里没有唯一可识别的元素枚举", candidates)
    assert sorted(candidates[0]) == absent, (candidates[0], absent)

    pack = {p["directory"]: p for p in dp.build()["packs"]}["minigame-design"]
    assert pack["validation"] == dp.INVALID, pack
    checker_missing = sorted(re.findall(r"manifest missing files\.([a-z_]+) declaration",
                                         " ".join(pack["validationErrors"])))
    assert len(checker_missing) == pack["validationErrorCount"] - 1, \
        ("除信封那条以外，每条理由都应当是一个 files.* 声明", checker_missing,
         pack["validationErrorCount"])
    declared_only = sorted(set(checker_missing) - set(absent))
    assert all((pack_dir / elements[name]).exists() for name in declared_only), \
        ("这些元素在校验器里被点名，磁盘上却也不存在：那它们属于真人那一类，"
         "延期条款的元素枚举该按现读改写", declared_only)

