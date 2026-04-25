---
name: doby
description: Structured plan-code index + spec-first fix workflow. Keyword to plan doc to code file to symbol in grep 1-2 calls.
user-invocable: true
triggers:
  - /doby
  - doby
  - /fix
  - fix
  - structured index
  - plan index
  - 수정
  - 고쳐
  - 고치자
  - 바꿔
  - 바꾸자
  - 변경
  - 업데이트
  - 추가해
  - 추가하자
  - 만들어
  - 만들자
  - 구현해
  - 구현하자
  - 개선해
  - 개선하자
  - 해줘
  - 해주세요
  - 하자
  - 적용해
  - 적용하자
  - 반영해
  - 반영하자
  - 넣어
  - 넣자
  - 빼줘
  - 빼자
  - 삭제해
  - 삭제하자
  - 제거해
  - 제거하자
  - 옮겨
  - 옮기자
  - 리팩토링
  - 리팩터
  - 분리해
  - 분리하자
  - 합쳐
  - 합치자
  - 연결해
  - 연동해
  - 교체해
  - 대체해
  - 개발해
  - 개발하자
  - 작업해
  - 작업하자
  - implement
  - add
  - remove
  - delete
  - update
  - change
  - modify
  - refactor
  - replace
  - integrate
  - connect
  - build
  - create
  - develop
argument-hint: "[build|resolve <keyword>|lint|update|compile|fix|status]"
scope: user
---

# Doby — Structured Memory + Spec-First Fix Workflow

## Purpose

Build and maintain a **keyword → plan doc → code file → symbol** 4-level mapping.
"Compile Once, Query Many" — reach any file via grep, never re-explore.

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
├── doby-pending.txt      ← Zero-cost change tracking
└── doby-rag/             ← L3 ChromaDB storage
```

## Model Routing

| Role | Model | Work |
|------|-------|------|
| Phase 1-2: Code→Doc extraction | **Python scripts** (0 tokens) | AST parse, heuristic mapping — MUST run before any LLM work |
| Phase 3,6: Supervise / classify / judge | **Opus** (direct) | Domain classification, status judgment, quality check |
| Phase 4: Keyword + symbol collection | **Haiku** (Agent) | Doc scan, keyword extraction, code path verification |

## 7 Modes

### Mode 1: `build` (Full Build)

**Trigger:** `/doby build` or `/doby`  
**When:** First run, or indexes missing/outdated

> **BLOCKING RULE:** Phase 1-2 (Python scripts) MUST complete before ANY LLM work (Phase 3+).
> Haiku Agents are NOT a substitute for the Python scripts. The scripts do deterministic AST/regex
> extraction at 0 tokens. Agents are only for Phase 4 (keyword + symbol enrichment after indexes exist).
> If you skip Phase 1-2 and jump to agents, you are violating this skill.

**Phase 0:** Ensure `.dobyrc.json` exists in project root.
If missing, create it by inspecting the project structure. Required keys:
```json
{
  "scan_dirs": ["packages/api", "packages/frontend/src", "packages/backend/src", ...],
  "file_extensions": [".py", ".tsx", ".ts", ".dart"],
  "plans_dir": ".omc/plans",
  "wiki_dir": ".omc/wiki",
  "docs_dir": "idea-digger/output",
  "keyword_to_doc": { "auth": "b5-7-auth-infra", "curriculum": "v2-master-spec", ... },
  "directory_rules": { "packages/api/app/routers": "v2-master-spec", ... },
  "exact_file_map": { "packages/api/app/routers/user.py": "b5-7-auth-infra", ... }
}
```
Populate `keyword_to_doc`, `directory_rules`, `exact_file_map` based on existing docs in `docs_dir`.
This is Opus direct work (config creation, not code execution).

**Phase 1:** Auto-generate spec docs from code (0 LLM tokens):
```bash
python ~/.claude/skills/doby/docgen.py --config .dobyrc.json --apply
```
Extracts FastAPI endpoints, Dart widgets, function signatures, imports via AST/regex. Generates one `.md` per domain. Skips domains that already have docs (use `--force` to overwrite).
**STOP if this fails.** Fix the config or script error before proceeding.

**Phase 2:** Auto-map code files to docs (0 LLM tokens):
```bash
python ~/.claude/skills/doby/automap.py --config .dobyrc.json --apply
```
4-tier heuristic (exact → directory → keyword → fuzzy) writes INDEX-codemap.md + INDEX.md.
**STOP if this fails.** Fix before proceeding.

**Phase 3:** Opus verifies mappings, judges status (active/archived/orphan/planning), normalizes keywords.

**Phase 4:** Haiku x2 parallel — extract keywords from docs, collect code symbols via LSP.
> This is the ONLY phase where Haiku Agents do collection work. Phase 1-2 are Python-only.

**Phase 5:** Optional L3 RAG index via `python ~/.claude/skills/doby/rag.py index`

**Phase 6:** Opus updates all INDEX files.

**INDEX.md format:** `@domain|plan_doc|code#symbol;code#symbol|status`  
**INDEX-keywords.md format:** `keyword:doc1.md,doc2.md`  
**INDEX-codemap.md format:** `src/file.ts:doc.md#symbol1,symbol2`  
**INDEX-log.md format:** `2026-04-23T12:00 build 50docs 20active 15archived 10orphan 5planning`

**Report:** Distribution of Haiku/Opus work, active/archived/orphan/planning counts, code coverage gaps.

---

### Mode 2: `resolve` (Keyword Search)

**Trigger:** `/doby <keyword>` or auto-called from Mode 6 (fix)  
**Model:** Opus direct (grep only, ~100 tokens)

```bash
Step 1: grep "keyword" .omc/plans/INDEX-keywords.md
Step 2: grep "^@domain" .omc/plans/INDEX.md
Step 3 (optional): grep "filename" .omc/plans/INDEX-codemap.md
```

**Reverse (code → doc):** `grep "file.ts" .omc/plans/INDEX-codemap.md`

**L3 Fallback:** `python ~/.claude/skills/doby/rag.py query "natural language search"`

---

### Mode 3: `lint` (Health Check)

**Trigger:** `/doby lint`  
**Model:** Haiku collect → Opus judge

Haiku checks: broken code links, orphan docs, missing mappings, symbol changes.  
Opus generates fix suggestions.

---

### Mode 4: `update` (Incremental Update)

**Trigger:** `/doby update` or auto-suggested when `doby-pending.txt` exists  
**Model:** Plan doc change → Haiku rescan; code change → Opus direct

Reads pending file, updates changed entries only via `grep -n` + `Edit`.  
Total cost: ~300 tokens.

---

### Mode 5: `compile` (Auto-Generate Wiki)

**Trigger:** `/doby compile` or `/doby compile <doc_name>`  
**Model:** Opus direct

Reads plan doc + linked code files, generates `.omc/wiki/<topic>.md` with architecture, decisions, constraints, cross-references.  
Cost: ~2,000 tokens per wiki page (manual trigger only).

---

### Mode 6: `fix` (Spec-First Fix Workflow)

**Trigger:** `/doby fix`, `/fix`, or modification keyword detected  
**When:** Feature add, bug fix, refactor, UI/API change  
**Exception:** Config edits, doc-only edits, doby index tasks skip fix mode.

#### Core Principle
```
doby resolve → spec update → verification loop → implementation → doby sync + consistency check
```

Never modify code first. Always update spec docs first. Use doby resolve to minimize exploration.

#### Phase 0: doby resolve (auto-run, report required)

Extract keywords from request → invoke Mode 2 internally.

**Report format:**
```
🔍 doby resolve: "keyword"
📄 Docs: doc1.md, doc2.md
📁 Code: file1.py#symbol1, file2.dart#symbol2
🏷️ Domain: @domain (status)
📏 Scale: small/medium/large
```

#### Phase 1: Spec Review
Read only docs from Phase 0. Identify diff between current spec and request.

#### Phase 2: Spec Update
Apply changes to spec docs first. **User approval required.**

#### Phase 3: Plan Verification Loop (repeat until consensus)
Opus verifies 3 perspectives: feasibility, architecture, risk.  
Report per round. Max 3 rounds before warning user.

#### Phase 4: Implementation + Verification Loop (repeat until consensus)

Scale-based branching:
- Small (1-3 files): 1 Haiku Agent, sequential
- Medium (4-10 files): 2-3 Haiku Agents parallel
- Large (10+ files): 3-5 Haiku Agents parallel

Opus verifies: spec-code consistency, code quality, project conventions.  
Max 5 rounds before warning user.

#### Phase 5: Integration Test
Local API test → frontend check → deploy + production test.

#### Phase 6: doby sync + Consistency Check
Invoke Mode 4 (update). Verify spec-code consistency.

**Final report:**
```
✅ Spec-code consistency: @domain
📄 Spec: N changes applied
📁 Code: file1.py#symbol1, file2.dart#symbol2
🔄 doby: INDEX updated
⚠️ Inconsistencies: (list or "none")
📊 Distribution: Haiku N / Opus M
🔎 Loops: plan N rounds, impl M rounds
```

#### Phase 7: Complete
Mark spec as done. Append to INDEX-log.md.

#### Fix Rules
- Phase order strict: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7
- Phase 0 (doby resolve) mandatory
- Phase 3, 4 loops repeat until consensus — never single-pass
- Phase 6 (doby sync) mandatory
- No code before Phase 2 approval
- No spec changes without user approval
- Follow project conventions in CLAUDE.md or .dobyrc.json

---

### Mode 7: `status` (Quick Status)

**Trigger:** `/doby status`  
**Model:** Opus direct (grep only, ~50 tokens)

Count domains, active docs, mapped code files, keywords. Report last update.

---

## Hook Integration

**PostToolUse Hook (detect-change.mjs):** Zero-token change tracking — appends file path to `doby-pending.txt` when plan docs or tracked code files are modified.

**Stop Hook (batch-report.mjs):** Reports accumulated changes if pending file exists, suggests `/doby update`.

---

## Rules

- INDEX files live in `.omc/plans/` (same directory as plan docs)
- Wiki pages live in `.omc/wiki/` (separate from indexes)
- Build results must be reported to user before saving
- Lint auto-fix forbidden — user approval required
- All INDEX changes logged in INDEX-log.md
- Haiku collects (Phase 4 only), Opus judges — no role mixing
- **Build phase order is STRICT:** Phase 0 (config) → 1 (docgen.py) → 2 (automap.py) → 3 (Opus verify) → 4 (Haiku enrich) → 5 (RAG) → 6 (final INDEX). NEVER skip Phase 0-2.
- **Python scripts are NOT optional.** If `.dobyrc.json` is missing, create it first (Phase 0). If scripts fail, fix the error. Do NOT substitute with LLM agents — that defeats the 0-token design.
- **Haiku Agents are Phase 4 only.** They enrich existing indexes with keywords/symbols AFTER Python scripts have generated the base indexes. Using agents for Phase 1-2 work wastes tokens and violates the skill.
