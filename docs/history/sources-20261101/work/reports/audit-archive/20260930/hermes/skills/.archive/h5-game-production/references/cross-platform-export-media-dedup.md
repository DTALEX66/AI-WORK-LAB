# Cross-Platform Export Media Dedup (canonical-source governance)

## When
A Canvas mini-game with multiple generated targets (android-minigame, douyin-minigame,
wechat-minigame, android-webview assets) commits the SAME media bytes into each target
directory, inflating repo size and doubling/quadrupling every PNG/WAV.

## Symptom
A ~231 MiB `minigame-runtime/` where a single media family exists in 4–5 byte-identical
copies. Content-hash scan reports dozens of duplicate groups and tens of MB of pure waste.

## Detect (content-hash, not filename)
Hash every TRACKED media blob via `git show HEAD:<path>` (works without a full checkout —
no need to read the working tree), group by sha256, count groups with >1 member.

```python
import subprocess, hashlib, collections
def git_ls(p):  # tracked files under prefix
    r = subprocess.run(['git','ls-files',p],capture_output=True,text=True,cwd=ROOT)
    return [l for l in r.stdout.split('\n') if l]
media = git_ls('minigame-runtime')  # filter png/wav/gif/mp3/jpg
groups = collections.defaultdict(list)
for f in media:
    blob = subprocess.run(['git','show',f'HEAD:{f}'],capture_output=True,cwd=ROOT).stdout
    groups[hashlib.sha256(blob).hexdigest()[:16]].append(f)
dups = {h:ps for h,ps in groups.items() if len(ps)>1}
# waste per group = size(copy) * (len(copies)-1); size via `git cat-file -s HEAD:<f>`
```

**This is the authoritative number.** 363 media → 111 unique hashes → 90 duplicate groups →
~106 MB waste is a precise, auditable finding (matches an independent audit exactly).

## Root cause / the fix pattern
The build already regenerates the per-platform copies from canonical sources:

```
build.js syncAssetDirectory():
  assets/minigame-audio/                      ->  <target>/audio/           (every platform)
  games/.../abnormal_elevator_visual_assets/  ->  <target>/visual/          (every platform)
  (android-minigame, douyin-minigame, wechat-minigame all produced this way)
prepare-android-webview.mjs:  rebuild + copy ->  android-webview/app/src/main/assets/
```

So the DERIVED per-platform copies (`android-minigame/visual`, `douyin-minigame/visual`,
`wechat-minigame/visual`, each `*/audio`, and the webview asset copy) are build outputs, not
canonical. Governance is:
1. **Keep canonical only**: `assets/minigame-audio/` and
   `games/.../abnormal_elevator_visual_assets/` stay tracked (unique bytes).
2. **Untrack + gitignore the derived platform dirs**; the build regenerates them.
3. **Gate it**: run `npm test` + the deterministic drift gate after removal; prove a fresh
   build reproduces everything and `git status` stays clean.
4. Large canonical GIF/PNG (>1 MiB, e.g. 8–12 MB generated loops) are unique copies — do NOT
   delete them as "duplicates"; decide separately under LFS/Release-Artifact policy.
5. Expected win ≥80% of measured waste.

## Pitfalls
- **Derived dirs are BOTH gitignored AND tracked** (`.gitignore` has `android-minigame/`,
  `android-webview/app/src/main/assets/`, but the files are `git ls-files`-listed). Removing
  them needs `git rm` + the ignore already present. This gitignore-vs-committed-artifact
  conflict is itself governance debt.
- **Don't delete large canonical generated assets** just because they're big — measure
  duplicates by content hash across the WHOLE tree first; only byte-identical copies are
  dedup candidates.
- Do not run a heavyweight full build immediately after deleting caches if it recreates
  hundreds of MB; use `npm test` + target bundle checks + drift gate and state which
  heavyweight build was intentionally not rerun.
- Report before/after byte counts and keep the list of remaining large directories.
