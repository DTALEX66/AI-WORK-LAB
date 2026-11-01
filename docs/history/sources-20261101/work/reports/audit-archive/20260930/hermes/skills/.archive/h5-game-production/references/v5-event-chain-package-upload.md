# V5 Event-Chain, Package, and Upload Closeout

## Use when

Use this reference when a WeChat/Douyin Canvas game has scheduled event chains, generated platform bundles, large visual assets, and a user request to continue or upload everything.

## Boundary matrix

| Boundary | Required evidence | Common false positive |
|---|---|---|
| Content → scheduler | content IDs resolve; first and later chain steps install | JSON exists but IDs are unreachable |
| Scheduler → Runtime | every installed `currentShift` creates a new pending inspection | `currentShift` changes while `inspection` stays resolved |
| Renderer → decision | visible quick/identity/classification/high-risk buttons carry semantic decision metadata | click falls through to legacy `performAction()` |
| Decision → chain | accepted result advances exactly one step; timeout has explicit wrong outcome | tutorial handoff advances and skips chain step 0 |
| Consequence → next shift | flags select ending; modifiers change next shift once and clear | modifier is stored but never consumed |
| Runtime → bundle | regenerated WeChat and Douyin bundles contain the current WIP | source is fixed but tracked bundle is stale |
| Bundle → upload | local HEAD equals remote branch SHA | local commit is reported as uploaded without `ls-remote` readback |

## Safe package split

If the repository already has a canonical asset directory such as `visual/`:

1. Keep the manifest paths and copied filesystem paths unchanged.
2. Declare that directory as a native subpackage in generated `game.json`, for example:

```json
{
  "subPackages": [{ "root": "visual", "name": "v5-visual" }]
}
```

3. Measure separately:
   - non-subpackage/main bytes;
   - subpackage bytes;
   - total bytes;
   - stale legacy directories.
4. Confirm the build does not leave historical output such as an old game directory under the target root.
5. Test asset manifest count and generated output count together; an alias must be explicit and included in the manifest contract.

This avoids a path migration that fixes bytes but breaks runtime image loading. It also makes a large visual pack visible to package-limit gates rather than hiding it under an arbitrary folder.

## Reusable commands

```bash
npm test
npm run douyin:build
npm run douyin:check
node build.js wechat
node scripts/check-wechat-bundle.mjs --strict
git diff --check
```

Package report, using POSIX shell/Python on Windows Git-Bash:

```bash
python - <<'PY'
import os
for target in ['wechat-minigame', 'douyin-minigame']:
    total = main = sub = legacy = 0
    for root, dirs, files in os.walk(target):
        for name in files:
            p = os.path.join(root, name)
            size = os.path.getsize(p)
            total += size
            rel = os.path.relpath(p, target)
            if '电梯异常' in rel:
                legacy += size
            elif rel.startswith('visual' + os.sep):
                sub += size
            else:
                main += size
    print(target, {'total': total, 'main': main, 'subpackage': sub, 'legacy': legacy})
PY
```

## Protected upload sequence

```bash
git diff --name-only
git add -A
if git diff --cached --name-only | grep -E '(^|/)(release\.config\.json|project\.private\.config\.json|\.tmp/)'; then
  echo 'forbidden file staged' >&2
  exit 1
fi
git diff --cached --check
git commit -m 'feat(game001): complete V5 night protocol runtime'
git push origin HEAD
local_sha=$(git rev-parse HEAD)
remote_sha=$(git ls-remote origin refs/heads/<branch> | cut -f1)
printf 'LOCAL_SHA=%s\nREMOTE_SHA=%s\n' "$local_sha" "$remote_sha"
test "$local_sha" = "$remote_sha"
git status --short --branch
```

Use a separate `docs:` commit for the evidence update if the project keeps code and evidence commits distinct. Never include private release overlays in a convenience `git add -A` without an explicit staged-path rejection.

## Claim discipline

- `npm test` and strict bundle checks prove development acceptance, not real platform upload readiness.
- A `touristappid` or placeholder fallback is acceptable only for development checks; release readiness must fail closed until private AppID and ad units are injected.
- A browser acceptance screenshot is not a WeChat/Douyin Developer Tool or device proof.
- Report exact package bytes, exact test counts, exact branch, and exact local/remote SHA.
