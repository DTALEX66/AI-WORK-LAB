---
name: github-auth
description: "GitHub auth setup: HTTPS tokens, SSH keys, gh CLI login."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Authentication, Git, gh-cli, SSH, Setup]
    related_skills: [github-pr-workflow, github-code-review, github-issues, github-repo-management]
---

# GitHub Authentication Setup

This skill sets up authentication so the agent can work with GitHub repositories, PRs, issues, and CI. It covers two paths:

- **`git` (always available)** — uses HTTPS personal access tokens or SSH keys
- **`gh` CLI (if installed)** — richer GitHub API access with a simpler auth flow

## Detection Flow

When a user asks you to work with GitHub, run this check first:

```bash
# Check what's available
git --version
gh --version 2>/dev/null || echo "gh not installed"

# Check if already authenticated
gh auth status 2>/dev/null || echo "gh not authenticated"
git config --global credential.helper 2>/dev/null || echo "no git credential helper"
```

**Decision tree:**
1. If `gh auth status` shows authenticated → you're good, use `gh` for everything
2. If `gh` is installed but not authenticated → use "gh auth" method below
3. If `gh` is not installed → use the SSH/public Git method below; stop before GitHub API writes or unattended private HTTPS operations

---

## Method 1: Git-Only Git Transport (No gh, No API)

This works on any machine with `git` installed. SSH and public repository operations
do not require `gh`; persistent private HTTPS authentication must be configured by
the user through an OS-backed credential manager. The agent never reads, creates,
or persists token values.

### Option A: HTTPS with Personal Access Token (User-operated, one-shot)

This can be used for a user-operated one-shot Git operation. It does not establish
persistent unattended authentication by itself.

**Step 1: Create a personal access token**

Tell the user to go to: **https://github.com/settings/tokens**

- Click "Generate new token (classic)"
- Give it a name like "hermes-agent"
- Select scopes:
  - `repo` (full repository access — read, write, push, PRs)
  - `workflow` (trigger and manage GitHub Actions)
  - `read:org` (if working with organization repos)
- Set expiration (90 days is a good default)
- Copy the token — it won't be shown again

**Step 2: Perform a user-operated authenticated Git operation**

```bash
# The user may provide credentials interactively for this one operation.
# The agent must not type, capture, print, or persist the token.
# Username: <their-github-username>
# Password: <paste the personal access token, NOT their GitHub password>
git ls-remote https://github.com/<their-username>/<any-repo>.git
```

Do not assume credentials are saved or available to later commands. For repeated
private HTTPS or unattended work, the user must install `gh` and run
`gh auth setup-git`, or configure an OS-backed credential manager themselves.

**Alternative: OS-backed credential manager (user-owned)**

```bash
# The user may configure the platform credential manager outside this workflow.
# Do not use plaintext `store`, process-local token helpers, or remote URLs with credentials.
```

**Alternative: set the token directly in the remote URL (per-repo)**

```bash
# Embed token in the remote URL (avoids credential prompts entirely)
# Never embed credentials in a remote URL. Keep the remote credential-free and use `gh auth setup-git`.
```

**Step 3: Configure repository-local git identity (user-authorized)**

```bash
# Required for commits in this repository — set name and email only after user confirmation
git config --local user.name "Their Name"
git config --local user.email "their-email@example.com"
```

**Step 4: Verify**

```bash
# Optional interactive read check; it may prompt again because one-shot credentials are not persisted
git ls-remote https://github.com/<their-username>/<any-repo>.git

# Verify repository-local identity
git config --local user.name
git config --local user.email
```

### Option B: SSH Key Authentication

Good for users who prefer SSH or already have keys set up.

**Step 1: Check for existing SSH keys**

```bash
if [ -e ~/.ssh/id_ed25519 ] || [ -e ~/.ssh/id_ed25519.pub ]; then
  echo "id_ed25519 already exists; stop and choose a reviewed path"
else
  echo "No id_ed25519 key found"
fi
```

**Step 2: Generate a key if needed**

This writes to the external `~/.ssh` path and must never be run by the agent.
The user must explicitly authorize that exact path and operation, confirm that
both files are absent, and enter a passphrase interactively. Do not use an empty
passphrase or overwrite an existing key.

```bash
# User-operated only, after the authorization and collision checks above.
# ssh-keygen prompts the user for a passphrase; do not pass -N from automation.
ssh-keygen -t ed25519 -C "their-email@example.com" -f ~/.ssh/id_ed25519

# User-operated only: display public material for GitHub registration.
cat ~/.ssh/id_ed25519.pub
```

Tell the user to add the public key at: **https://github.com/settings/keys**
- Click "New SSH key"
- Paste the public key content
- Give it a title like "hermes-agent-<machine-name>"

**Step 3: Test the connection**

```bash
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated..."
```

**Step 4: Configure this repository to use SSH (user-authorized)**

```bash
# Do not rewrite GitHub URLs globally; change only the confirmed repository remote
git remote set-url origin git@github.com:<owner>/<repo>.git
```

**Step 5: Configure repository-local git identity (user-authorized)**

```bash
git config --local user.name "Their Name"
git config --local user.email "their-email@example.com"
```

Changing a remote or commit identity is a separate write. Confirm the target
repository and obtain explicit user authorization before running either command.

---

## Method 2: gh CLI Authentication

If `gh` is installed, it handles both API access and git credentials in one step.

### Interactive Browser Login (Desktop)

```bash
gh auth login
# Select: GitHub.com
# Select: HTTPS
# Authenticate via browser
```

### Token-Based Login (Headless / SSH Servers)

```bash
gh auth login

# Set up git credentials through gh
gh auth setup-git
```

### Verify

```bash
gh auth status
```

---

## GitHub API Access

GitHub API operations require an authenticated `gh` client or another explicitly
approved client operated by the user. When `gh` is unavailable or unauthenticated,
stop and report the blocker; do not construct curl requests with tokens.

### Safe Auth Boundary

Never read, parse, copy, or extract values from `.env`, `credential files`, SSH private keys, OAuth stores, or credential databases. Do not embed a token in a remote URL or command argument. Use the supported interactive flow:

```bash
gh auth status
# If unauthenticated, ask the user to run:
gh auth login
gh auth setup-git
```

For API operations, use `gh api` after `gh auth status` succeeds. If `gh` is unavailable or unauthenticated, stop and report the blocker; never fall back to credential-file extraction. Only an already-provided, redacted-safe environment classification may be reported as `GITHUB_TOKEN=present`, never its value.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | GitHub disabled password auth. Use a personal access token as the password, or switch to SSH |
| `remote: Permission to X denied` | Token may lack `repo` scope — regenerate with correct scopes |
| `fatal: Authentication failed` | Cached credentials may be stale — run `git credential reject` then re-authenticate |
| `ssh: connect to host github.com port 22: Connection refused` | Try SSH over HTTPS port: add `Host github.com` with `Port 443` and `Hostname ssh.github.com` to `~/.ssh/config` |
| Credentials not persisting | Use `gh auth status` and `gh auth setup-git`; do not enable plaintext `store` or process-local token helpers |
| Multiple GitHub accounts | Use SSH with different keys per host alias in `~/.ssh/config`, or per-repo credential URLs |
| `gh: command not found` + no sudo | Use git-only Method 1 above — no installation needed |
