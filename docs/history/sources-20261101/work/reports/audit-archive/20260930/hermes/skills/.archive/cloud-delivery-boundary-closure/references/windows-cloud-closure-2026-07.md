# Windows/cloud closure evidence pattern

## Boundary reproduction

A project test bootstrap set `TMP`, `TEMP`, and `TMPDIR` to `.hermes/task-runtime`, but pytest still created:

```text
C:\Users\ALEX\AppData\Local\Temp\pytest-of-ALEX\pytest-378\...
```

The regression failed because `tempfile.gettempdir()` remained `C:\Users\ALEX\AppData\Local\Temp`. The durable fix was to set `tempfile.tempdir` explicitly during pytest bootstrap, set `PYTHONPYCACHEPREFIX` to a project-local ignored path, and assert both `tmp_path` and `tempfile.gettempdir()` containment.

After pytest processes exited, only the exact project-generated `pytest-*` directories were removed. Windows read-only files required an `onerror` callback that restored write permission before retrying. The external prefix was rescanned and confirmed absent.

## External-path classification

A same-name directory under the user home was a separate Git worktree with a different remote repository and a dirty `.gitignore`. It was preserved rather than deleted. A project-specific AppData WebView2 profile had no recent writes, no active process used its path, and authoritative development/installed targets already existed under the project `.hermes/task-runtime`; only that exact stale profile was removed.

## Cloud delivery closure

The first remote push landed only on a feature branch while the repository default branch stayed unchanged. A connected repository reader therefore continued to see the old default-branch tree. The corrected sequence is: verify the complete worktree, commit, push, create a PR to the default branch, verify head/base SHAs and CI, merge only when authorized and green, then read back the default-branch SHA and key files. Repository description metadata changing is not evidence that branch file content changed.
