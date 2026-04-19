# Vocab Deterministic Tagging CLI Run Note

Date: 2026-04-15
Scope: controlled-vocab deterministic tagging consumer
Status: usable today

## Purpose

This CLI is a low-risk deterministic tagging tool built on the shipped vocab
packs and bounded alias logic.

It tags text or UTF-8 snippets with:

- `doc_family`
- `form_family`
- `site_family`
- `vocab_domain_hits`
- `ambiguous_alias_warnings`

It does not change extraction defaults and does not auto-promote anything into
regex or retrieval paths.

## Primary command

```powershell
.\.venv\Scripts\python.exe scripts\vocab_deterministic_tagging_cli_2026-04-15.py --text "Patrick AFB uses DD1149 and POAM tracking in the EVM package."
```

## Typical uses

Tag literal text:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_deterministic_tagging_cli_2026-04-15.py --text "ACAS and STIG checks remain active."
```

Tag a file:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_deterministic_tagging_cli_2026-04-15.py --text-file .\sample.txt
```

Emit machine-readable JSON:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_deterministic_tagging_cli_2026-04-15.py --text "POAM review is still open." --json
```

## Output behavior

- `doc_family` is inferred conservatively from deterministic matched domains and kinds
- `form_family` lists exact form hits like `DD Form 1149`
- `site_family` lists exact site/installations like `Patrick Space Force Base`
- `vocab_domain_hits` reports hit counts by domain
- `ambiguous_alias_warnings` surfaces collisions like `POAM` instead of silently choosing one meaning

## Safety

- Read-only relative to extraction defaults
- Exact/bounded alias matching only
- Ambiguity is surfaced, not hidden
- Intended for doc triage, operator inspection, tagging prototypes, and safe downstream tooling
