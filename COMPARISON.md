# doby — Structured Memory for LLM-Driven Development

## The Problem

The biggest token waste in LLM-driven development is **finding where to make changes**.

When a project grows to 100+ plan docs and hundreds of code files, a simple request like "fix the audio playback" triggers:

1. Grep `.omc/plans/` — dozens of hits
2. Read candidate docs one by one — 200-500 tokens each
3. Explore code via Serena/LSP — 5-10 calls
4. Navigate to symbol definitions — 3-5 more calls

**A single change request burns 2,000-5,000 tokens just on navigation.**
Over a long session, 20-30% of the context window is wasted on "finding the way."

### Root Cause

No structured connection exists between plan documents and code.

- Plan docs are natural language markdown — LLM must "read and understand" every time
- Code is scattered across the file system — no explicit link to which plan it implements
- Symbols (functions/classes) live only in code — unreachable without LSP calls

## The Solution

**"Compile Once, Query Many"** — Karpathy's LLM Wiki pattern applied to plan-code mapping, extended with semantic RAG and auto-generated wiki pages.

### 4-Layer Architecture

```
L1: Flat-line Index (grep)     100 tokens    always active
L2: Wiki Pages (Read)          500 tokens    on "why?" questions only
L3: Semantic RAG (ChromaDB)    300 tokens    on L1 miss only
L4: Auto-Compile (LLM)        2,000 tokens  manual trigger only
```

**90% of daily work stays in L1.** Higher layers activate only when explicitly needed.
Core token savings are never diluted.

### How It Works

```
User: "fix the audio playback"

grep "audio" INDEX-keywords.md
→ audio-playback.md

grep "audio-playback.md" INDEX.md
→ @audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play;api/audio.py#get_audio|active

Done. 2 grep calls = ~100 tokens.
```

### Flat-Line Format

All INDEX files use **1 line = 1 record**. Not markdown tables — grep -n reaches the exact line number.

```
@audio|audio-playback.md|src/hooks/useAudio.ts#useAudio,play;api/audio.py#get_audio|active
```

One line contains domain, plan doc, code files, symbols, and status.
Updates use grep -n to find the line number, then Edit that line only. **No Read required.**

---

## Competitive Analysis: 15 Tools Compared (2025-2026)

### Tools Evaluated

| # | Tool | By | Approach |
|---|------|-----|----------|
| 1 | **doby** | Custom | Flat-line index + grep + plan↔code mapping |
| 2 | **LLM Wiki** | Karpathy pattern | Semantic wiki graph, Compile Once |
| 3 | **Cursor .cursorrules** | Cursor IDE | Modular .mdc rule files |
| 4 | **Cline Memory Bank** | Cline | Hierarchical markdown knowledge bank |
| 5 | **Aider repo-map** | Aider | AST + PageRank dependency graph |
| 6 | **Windsurf Cascade** | Windsurf | Auto-indexing engine + auto-memory |
| 7 | **Continue.dev** | Continue | @mention context providers |
| 8 | **Copilot Workspace** | GitHub | Spec → Plan → Code pipeline |
| 9 | **Augment Code** | Augment | Real-time semantic embeddings (100M+ LOC) |
| 10 | **Devin** | Cognition | SWE-grep + Planner/Coder/Critic |
| 11 | **OpenHands** | Open source | Python SDK agent platform |
| 12 | **SWE-agent** | Princeton | ACI commands (find_file, search_file) |
| 13 | **Repomix** | Open source | Single-file repo packing + tree-sitter |
| 14 | **Mentat** | Open source | Multi-file coordination + CI/CD |
| 15 | **Greptile** | Greptile | AST + recursive docstring embeddings |

---

### Dimension 1: Code Navigation

| Tool | Method | Query Cost | Accuracy |
|------|--------|-----------|----------|
| **doby** | grep 1-2 calls (flat-line index) | ~100 tokens | Curated → very high |
| **LLM Wiki** | Wiki page Read | ~500-1,000 tokens | Semantic → high |
| **Aider repo-map** | PageRank file ranking | ~1,000 tokens (budget) | Dependency-based → high |
| **Greptile** | AST docstring embeddings | API call cost | Semantic+structural → very high |
| **Augment Code** | Real-time vector search | API call cost | Real-time sync → high |
| **Devin** | SWE-grep dedicated model | Internal | Dedicated model → very high |
| **SWE-agent** | find_file/search_file commands | ~300 tokens | Summary output → medium |
| **Repomix** | Full repo packing | 70% compressed but still large | All-inclusive → low (noise) |

**doby advantage**: The only tool with a **Read 0 principle**. All other tools require at least one file read or API call. doby's grep output contains domain/doc/code/symbol/status in a single line.

### Dimension 2: Plan ↔ Code Mapping

| Tool | Plan Integration | Bidirectional | Auto-sync |
|------|-----------------|---------------|-----------|
| **doby** | ★★★★★ Core feature | ✅ Code→doc, doc→code | Hook-based pending tracking |
| **LLM Wiki** | ★★★★ Decision records | One-way (wiki→code) | LLM-based (token cost) |
| **Cline Memory Bank** | ★★★★ productContext.md | One-way (doc→code) | Manual |
| **Copilot Workspace** | ★★★★★ Spec→Plan→Code | One-way (plan→code) | One-shot (per session) |
| **Aider repo-map** | ★★ File ranking only | None | Static snapshot |
| **Greptile** | ★★★ NL query | One-way (query→code) | Auto-indexing |

**doby advantage**: The only tool supporting **bidirectional mapping**. INDEX-codemap.md enables code→doc reverse lookup in 1 grep call.

### Dimension 3: Token Efficiency

| Tool | Build Cost | Query Cost | Update Cost | Change Tracking |
|------|-----------|-----------|-------------|----------------|
| **doby** | 5K-10K (once) | **100-200** | 300-500 | **0** (hook) |
| **LLM Wiki** | 10K-50K (once) | 500-1,000 | 5K-10K | LLM-based (cost) |
| **Cline Memory Bank** | Manual | 500-2,000 | Manual | Manual |
| **Aider repo-map** | tree-sitter parse | 1,000 (budget) | Re-parse | None |
| **Greptile** | Embedding gen (external) | API call | Auto | Auto (external cost) |
| **Augment Code** | Embedding gen (external) | API call | Real-time | Real-time (external cost) |

**Per-session savings** (5-10 change requests):
- Legacy grep/Serena: 10,000-50,000 tokens
- doby: 500-2,000 tokens
- **90-95% token reduction**

**doby advantage**: Change tracking cost is **exactly 0**. The PostToolUse hook appends file paths to a .txt file via shell script — zero LLM token consumption.

### Dimension 4: Infrastructure

| Tool | Requirements | Cost | Portability |
|------|-------------|------|-------------|
| **doby** | 4 markdown files + grep + optional chromadb | Free | ★★★★★ Anywhere |
| **LLM Wiki** | Markdown + optional Obsidian | Free | ★★★★ |
| **Aider repo-map** | Python CLI + tree-sitter | Free | ★★★★ |
| **Cursor .cursorrules** | Cursor IDE | $20/mo | ★★ Cursor only |
| **Greptile** | Cloud API + embeddings | Paid (API) | ★★★ MCP |
| **Augment Code** | Embedding service | Paid | ★★★ MCP |
| **Devin** | Cognition cloud | $500+/mo | ★ Locked in |

### Dimension 5: Scalability

| Tool | Small (<100 files) | Medium (100-1K) | Large (1K+) |
|------|-------------------|-----------------|-------------|
| **doby** | ★★★★★ | ★★★★ | ★★★ (manual upkeep) |
| **Aider repo-map** | ★★★★ | ★★★★★ | ★★★★ (PageRank auto) |
| **Greptile** | ★★★ (overkill) | ★★★★★ | ★★★★★ |
| **Augment Code** | ★★★ (overkill) | ★★★★★ | ★★★★★ (100M+ LOC) |

---

### Overall Rating Matrix

| Dimension | doby | LLM Wiki | Aider | Greptile | Augment | Devin |
|-----------|----------|----------|-------|----------|---------|-------|
| Query token efficiency | ★★★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★ |
| Plan↔code mapping | ★★★★★ | ★★★★ | ★★ | ★★★ | ★★★ | ★★★★ |
| Bidirectional navigation | ★★★★★ | ★★ | ★ | ★★ | ★★ | ★★★ |
| Infrastructure lightness | ★★★★★ | ★★★★ | ★★★★ | ★★ | ★★ | ★ |
| Large-scale scalability | ★★★ | ★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| Auto-maintenance | ★★★★ | ★★★ | ★★★ | ★★★★★ | ★★★★★ | ★★★★★ |
| Transparency/debugging | ★★★★★ | ★★★★ | ★★★★ | ★★ | ★★ | ★ |
| Team sharing | ★★★★★ | ★★★★ | ★★★ | ★★★★ | ★★★ | ★★★ |

---

### doby vs LLM Wiki: Deep Comparison

| Aspect | doby | LLM Wiki |
|--------|----------|----------|
| Philosophy | "Where is it?" — instant navigation | "What is it?" — deep explanation |
| Analogy | Library index card | Encyclopedia |
| Best for | Change requests (navigation) | Understanding / onboarding |
| Query cost | 100 tokens (grep) | 500-1,000 tokens (Read) |
| Bidirectional | ✅ Code→doc + doc→code | ❌ Wiki→code only |
| Change tracking | 0 tokens (shell hook) | LLM tokens (re-read + re-write) |
| Knowledge graph | ❌ Flat structure | ✅ [[wikilink]] cross-references |
| Semantic richness | ❌ Structured metadata only | ✅ Natural language context |
| Auto-generation | ✅ Python heuristics (0 tokens) | ✅ LLM compilation (high tokens) |

**With 4-layer architecture, doby absorbs LLM Wiki's strengths:**
- L2 (Wiki pages) covers semantic richness and design decisions
- L3 (RAG) covers semantic search / natural language queries
- L4 (Auto-compile) covers wiki generation
- L1 (grep index) preserves doby's core advantage: 100-token navigation

---

### When doby Is Optimal

1. **Small-to-medium projects** (100-500 files) with plan docs
2. **Token-constrained budgets** — minimize per-query API cost
3. **Plan-driven development** — plan docs are source of truth
4. **Infrastructure constraints** — no external services or paid IDEs
5. **Transparency required** — fully understand and control the index

### When doby Falls Short

1. **Large monorepos** (10K+ files) — Greptile/Augment auto-indexing wins
2. **No plan docs** — doby's core value disappears
3. **Fully autonomous coding** — Devin/SWE-agent are better suited
4. **Multi-language repos** — Aider's 130+ language tree-sitter support wins

---

## Quick Start

```bash
# Install
git clone https://github.com/yourname/doby ~/.claude/skills/doby

# Setup in your project
cd your-project
bash ~/.claude/skills/doby/install.sh

# Edit .dobyrc.json with your project's mappings
# Then build the index
# /doby build
```

## Layer Details

### L1: Flat-Line Index (Core)

4 INDEX files in `.omc/plans/`. grep-only access. 100 tokens per query.

### L2: Wiki Pages

Markdown files in `.omc/wiki/`. Contains design decisions, trade-offs, and context.
Only opened when user asks "why?" — never auto-loaded.

### L3: Semantic RAG (ChromaDB)

Local vector search. Indexes plan docs + code files.
Activates only when L1 grep returns no results.

```bash
# Index
python ~/.claude/skills/doby/rag.py index

# Query
python ~/.claude/skills/doby/rag.py query "recommend places near user"
```

### L4: Auto-Compile

LLM generates wiki pages from plan docs + code.
Manual trigger only: `/doby compile <topic>`.

## Design Philosophy

1. **Compile Once, Query Many** — build index once, reach any file via grep
2. **Read 0 Principle** — resolve/update never Read INDEX files; grep output only
3. **Layered Cost** — expensive layers only activate when explicitly needed
4. **Zero-Cost Tracking** — change detection uses 0 LLM tokens
5. **Opus supervises, Haiku executes** — cost-efficient model routing
