# Vocab Validation / Lookup CLI Run Note

Date: 2026-04-15
Scope: BUILD-03 controlled vocabulary first consumer
Status: usable today

## Purpose

This CLI is the first low-risk consumer of the controlled vocabulary packs.
It does three deterministic things without changing extraction defaults:

- validates the shipped vocab packs
- resolves exact alias/canonical lookups
- scans text or a UTF-8 text file for bounded literal vocab hits

## Primary command

```powershell
.\.venv\Scripts\python.exe scripts\vocab_validation_lookup_cli_2026-04-15.py --lookup DD1149 --lookup POAM --text "Patrick AFB uses DD1149 and POAM tracking."
```

## Typical uses

Validate packs only:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_validation_lookup_cli_2026-04-15.py
```

Lookup a known alias:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_validation_lookup_cli_2026-04-15.py --lookup "Patrick AFB"
```

Scan a file:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_validation_lookup_cli_2026-04-15.py --text-file .\sample.txt
```

Emit machine-readable JSON:

```powershell
.\.venv\Scripts\python.exe scripts\vocab_validation_lookup_cli_2026-04-15.py --lookup POAM --json
```

## Output behavior

- Reports pack counts, entry counts, regex-safe counts, retrieval-expand counts
- Flags cross-pack alias collisions such as `POAM`
- Shows exact lookup hits and whether a lookup is ambiguous
- Shows text-scan hit spans and canonical targets

## Safety

- Read-only relative to extraction defaults
- No automatic regex promotion
- No automatic retrieval rewiring
- Intended for validation, inspection, normalization prep, and safe downstream tooling
