# Draft Release URL provenance

## Failure pattern

A GitHub draft release created with `gh release create <tag> --draft` can expose a temporary URL such as:

```text
.../releases/tag/untagged-<opaque-id>
```

After publication, the canonical URL is:

```text
.../releases/tag/<tag>
```

An artifact-side `release-identity.json` generated before draft creation should bind the eventual canonical tag URL. Comparing it directly to the draft `html_url` makes a valid draft fail closed during readback.

## Correct check

```powershell
$canonicalReleaseUrl = "$env:GITHUB_SERVER_URL/$env:GITHUB_REPOSITORY/releases/tag/$env:GITHUB_REF_NAME"
if ($identity.release.url -ne $canonicalReleaseUrl) {
  throw "canonical release identity URL mismatch"
}
```

Keep separate checks for draft state, asset set, provider digests, downloaded SHA-256, tag target, exact CI URL/run, and final public Release URL. If the run fails after creating an immutable tag, preserve the tag and unpublished draft; fix the workflow and use a new immutable remediation version.

## Observed recovery evidence

In the v0.4.2 remediation run, the remote draft exposed:

```text
https://github.com/DTALEX66/Cognitive-Loop-OS/releases/tag/untagged-731ae7beb3c9dd482338
```

while the downloaded identity contained the eventual canonical URL:

```text
https://github.com/DTALEX66/Cognitive-Loop-OS/releases/tag/v0.4.2
```

The failing assertion was the combined provenance check for `source.ci_run` or `release.url`. Asset provider digests, downloaded SHA-256 values, tag target, commit, and tree had already passed. The safe response was to leave `v0.4.2` immutable and unpublished, patch the workflow to compare `$canonicalReleaseUrl`, and move the retry to a new remediation version rather than rerunning or rewriting the failed tag.
