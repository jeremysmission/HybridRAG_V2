# Tier 1 Regex Research Synthesis — 2026-04-12

**Author:** Agent 4  
**Repo:** `C:\HybridRAG_V2`  
**Scope:** External research synthesis for the Tier 1 regex hardening lane, mapped onto the current `PART` / `PO` pollution problem in HybridRAG_V2.  
**Primary local problem statement:** current Tier 1 extraction polluted `PO` and `PART` with security-control / STIG / baseline identifiers. See [NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md](./NIST_REGEX_OVER_MATCHING_INVESTIGATION_2026-04-12.md) and [V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md](./V2_DEMO_READINESS_GAP_ANALYSIS_2026-04-12.md).

## 1. Executive Summary

The strongest external pattern is not "write a better regex and rerun." It is:

1. treat regex as a **candidate generator**, not the full truth layer
2. add **type-specific validators / invalidators**
3. run a **dry-run or shadow pass** on representative slices before enabling the real action
4. measure **precision on critical slices**, not only overall random samples
5. only approve the full rerun after both **adversarial fixtures** and **corpus-backed audits** pass

That is the common shape across:

- mature rule engines and IE toolkits such as spaCy, Stanford CoreNLP, and Microsoft Presidio
- operational detection systems such as GitHub secret scanning
- weak-supervision / data-centric systems such as Snorkel and skweak
- official assessment and sampling guidance from NIST

### Bottom-line conclusion for HybridRAG_V2

Rules-only extraction can be trustworthy enough **only** for narrow, high-precision business identifier types when all of the following are true:

- the patterns are token-aware or structure-aware, not raw free-text regex only
- known collision namespaces are explicitly blocked
- positive context evidence is required for ambiguous identifiers
- a shadow run plus manual precision audit passes before the full rerun

For this project, the best defensible path is **hybrid rules + validators + slice-based validation + acceptance gates**, not regex-only and not a last-minute classifier project.

## 2. Source Confidence Ladder

### High-confidence sources

- **NIST SP 800-53 Rev. 5** and **SP 800-53A Rev. 5**: official control-family taxonomy plus staged assessment methodology. [E1] [E2]
- **NIST/SEMATECH Engineering Statistics Handbook**: sample-size and confidence-interval guidance for proportion estimates. [E3] [E4]
- **GitHub secret scanning docs**: concrete operational pattern for custom-pattern dry runs, reviewing false positives, and only then enabling blocking behavior. [E5] [E6]
- **Microsoft Presidio docs**: explicit architecture support for regex + deny-list + context words + validation / invalidation hooks. [E7] [E8] [E9]
- **spaCy** and **Stanford CoreNLP** docs: token-aware rule systems, overlap control, POS gating, and combining rules with broader NER pipelines. [E10] [E11] [E12]
- **Snorkel / data programming / skweak / slicing papers**: multiple noisy heuristic sources, explicit LF precision / coverage review, and slice-based monitoring instead of trusting a single heuristic blindly. [E13] [E14] [E15] [E16] [E17]
- **FAA / EASA** maintenance-record guidance: part number and serial number handling is record-and-context grounded, not pattern-only. [E18] [E19]
- **DISA / STIG / CVE official sources**: the colliding namespaces in this corpus are real governed identifier systems, not accidental strings. [E20] [E21] [E22] [E23]

### Medium-confidence sources

- **SAP Community**: useful product-specific evidence that SAP PO number length is standard 10 digits, but still community guidance rather than formal product spec. [E24]

### Lower-confidence practitioner corroboration

- **Stack Overflow** threads on Rasa regex extraction: regex features are appropriate for very regular identifiers; broad regexes create useless or over-broad matches. [P1] [P2]
- **spaCy GitHub discussion**: practitioners recommend combining simple business rules with a model / weak supervision and labeling at least a modest dev set. [P3]
- **Reddit / weak supervision practice discussion**: practitioners repeatedly report that they still need a trusted validation sample to know whether weak supervision is helping. [P4]

## 3. Best-Practice Sequence Before A Major Rerun

### External consensus

The best-practice sequence is:

1. **Freeze the failure taxonomy first.**
   For us: `PO` pollution by control-family IDs, `PART` pollution by STIG / CCI / baseline IDs, plus OCR / table / archive-specific edge cases. NIST SP 800-53 and DISA / STIG documentation matter here because the false positives come from official governed namespaces, so the collision classes are knowable up front. [E1] [E20] [E21] [E22]
2. **Move from raw regex to token-aware candidate generation.**
   spaCy and CoreNLP both emphasize token-aware rule systems over raw text regex because token attributes, overlap rules, and POS / context constraints reduce brittle matching. [E10] [E11] [E12]
3. **Separate matching from validation.**
   Presidio exposes `validate_result`, `invalidate_result`, deny-lists, and context-aware score enhancement for exactly this reason: weak patterns often need secondary logic. [E7] [E8] [E9]
4. **Dry-run on a representative corpus slice before turning the action on.**
   GitHub’s mature operational workflow for custom patterns is: define pattern, dry run, inspect a sample of results, fix false positives, repeat, then publish or enable blocking. [E5] [E6]
5. **Measure precision on critical slices, not only globally.**
   Snorkel slicing, Slice-based Learning, and Slice Finder all reinforce that concentrated failure modes can hide inside otherwise decent overall metrics. [E15] [E16] [E17]
6. **Use a small trusted evaluation set before trusting weak supervision or heuristic rules.**
   Snorkel’s LF workflow explicitly reviews LF precision / coverage on a selected split; practitioner discussions say the same thing more bluntly. [E14] [P3] [P4]
7. **Only then run the expensive full rerun.**
   NIST’s assessment framing and GitHub’s push-protection sequencing both imply that blocking / production-scale actions come after dry-run evidence, not before. [E2] [E5]

### Practical interpretation for this repo

The major mistake to avoid is using the full Tier 1 rerun as the validation mechanism. Mature teams validate **before** the expensive action, not by spending the expensive action and then auditing after the fact.

## 4. Recommended Acceptance Gate For HybridRAG_V2

### Recommended minimum rerun gate

Authorize a full Tier 1 rerun only if **all** of the following pass:

1. **Deterministic adversarial suite: 100% pass**
   Every known bad pattern must be rejected in `PO` / `PART`.
   Every known good anchor must still pass.
2. **Shadow extraction on 5,000-10,000 representative chunks**
   Do not start with the 10.4M corpus.
   Run on pre-defined slices only.
3. **Top-frequency audit hard fail**
   In the shadow run, the top 50 most frequent `PO` values and top 50 most frequent `PART` values must contain **zero** known control-family / STIG / MITRE namespaces.
4. **Manual precision audit by class**
   Audit at least **385 extracted candidates per risky class** (`PO`, `PART`) if you want a worst-case ±5% margin at 95% confidence for a proportion estimate. This is an inference from NIST’s proportion sample-size guidance, using the conservative `p=.5` worst case. [E3] [E4]
5. **Slice audit minimums**
   Audit at least **50 extracted hits per critical slice per risky class** even if the overall 385 sample is already satisfied. This is not for tight confidence intervals; it is to catch concentrated slice failures before rerun. [E15] [E16] [E17]
6. **Precision floor**
   Require an **audited point precision >=95% for `PART` and >=97% for `PO`** on the shadow run.
   Also require the **lower 95% confidence bound** to stay above a coordinator-defined floor, recommended **>=90%** for both.
7. **No unexplained count explosions**
   The shadow run must not create new top-frequency dominant values or dramatic class-count inflation without a written explanation.

### Why this gate is defensible

- It follows the same dry-run-before-enable pattern used by GitHub secret scanning. [E5] [E6]
- It uses a real sampling rationale instead of eyeballing a handful of rows. [E3] [E4]
- It treats known dangerous slices as first-class validation targets. [E15] [E16] [E17]
- It does not require building a new ML system before May 2.

## 5. Recommended Validation Methodology

### A. Three validation layers

1. **Fixture layer**
   Curated positive / negative strings derived from already-known collisions.
   This is the fastest gate and must run on every rule change.
2. **Shadow corpus layer**
   Run the Tier 1 extractor on a bounded chunk sample with the real parser / chunker / source_path conditions.
3. **Manual audit layer**
   Manually judge extracted outputs using a fixed rubric and compute class precision with confidence intervals.

### B. Required slices for this corpus

Use at least these slices:

- `3.0 Cybersecurity` and other cyber-heavy paths
- logistics / procurement paths
- maintenance / MSR / CAP / site-visit paths
- spreadsheet / tabular chunks
- OCR-poor or archive-heavy chunks
- archive-member or zipped-file derived chunks if those exist in the extraction path

### C. Required measurements

For each risky class and slice, compute:

- audited precision
- confidence interval for precision
- top-frequency values
- blocked-namespace leakage count
- ambiguous / rejected candidate count
- net count delta vs prior regex behavior

### D. Audit rubric

Every audited extraction should be labeled as one of:

- `valid_business_id`
- `valid_nonbusiness_security_id`
- `ambiguous_needs_context`
- `invalid_false_positive`

This matters because some strings are real identifiers but belong to the wrong ontology. For example, `CCI-000172` is a valid identifier in DISA/STIG land, but it is still a **false positive for `PART`**. [E20] [E21]

## 6. Recommended Sample Strategy

### Recommended plan

1. **Adversarial fixture pack**
   Build from known collisions and known true positives.
   Minimum: 100-300 rows.
   Required result: 100% pass.
2. **Shadow-run chunk sample**
   Sample 5,000-10,000 chunks across the defined slices.
   Oversample the failure-prone slices rather than using purely uniform random sampling.
3. **Manual precision audit**
   For `PO` and `PART`, audit 385 extracted hits each for overall precision.
4. **Slice minimum audit**
   Audit 50 hits minimum in each critical slice even if the overall total already covers more.
5. **Top-K frequency review**
   Manually review the top 50 values by count for `PO` and `PART`.

### Why not just a global random sample?

Because the failure here is concentrated in cybersecurity-heavy content. Slice-based evaluation literature exists precisely because global averages can look acceptable while critical subsets remain broken. [E15] [E16] [E17]

### If time is tight

The minimum honest shortcut is:

- full adversarial fixture suite
- 5,000 chunk shadow run
- top-50 frequency review per risky class
- 100 audited hits per risky class plus 25-50 hits per critical slice

That is weaker than the preferred gate, but still much better than rerunning the whole corpus blind.

## 7. Recommended Rule / Validator Architecture

### Recommended architecture

1. **Candidate generator**
   Keep regex / token rules broad enough to catch true positives.
2. **Negative validator / invalidator**
   Reject candidates matching official collision namespaces.
3. **Positive context validator**
   Require nearby evidence for ambiguous business identifiers.
4. **Type arbitration**
   If a candidate fits a security-ID ontology better than a business-ID ontology, do not let it stay in `PO` / `PART`.
5. **Corpus-level monitor**
   Frequency tables, slice metrics, and audit reports are part of the extractor contract.

### What this means concretely

#### For `PO`

Do **not** use a single "report-like or PO-like identifier" bucket.

Split the logic into:

- `BUSINESS_PO`
- `REPORT_ID`
- optional future `SECURITY_CONTROL_ID`

For `BUSINESS_PO`, require stronger positive evidence:

- SAP-style 10-digit number with nearby `PO`, `Purchase Order`, `P.O.`, `PR`, `requisition`, or table/header context
- or a path / document-family cue that this is procurement material

For `REPORT_ID`, keep explicit report families such as `FSR`, `UMR`, `ASV`, `RTS` separate from procurement numbers.

Do **not** let `IR-*` remain inside the business-facing `PO` class. `IR` is an official NIST control-family prefix for Incident Response, so in this corpus it is a known collision namespace, not a safe business-ID family. [E1]

#### For `PART`

Keep generic part matching only if it is followed by validation:

- reject official control / baseline / vulnerability namespaces like `CCI-`, `SV-`, `CVE-`, `CCE-`, `GPOS-`, `OS-`, `AS-`, `HS-`
- use more careful NIST family blocking based on shape, not naive prefix-only blocking
- require positive context for ambiguous short codes: `part`, `serial`, `qty`, `replace`, `removed`, `installed`, `NSN`, `model`, `cable`, `connector`, manufacturer names, BOM / spares / packing list headers

This is exactly the pattern Presidio recommends for weak regexes: low-trust pattern + context words + validation hooks. [E7] [E8] [E9]

### When denylist / prefix blocking is appropriate

Use denylist or block-pattern logic when:

- the namespace is governed and standardized
- the false-positive family is stable and high-volume
- the blocked shapes are semantically not the same thing as the business entity type you are extracting

That is true for:

- NIST control-family identifiers from SP 800-53 [E1]
- DISA `CCI-*` identifiers [E20]
- STIG `SV-*` and `SRG-...-GPOS-...` style identifiers [E21]
- MITRE `CVE-*` syntax [E22]

### When denylist / prefix blocking becomes too brittle

It becomes brittle when:

- the same prefix family also contains real business identifiers in your corpus
- the block rule is only prefix-based and ignores suffix length or context
- you are using it to compensate for missing ontology separation

This is why HybridRAG_V2 should prefer **regex-shaped invalidators** over raw prefix lists for NIST families. A blanket `PS-*` block would be too blunt if real parts like `PS-800` exist. A shape-aware rule like "NIST family + 1-2 digit control number with optional enhancement" is much safer.

## 8. What Not To Waste Time On

Do not spend this lane on:

- building a perfect universal regex for every identifier family
- a full classifier training project before the rerun gate exists
- full-corpus reruns "just to see"
- overall random sampling only
- ontology redesign across every entity class before May 2
- arguing whether rules-only can be perfect

The useful question is not "can regex be perfect?" It is "can we make the risky business-ID classes precise enough to justify a rerun?" External evidence says yes, but only with validators and gates.

## 9. Concrete Recommendations For HybridRAG_V2

### Priority 1

Keep the current architectural direction: **regex / token rules + invalidators + context checks**, not regex-only.

Why:

- Presidio, GitHub secret scanning, and rule-based IE frameworks all separate pattern detection from validation / context / enablement. [E5] [E6] [E7] [E8] [E9]

### Priority 2

Treat `PO` and `REPORT_ID` as separate business concepts.

Why:

- Your current `IR-*` collision exists because one pattern tried to cover two ontologies at once.
- External sources show `IR` is a formal control-family namespace in this corpus’s cyber documents. [E1]

### Priority 3

Use official collision namespaces as first-class blocked shapes.

Minimum immediate block families for business-facing `PO` / `PART`:

- NIST SP 800-53 family identifiers in control-number shape
- `CCI-*`
- `SV-*`
- `CVE-*`
- `CCE-*`
- STIG baseline families `AS-*`, `OS-*`, `GPOS-*`, `HS-*`

Why:

- these are governed identifier systems, not guesswork. [E1] [E20] [E21] [E22]

### Priority 4

Require positive context for ambiguous identifiers.

Examples:

- unlabeled 10-digit number is not enough to become `BUSINESS_PO`
- short alphanumeric hyphen code is not enough to become `PART`

Why:

- part / serial guidance in maintenance records is context-grounded, not string-only. [E18] [E19]
- Presidio explicitly boosts weak matches only when context words support them. [E8]

### Priority 5

Do a shadow run before the massive rerun.

Recommended order:

1. adversarial fixtures
2. 5,000-10,000 chunk shadow run
3. manual audit + top-frequency review
4. only then full Tier 1 rerun

Why:

- this is the same operational pattern mature detection systems use before enabling blocking or wide scans. [E5] [E6]

### Priority 6

If ambiguity remains after validators, reject or route it to a separate future class instead of forcing it into `PO` / `PART`.

Why:

- for May 2, a false negative is often less dangerous than a false positive in business-facing aggregates.

## 10. Strongest Defensible "Good Enough To Rerun" Gate

The strongest practical gate for this project is:

- 100% pass on curated adversarial fixtures
- zero blocked-namespace leakage in top-50 `PO` and `PART` values from a shadow run
- audited point precision >=95% for `PART` and >=97% for `PO`
- lower 95% confidence bound >=90% for both
- no critical slice below floor
- written signoff on the audit artifact before rerun

That is not perfection. It is an auditable, data-centric, production-defensible rerun gate.

## Appendix A — Mapping External Best Practices To The Exact HybridRAG_V2 PO / PART Problem

### Known local failure

- `PO` polluted by `IR-8`, `IR-4`, etc.
- `PART` polluted by `AS-5021`, `OS-0004`, `GPOS-0022`, `CCI-0003`, `SV-2045`, etc.

### External best-practice mapping

| Local problem | External best practice | HybridRAG_V2 implication |
|---|---|---|
| `IR-*` controls entering `PO` | NIST says `IR` is an official control-family namespace; do not let one regex represent both report IDs and business POs. [E1] | Remove `IR` from report-ID logic or route it through explicit disambiguation. |
| Generic `[A-Z]{2,}-\d{3,4}` matching STIG / DISA codes | Presidio-style weak regex should be followed by validation / invalidation and context checks. [E7] [E8] [E9] | Keep broad part matcher only if followed by official blocked-shape checks plus positive context. |
| Desire to rerun the whole corpus immediately | GitHub custom-pattern workflow is dry-run first, review false positives, iterate, then enable. [E5] [E6] | Do a shadow Tier 1 run first, not a 10.4M blind rerun. |
| Overall metrics may hide cyber-heavy failures | Slice-based monitoring literature says critical slices must be measured separately. [E15] [E16] [E17] | Audit cyber, procurement, maintenance, OCR, and table slices separately. |
| Need to know whether the rules are "good enough" | NIST sampling guidance supports explicit precision audits with confidence bounds. [E3] [E4] | Report audited precision with CIs, not vibes. |

## References

### External

- [E1] NIST SP 800-53 Rev. 5, Security and Privacy Controls for Information Systems and Organizations. https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final
- [E2] NIST SP 800-53A Rev. 5, Assessing Security and Privacy Controls in Information Systems and Organizations. https://csrc.nist.gov/pubs/sp/800/53/a/r5/final
- [E3] NIST/SEMATECH e-Handbook: sample sizes required for proportions. https://www.itl.nist.gov/div898/handbook/prc/section2/old.prc272.htm
- [E4] NIST/SEMATECH e-Handbook: confidence limits for proportions. https://www.itl.nist.gov/div898/handbook/prc/section2/old.prc271.htm
- [E5] GitHub Docs: defining custom patterns for secret scanning. https://docs.github.com/en/code-security/secret-scanning/using-advanced-secret-scanning-and-push-protection-features/custom-patterns/defining-custom-patterns-for-secret-scanning
- [E6] GitHub Docs: supported secret scanning patterns. https://docs.github.com/code-security/secret-scanning/secret-scanning-patterns
- [E7] Microsoft Presidio: developing recognizers. https://microsoft.github.io/presidio/analyzer/developing_recognizers/
- [E8] Microsoft Presidio: context enhancement. https://microsoft.github.io/presidio/tutorial/06_context/
- [E9] Microsoft Presidio Analyzer Python API. https://microsoft.github.io/presidio/api/analyzer_python/
- [E10] spaCy: rule-based matching. https://spacy.io/usage/rule-based-matching/
- [E11] Stanford CoreNLP: TokensRegexNERAnnotator / RegexNER. https://stanfordnlp.github.io/CoreNLP/regexner.html
- [E12] Stanford CoreNLP: TokensRegex. https://stanfordnlp.github.io/CoreNLP/tokensregex.html
- [E13] Ratner et al., "Snorkel: rapid training data creation with weak supervision." https://cs.brown.edu/people/sbach/files/ratner-vldbj20.pdf
- [E14] Snorkel Docs: creating good labeling functions. https://docs.snorkel.ai/docs/0.93/user-guide/best-practices/creating-good-labeling-functions
- [E15] Lison et al., "skweak: Weak Supervision Made Easy for NLP." https://arxiv.org/abs/2104.09683
- [E16] Snorkel: slicing functions / get started. https://snorkelproject.org/get-started/
- [E17] Slice-based learning / slice finder references: https://arxiv.org/abs/1909.06349 and https://arxiv.org/abs/1807.06068
- [E18] EASA FAQ: part number and serial number can be conclusively identified from record review. https://www.easa.europa.eu/en/faq/19492
- [E19] FAA AC 43-9D: maintenance records, part number and serial number tracking. https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43-9D.pdf
- [E20] DoD Cyber Exchange: Control Correlation Identifier (CCI). https://public.cyber.mil/stigs/cci/
- [E21] STIG Viewer example showing `SV-*`, `CCI-*`, `GPOS-*` security identifiers. https://stigviewer.com/stigs/red_hat_enterprise_linux_8/2025-03-26/finding/V-230411
- [E22] CVE FAQ: CVE ID syntax. https://www.cve.org/Resources/Media/Archives/OldWebsite/about/faqs.html
- [E23] DISA briefing: CCI and SRG / STIG data model. https://www.disa.mil/~/media/files/disa/news/conference/cif/briefing/ia_stig_scap_and_data_metrics.pdf
- [E24] SAP Community: standard SAP PO number length remains 10 digits. https://community.sap.com/t5/enterprise-resource-planning-q-a/how-to-ensure-purchase-order-length-is-10-digits-for-external-number-range/qaq-p/594818 and https://community.sap.com/t5/enterprise-resource-planning-q-a/how-to-extend-the-number-range-from-10-digits-to-12-16-digits-for-purchase/qaq-p/12757407

### Lower-confidence practitioner corroboration

- [P1] Stack Overflow: regex features are appropriate for very regular entities. https://stackoverflow.com/questions/62504891/using-regex-with-enitities-in-rasa-nlu
- [P2] Stack Overflow: overly broad regex entity extractors produce false positives. https://stackoverflow.com/questions/70070850/rasa-regexentityextractor-extracting-non-entities-as-entities
- [P3] spaCy GitHub discussion: combine simple business rules with a model / weak supervision; label at least a modest dev set. https://github.com/explosion/spaCy/discussions/10808
- [P4] Reddit weak supervision practice discussion: collect a trusted validation sample before trusting weak supervision. https://www.reddit.com/r/MachineLearning/comments/rogiq2
