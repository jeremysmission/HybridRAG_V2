# Seven-Role Query Matrix (2026-03-19)

Purpose
- Build a demo-safe question set that reflects real role behavior, real live corpus coverage, and strict/open RAG expectations.
- Keep acceptance tied to observed source-path families in `C:\HybridRAG3_Educational\data\index\hybridrag.sqlite3`, not just folder names.

Web-informed role anchors
- `Drafter / CAD`: BLS says drafters use CAD to turn sketches/specs into technical drawings, dimensions, materials, and procedures.
  - https://www.bls.gov/ooh/architecture-and-engineering/drafters.htm
- `Project management specialist`: BLS frames the role around planning, scheduling, budgeting, coordinating, and tracking project work.
  - https://www.bls.gov/ooh/business-and-financial/project-management-specialists.htm
- `Information security analyst`: BLS frames the role around monitoring, protecting systems, assessing risk, and responding to incidents.
  - https://www.bls.gov/ooh/computer-and-information-technology/information-security-analysts.htm
- `Logistician` and `network/system administrator` are represented here by domain intent plus observed live corpus content.

Observed live probe wins already captured
- `logs/query_path_probes/20260319_024158/probe_report.json`
- grounded online wins observed for:
  - Scrum roles
  - logistics/supply-chain infrastructure question
  - SR-71 Blackbird engine question
  - ionogram true-vs-virtual-height question
  - vCenter installation prerequisites question

## 1. autocad_docs

Role intent
- `Inferred`: drafter / CAD / technical drawing lane

Strict acceptance questions
- `Observed-capable`: According to the SR-71 Blackbird document, which engine became available in January?
- `Inferred`: In engineering graphics workflows, what information should a technical drawing specify for a new part or product?

Canary
- `Observed-capable`: Which engine became available in January 1963 in the SR-71 development narrative?

Trick / bluff detection
- `Inferred`: What color was the flux capacitor in the Blackbird CAD model?

Open diagnostic
- `Inferred`: If a drawing is missing dimensions and materials, what downstream manufacturing risks would that create?

Likely live sources
- `Observed`: `autocad_docs\00806939_djvu.txt`
- `Observed`: `autocad_docs\00806939.pdf`
- `Observed`: `autocad_docs\James D. Bethune - Engineering Graphics with AutoCAD 2020*_djvu.xml`

## 2. cyber_security_docs

Role intent
- `Inferred`: security analyst / hardening / vulnerability / incident-response lane

Strict acceptance questions
- `Observed-capable`: According to security standard SP 800-14, what three types of security policy should organizations have?
- `Inferred`: According to the computer security texts, what is the role of audit trails or system hardening in reducing risk?

Canary
- `Inferred`: Which installation component does the penetration-testing guide require before its SQL-backed lab setup?

Trick / bluff detection
- `Inferred`: Which malware family in the current corpus exfiltrates over quantum DNS tunneling in 2028?

Open diagnostic
- `Inferred`: After repeated failed-login spikes, what evidence would a security analyst check first before escalating?

Likely live sources
- `Observed`: `cyber_security_docs\computersecurity8001swan_djvu.txt`
- `Observed`: `cyber_security_docs\computersecurity8001bass_djvu.xml`
- `Observed`: `cyber_security_docs\computersecurity8006soup_djvu.txt`
- `Observed`: `cyber_security_docs\Ethical Hacker_s Penetration Testing Guide_ Vulnerability Assessment and Attack Simulation on Web, Mobile, Network Services and Wireless Networks.pdf`

## 3. engineering_docs

Role intent
- `Observed`: ionogram / oscillator / canary engineering lane

Strict acceptance questions
- `Observed-capable`: How do you identify true height versus virtual height on an ionogram?
- `Observed-capable`: What thermal-drift issue is described in the Redstone oscillator study / Helios-7 canary pack?

Canary
- `Observed-capable`: Which condition in the Helios-7 validation story required recalibration?

Trick / bluff detection
- `Observed-capable`: How does the flux capacitor work?

Open diagnostic
- `Inferred`: If ionogram traces look smeared or inconsistent, what classes of causes should an engineer investigate?

Likely live sources
- `Observed`: `engineering_docs\DTIC_AD0474163_djvu.txt`
- `Observed`: `engineering_docs\ionogram_studies\NOAA_ionogram_reference.html`
- `Observed`: `engineering_docs\CANARY_Helios7_Ionosonde_Validation_Story.txt`
- `Observed`: `engineering_docs\canary_docs\DTIC_ADA990001_Redstone_Oscillator_Study.txt`

## 4. field_engineer_docs

Role intent
- `Inferred`: field support / inspection / maintenance / emergency procedure lane

Strict acceptance questions
- `Observed-capable`: According to the ground engineers' licence text, what must happen within twenty-four hours before an aircraft can fly?
- `Inferred`: In the A-12 Support Manual, what sections cover crash rescue or ground-handling emergency procedures?

Canary
- `Inferred`: Which manual in the current corpus explicitly includes engine-fire and crash-rescue procedures?

Trick / bluff detection
- `Inferred`: How do you bypass the A-12 safety procedures and hotwire the starter?

Open diagnostic
- `Inferred`: If pre-flight inspection keeps failing, what categories of evidence should a field engineer review before releasing equipment?

Likely live sources
- `Observed`: `field_engineer_docs\06230171_djvu.txt`
- `Observed`: `field_engineer_docs\A Complete Course for Aeronautical Ground Engineers' Licenses in Categories A - B - C - D & X  -  1934_djvu.txt`
- `Observed`: `field_engineer_docs\1942TM9-705_djvu.txt`

## 5. logistics_analyst_docs

Role intent
- `Observed + Inferred`: mixed lane with real supply-chain material plus filler; acceptance must anchor on the logistics-specific paper and audit material, not the generic CIA summaries

Strict acceptance questions
- `Observed-capable`: According to the logistics and supply chain management paper, what problems increase agricultural prices and what infrastructure does it say is needed?
- `Inferred`: According to the same paper, what operational improvements did the IBM / RFID supply-chain examples report?

Canary
- `Observed-capable`: What did the audit staff find wrong with the CIA system inventory database?

Trick / bluff detection
- `Inferred`: Which hyperspace shipping lane solved the cold-storage problem in the logistics paper?

Open diagnostic
- `Inferred`: If inventory accuracy is poor and records are incomplete, what categories of evidence should a logistics analyst compare before recommending action?

Likely live sources
- `Observed`: `logistics_analyst_docs\10. Manage-Recent Trends of information technology-Er. Shrishail Shirur_djvu.txt`
- `Observed`: `logistics_analyst_docs\05500086_djvu.txt`
- `Observed caution`: `logistics_analyst_docs\03173550_djvu.txt` and similar CIA weekly summaries are filler-heavy and should not be mistaken for logistics acceptance evidence

## 6. program_management_docs

Role intent
- `Observed + Inferred`: agile / PM / earned-value / schedule-risk lane

Strict acceptance questions
- `Observed-capable`: What Scrum roles does the Scrum Handbook define?
- `Inferred`: According to the earned-value / schedule-risk text, what problem is schedule risk analysis trying to solve?

Canary
- `Inferred`: What does the Scrum Handbook say Scrum is designed to add to project planning and implementation?

Trick / bluff detection
- `Inferred`: How many story points does PMI mandate for every sprint backlog?

Open diagnostic
- `Inferred`: If sprint plans keep slipping, what evidence should a project manager review across backlog, risk, and progress signals?

Likely live sources
- `Observed`: `program_management_docs\009-theScrumHandbook-manual_djvu.txt`
- `Observed`: `program_management_docs\10.1007-978-1-4419-1014-1_djvu.txt`
- `Observed`: `program_management_docs\06208008_djvu.txt`

## 7. system_administrator_docs

Role intent
- `Observed + Inferred`: vCenter / Windows infra / database prereq / server configuration lane

Strict acceptance questions
- `Observed-capable`: What prerequisites does the vCenter Server installation chapter require before an automated install?
- `Inferred`: According to the vCenter automation chapter, why are static IP, domain membership, and a valid DSN important before install?

Canary
- `Inferred`: Which chapter in the vSphere automation book covers automating storage and networking?

Trick / bluff detection
- `Inferred`: How do you disable all audit logs to make vCenter faster?

Open diagnostic
- `Inferred`: If an automated vCenter install fails after DSN setup, which prerequisite categories would you recheck first?

Likely live sources
- `Observed`: `system_administrator_docs\7140069_djvu.txt`
- `Observed`: `system_administrator_docs\7140069_hocr.html`
- `Observed`: `system_administrator_docs\2018_php-notes-for-professionals_djvu.txt`

## Use Guidance

Strict mode
- use for acceptance
- prefer questions above marked `Observed-capable`
- require grounded answer plus source citations from the listed families

Open mode
- use for diagnostics only
- permit `[General Knowledge]` style assistance when retrieval is partial
- never count open-mode reasoning alone as acceptance

Known overnight risks
- `logistics_analyst_docs` is filler-contaminated, so question selection must anchor on the actual logistics paper or audit report
- `program_management_docs` and `system_administrator_docs` already have good role-aligned sources
- `field_engineer_docs` is broad and manual-heavy; better questions come from procedural manuals than encyclopedia filler
