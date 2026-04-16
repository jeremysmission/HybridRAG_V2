# Corpus Family Burden Recon — 2026-04-13

**Purpose:** Prioritize parser, OCR, table, enrichment, and metadata work by family-level product impact.

## Executive Read

- Query pressure is dominated by:
  - CDRLs
  - Logistics
- Together they account for the majority of real product pressure.
- The dominant burden is **metadata**, not OCR.
- Table burden is highly concentrated in logistics families.
- OCR burden is real but comparatively narrow.

## Highest-Leverage Families

- CDRL deliverables
- Logistics:
  - packing lists
  - received POs
  - calibration
  - spares
  - BOMs
  - DD250s

## Healthy / Lower-Risk Families

- Program Management
- Systems Engineering
- Site Visits
- Cyber narrative and exact-ID content

## Low-Demand / Overfocused Families

- archives
- drawings
- image-heavy special handling

## Coordinator Conclusion

- The next pre-demo family priorities are:
  1. logistics metadata emit + row extraction
  2. CDRL typed metadata
  3. provider-agnostic router guards
  4. packing-list / received-PO table pilot
  5. cyber revision/date/source metadata
- OCR is not the main bottleneck before May 2.
- The biggest hidden product-value gap remains:
  - Forge -> V2 metadata contract is too thin
  - V2 is still reconstructing too much from `source_path`
