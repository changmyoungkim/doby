# stmemory — Structured Memory for LLM-Driven Development

**Keyword → Plan Doc → Code File → Symbol** in 2 grep calls (~100 tokens).

The biggest token waste in LLM-driven development is **finding where to make changes**. A single change request burns 2,000-5,000 tokens just on navigation. stmemory cuts that to ~100 tokens by maintaining a pre-compiled index.

## Architecture: 4 Layers

```
Layer    Method              Cost         When
─────    ──────              ────         ────
L1       Flat-line Index     ~100 tokens  Always (90% of work)
L2       Wiki Pages          ~500 tokens  "Why?" questions only
L3       Semantic RAG        ~300 tokens  L1 miss (grep returns nothing)
L4       Auto-Compile        ~2,000 tokens Manual trigger only
```

**90% of daily work stays in L1.** Higher layers activate only when explicitly needed — core token savings are never diluted.

### How L1 Works

```
User: "fix the audio playback"

grep "audio" INDEX-keywords.md
→ audio:audio-playback.md,tts-config.md

grep "audio-playback.md" INDEX.md
→ @audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play;api/audio.py#get_audio|active

Done. 2 grep calls. Domain, plan doc, code files, symbols, status — all in one line.
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/changmyoungkim/stmemory ~/.claude/skills/stmemory

# 2. Install (creates directories, installs chromadb)
cd your-project
bash ~/.claude/skills/stmemory/install.sh

# 3. Configure
# Edit .stmemoryrc.json with your project's mappings
# (install.sh copies the template automatically)

# 4. Build the index
# In Claude Code: /stmemory build
```

## Configuration

`.stmemoryrc.json` in your project root defines the mapping rules:

```json
{
  "scan_dirs": ["src", "backend", "frontend"],
  "file_extensions": [".py", ".ts", ".tsx", ".js"],
  "plans_dir": ".omc/plans",
  "wiki_dir": ".omc/wiki",

  "exact_file_map": {
    "src/index.ts": "app-entry"
  },
  "directory_rules": {
    "src/auth/": "auth-system",
    "backend/services/payment/": "payment-processing"
  },
  "keyword_to_doc": {
    "auth": "auth-system",
    "cache": "caching-layer"
  }
}
```

**Matching priority** (highest first):
1. `exact_file_map` — exact filepath match
2. `directory_rules` — directory prefix match (longest wins)
3. `keyword_to_doc` — keyword extracted from filepath
4. Fuzzy match — Jaccard similarity against doc names

## 5 Modes

### `build` — Full Index Build

```
/stmemory build
```

1. **Phase 1**: Python automapper scans codebase, applies 4-tier matching (0 LLM tokens)
2. **Phase 2**: LLM verifies mappings, classifies status (active/archived/orphan/planning)
3. **Phase 3**: Keyword extraction + symbol collection (parallel agents)
4. **Phase 4**: Optional ChromaDB RAG indexing
5. **Phase 5**: Write all 4 INDEX files, log, report

### `resolve` — Keyword Search

```
/stmemory audio
```

2 grep calls, 0 file reads. Returns domain, plan doc, code files, symbols, status.

Reverse lookup (code → doc):
```
grep "useAudio.ts" INDEX-codemap.md → plan doc + symbols in 1 call
```

### `update` — Incremental Update

```
/stmemory update
```

Processes changes tracked by the PostToolUse hook. Uses `grep -n` to find the exact line, then edits that line only. ~300 tokens per update.

### `lint` — Health Check

```
/stmemory lint
```

Finds broken code links, orphan docs, missing mappings, renamed symbols. Suggests fixes — applies only after user approval.

### `compile` — Generate Wiki Page

```
/stmemory compile audio-playback
```

Reads plan doc + linked code, generates a wiki page with architecture overview, design decisions, and trade-offs. ~2,000 tokens per page, manual trigger only.

## Index Files

All files live in `.omc/plans/`. Flat-line format: 1 line = 1 record, reachable by `grep -n`.

### INDEX.md (Master Record)

```
@domain|plan_doc|code#symbol;code#symbol|status

@audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play;api/audio.py#get_audio|active
@auth|auth-system.md|src/pages/login.tsx;api/auth.py#login,refresh|active
@feature|feature-spec.md||planning
```

### INDEX-keywords.md (Keyword Map)

```
audio:audio-playback.md,tts-config.md
auth:auth-system.md
playback:audio-playback.md
```

### INDEX-codemap.md (Reverse Map: Code → Doc)

```
src/hooks/useAudio.ts:audio-playback.md#useAudio,play
api/auth.py:auth-system.md#login,refresh
```

### INDEX-log.md (Change History)

```
2025-01-15T12:00 build 50docs 20active 15archived 10orphan 5planning
2025-01-15T15:30 update audio-playback.md symbol_change:play→playTrack
```

## Hooks (Zero-Cost Change Tracking)

stmemory uses PostToolUse hooks to track file changes with **0 LLM tokens** — pure shell script.

Add to `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "node ~/.claude/skills/stmemory/detect-change.mjs"
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "node ~/.claude/skills/stmemory/batch-report.mjs"
      }]
    }]
  }
}
```

- **detect-change.mjs**: When a tracked file is modified, appends its path to `stmemory-pending.txt`
- **batch-report.mjs**: At session end, reports accumulated changes and suggests `/stmemory update`

## L3: Semantic RAG (ChromaDB)

Activates only when L1 grep returns no results. Provides natural language search over plan docs and code.

```bash
# Index all plans and code
python ~/.claude/skills/stmemory/rag.py index

# Search
python ~/.claude/skills/stmemory/rag.py query "recommend places near user"

# Clear and rebuild
python ~/.claude/skills/stmemory/rag.py rebuild
```

## Token Efficiency

| Operation | Cost | Method |
|-----------|------|--------|
| `resolve` (search) | ~100 tokens | grep 2 calls, 0 file reads |
| `update` (incremental) | ~300 tokens | grep -n + line edit |
| `build` (full, once) | ~5,000-10,000 | Python heuristics + LLM verify |
| `lint` (health check) | ~1,000-2,000 | Parallel collect + judge |
| `compile` (wiki page) | ~2,000 | Manual trigger only |
| L3 RAG query | ~300 | On L1 miss only |
| Change tracking | **0** | Shell hook, no LLM |

**Per-session savings** (5-10 change requests):
- Without stmemory: 10,000-50,000 tokens on navigation
- With stmemory: 500-2,000 tokens
- **90-95% token reduction**

## Design Principles

1. **Compile Once, Query Many** — build index once, reach any file via grep
2. **Read 0 Principle** — resolve/update never open INDEX files; grep output only
3. **Layered Cost** — expensive layers activate only when explicitly needed
4. **Zero-Cost Tracking** — change detection uses 0 LLM tokens

## File Structure

```
~/.claude/skills/stmemory/
├── SKILL.md                  Skill definition (modes, rules, format)
├── README.md                 This file
├── COMPARISON.md             15-tool competitive analysis
├── automap.py                Python automapper (4-tier heuristic)
├── rag.py                    ChromaDB semantic search (L3)
├── detect-change.mjs         PostToolUse hook (change tracking)
├── batch-report.mjs          Stop hook (session report)
├── install.sh                Setup script
└── .stmemoryrc.example.json  Config template

your-project/
├── .stmemoryrc.json          Project config (from template)
└── .omc/
    ├── plans/
    │   ├── INDEX.md           Master record
    │   ├── INDEX-keywords.md  Keyword map
    │   ├── INDEX-codemap.md   Code → doc reverse map
    │   ├── INDEX-log.md       Change history
    │   └── *.md               Plan documents
    ├── wiki/                  L2 wiki pages
    └── state/
        ├── stmemory-pending.txt  Change tracking
        └── stmemory-rag/         ChromaDB storage
```

## When to Use stmemory

**Good fit:**
- Small-to-medium projects (100-500 files) with plan docs
- Token-constrained budgets
- Plan-driven development (plan docs are source of truth)
- No external service dependencies needed

**Not ideal:**
- Large monorepos (10K+ files) — consider Greptile or Augment
- No plan docs — stmemory's core value requires documentation
- Fully autonomous coding — Devin/SWE-agent are better suited

See [COMPARISON.md](COMPARISON.md) for a detailed analysis against 15 tools.

## License

MIT
