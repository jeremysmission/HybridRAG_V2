# Background Runbook — 2026-04-12

**Window:** next 48 hours from 2026-04-12 late evening MDT
**Scope:** Machine assignment, dependency gates, and stop rules
**Goal:** Keep one truthful demo lane moving without touching frozen operator surfaces

## Gates

| Gate | Must be true before next phase | Unlocks |
|---|---|---|
| G0 | Installer correctness is frozen: reviewer B+C lands, `scripts\verify_install.py` passes on the workstation desktop and laptop | Any unattended workstation run |
| G1 | Tier 2 OOM root cause is confirmed and the recovery action is approved | Clean primary workstation work resumes |
| G2 | Clean Tier 1 rerun completes on the authoritative store | Truthful eval against clean data |
| G3 | Production eval on the cleaned store is complete and the demo query pack is narrowed | Rehearsal |
| G4 | Rehearsal passes: canary controls pass if used, narrow real-scoped checks pass, scripted queries pass on the actual machine | Aggregation allowed in the live script |

## Asset Assignments

### primary workstation GPU 1

- **Now until G1:** Reserve for Tier 2 OOM investigation and the approved recovery path only. No competing long jobs.
- **After G1:** Run the clean Tier 1 rerun on the authoritative primary workstation store.
- **After G2:** Run any remaining clean-store extraction or verification work that is required for the demo path.
- **After G3:** Hold as the primary authoritative rehearsal lane and final demo-box validation lane.

### primary workstation GPU 0

- **Now until G2:** Keep free for short probes, installer smoke tests, query-pack checks, and emergency support. Do not start another long extraction.
- **After G2:** Use as the support lane for retrieval smoke tests, canary validation, and backup query rehearsal.
- **After G3:** Keep as contingency capacity only. Do not steal resources from the primary demo lane.

### Workstation Desktop

- **Now until G0:** No unattended production run. Limit work to reachability, power, disk, and basic readiness checks.
- **Immediately after G0:** Pull or zip-pull the frozen installer state, run `scripts\verify_install.py`, and become the unattended backup compute lane.
- **Preferred use after G0:** Long unattended rebuild or extraction work that should not block primary workstation.
- **After G2:** If counts and scripted queries match the frozen packet, hold as the validated backup demo machine.

### Workstation Laptop

- **Now until G0:** No reinstall churn and no long extraction work.
- **Immediately after G0:** Zip-pull the frozen installer state, run `scripts\verify_install.py`, and use it for operator smoke tests and retrieval-first rehearsal.
- **After G3:** Hold as the presentation fallback, notes, and source-evidence station. Do not treat it as the primary heavy-compute lane.

## 48-Hour Sequence

### Phase 1 — Close the blockers in parallel

- Close **G1** on primary workstation first. Without the Tier 2 resolution, the clean store cannot be trusted.
- Close **G0** in parallel on the workstation desktop and laptop. Do not wait on primary workstation to freeze installer correctness.
- Keep primary workstation GPU 0 open for fast checks while GPU 1 stays protected.

### Phase 2 — Rebuild and remeasure

- Once **G1** closes, run the clean Tier 1 rerun on primary workstation GPU 1 and freeze the resulting counts.
- Once **G0** closes, use the workstation desktop for any long unattended backup run and the laptop for smoke and operator checks only.
- Do not start rehearsal until **G2** and **G3** are both closed.

### Phase 3 — Rehearse only on frozen truth

- Run rehearsal only after the cleaned-store eval and narrowed query pack exist.
- If aggregation is still in scope, require **G4** before it appears in the live script.
- If **G4** does not close in time, downgrade to the retrieval-first script and stop there.

## Stop Rules

- Do not run unattended workstation jobs before **G0**.
- Do not run the clean Tier 1 rerun before **G1**.
- Do not run eval on a store that is not the frozen authoritative store from **G2**.
- Do not rehearse aggregation before **G4**.
- If counts drift on any machine after freeze, remove that machine from the demo lane until it is rechecked.

## Default Fallback If Gates Slip

- **Primary live path:** retrieval-first demo on the authoritative primary workstation store
- **Backup machine:** validated workstation desktop
- **Operator support box:** workstation laptop
- **Dropped capability first:** broad aggregation claims
