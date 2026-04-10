# HybridRAG V2 — Repository Rules

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-04 MDT
**Applies to:** All files in this repository and the EmbedEngine companion repo

---

## 1. Code Rules

- **500 lines max per class** (comments/docstrings excluded). Keeps code AI-reviewable, portable, and modular.
- **No offline LLM mode.** Online-only, single code path. No mode switching.
- **Pin openai SDK to v1.x** — NEVER upgrade to 2.x without explicit approval.
- **DO NOT use `pip install sentence-transformers[onnx]`** — the `[onnx]` extra pulls CPU-only torch from PyPI, overwriting the CUDA wheel.
- **Config validated once at boot, immutable after.** No runtime config mutation.

## 2. File Naming Convention

All documents and deliverables use the format:

```
Intuitive_Title_YYYY-MM-DD.ext
```

Examples:
- `V2_Design_Proposal_2026-04-04.md`
- `Sprint_Plan_2026-04-04.md`
- `Requested_Waivers_2026-04-04.md`

Code files use standard Python naming (`snake_case.py`).

## 3. Waiver Compliance

- All new packages must be **MIT, Apache 2.0, or BSD** licensed.
- All new packages must originate from **USA or NATO ally countries**.
- Check `docs/Requested_Waivers_2026-04-04.md` before adding ANY dependency.
- Every new dependency must have a documented **fallback** using already-approved software.
- **Banned packages** (do not use, do not propose):
  - LangChain (200+ deps, version instability)
  - ChromaDB (telemetry, forces onnxruntime)
  - Milvus/pymilvus (China origin, NDAA)
  - DuckDB+VSS (crash risk, RED on waiver sheet)
  - BGE/BGE-M3 embeddings (BAAI, China, NDAA)
  - Qwen models (Alibaba, China, NDAA)
  - DeepSeek (China, NDAA)
  - Meta Llama (AUP prohibits military use)
  - E5 models (developed at Microsoft Research Asia, Beijing)
  - Jina embeddings v4 (CC BY-NC 4.0 — non-commercial license)
  - PyMuPDF (AGPL copyleft — viral license)

## 4. Sanitization Before Remote Push

**MANDATORY:** Run the sanitization script before every push to any remote repository.
This includes anything that will be used on workstations or by workstation operators.

```bash
# Dry-run first (report only, no changes):
python sanitize_before_push.py

# Apply sanitizations in-place:
python sanitize_before_push.py --apply

# Archive originals before rewriting:
python sanitize_before_push.py --apply --archive-dir "C:\Pre_Sanitized_Archives"
```

### What Gets Sanitized

| Category | Examples | Replaced With |
|---|---|---|
| AI tool references | CoPilot+, opus, approved vendor, CoPilot+ | CoPilot+ or approved vendor |
| Agent references | reviewer-6, design review, review board | team review, design review |
| Corporate/org names | organization names, org abbreviations | organization, enterprise |
| Personal paths | {USER_HOME}, {USER_HOME} | {USER_HOME}, {PROJECT_ROOT} |
| Personal identifiers | GitHub usernames, email addresses | {GITHUB_USER}, {USERNAME} |
| Compliance terms | Specific standard numbers, authorization refs | Generic equivalents |
| enterprise-specific terms | restricted, offline, production-grade | Restricted, offline, production-grade |

### Rules for Document Authors

When writing any `.md`, `.py`, `.yaml`, or other text file:

1. **Do not reference AI vendor names** (no CoPilot+, no Opus, no approved vendor, no CoPilot+). Use "CoPilot+" as the attributed author.
2. **Do not reference agent names** (no reviewer-6). Use "design review" or "team evaluation" instead.
3. **Do not reference review boards or debate sessions.** Use "design review" or "competitive evaluation."
4. **Do not include personal paths.** Use `{PROJECT_ROOT}`, `{USER_HOME}`, `{DATA_DIR}` placeholders.
5. **Do not include GitHub usernames** in documents. Use `{GITHUB_USER}` if referencing the repo.
6. **Sign documents as** `Jeremy Randall (CoPilot+)` or just `Jeremy Randall`.

The sanitization script is the safety net. These rules are the first line of enterprise.
Do not treat the script as the sole sanitizer.
Workstation-bound content must be authored in sanitized form first, then checked by the script as the final catchall.

### Adding the Sanitization Script to New Repos

Every new repo (HybridRAG_V2, EmbedEngine, etc.) must include:
1. A copy of `sanitize_before_push.py` at the repo root
2. This rules document in `docs/`
3. The script listed in `SKIP_FILENAMES` so it does not sanitize its own replacement patterns

## 5. Git Rules

- **Do not push to remote without running the sanitization script first.**
- **Do not commit** `.env`, `credentials.json`, `*.key`, `*.pem`, or any secrets.
- **Do not commit** large data files (`.sqlite3`, `.faiss`, `.f16.dat`, `.lance/`). These go in `.gitignore`.
- **Do not amend published commits.** Create new commits instead.
- **Do not force-push** to main/master without explicit approval.
- **Commit messages** should be concise and describe the "why," not the "what."

## 6. Testing

- Golden eval queries live in `tests/golden_eval/`.
- Run tests with `pytest tests/`.
- Target: 20+ golden queries passing by demo date.
- Every sprint exit requires documented eval results.
- **3-Tier Test Corpus (MANDATORY for all end-to-end tests):**
  - **Tier 1 (smoke):** Easy, clean files that should always pass (`tests/test_corpus/tier1_smoke/`)
  - **Tier 2 (stress):** Messy, real-world files — OCR garbage, email chains, fragmented data (`tests/test_corpus/tier2_stress/`)
  - **Tier 3 (negative):** Files the system must NOT let through — empty, binary, injections, foreign language (`tests/test_corpus/tier3_negative/`)
- Every new test must exercise all three tiers. No shortcuts.
- **Real hardware testing (MANDATORY):** Every sprint QA must include a "primary workstation hardware pass" — real GPU embedding, real corpus data, real API calls on the development workstation. Virtual/mocked tests are necessary but insufficient. Mark tests as hardware-verified vs virtual-only.
- **QA uses real data whenever possible:** Don't just QA against the small test corpus. When primary workstation is available, import and test against real production enterprise program documents (or a representative subset of the 700GB corpus). Synthetic tests prove code compiles — real data proves it works.
- **Single-GPU to emulate Blackwell workstations:** the development workstation may have more local GPU headroom than work machines. Always QA with `CUDA_VISIBLE_DEVICES=0` to constrain to one GPU. This catches memory pressure, batch sizing, and concurrency issues that otherwise stay hidden.

## 7. Documentation

- All design docs, sprint plans, and waiver requests go in `docs/`.
- All docs are produced in both `.md` and `.docx` format.
- Use the `scripts/convert_docs_to_docx.py` script to generate `.docx` from `.md`.
- Keep docs current — update when architecture changes, not retroactively.

---

Jeremy Randall | HybridRAG_V2 | 2026-04-04 MDT
