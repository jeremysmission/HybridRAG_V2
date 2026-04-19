# Tier 1 Proactive Quality Plan 2026-04-12

## Purpose

This document records the current findings, lessons learned, technical plan, and theory of operation for getting Tier 1 into a trustworthy state and keeping future network-drive additions from polluting production again.

The core decision is:

- do not run another blind full Tier 1 rerun
- do not treat regex as the truth layer
- make Tier 1 pass a staged automated quality gate before any full rerun or future production promotion

## Status

As of 2026-04-12:

- Tier 1 regex hardening, corpus confusion-set research, automated pre-rerun gate, and external best-practice research are complete
- the current system now has a concrete pre-rerun process instead of guess-and-check
- the next step is a gated shadow run, not a full rerun

Relevant recent work:

- `34b64d8` Tighten Tier 1 PO and part boundary guards
- `d0476bb` docs: audit tier1 PO and PART confusion sets
- `f3bafb7` Add Tier 1 regex pre-rerun gate
- `a45e62f` fix(ops): strengthen tier1 regex gate curated cases
- `1620084` docs: formalize tier1 regex acceptance gate
- `e94d704` docs: add Tier 1 regex research synthesis
- `54eadec` docs: add tier1 regex corpus rerun audit

Supporting docs:

- `docs/TIER1_REGEX_ACCEPTANCE_GATE_2026-04-12.md`
- `docs/TIER1_REGEX_CORPUS_AUDIT_2026-04-12.md`
- `docs/TIER1_REGEX_GATE_RUNBOOK_2026-04-12.md`
- `docs/TIER1_REGEX_RESEARCH_SYNTHESIS_2026-04-12.md`

## Findings

The main findings are:

- `PO` and `PART` were polluted by security-standard and cyber-governance tokens, not by a small number of isolated bad regexes
- a one-time regex cleanup is not enough; this must become a staged promotion process
- the right model is not "regex is truth"
- the right model is "regex is a candidate generator, then validators decide what becomes a business entity"
- external best-practice research strongly supports shadow runs, sample-based acceptance gates, and fail-closed promotion

Important confusion-set examples already proven in the corpus:

- `PO` junk:
  - `IR-8`, `IR-4`, `IR-9`, `IR-3`
  - `IR-4A`, `IR-1N-04`
  - `FSR-L22`, `ASV-VAFB`, `RTS-DATA`
- `PART` junk:
  - `AS-5021`, `OS-0004`, `GPOS-0022`
  - `CCI-0003`, `SV-2045`, `CCE-8043`, `CVE-2018`, `RHSA-2018`
  - `pam_faillock`, `SERVICE_STOP`, `SNMP`, `mode`, `NORMAL`, `failure`

Important preserve-set examples already proven in the corpus:

- `PO`:
  - `7000372377`, `7200751620`, `5000696458`, `5300168230`
- `PART`:
  - `RG-213`, `LMR-400`, `FGD-0800`, `PCE-4129`, `PT-2700`, `TK-423`, `PS-110`, `MRF-141`

## Lessons Learned

1. A successful run is not the same thing as a trustworthy run.
2. Regex-only extraction is too brittle if it is allowed to write directly to the authoritative store.
3. Future data additions will keep introducing new collisions unless we fail closed.
4. The expensive mistake is not "writing too many tests." The expensive mistake is burning a full rerun day on dirty logic.
5. The process must be proactive:
   - stage
   - audit
   - promote
   - never "rerun first, inspect later"

## Path Forward

### Immediate next step

Run the pre-rerun gate:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe scripts\audit_tier1_regex_gate.py
```

### If the gate passes

Run a shadow Tier 1 job on roughly 5,000 to 10,000 chunks.

The shadow run must be judged against:

- zero blocked-namespace leakage in top `PO` and `PART` values
- preserve-set identifiers still present
- manual spot check of post-run top values
- sampled precision target:
  - `PO >= 97%`
  - `PART >= 95%`

### Only then

- run the full clean Tier 1 rerun once
- rerun the 400-query production baseline on the cleaned store
- then prioritize:
  - retrieval miss families
  - router quality
  - structured-answer improvements

## Technical Theory Of Operation

The production-safe design for Tier 1 should be:

1. New network-drive data lands in staging.
2. Tier 1 regex produces entity candidates on the staged delta.
3. Validators and invalidators decide what can become business entities.
4. Automated gates inspect:
   - curated adversarial cases
   - preserve sets
   - top values
   - drift against prior good distributions
5. Only a passing delta is promoted into the authoritative store.

In technical terms:

- regex is the broad matcher
- validators add context, shape checks, and governed-namespace invalidation
- ambiguity fails closed
- production writes happen only after automated approval

The long-term architecture should evolve toward:

- `BUSINESS_PO` separated from `REPORT_ID`
- future `SECURITY_CONTROL` / `CYBER_BASELINE` buckets instead of business-entity collisions
- mandatory staging and promotion for every new delta

## Non-Technical Theory Of Operation

Plain-English version:

- the system was finding things that looked like parts and purchase orders
- some of those were not real business items; they were security-control codes and cyber-governance labels
- if we let those flow straight into production, the system can answer with bad data
- the fix is not to "hope the regex is better now"
- the fix is to make every future update pass an automated quality inspection before it is allowed into production

## Manager Status Summary

If asked why this is taking time, the short answer is:

"We found that Tier 1 was capable of producing clean-looking but misleading business entities because some security-standard identifiers were being mistaken for parts and purchase orders. We stopped the blind rerun path, hardened the extraction rules, built an automated gate, built a corpus-derived confusion audit, and defined a shadow-run approval process so future data additions can be blocked before they contaminate production. The work is now in the stage where we can do one intentional shadow run and one intentional clean rerun instead of repeatedly losing full days to dirty runs."

## Definition Of Done For This Phase

This phase is complete when:

- the automated gate passes
- the shadow run passes
- the full clean Tier 1 rerun is completed once
- the cleaned store becomes the new baseline for retrieval and RAGAS work

