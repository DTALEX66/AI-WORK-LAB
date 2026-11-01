# SPDX-License-Identifier: MIT
"""DL-CORE-001: object-model schema round-trip tests.

Validates that every core object in object-model.json:
1. has a resolvable schemaRef (schema file exists),
2. the schema parses as valid JSON Schema,
3. a minimal fixture instance round-trips (validates against the schema).

Requires: jsonschema (declared in requirements.txt).
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore

OBJECT_MODEL = ROOT / "design-lab" / "config" / "object-model.json"

#: Minimal instances the synthesiser below cannot build, hand-built instead of skipped.
#: ``design-system`` is the one object whose contract is a recursive ``$ref``-rooted document:
#: ``interop-dtcg-document.schema.json`` puts its rules in ``$defs/rootGroup`` (``minProperties: 1``
#: plus ``patternProperties`` for non-``$`` members), and ``_build_minimal`` walks only a schema's own
#: ``required``/``properties``, so it synthesised ``{}`` and the schema correctly refused it. The
#: document below is the smallest thing the product's own semantic validator accepts, so this row now
#: proves the contract is satisfiable rather than excusing it -- and it is checked against
#: ``dtcg.validate_document`` in ``test_design_system_instance_is_semantically_valid`` too, which the
#: structural schema alone cannot do ($type inheritance across groups is unresolved at schema level).
MINIMAL_INSTANCES = {
    "design-system": {"brand": {"$type": "color", "$value": "#316CFF"}},
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@unittest.skipIf(jsonschema is None, "jsonschema not installed")
class ObjectModelRoundTripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_json(OBJECT_MODEL)
        cls.objects = cls.model["objects"]
        cls.schemas_dir = ROOT / "design-lab" / "schemas"

    def test_all_objects_have_resolvable_schema_ref(self):
        missing = []
        for obj in self.objects:
            ref = obj.get("schemaRef", "")
            schema_path = self.schemas_dir / Path(ref).name
            if not schema_path.exists():
                missing.append(f"{obj['id']} -> {ref}")
        self.assertEqual(missing, [], f"missing schemas: {missing}")

    def test_all_schemas_parse_as_valid_json_schema(self):
        bad = []
        for obj in self.objects:
            ref = obj.get("schemaRef", "")
            schema_path = self.schemas_dir / Path(ref).name
            if not schema_path.exists():
                continue
            try:
                schema = load_json(schema_path)
                jsonschema.Draft202012Validator.check_schema(schema)
            except Exception as exc:
                bad.append(f"{obj['id']}: {exc}")
        self.assertEqual(bad, [], f"invalid schemas: {bad}")

    def _resolve(self, ref: str, root: dict) -> dict:
        """Follow a local `$ref`.

        The synthesiser used to fall through to `"test-value"` for any property it could
        not type, and a `$ref` has no `type` of its own -- so `juror`, which is an object
        in `#/$defs/juror`, was built as a string and the round-trip convicted the schema
        for the builder's blind spot. That surfaced when object-model re-pointed
        quality-report onto assurance-jury-record-v2.schema.json (commit 463416fa).
        """
        if not ref.startswith("#/"):
            self.fail(f"only local $refs are supported here, got {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node.get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            self.fail(f"$ref {ref} does not resolve inside the document")
        return node

    def _build_minimal(self, schema: dict, depth: int = 0, root: dict | None = None) -> dict:
        """Build a minimal valid instance from schema constraints."""
        root = schema if root is None else root
        if depth > 3:
            return {}
        instance = {}
        required = schema.get("required", [])
        for req in required:
            prop = schema.get("properties", {}).get(req, {})
            instance[req] = self._value_for(prop, depth, key=req, root=root)
        return instance

    def _value_for(self, prop: dict, depth: int, key: str = "", root: dict | None = None) -> object:
        if "$ref" in prop:
            return self._value_for(self._resolve(prop["$ref"], root or prop), depth,
                                   key=key, root=root)
        if "const" in prop:
            return prop["const"]
        if "enum" in prop:
            return prop["enum"][0]
        t = prop.get("type")
        if t == "array":
            items = prop.get("items", {})
            min_items = prop.get("minItems", 0)
            return [self._value_for(items, depth + 1, root=root)] * max(1, min_items)
        if t == "object":
            return self._build_minimal(prop, depth + 1, root)
        if t == "integer" or t == "number":
            return 1
        if t == "boolean":
            return True
        # A pattern that asks for a digest has to be answered with one. This is tried before the
        # legacy contentHash branch because that one emits an all-zero digest, which
        # assurance-jury-record-v2.schema.json rejects on purpose ("an all-zero digest is not a
        # judged artifact") -- the field name is hashed so the value is nonzero and reproducible.
        if "sha256:" in (prop.get("pattern") or ""):
            return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
        # Same blind spot, second shape: `#/$defs/rfc3339` guards the timestamp with a
        # pattern (the installed jsonschema enforces no `format`), and a string-typed
        # property with no pattern-aware builder here produced "test-value" for it.
        # Fixed rather than now(): a fixture that moves with the clock cannot be re-checked.
        if "\\d{4}-\\d{2}-\\d{2}" in (prop.get("pattern") or ""):
            return "2026-10-08T09:00:00Z"
        # contentHash-style fields require sha256:<64hex>; others use test-value
        if key in ("contentHash", "content_hash", "content_hash64"):
            return "sha256:" + "0" * 64
        return "test-value"

    def test_minimal_fixture_round_trips(self):
        """A minimal fixture instance must validate against each schema."""
        failures = []
        for obj in self.objects:
            ref = obj.get("schemaRef", "")
            schema_path = self.schemas_dir / Path(ref).name
            if not schema_path.exists():
                failures.append(f"{obj['id']}: schema missing")
                continue
            schema = load_json(schema_path)
            instance = MINIMAL_INSTANCES.get(obj["id"]) or self._build_minimal(schema)
            try:
                jsonschema.validate(instance, schema)
            except jsonschema.ValidationError as exc:
                failures.append(f"{obj['id']}: {exc.message[:120]}")
        self.assertEqual(failures, [], f"round-trip failures: {failures}")

    def test_design_system_instance_is_semantically_valid(self):
        """Structure is not enough for a token document, so the product's own validator runs too."""
        sys.path.insert(0, str(ROOT / "src"))
        from design_lab.interop import dtcg

        schema = load_json(self.schemas_dir / "interop-dtcg-document.schema.json")
        document = MINIMAL_INSTANCES["design-system"]
        jsonschema.validate(document, schema)
        report = dtcg.validate_document(document)
        self.assertEqual(1, report["token_count"],
                         f"the minimal document must carry exactly one token: {report}")
        self.assertTrue(report["canonical"], report)
        self.assertEqual({"color": 1}, report["types"], report)

    def test_object_count(self):
        self.assertGreaterEqual(len(self.objects), 11, "taskpack requires >= 11 core objects")


if __name__ == "__main__":
    unittest.main()
