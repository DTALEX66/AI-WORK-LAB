# Source Drive Path Migration

When the user's source data drive or directory structure changes (e.g. `E:/学习数据` → `E:/服务器` with flat topic structure).

## Detection
- Vault pages reference old paths (e.g. `E:/学习数据/01_设计系统/...`)
- File explorer shows new directory structure
- Audit re-run shows `missing_raw_source` regressions

## Migration Steps (in order)

### 1. Scan new directory tree
```python
dir_index = {}
for d in Path(new_root).rglob('*'):
    if d.is_dir():
        dir_index[d.name.lower()] = str(d)
```

### 2. Match courses to new paths
For each course page:
- Extract `source_title` from frontmatter
- Try exact match against `dir_index`
- If no exact match, try cleaned match: strip special chars `【】·&（）`, compare substrings
- Fallback: match course directory name against dir_index

### 3. Update frontmatter
- Replace `source_path:` value with matched new path
- Replace `source:` body references
- Do NOT do blanket `text.replace(old_root, new_root)` — old subdirectory structure may not exist under new root

### 4. Verify
```bash
python scripts/v10/course_verification_audit.py \
  --vault 'E:/BaiduSyncdisk/Obsidian知识库' \
  --source-root '<new_root>' \
  ...
```
- `missing_raw_source` should not regress
- `verified_by_available_methods` should match or exceed previous count

## Common Failure Patterns
- **Simple text replace of root path**: old `01_设计系统/视频课程/` doesn't exist under new root `设计课程/` — paths break
- **Name mismatches**: `版式设计` course matched to old source `版式设计/` but new source is `优设青爵版式设计全能特训/`
- **Split categories**: `心理记忆学习力` materials now split across `记忆力与学习力/` and `心理学/`

## Category Renaming (when domain names change)

When the data disk renames categories (e.g. `设计系统` → `设计课程`), the vault domain directories MUST be renamed to match. Do all passes in ONE batch — intermediate states break wikilinks.

### Full Cascade Checklist (run as single script)
1. `category:` frontmatter fields in ALL vault .md files
2. `os.rename()` or `shutil.move()` the domain directories
3. `[[02_课程库/<old>/...]]` wikilinks (fresh scan after renames)
4. `00_课程库总览.md` domain table rows
5. `02_课程卡片墙.md` section headers
6. Delete stale `*课程列表.md` files with old names
7. `50_领域知识/` subdirectory names (if numbered-prefix: `05_设计系统/` → `设计课程/`)
8. `领域：旧名` and `category: 旧名` fields inside material pages under domain dirs

### Legacy Shell Cleanup

If vault has old OBS workspace directories (`00_OBS_Command_Center/` etc.) competing with TALOS shell (`00_主页/`):
1. Check references: `grep -r "OBS_Command_Center" --include='*.md'`
2. If equivalent TALOS page exists, replace ALL wikilinks and DELETE OBS dir
3. Do not keep redundant navigation — it confuses the user

### Junk Scan (run after every restructure)
```python
# Patterns to check:
- 未命名.* / Untitled.*           # auto-created junk
- Excalidraw/Drawing *            # accidental drawings
- *.md < 100B                     # empty placeholder pages  
- .smart-env/multi/*Untitled*     # smart-env junk
- *课程列表.md with stale names   # from renamed categories
- E:/学习数据 references           # stale paths
```
