# HybridRAG V2 — CLAUDE.md

Auto-loaded rules for all agents working in this repo.

---

## Project

HybridRAG V2 is a tri-store retrieval and answer system for IGS/NEXION maintenance documents. It consumes pre-built chunks from CorpusForge and serves semantic, entity, aggregation, and tabular queries.

- **Repo:** C:\HybridRAG_V2
- **Venv:** `.venv` (Python 3.11+, torch CUDA cu128)
- **Demo target:** 2026-05-02
- **Cross-repo dependency:** CorpusForge (C:\CorpusForge) produces chunk exports; this repo imports them

---

## Code Rules

- **500 lines max per class** (comments/docstrings excluded)
- **No offline LLM mode** — online-only, single code path, no mode switching
- **Pin OpenAI SDK to v1.x** — NEVER upgrade to 2.x without explicit approval
- **DO NOT install `sentence-transformers[onnx]`** — it pulls CPU-only torch, nuking the CUDA wheel
- **CUDA-only embedding** — CPU/Ollama HTTP is 45x slower, unacceptable for production
- **Config validated once at boot, immutable after** — no runtime config mutation
- **Provider auto-detect:** `OPENAI_API_KEY` (home) or `AZURE_OPENAI_ENDPOINT` + key (work)
- **phi4:14b ($0 local) for bulk extraction** — GPT-4o for user-facing queries only
- **Ollama = dev/test only** — never for production answers
- **Hardware preset in config** — one code path with hardware-specific config, not separate product modes

## Dependency Policy

- All new packages: **MIT, Apache 2.0, or BSD** licensed
- All new packages: **USA or NATO ally** country of origin
- Check `docs/Requested_Waivers_2026-04-04.md` before adding ANY dependency
- Every new dependency must have a documented fallback using already-approved software
- **Banned packages** (do not use, do not propose):
  - LangChain, ChromaDB, Milvus/pymilvus, DuckDB+VSS
  - BGE/BGE-M3, Qwen, DeepSeek, Meta Llama, E5 models
  - Jina embeddings v4 (CC BY-NC 4.0), PyMuPDF (AGPL)

## File Naming

- Documents: `Intuitive_Title_YYYY-MM-DD.ext`
- Code files: standard Python `snake_case.py`
- Produce docs in both `.md` and `.docx` format

---

## Git Rules

- **Sanitize before every remote push:** `python sanitize_before_push.py --apply` then commit, then push
- **Never commit:** `.env`, `credentials.json`, `*.key`, `*.pem`, secrets, large data files
- **Never amend published commits** — create new commits
- **Never force-push** main/master without explicit approval
- **Commit messages:** concise, describe the "why" not the "what"
- **No AI attribution** — use "CoPilot+" only, commits by Jeremy Randall only. Never mention claude/anthropic/agent/AI in code or commits.
- **Sign all war room posts:** `Signed: Agent N (Role) | HybridRAG_V2 | YYYY-MM-DD | [Time MDT]`

---

## Sanitization Rules

Run `sanitize_before_push.py` before every push. The script catches:
- AI tool/vendor references → "CoPilot+" or "approved vendor"
- Agent references → "team review", "design review"
- Corporate/org names → generic equivalents
- Personal paths → `{USER_HOME}`, `{PROJECT_ROOT}`
- GitHub usernames → `{GITHUB_USER}`

**Author documents in sanitized form first.** The script is the safety net, not the sole sanitizer.

---

## Testing

### 3-Tier Test Corpus (MANDATORY)

- **Tier 1 (smoke):** `tests/test_corpus/tier1_smoke/` — clean files, always pass
- **Tier 2 (stress):** `tests/test_corpus/tier2_stress/` — OCR garbage, email chains, fragments
- **Tier 3 (negative):** `tests/test_corpus/tier3_negative/` — empty, binary, injections, foreign language
- Every new test must exercise all three tiers. No shortcuts.

### Golden Eval

- Queries in `tests/golden_eval/`
- Run with `pytest tests/`
- Target: 20/25+ passing on production data by demo date
- Every sprint exit requires documented eval results

### Real Hardware Testing (MANDATORY)

- Every sprint QA includes a Beast hardware pass (real GPU, real corpus data, real API)
- Single-GPU mode: `CUDA_VISIBLE_DEVICES=0` to emulate work Blackwell machines
- Virtual/mocked tests are necessary but insufficient
- Mark tests as hardware-verified vs virtual-only

---

## QA — 5 Pillars (Every Sprint Exit)

1. **Boot & Config** — loads, validates, bad config caught
2. **Core Pipeline** — embedding on CUDA, LLM connects, router classifies, full query E2E, streaming
3. **3-Tier Corpus** — all three tiers tested
4. **Real Data Pass** — import real docs, embed on GPU, extract entities, query returns real content
5. **Graceful Degradation** — no API key → 503, empty store → 503, corrupted input → skip+log

### Agentic/LLM QA

- Test each nondeterministic stage separately (router, retrieval, context, generation, CRAG)
- Multidimensional eval: factual correctness, context use, consistency, latency, cost, safety
- Grader hierarchy: deterministic first, LLM-as-judge second, human review for critical cases
- Adversarial coverage: prompt injection, jailbreak, corrupt chunks, encoding issues
- Variance: rerun stochastic evals 3+ times, report variance alongside pass/fail

---

## GUI QA (When GUI Changes Present)

### Test Tiers

- **Tier A:** Scripted functional (automated event injection)
- **Tier B:** Smart monkey (targeted chaos — rapid submit, cancel mid-stream, resize)
- **Tier C:** Dumb monkey (60s random clicks, 0 crashes/freezes tolerance)
- **Tier D:** Human button smash (10 min, non-developer tries to break it)

### Key Smash Test Cases

- Q1-Q8: Query panel (rapid submit, empty query, submit during stream, cancel, paste 10KB, SQL injection, unicode, double-click)
- I1-I5: Index panel (start/cancel toggle, close during index, switch tabs, re-index while running, empty dir)
- S1-S3: Settings (invalid values, rapid save, change mid-query)
- W1-W5: Window (resize minimum, resize during stream, minimize during query, multi-monitor, close during boot)
- T1-T4: Threading (query+index simultaneous, rapid tab switching, status bar consistency, memory leak <100MB/50 queries)

**Demo gate requires** a human button smash by someone who didn't write the code.

---

## QA While Running: Next-Sprint Prep Protocol

QA time = planning time. In parallel:
1. Re-read architecture docs for next sprint
2. Web search current best practices (mandatory — never guess)
3. Write slice breakdown with effort estimates, dependencies, risks
4. Capture the game plan so sprint starts immediately when QA passes

---

## GPU Rules

- Beast: dual 3090 FE (24GB each). GPU 0 = idle/compute, GPU 1 = display
- Always check `nvidia-smi` before GPU work, pick the lesser-used GPU
- Use `CUDA_VISIBLE_DEVICES=0` for single-GPU QA passes

## Workstation Reminders

- Use repo venv: `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe`
- Work network proxy: set `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` session vars
- Verify torch CUDA: `.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"`
- Throughput: 5M/hour sustained = ~83K tokens/min; 10M/hour = ~167K tokens/min

---

## Porting Guardrail

When copying code from another repo:
- Diff parser coverage against the active allowlist
- Identify fully parsed / placeholder-only / hashed-only / unsupported formats
- Confirm deferred formats are operator-visible in skip accounting
- Document inherited deferrals before production use
- Silent format loss is a production bug

---

## Related Docs

- `GUIDE.md` — architecture overview and dev constraints
- `docs/Repo_Rules_2026-04-04.md` — full repo rules (source for this file)
- `docs/QA_EXPECTATIONS_2026-04-05.md` — full QA protocol
- `docs/QA_GUI_HARNESS_2026-04-05.md` — full GUI QA harness
- `docs/SPRINT_SYNC.md` — cross-repo sprint coordination
- `docs/Requested_Waivers_2026-04-04.md` — dependency waiver sheet
