---
name: project-init-from-spec
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/project-init-from-spec/SKILL.md
---

---
name: project-init-from-spec
description: "Turn a product specification document into a complete project scaffold — directory structure, documentation, data models, shared code, git init + GitHub push."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [project, scaffolding, initialization, product-spec, data-modeling]
    related_skills: [github-repo-management, github-auth]
---

# Project Initialization from Specification

Take a product spec doc (user's description of what they want to build) and turn it into a real, working project skeleton pushed to GitHub.

## Triggers

- User pastes a long spec doc ("# Project Name\n\n## Goal\n...") and says "review", "set up", "initialize", or "let's start"
- User mentions a new repo name + project directory and provides any amount of functional description
- User says "全面梳理这个项目" (comprehensive review) with a spec attached

## Sequence

### 1. Read & Analyze the Spec

Extract these dimensions from the spec:

| Dimension | What to look for |
|-----------|-----------------|
| **Core value prop** | What does this do? One sentence. |
| **Phases/Milestones** | Explicit or implicit staging (MVP vs later) |
| **Tech stack hints** | Frontend framework, language, database, backend |
| **Data entities** | People, Content, Songs, Teams — every noun that stores data |
| **Core workflows** | User actions: add, search, filter, share, export |
| **Explicit boundaries** | "Not a video downloader", "no AI", "Phase 1 doesn't need X" |

### 2. Create Project Documentation

Always create these under `docs/`:

- **README.md** — Project identity, one-liner, phases table, tech stack, directory structure, dev commands
- **ARCHITECTURE.md** — Architecture diagram (ASCII/mermaid), module breakdown, data flow, Phase 2+ extension points
- **DATA_MODEL.md** — Every entity as a JSON example + TypeScript interface, field-by-field docs, enums, dedup rules
- **PHASE_PLAN.md** — Sprint breakdown for Phase 1, future phases as bullet lists, explicit "NOT included" section per phase

### 3. Design Shared Data Models

Create shared TypeScript types under `shared/models/`:

```typescript
// For each entity in the spec, write:
interface EntityName {
  id: string;           // prefix_xxx format
  name: string;         // display name
  // All fields mentioned in the spec
  status: EntityStatus; // enum if status is tracked
  created_at: string;   // ISO date
  updated_at: string;
}

// Define ALL enums from the spec
type ContentStatus = 'NEW' | 'SAVED' | 'SEEN' | 'IGNORED' | 'BLOCKED';
```

Pattern: entities get string IDs with prefixes (`person_xxx`, `content_xxx`), timestamps are ISO strings, enums capture every state mentioned in the spec.

### 4. Create Shared Utilities

Shared utils go under `shared/utils/`. Common ones from spec analysis:

- **`id.ts`** — `generateId(prefix)` using timestamp + random
- **`platform.ts`** — URL pattern matching (platform identification from domain)
- **`slug.ts`** — name-to-slug conversion for URL-safe identifiers

### 5. Framework Scaffold

Create the appropriate sub-package under `packages/`:

| Stack hint | Scaffold pattern |
|-----------|-----------------|
| uni-app / mini-program | `packages/fan-memory-app/` with `src/pages/` (one dir per page), `src/components/`, `src/stores/`, `src/utils/`, `src/models/` |
| React / Next.js | `packages/web/` with standard `src/app/` or `src/pages/` |
| Python (FastAPI) | `packages/backend/` with `src/api/`, `src/services/`, `src/models/`, `src/db/` |

Create at minimum:
- `package.json` (or `pyproject.toml` / `requirements.txt`)
- Framework-specific config (e.g. `pages.json` for uni-app)

### 6. Page/Module Skeletons

Create one directory per page/module mentioned in the spec, even if empty. This maps the spec's mental model directly to the filesystem. Example for Fan Memory OS:

```
src/pages/
├── index/          # Home: star list, recent updates
├── star/           # Star profile page
├── collection/     # Full collection library
├── timeline/       # Chronological view
├── search/         # Full-text + multi-dimension filter
├── reminder/       # Alerts and calendar
└── settings/       # Import/export, data management
```

### 7. Git Setup & Push

```bash
cd /path/to/project
git init
git branch -m main
git add -A
git commit -m "🎬 init: <Project Name> 项目初始化

- README: project overview
- ARCHITECTURE: layered architecture
- DATA_MODEL: complete data model
- PHASE_PLAN: phased development roadmap
- shared/models: TypeScript type definitions
- shared/utils: utility functions
- packages/<app>: framework scaffold"
git remote add origin git@github.com:<user>/<repo>.git
git push -u origin main
```

## Pitfalls

- **Don't over-commit to tech stack decisions** the spec only hints at. If the spec says "mini-program or app", scaffold for uni-app (it compiles to both). Don't pick Flutter unless the spec explicitly names it.
- **Don't build any actual features** in the init phase. The scaffold is the directory structure, types, and docs — no business logic, no services, no UI components beyond empty page files.
- **Don't install dependencies** during scaffold. The `package.json` lists them but `npm install` is a Sprint 1 task.
- **Explicit boundaries in the spec** go into PHASE_PLAN.md's "Not included" section verbatim. This protects against scope creep later.
- **CRLF warnings on Windows** are normal for `git add`. They don't affect functionality and you don't need to fix them.
- **Commit message should be descriptive but not excessive** — ~10 bullet points summarizing what was created, consistent with the user's project convention (🎬 init: prefix).

## Verification

After push, verify with:
```bash
gh repo view <user>/<repo> --json name,isEmpty,defaultBranchRef
# Expected: isEmpty=false, defaultBranchRef.name=main
```

Also confirm the directory structure is correct:
```bash
ls -R <project_dir>
```

## Post-Scaffold: Sprint Execution Pattern

After the scaffold is pushed, the user typically wants to go straight into implementation (Sprint 1+). The pattern below works for any Phase 1 MVP.

### Sprint 1 — Framework & Core Services

**Goal:** Install deps, create working build, implement core services.

1. **Install dependencies** — `npm install --legacy-peer-deps` (Windows alpha packages)
2. **Create framework config** — `vite.config.ts`, `tsconfig.json`, `pages.json` (routing + tabBar)
3. **Create entry files** — `main.ts`, `App.vue` (with global styles), `index.html` (for H5 builds)
4. **Implement StorageService** — Wrap `uni.setStorageSync`/`uni.getStorageSync` with typed `LocalDatabase` interface
5. **Create Pinia stores** — One per primary entity (person, content, team)
6. **Build page stubs** — Every route gets a minimal Vue component
7. **Run framework build** — `npm run build:h5` to verify the pipeline works

**Vue 3 import rules (critical):**

| Symbol | Import from | Notes |
|--------|-------------|-------|
| `ref`, `computed`, `reactive` | `'vue'` | Standard Vue 3 |
| `onShow`, `onLoad`, `onHide` | `'@dcloudio/uni-app'` | NOT from `vue` |
| `getCurrentPages` | **Global** | Do NOT import |
| `navigateTo`, `showToast` | `uni.xxx` global | Or import from `@dcloudio/uni-app` |

**Build errors & fixes:**

| Error | Fix |
|-------|-----|
| `"onShow" is not exported by "vue"` | Import `onShow` from `@dcloudio/uni-app` |
| `"getCurrentPages" is not exported` | Use as global, do not import |
| `Could not resolve entry module "index.html"` | Create `index.html` at project root |
| `Cannot find module 'vite'` | `npm install vite@^5.0.0` |
| `Cannot find module '@vitejs/plugin-vue'` | `npm install @vitejs/plugin-vue` |

**Framework build verification:**
```bash
npm run build:h5
# Expected: "DONE Build complete."
```

### Sprint 2 — UI Polish & Navigation

**Goal:** Connect all pages into a navigable app, add UX polish.

1. **TabBar icons** — Create SVG icons (5 pairs for normal/active states)
2. **Page navigation** — Every card/row click navigates to a detail or edit page
3. **Toast utility** — Unified `showToast()`, `showSuccess()`, `confirm()` helpers
4. **Page transitions** — Add `animationType: "slide-in-right"` in `pages.json`
5. **Global animations** — `fadeIn`/`cardIn` CSS keyframes in `App.vue`
6. **Settings links** — Wire up data management, team management, block rules
7. **Build verification** — Confirm all page imports resolve

### Sprint 3+ — Feature Completion

For Phase 1 MVP, the remaining features follow a pattern:

1. **Detail/Edit pages** — One per entity (Person, Content, Team). Fields mirror data model. Save calls `store.updateX(id, {...})`.
2. **Filtering** — Add `filters` to list pages (all/unwatched/seen, by platform, by person)
3. **Settings — Import/Export** — `exportJSON()` copies to clipboard, `importJSON()` with validation
4. **Block rules** — CRUD UI for `IgnoreRule` entities with picker-based type selection
5. **Core logic tests** — Pure-function test script (see below)

### Verification Test Script

Create `scripts/test-core-logic.js` after scaffold, before building UI:

```javascript
// Copy pure functions from shared/utils/* into Node.js-compatible versions
// Run: node scripts/test-core-logic.js

function assertEqual(actual, expected, name) { ... }
function identifyPlatform(url) { ... }  // copy from shared/utils/platform.ts
function generateId(prefix) { ... }     // copy from shared/utils/id.ts
// ... test every platform, ID generation, and simulate full CRUD flow
```

Benefits: zero deps, runs in any Node, catches spec→code mapping errors before UI work.

## Recommended Follow-up: Core Logic Testing

After scaffold is pushed, write a **pure-function test script** that validates the business logic layer without framework dependencies (no uni-app/Vue runtime needed). This catches spec→code translation bugs before you build UI.

Location: `scripts/test-core-logic.js` (or the project's test convention)

What to test (copy the pure functions into the script verbatim):

| Layer | What to test | Example |
|-------|-------------|---------|
| **Platform identification** | Every platform URL pattern matches correctly | B站, YouTube, QQMusic, unknown |
| **ID generation** | Prefix, uniqueness, length | `person_xxx`, `content_xxx` |
| **Title extraction** | URL → human-readable title | Bilibili → "B站视频" |
| **Data flow simulation** | Create entity → add content → dedup → toggle status → filter → search | Full CRUD cycle |
| **Tag management** | Dedup on insert | Adding same tag twice = 1 entry |

**Pattern:** Write a single Node.js script that reproduces the pure functions from `shared/utils/` and `utils/`, then runs `assert`/`assertEqual` against them. No imports, no test framework — just `node scripts/test-core-logic.js`.

Benefits:
- **Zero framework dependencies** — runs with plain `node scripts/test-core-logic.js`
- **Catches spec→code translation bugs** early (wrong platform mapping, missing URL patterns)
- **Serves as living documentation** — each test case documents an expected behavior
- **Portable** — can be copy-pasted into any project scaffold immediately after init

See `scripts/test-core-logic.js` in the Fan Memory OS repo for a complete worked example (38 tests covering platform identification, ID generation, title extraction, full data flow simulation, tag dedup).

## Phase 2 Pattern: Backend Discovery Service

When the project requires a backend after the frontend MVP (common pattern: Phase 1 = local/frontend, Phase 2 = API + scheduler), use this pattern:

### Structure

```
packages/<service-name>/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app with lifespan
│   ├── config.py            # pydantic-settings config
│   ├── database.py          # SQLAlchemy async + SQLite
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response models
│   ├── routers/             # Route modules (health, people, discovery...)
│   ├── services/            # Business logic (RSSHub, dedup...)
│   └── tasks/               # APScheduler scheduled jobs
├── tests/                   # API tests
├── Dockerfile
├── requirements.txt
└── .env.example
```

### Database Pattern (SQLAlchemy async + SQLite)

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine("sqlite+aiosqlite:///./data/db.sqlite")
async_session = async_sessionmaker(engine, class_=AsyncSession)

class Base(DeclarativeBase): pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### Async Greenlet Pitfall

When using SQLAlchemy async with FastAPI, **accessing lazy-loaded relationships** (e.g. `person.sources` after loading a Person without `selectinload`) throws `MissingGreenlet`:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here.
```

**Fix — always eager-load relationships that will be serialized:**

```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(Person)
    .options(selectinload(Person.sources), selectinload(Person.discoveries))
    .where(Person.uid == uid)
)
person = result.scalar_one_or_none()
```

### Scheduler Lifecycle (APScheduler + FastAPI)

Use FastAPI's `lifespan` context manager to start/stop the scheduler:

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(my_task, "interval", minutes=60, id="my_task")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

### Docker Deployment

For multi-package repos, place `docker-compose.yml` at the root, referencing sub-package Dockerfiles:

```yaml
# docker-compose.yml (repo root)
services:
  backend:
    build:
      context: ./packages/backend
      dockerfile: Dockerfile
    ports:
      - "8766:8766"
    volumes:
      - data:/app/data
    restart: unless-stopped

volumes:
  data:
```

Backend `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8766"]
```

### Quick verification

```bash
# Start server
cd packages/<service>
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8766

# Run API tests
.venv/bin/python tests/test_api.py
```

## Pitfalls (continued)

- **Don't install npm dependencies until Sprint 1.** The scaffold phase produces docs + types + dir structure only. Move to Sprint 1 (npm install + build) as a separate commit.
- **Don't build UI components in the scaffold commit.** Page files should be empty stubs or minimal skeleton templates. Full components belong in Sprint 1+.
- **The `create-uni` CLI exists (`npx create-uni`) but its non-interactive mode is unreliable.** The `vue3-ts` template is not available, and `-t` flag parsing fails. For uni-app Vue 3 on Windows, prefer manual setup with known-working version pins (see `windows-development-environment` skill's `references/uni-app-vue3-setup.md`).

## Reference

See `references/fan-memory-os-example.md` for a complete worked example of this skill, including the full product spec → scaffold translation for the Fan Memory OS project (Star-Trails-Log).
