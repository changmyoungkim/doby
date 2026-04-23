---
name: stmemory
description: Build and query structured plan↔code indexes. Keyword → plan doc → code file → symbol in grep 1-2 calls.
user-invocable: true
triggers:
  - /stmemory
  - stmemory
  - structured index
  - plan index
argument-hint: "[build|resolve <keyword>|lint|update|compile]"
scope: user
---

# /stmemory — Structured Memory for LLM-Driven Development

## Purpose

Build and maintain a **keyword → plan doc → code file → symbol** 4-level mapping.
Applies the LLM Wiki "Compile Once, Query Many" pattern — reach any file via grep, never re-explore.

## Architecture: 4 Layers

```
L1: Flat-line Index (grep)     — 100 tokens   — always active
L2: Wiki Pages (Read)          — 500 tokens   — on "why?" questions only
L3: Semantic RAG (ChromaDB)    — 300 tokens   — on L1 miss only
L4: Auto-Compile (LLM)        — 2,000 tokens  — manual trigger only
```

90% of work stays in L1. Higher layers activate only when explicitly needed.

## Output Files

```
.omc/plans/
├── INDEX.md              ← Master record (1 line = 1 doc)
├── INDEX-keywords.md     ← Keyword → doc flat map
├── INDEX-codemap.md      ← Code file → doc reverse map
└── INDEX-log.md          ← Change history (append-only)

.omc/wiki/                ← L2 wiki pages (design decisions, context)

.omc/state/
├── stmemory-pending.txt  ← Zero-cost change tracking
└── stmemory-rag/         ← L3 ChromaDB storage
```

## Model Routing

| Role | Model | Work |
|------|-------|------|
| Supervise / classify / judge | **Opus** (direct) | Domain classification, status judgment, quality check |
| Collect / scan / extract | **Haiku** (Agent) | Doc scan, keyword extraction, code path verification |
| Forbidden | ~~Sonnet~~ | Not used |

## 5 Modes

---

### Mode 1: `build` (Full Build)

**Trigger:** `/stmemory build` or `/stmemory`
**When:** First run, or indexes are missing/outdated

#### Phase 1: Python Auto-mapping (0 LLM tokens)

```bash
python ~/.claude/skills/stmemory/automap.py --apply
```

Reads `.stmemoryrc.json` from project root for project-specific config:
- 4-tier heuristic matching: exact_file_map → directory_rules → keyword_to_doc → fuzzy match
- `--apply` updates INDEX-codemap.md + INDEX.md
- `--dry-run` for preview only

#### Phase 2: Domain Classification + Status (Opus direct)

```
Opus verifies Python output:
  - Check mapping accuracy (fix incorrect matches)
  - Judge each doc status: active / archived / orphan / planning
  - Normalize keywords (merge synonyms)
  - Add unmatched files to exact_file_map in .stmemoryrc.json
```

#### Phase 3: Keyword Index Enhancement (Haiku ×2 parallel, if needed)

```
Agent(model="haiku", run_in_background=true) × 2:
  - Agent A: Extract keywords from newly added docs → update INDEX-keywords.md
  - Agent B: Collect code symbols (LSP document_symbols) → enhance INDEX-codemap.md
```

#### Phase 4: L3 RAG Index (optional)

```bash
python ~/.claude/skills/stmemory/rag.py index
```

Indexes plan docs + code files into ChromaDB for semantic fallback search.

#### Phase 5: Verify + Log (Opus direct)

Update all 4 INDEX files. **All INDEX files use flat-line format** — 1 line = 1 record, reachable by grep -n.

**INDEX.md** — Master record (1 line = 1 doc):
```
Format: @domain|plan_doc|code#symbol;code#symbol|status
```
```
@audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play;api/audio.py#get_audio|active
@auth|auth-system.md|src/pages/login.tsx;api/auth.py#login,refresh|active
@feature|feature-spec.md||planning
```

**INDEX-keywords.md** — Keyword → doc (1 line = 1 keyword):
```
audio:audio-playback.md,tts-config.md
auth:auth-system.md
playback:audio-playback.md
```

**INDEX-codemap.md** — Code → doc reverse map (1 line = 1 code file):
```
src/hooks/useAudio.ts:audio-playback.md#useAudio,play
api/auth.py:auth-system.md#login,refresh
```

**INDEX-log.md** — Change history (append-only):
```
2026-04-23T12:00 build 50docs 20active 15archived 10orphan 5planning
```

Report:
```
Distribution: Haiku {N} / Opus direct {M}
Result: active {A} / archived {B} / orphan {C} / planning {D}
Gap: {N} code files without plan docs
```

---

### Mode 2: `resolve` (Keyword Search)

**Trigger:** `/stmemory <keyword>` or auto-called from other skills
**Model:** Opus direct (grep 1-2 calls, no Agent needed)
**0 Read calls.** Never open INDEX files. grep output only.

```
Step 1: grep "keyword" .omc/plans/INDEX-keywords.md
  → "audio:audio-playback.md,tts-config.md"

Step 2: grep "audio-playback.md" .omc/plans/INDEX.md
  → "@audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play|active"

Total cost: grep 2 calls = ~100 tokens
```

**Reverse (code → doc):**
```
grep "useAudio.ts" .omc/plans/INDEX-codemap.md
→ 1 grep call
```

**L3 Fallback (when grep misses):**
```
python ~/.claude/skills/stmemory/rag.py query "recommend places near user location"
→ Returns matching docs + code files via semantic search
→ ~300 tokens
```

**Skill integration:**
- `/fix` Phase 1 → replaced by `stmemory resolve`
- `/ralph` start → scope confirmation via `stmemory resolve`
- LSP → use resolved symbols for `lsp_goto_definition`

---

### Mode 3: `lint` (Health Check)

**Trigger:** `/stmemory lint`
**Model:** Haiku collect → Opus judge

```
Haiku parallel checks:
  - Broken code links: do file paths in INDEX-codemap.md exist?
  - Orphan docs: active docs with no code connection
  - Missing mappings: major code files not in INDEX
  - Symbol changes: renamed/deleted symbols (LSP verification)

Opus judgment:
  - Generate fix suggestion list
  - Apply after user approval
```

---

### Mode 4: `update` (Incremental Update)

**Trigger:** `/stmemory update` or auto-suggested when pending file exists
**Model:** Plan doc change → Haiku rescan + Opus line replace. Code change → Opus direct.
**Principle:** 0 Read calls. grep -n to find line number → Edit that line only.

```
Step 1: Read pending file
  cat .omc/state/stmemory-pending.txt
  → "2026-04-23T15:30  plan  audio-playback.md"
  → "2026-04-23T16:00  code  src/hooks/useAudio.ts"

Step 2-A: Plan doc changed
  Agent(model="haiku"): Read that doc only → re-extract keywords/code/symbols
  grep -n "audio-playback.md" INDEX.md → line number N
  Edit(INDEX.md, line N old, line N new)

Step 2-B: Code changed
  grep -n "useAudio.ts" INDEX-codemap.md → line number N
  Opus: check symbol changes (LSP document_symbols, 1 call)
  Edit(INDEX-codemap.md, line N old, line N new)

Step 3: Append to INDEX-log.md
Step 4: Delete pending file

Total cost: grep 2-4 + Edit 2-4 + Haiku 0-1 = ~300 tokens
```

---

### Mode 5: `compile` (Auto-Generate Wiki)

**Trigger:** `/stmemory compile` or `/stmemory compile <doc_name>`
**Model:** Opus direct (reads plan doc + code → generates wiki page)

```
Step 1: Read plan doc + linked code files
Step 2: Generate .omc/wiki/<topic>.md with:
  - Architecture overview
  - Design decisions and rationale
  - Key constraints and trade-offs
  - Related topics (cross-references)
Step 3: Update INDEX.md with wiki pointer

Cost: ~2,000 tokens per wiki page (manual trigger only)
```

---

## Hook Integration

### PostToolUse Hook (Write|Edit detection)

`detect-change.mjs` — zero-token change tracking:
- Detects when plan docs or tracked code files are modified
- Appends file path to `stmemory-pending.txt`
- **0 LLM tokens** — shell script only

### Stop Hook (Session end report)

`batch-report.mjs` — reports accumulated changes:
- Only fires if pending changes exist
- Suggests `/stmemory update` for next session

## Setup

```bash
cd your-project
bash ~/.claude/skills/stmemory/install.sh
```

This will:
1. Install chromadb (for L3 RAG)
2. Create `.omc/plans/`, `.omc/wiki/`, `.omc/state/` directories
3. Copy `.stmemoryrc.example.json` as starting config
4. Print hook configuration instructions

## Token Efficiency

| Operation | Token Cost |
|-----------|-----------|
| **build** (once) | ~5,000-10,000 (Haiku executes, Opus judges) |
| **resolve** (search) | ~100-200 (grep 2 calls, 0 Read) |
| **update** (incremental) | ~300-500 (grep -n + Edit, changed files only) |
| **lint** (health check) | ~1,000-2,000 (Haiku collect + Opus judge) |
| **compile** (wiki gen) | ~2,000 per page (manual trigger) |
| **L3 RAG query** | ~300 (on L1 miss only) |
| **Change tracking** | **0** (hook appends filepath to .txt) |

## Rules

- INDEX files live in `.omc/plans/` (same directory as plan docs)
- Wiki pages live in `.omc/wiki/` (separate from indexes)
- Build results must be reported to user before saving
- Lint auto-fix forbidden — user approval required
- All INDEX changes logged in INDEX-log.md
- Haiku collects, Opus judges — no role mixing
