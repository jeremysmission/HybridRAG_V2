# Installed-Base Denominator — Source Scouting Note

**Author:** Jeremy Randall (CoPilot+)
**Repo:** HybridRAG_V2
**Date:** 2026-04-19 MDT
**Backlog item:** AGGREGATION P1 — Identify denominator sources needed for true failure rates on NEXION/ISTO systems
**Unblocks:** Q3 YELLOW → GREEN upgrade (`top 5 failure-rate parts ranked each year × 7 years`)

---

## Purpose

Without an installed-base denominator substrate, failure **counts** can be GREEN but failure **rates** stay YELLOW per the evidence contract. This note identifies which source families in the corpus carry deployment / inventory / as-built data and what extractor work is needed to turn them into a `installed_base` SQLite table.

---

## Candidate source families (from 93,636 source_metadata rows)

Path-match scan on `data/index/retrieval_metadata.sqlite3`:

| Folder / filename marker | Row count | Signal strength |
|-------------------------|-----------|-----------------|
| `%inventory%`           | 1,403 | STRONG — explicit inventory docs |
| `%as_built%`            | 1,762 | STRONG — as-built configs at install |
| `%as-built%`            | 1,682 | STRONG — same (hyphen variant) |
| `%installation%`        | 2,454 | STRONG — install summaries, prep |
| `%site_survey%`         | 1,215 | MEDIUM — site characterization |
| `%equipment%`           | 886   | MEDIUM — equipment lists |
| `%spares%`              | 195   | MEDIUM — spares inventory (narrow) |
| `%configuration%`       | 496   | MEDIUM — config baselines |

**Total candidate universe:** ~10,000 unique documents likely to carry installed-base data.

---

## Top 5 high-yield document families

### 1. Site Inventory Report (xlsx) — HIGHEST YIELD
**Pattern:** `! Site Visits\(01) Sites\<SITE>\<date-range>\Site Inventory\Site Inventory Report_<SITE> (<date>).xlsx`

**Example paths:**
```
D:\CorpusTransfr\verified\IGS\! Site Visits\(01) Sites\Alpena\2021-06-02 thru 06-08 (NEXION_ASV-RTS)(Seagren-Pitts)\Site Inventory\Site Inventory Report_Alpena (2-8 Jun 2021).xlsx
D:\CorpusTransfr\verified\IGS\! Site Visits\(01) Sites\Alpena\2021-06-02 thru 06-08 (NEXION_ASV-RTS)(Seagren-Pitts)\Site Inventory\Copy of Alpena Inventory  Spares Report.xlsx
```

**Why high yield:**
- Structured xlsx (tabular substrate already extractable via existing `extracted_tables` path)
- Explicit per-site scope
- Explicit date in filename (year extraction free)
- Recurring cadence (likely one per ASV visit per year per site)
- Almost certainly contains part_number + quantity + location columns

**Expected extractable fields:**
- `part_number`, `qty_on_hand`, `qty_installed`, `qty_spare`
- `site` (from folder path, same as source_metadata.site_token)
- `snapshot_date` (from filename + folder path)
- `system` ("NEXION_ASV" in path tokens — detectable)

### 2. As-Built Drawings / Documents
**Pattern:** `... \Installation Summary Documents\Attachments\<SITE>_As-Built *<date>*.pdf|xlsx|docx`

**Examples:**
```
\Installation Summary Documents\Attachments\Ascension Island_As-Built_20081010 RevA.pdf
\Installation Summary Documents\Attachments\Guam_As-Built Drawings_200811009_RevA.pdf
\Installation Summary Documents\Archive\San Vito_As-Built Drawings_200811005 RevA.pdf
```

**Why useful:** first-deployment record — anchor the installed-base timeline. Once we know install-date + parts-list, we have the `t=0` for any per-year rate calculation.

**Extractable fields:** `system`, `site`, `install_date`, `part_number` (if drawings enumerate parts)

### 3. Spares Inventory docs
**Pattern:** `... Spares Inventory (<SITE>)_(<date>).pdf|xlsx`

**Examples:**
```
\Alpena\2017-08-13 thru 08-18\Spares Inventory (Alpena)_(2017-08-16).pdf
\Alpena\2021-06-02 thru 06-08\Site Inventory\Copy of Alpena Inventory  Spares Report.xlsx
```

**Why useful:** complements installed count with spare-kit coverage. Gives a denominator for "spare days of coverage" metrics.

### 4. Post/Pre-Deployment Test Cards
**Pattern:** `... \Install\TAB 12 - TEST PLAN\POST-DEPLOYMENT\...` / `PRE-DEPLOYMENT`

**Why useful:** bookends the install event. Tells us the deployment date boundary for rate calculation over a known operational period.

### 5. Additional Inventory (loose)
**Pattern:** `...\Misc\Additional Inventory.pdf` etc.

**Why useful:** catches late additions to the installed base. Lower structure but easy to dedup against #1.

---

## Proposed `installed_base` SQLite schema

```sql
CREATE TABLE installed_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_doc_hash TEXT NOT NULL DEFAULT '',
    extraction_method TEXT NOT NULL DEFAULT '',   -- 'inventory_xlsx_v1', 'as_built_pdf_v1', etc.
    system TEXT NOT NULL DEFAULT '',              -- NEXION, ISTO
    site_token TEXT NOT NULL DEFAULT '',
    part_number TEXT NOT NULL DEFAULT '',
    qty_installed INTEGER,
    qty_on_hand INTEGER,
    qty_spare INTEGER,
    snapshot_date TEXT,                           -- 'YYYY-MM-DD'
    snapshot_year INTEGER,
    install_date TEXT,                            -- first-install anchor
    confidence REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ib_part ON installed_base(part_number);
CREATE INDEX idx_ib_sys_site_year ON installed_base(system, site_token, snapshot_year);
CREATE UNIQUE INDEX uq_ib_snapshot
    ON installed_base(source_path, part_number, snapshot_date);
```

## Rate SQL shape (once populated)

```sql
-- Failure rate = failures / installed-qty for a (part, system, site, year) tuple.
SELECT
    f.part_number,
    f.system,
    f.site_token,
    f.event_year,
    COUNT(*) AS failures,
    (
      SELECT SUM(qty_installed)
      FROM installed_base ib
      WHERE ib.part_number = f.part_number
        AND ib.system      = f.system
        AND ib.site_token  = f.site_token
        AND ib.snapshot_year <= f.event_year
      ORDER BY ib.snapshot_year DESC
      LIMIT 1
    ) AS installed_qty
FROM failure_events f
WHERE f.part_number != ''
GROUP BY f.part_number, f.system, f.site_token, f.event_year
HAVING installed_qty IS NOT NULL AND installed_qty > 0
ORDER BY (CAST(failures AS REAL) / installed_qty) DESC
LIMIT 5;
```

This lets us answer Q3 as **GREEN** for (part, site, year) tuples where both numerator and denominator exist, and cleanly degrade to YELLOW where the denominator is missing.

---

## Extractor work required (estimated)

| Component | Scope | Est. effort |
|-----------|-------|------------|
| xlsx table parser for "Site Inventory Report" family | 1 family, structured | 3-5 days |
| As-built PDF/docx extractor (header + parts list) | heterogeneous PDFs | 3-5 days |
| Install-date anchor extractor (folder path date tokens) | parse `YYYY-MM-DD thru MM-DD` patterns in folder names | 1 day |
| Site alias reuse | reuse `config/canonical_aliases.yaml` | 0 (done) |
| Populate script `scripts/populate_installed_base.py` | mirror of failure_events populate | 1-2 days |
| Integration with `aggregation_executor.py` rate branch | add `rate_by_group` SQL template | 1 day |

**Total: 9-14 days of engineering** — fits in Sprint 6 of the mega plan (post-demo acceptable).

---

## Known gaps / risks

1. **As-built drawings are heterogeneous** — PDFs with varying layouts; expect per-site customization. Plan: template-detection first, then per-template extractor.
2. **Snapshot date vs. install date** — inventory snapshots change over time; we need the *as-of* semantics right (use the snapshot closest to but not after the failure year).
3. **Spares vs. installed semantics** — a "spare" part isn't in use until consumed; may need separate `qty_spare` vs `qty_active` accounting.
4. **Multi-visit same-site same-year** — several ASV visits per year to the same site; pick the latest inventory per (site, year) to avoid double-counting.
5. **Small-N rate amplification** — rate = 1/1 = 100% reads catastrophic but is a single event. Add a `min_installed` threshold (e.g., ≥ 3) before promoting to GREEN for rate; otherwise YELLOW with "small denominator" caveat.

---

## Next actionable slice (for future sprint)

1. Sample 10 `Site Inventory Report_*.xlsx` files (one per major site)
2. Document the column-header variants across them
3. Build xlsx parser against that template
4. Populate `installed_base` with 10-site pilot (est. ~500-2000 rows)
5. A/B test Q3: rate calculations where denominator exists → GREEN cell; elsewhere YELLOW
6. QA gate

---

## Relationship to existing V2 substrate

- `source_metadata.sqlite3` already has the `site_token` + path info we need to scope the scan.
- `failure_events.sqlite3` is the numerator substrate — this doc proposes the denominator companion.
- The aggregation executor's rate branch already flags YELLOW correctly; no executor code change needed until denominator exists.
- Truth pack `FAIL-AGG-03` already references `requires_denominator: true` — it will auto-upgrade to GREEN once the substrate exists.

---

Jeremy Randall | CoPilot+ | HybridRAG_V2 | 2026-04-19 MDT
