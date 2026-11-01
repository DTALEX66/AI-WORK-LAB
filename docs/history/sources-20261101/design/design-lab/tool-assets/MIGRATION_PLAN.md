# Tool Asset Migration Plan

`knowledge/tool-control/scripts/` contains executable automation assets and must not receive new scripts. Existing assets remain in place until the following per-family migration is verified:

1. Inventory each file, SPDX/license sidecar, hash, registry and SBOM reference.
2. Identify every in-repository consumer and compatibility path.
3. Move one family at a time into `tool-assets/{photoshop,illustrator,inkscape,comfyui,style-dictionary}` or its owning creative-tool adapter.
4. Add a compatibility mapping, update all consumers, registry, SBOM and license coverage.
5. Run the complete verifier chain; only then retire the old active path.

No external tool is invoked by this migration plan, and no claim of runtime usability is derived from the archive.
