# Demo-Day Research — Enterprise RAG Demo Patterns For 2025-2026

**Author:** reviewer  
**Repo:** `C:\HybridRAG_V2`  
**Purpose:** Research published demo-day patterns for enterprise RAG systems and convert them into concrete guidance for V2’s May 2 demo  
**Scope:** Web research plus synthesis for enterprise/non-technical audiences such as program managers, logistics leads, and enterprise/government stakeholders  
**Research posture:** Recency-first, source-linked, and explicit when a recommendation is an inference rather than a direct published rule

---

## Executive Summary

### Finding 1

The current published pattern is **outcome-first, not architecture-first**. Enterprise demo guidance still centers on the prospect’s critical business issue, desired capability, and measurable value before the feature walkthrough. For V2, that means the May 2 demo should start with one question that obviously matters to a PM or operations lead, not with LanceDB, GLiNER, or a system diagram.

Source note: Used Great Demo planning checklist `https://greatdemo.com/wp-content/uploads/2024/01/Planning-Execution-Checklists.pdf` and Guideflow’s 2026 SE demo practices `https://www.guideflow.com/blog/sales-engineering-demo-best-practices` (checked 2026-04-11).

### Finding 2

Published demo-ops guidance strongly favors **modular, persona-specific demo segments** over one long improvised tour. For V2, the practical implication is a small stack of rehearsed query modules by persona: program, logistics, field, cyber, plus one bounded limitation segment. This is the closest published equivalent to the internal “known-good canary” idea.

Source note: Used Guideflow’s recommendation to create reusable demo modules and route content by persona/use case `https://www.guideflow.com/blog/sales-engineering-demo-best-practices`, plus Storylane guidance to pick the right demo type and prepare backup plans `https://www.storylane.io/blog/how-to-run-a-product-demo/` (checked 2026-04-11).

### Finding 3

I did **not** find a widely-adopted public term “canary query” in enterprise RAG demo literature. What I did find is a consistent operational pattern: use a **repeatable gold path**, keep backup variants ready, and independently evaluate with a buyer-owned or agency-owned test set. For V2, “canary queries” should be framed as our implementation of that broader pattern, not as an industry-standard named object.

Source note: Used AWS Bedrock RAG evaluation docs on retrieve-only vs retrieve-and-generate jobs `https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html` and White House memo M-25-22 on agency-defined evaluation data, portability, and ongoing testing `https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf` (checked 2026-04-11).

### Finding 4

The live-demo recovery pattern is **not** “debug the model in public.” It is: acknowledge the miss, fall back to source evidence or a backup path, and reframe the limitation as a trust boundary. For V2, that means rehearsing what the operator says when an answer is incomplete, not just rehearsing success.

Source note: Used Storylane guidance on backup plans and picking the right demo mode `https://www.storylane.io/blog/how-to-run-a-product-demo/`, plus OECD public-sector AI guidance on guardrails, transparency, oversight, and trustworthy adoption `https://www.oecd.org/en/publications/2025/06/governing-with-artificial-intelligence_398fa287.html` (checked 2026-04-11).

### Finding 5

For enterprise/government audiences, the strongest framing for a home-grown or self-hosted RAG is **control, portability, data locality, and procurement realism**. “Free” is not enough. The better message is “no recurring platform tax on the core retrieval plane, auditable components, portable data, and compatibility with disconnected or sovereign deployment patterns.”

Source note: Used GSA OneGov guidance on cost savings, direct OEM relationships, consistent security standards, and reduced acquisition burden `https://www.gsa.gov/buy-through-us/purchasing-programs/multiple-award-schedule/onegov`, White House memo M-25-22 on open/standard APIs, portability, and lock-in protections, and Microsoft Sovereign Cloud positioning on local control and disconnected environments `https://www.microsoft.com/en-us/sovereignty` (checked 2026-04-11).

### Finding 6

Commercial platform vendors are competing hardest on **managed governance, evaluation, security wrappers, and procurement vehicles**, not only model quality. If V2 is compared to Bedrock, Azure, or Red Hat AI, it should not claim “we beat them.” It should claim “we chose a smaller, more controllable architecture for this corpus and this operating model.”

Source note: Used AWS Bedrock RAG evaluation docs `https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html`, Microsoft Foundry regional-availability guidance `https://learn.microsoft.com/en-us/azure/foundry/reference/region-support`, Red Hat OpenShift AI docs on secure endpoints and OpenAI-compatible RAG APIs `https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4`, and GSA’s approved vendor OneGov press release showing commercial AI is also moving on affordability and federal distribution `https://www.gsa.gov/about-us/newsroom/news-releases/gsa-strikes-onegov-deal-with-approved vendor-08122025` (checked 2026-04-11).

### Finding 7

The cost story that resonates with procurement-sensitive audiences is **full lifecycle TCO**, not “cost per query.” The line items that matter are infrastructure, integration, maintenance, training, evaluation, governance, and switching costs. For V2, that means any “$0 infrastructure” line should be softened into a more credible “no recurring managed-platform fee on the core retrieval path; hardware and operator time still cost real money.”

Source note: Used Glean’s AI TCO breakdown `https://www.glean.com/perspectives/how-to-budget-for-the-total-cost-of-ownership-of-ai-solutions`, Great Demo’s value-quantification categories `https://greatdemo.com/wp-content/uploads/2024/01/Planning-Execution-Checklists.pdf`, and White House memo M-25-22 on performance/cost justification, portability, and sunset criteria (checked 2026-04-11).

---

## Method And Source Quality Notes

- I found **more high-quality material on enterprise demo operations and public-sector AI procurement than on “RAG demo scripts” specifically**.
- For demo choreography, the most useful sources were current sales-engineering/demo-ops publications.
- For failure framing, public-sector procurement, portability, and offline narratives, the best sources were official government and vendor docs.
- Where I recommend a specific May 2 structure such as “5-7 queries in 30 minutes,” I mark that as an **inference** drawn from the sources, not as a universally published number.

---

## 1. Demo Structure Patterns

### 1.1 Outcome First, Technical Depth Later

Published enterprise-demo guidance still starts with the buyer’s current pain, expected outcome, and value frame. Great Demo’s checklists remain blunt about this: identify the prospect’s critical business issue, use the customer’s language, quantify value categories, and verify understanding before getting deeper into product detail. For V2, this argues against opening with architecture or “what’s new in V2.”

Source note: Used Great Demo’s planning and execution checklist on CBI, customer language, value categories, and situation slides `https://greatdemo.com/wp-content/uploads/2024/01/Planning-Execution-Checklists.pdf` (checked 2026-04-11).

### 1.2 Modular Persona Flows Beat One Big Tour

Guideflow’s 2026 SE guide recommends reusable demo modules organized by persona and use case. That pattern maps directly to an enterprise RAG demo: a PM module, a logistics module, a field engineering module, a cyber module, and a limitation/recovery module. The point is not aesthetics. It is recoverability. If one query goes sideways, the operator can pivot to the next module without rearchitecting the session live.

Source note: Used Guideflow’s 2026 advice on reusable demo modules, persona/use-case organization, and live-vs-async demo routing `https://www.guideflow.com/blog/sales-engineering-demo-best-practices` (checked 2026-04-11).

### 1.3 Backup Plans Are Part Of The Demo, Not An Emergency Add-On

Storylane’s current product-demo guidance explicitly calls out backup plans and matching demo mode to audience/context. That matters for V2 because May 2 is not a developer meetup. The operator needs a primary live path, a backup live path, and a pre-decided fallback if the system returns a weak or partial answer.

Source note: Used Storylane guidance on defining goals, choosing the right demo type, backup plans, and rehearsal `https://www.storylane.io/blog/how-to-run-a-product-demo/` (checked 2026-04-11).

### 1.4 Recommended 30-45 Minute Structure For V2

This exact timing is an **inference**, not a direct published template, but it fits the current guidance better than the existing “10 queries plus everything else” style:

| Segment | Minutes | Purpose |
|---|---|---|
| Opening business frame | 3-5 | State mission problem, corpus scope, and trust boundary |
| Core canaries | 8-12 | Run 2-3 known-good questions that always prove the system works |
| Persona proof | 10-15 | Run 2-3 persona-specific questions that show breadth without improvisation |
| Limitation / trust segment | 2-4 | Show a bounded refusal or explain a constraint deliberately |
| Cost / deployment / ops slide | 5-8 | Give procurement and operations stakeholders their lane |
| Q&A buffer | 5-10 | Keep time for discussion or controlled audience input |

### 1.5 Sequence Easy Wins Before The Hardest Case

The research points toward a clear answer here: **do not start with the hardest multi-hop or aggregation question.** Start with a high-confidence, business-relevant win. Once the room trusts the system, then show the harder or more novel behavior. The published demo literature does not say “easy wins first” in those exact words, but it repeatedly says to lead with the buyer’s core issue and a guided path rather than with a technical stunt.

Source note: Used Great Demo customer-centric sequencing and Guideflow’s modular live-demo guidance as the basis for this inference (checked 2026-04-11).

### Application To V2’s May 2 Demo

- Lead with a query that a PM or logistics lead immediately recognizes as useful.
- Keep the system diagram out of the first five minutes.
- Treat every query as a demo module, not a one-off improvisation.
- Put aggregation and audience-choice late in the deck, not early.

---

## 2. Query Selection For Demos

### 2.1 Demo-Safe Queries And Exploratory Queries Are Different Things

The research strongly supports separating the questions that prove the demo from the questions that explore the product. Enterprise demo guidance emphasizes qualification, modularity, and repeatability; public-sector AI guidance emphasizes independently evaluated data and ongoing testing. Those are not compatible with “let the room decide what to ask in the first five minutes.”

Source note: Used Guideflow on qualification and modular demo content `https://www.guideflow.com/blog/sales-engineering-demo-best-practices`, AWS Bedrock on retrieve-only versus retrieve-and-generate evaluation `https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html`, and White House M-25-22 on agency-defined evaluation data and independent testing `https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf` (checked 2026-04-11).

### 2.2 Recommended Query Count

I did not find a credible current source that says “a 30-minute AI demo should run exactly N queries.” The better inference is:

- enough queries to prove breadth
- few enough queries to leave recovery room
- no more queries than the operator can narrate confidently

For V2, that points to **5-7 queries total** in a 30-minute slot and **6-8 queries total** in a 45-minute slot, with at least one slot reserved for a limitation/recovery moment or discussion.

Source note: Inference from Great Demo’s outcome-first method, Guideflow’s modular-demo guidance, and Storylane’s emphasis on concise, rehearsed segments rather than exhaustive tours (checked 2026-04-11).

### 2.3 The Practical “Canary” Pattern

Again, “canary query” is not the common public term, but the functional pattern is clear:

1. Keep a small set of repeatable gold-path questions.
2. Know the expected source family in advance.
3. Separate retrieval proof from answer-generation flourish.
4. Re-run the same pack before the demo and after any major system change.

For V2, a canary should not merely “sound good.” It should be tied to one of:

- exact-token retrieval wins
- a stable spreadsheet family
- a semantic query that already passed on production data

Source note: Used AWS Bedrock’s retrieve-only evaluation pattern and White House M-25-22’s requirement for independent evaluation using agency-defined data as the closest current published analogues (checked 2026-04-11).

### 2.4 Criteria For Demo-Safe Queries

The best demo-safe queries share these traits:

| Criterion | Why it matters |
|---|---|
| Clear expected source family | Easier to verify quickly and narrate cleanly |
| High user value in plain English | Better for non-technical audiences |
| Stable answer surface | Lower chance of ambiguous or polluted outputs |
| Recoverable if partial | Operator can pivot without losing the room |
| Distinct proof point | Each query should prove something new |

### 2.5 Criteria For Exploratory Queries

Exploratory queries are still useful, but they belong in:

- the last five minutes
- a separate rehearsal lane
- a follow-up session

They are a bad fit for the opening act because they maximize uncertainty before trust has been built.

### Application To V2’s May 2 Demo

- Build the script around a small set of fixed canaries.
- Separate “safe” from “stretch” in the printed runbook.
- Treat audience-choice as optional, not mandatory.
- Avoid any query whose correctness depends on still-polluted `PART` or `PO` aggregates.

---

## 3. Failure Recovery During Live Demos

### 3.1 Do Not Debug The System In Public

The published pattern is not to pretend failures never happen. It is to keep control of the narrative when they do. Storylane’s backup-plan guidance and public-sector trust guidance both point in the same direction: recover to a controlled path and maintain trust.

Source note: Used Storylane’s backup-plan guidance `https://www.storylane.io/blog/how-to-run-a-product-demo/` and OECD’s framework around guardrails, transparency, oversight, and trustworthy adoption `https://www.oecd.org/en/publications/2025/06/governing-with-artificial-intelligence_398fa287.html` (checked 2026-04-11).

### 3.2 Recommended Recovery Script Pattern

If a live query returns a wrong or weak answer, the operator should:

1. Acknowledge it cleanly.
2. Shift from “answer confidence” to “source evidence.”
3. Restate the system boundary.
4. Move to the next rehearsed canary.

Example pattern for V2:

- “That answer is not strong enough to use as-is.”
- “Let me show you what the system actually retrieved.”
- “This is where we keep the trust boundary: we do not treat weak aggregation as authoritative.”
- “Now I’m moving to the next verified path.”

This is much stronger than arguing with the model live.

### 3.3 Pre-Canned Fallbacks To Prepare

For V2, the operator should have these fallbacks already written:

- **Fallback A:** swap to a different query in the same persona module
- **Fallback B:** swap from answer focus to source-document proof
- **Fallback C:** show a deliberate refusal / boundary case
- **Fallback D:** move to the cost/deployment slide if the live question stream is turning chaotic

### 3.4 How To Frame Limitations Without Sounding Weak

The productive framing is:

- deliberate constraints
- trust boundaries
- verification-first behavior
- phased promotion of structured capabilities

The unproductive framing is:

- “the AI is still learning”
- “it usually works”
- “this corpus is messy so anything can happen”

Source note: Used OECD’s trustworthy-AI framing and White House M-25-22’s emphasis on ongoing monitoring, independent evaluation, rollback expectations, and transparency (checked 2026-04-11).

### 3.5 Refusal Is A Feature If It Is Rehearsed

A controlled refusal can actually increase trust with enterprise/government audiences if:

- it is clearly bounded
- it is not the first query
- the operator explains why the refusal is safer than a hallucinated answer

### Application To V2’s May 2 Demo

- Include one rehearsed limitation moment.
- Never improvise failure language on stage.
- If a query misses, pivot to source evidence or a backup module immediately.
- Do not burn time trying to “save” a weak answer.

---

## 4. Competitive Positioning: Open-Source / Self-Hosted RAG Vs Commercial Platforms

### 4.1 What Commercial Platforms Are Selling Right Now

The official docs and procurement materials show that commercial AI platforms are competing on:

- managed evaluation
- managed guardrails
- secure endpoints
- region/compliance wrappers
- procurement convenience
- affordability programs at federal scale

That means a home-grown V2 story should not be “the clouds cannot do this.” They can. The differentiation is control and fit, not pretending the commercial platforms are incapable.

Source note: Used AWS Bedrock evaluation docs `https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html`, Microsoft Foundry regional-availability guidance `https://learn.microsoft.com/en-us/azure/foundry/reference/region-support`, Red Hat OpenShift AI docs on secure endpoints and OpenAI-compatible RAG APIs `https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4`, and GSA’s approved vendor OneGov announcement showing commercial AI now has aggressive federal pricing/distribution mechanics `https://www.gsa.gov/about-us/newsroom/news-releases/gsa-strikes-onegov-deal-with-approved vendor-08122025` (checked 2026-04-11).

### 4.2 What A Home-Grown / Self-Hosted RAG Should Claim Instead

The strongest current positioning for V2 is:

- corpus-specific control
- portable data and simpler lock-out risk
- transparent component boundaries
- offline-friendly architecture
- no mandatory recurring platform fee for the core retrieval plane

That is stronger than “free” and more credible than “better than Bedrock/Azure/Red Hat.”

Source note: Used White House M-25-22 on open and standard APIs, portability, and lock-in protections, plus GSA OneGov on what federal buyers value in procurement terms `https://www.gsa.gov/buy-through-us/purchasing-programs/multiple-award-schedule/onegov` (checked 2026-04-11).

### 4.3 What enterprise / Government Audiences Tend To Respond To

The current public-sector procurement language is consistent:

- cost savings
- consistent security standards
- direct vendor accountability
- reduced acquisition burden
- control over data handling
- ability to evaluate independently
- clear portability and exit paths

That is exactly why “free” on its own underperforms. A enterprise/government audience wants to know how they are protected if requirements, vendors, or networks change.

Source note: Used GSA OneGov’s statements on cost savings, direct OEM relationships, consistent security standards, and reduced administrative burden, plus White House M-25-22 on portability, IP rights, evaluation, testing, and vendor-lock protections (checked 2026-04-11).

### 4.4 How To Frame “Free” Without Sounding Amateur

Bad version:

- “This is basically free.”

Better version:

- “The core retrieval plane does not require a managed platform subscription or per-query platform fee.”
- “The cost profile shifts toward hardware, operator time, and governance, which are visible and controllable.”
- “That matters when you want to keep the corpus local and avoid being forced into a single vendor control plane.”

### 4.5 When To Mention Bedrock, Azure, Or Red Hat By Name

Only mention named platforms if the audience already thinks in those categories. If not, use category labels:

- managed commercial platform
- sovereign cloud option
- self-managed enterprise AI platform
- self-hosted corpus-specific stack

### Application To V2’s May 2 Demo

- Position V2 as **corpus-local and control-first**, not anti-cloud.
- Say the commercial platforms optimize for managed governance and procurement scale.
- Say V2 optimizes for local control, portability, and mission-specific fit.

---

## 5. Cost Narratives And TCO Framing

### 5.1 The Current Market Pattern Is Lifecycle TCO

Recent enterprise AI cost guidance is explicit that the real bill goes beyond licensing. Infrastructure, maintenance, training, and integration costs dominate more often than people expect. Government guidance adds evaluation, monitoring, portability, and sunset planning.

Source note: Used Glean’s AI TCO article `https://www.glean.com/perspectives/how-to-budget-for-the-total-cost-of-ownership-of-ai-solutions` and White House M-25-22 on performance/cost justification, ongoing monitoring, portability, and sunset criteria (checked 2026-04-11).

### 5.2 Standard Line Items To Show

For procurement-sensitive audiences, the most credible V2 cost slide is a line-item table:

| Bucket | V2-friendly wording |
|---|---|
| One-time build | corpus prep, import, index creation, query-pack rehearsal |
| Recurring operations | nightly delta, index maintenance, eval reruns, operator support |
| Compute | local workstation GPU/CPU, optional remote acceleration lane |
| Storage | source store, chunk store, backups, safety copies |
| Governance | validation, evidence packs, operator runbooks, QA |
| Switching / exit | data portability, reproducible indexes, no forced platform migration |

### 5.3 Multi-Year Framing Beats One-Time Framing

This is where the White House procurement memo and GSA procurement language matter. Federal buyers are being told to care about:

- ongoing operation and maintenance
- portability
- vendor lock-in protection
- ability to evaluate independently
- future switching cost

So V2 should show:

- Year 0 build and cleanup cost
- Year 1 operating cost
- vendor/platform tax avoided
- switching/portability advantage retained

Source note: Used White House M-25-22 sections on cost justification, lock-in protections, ongoing testing/monitoring, and contract closeout, plus GSA OneGov’s buyer guidance and savings language (checked 2026-04-11).

### 5.4 The Right Way To Talk About Savings

The credible savings story is:

- reduced analyst search time
- lower dependence on managed-platform subscriptions
- lower switching friction
- more controllable data path

The less credible savings story is:

- “the AI itself is free”
- “we only pay once”
- “operations are basically zero”

### 5.5 V2-Specific TCO Message To Use

Recommended message:

“V2 is designed so the expensive control points are visible. We know where storage lives, how retrieval is indexed, what evaluation pack we ran, and what would need to move if we ever changed models or deployment environments.”

That is much better than a generic low-cost boast.

Source note: Used Great Demo’s value categories for quantifying costs, efficiency, risk reduction, and redeployed labor `https://greatdemo.com/wp-content/uploads/2024/01/Planning-Execution-Checklists.pdf`, plus White House portability/evaluation guidance (checked 2026-04-11).

---

## 6. offline / restricted / Sovereign Deployment Narratives

### 6.1 The Standard Market Language Is “Sovereign” And “Disconnected,” Not “Trust Me, It’s offline”

The major platform vendors are all converging on more precise language:

- sovereign public cloud
- sovereign private cloud
- fully disconnected environments
- regulated environments

That is a useful cue for V2. The May 2 demo should use the same discipline.

Source note: Used Microsoft Sovereign Cloud `https://www.microsoft.com/en-us/sovereignty` and Red Hat OpenShift AI materials and release notes on disconnected and regulated environments `https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4` plus current Red Hat release-note/search results (checked 2026-04-11).

### 6.2 What To Say About Offline Capability

Good version:

- “The architecture is compatible with disconnected operation because retrieval, indexing, and core data stores are local.”
- “Remote inference can be added, but it is not structurally required for the retrieval plane.”

Bad version:

- “This is restricted-ready.”
- “This already satisfies every sovereign-cloud requirement.”

The first is defensible. The second is a compliance claim.

### 6.3 Region And Feature Parity Caveats Must Be Explicit

Microsoft’s current guidance is a good warning: regional and feature availability vary, and teams should verify model, quota, and dependent-service support before rollout. That same lesson applies beyond Azure. If V2’s narrative includes GovCloud or sovereign deployment, it must distinguish between:

- architectural compatibility
- actual environment availability

Source note: Used Microsoft Foundry’s regional-availability guidance and decision checklist `https://learn.microsoft.com/en-us/azure/foundry/reference/region-support` (checked 2026-04-11).

### 6.4 Why This Matters To enterprise / Government Audiences

enterprise/government stakeholders hear “offline” as:

- network boundary
- operator control
- patching and support burden
- approved supply chain
- evidence and auditability

So the persuasive message is not glamour. It is operational clarity:

- what stays local
- what leaves the boundary
- what can be swapped later

### 6.5 The Best V2 Wording

Recommended wording:

“V2’s retrieval architecture is local-first and portable. That makes it a good fit for disconnected or sovereign deployment patterns, but the exact controls, model endpoints, and accreditation path still depend on the target environment.”

Source note: Used Microsoft Sovereign Cloud on local control and fully disconnected environments, Red Hat on fully disconnected regulated environments and OpenAI-compatible RAG APIs, and OECD’s public-sector guardrails framing (checked 2026-04-11).

---

## Patterns To Adopt

### Pattern A

**Open with one mission-relevant win, not with the architecture.**  
Application to V2: start with a PM or logistics question whose value is obvious in one sentence.

Source note: Great Demo + Guideflow.

### Pattern B

**Build the demo as modules by persona.**  
Application to V2: PM, logistics, field, cyber, limitation/recovery.

Source note: Guideflow + Storylane.

### Pattern C

**Maintain a fixed canary pack and treat it like an evaluation asset, not a favorite query list.**  
Application to V2: run the same pre-demo pack after any major routing, index, or extraction change.

Source note: AWS Bedrock evaluation + White House M-25-22.

### Pattern D

**Rehearse the failure script, not only the success path.**  
Application to V2: operator language for weak answer, partial answer, and refusal should be written down.

Source note: Storylane + OECD + White House M-25-22.

### Pattern E

**Frame V2 as control-first and portable, not anti-cloud.**  
Application to V2: contrast local control and data locality with managed-platform convenience without insulting the platforms.

Source note: GSA OneGov + White House M-25-22 + Microsoft Sovereignty + Red Hat OpenShift AI.

### Pattern F

**Use lifecycle TCO, not “cost per prompt,” as the procurement frame.**  
Application to V2: present build cost, recurring ops, validation cost, and portability value.

Source note: Glean + Great Demo + White House M-25-22.

### Pattern G

**Use “architecture-compatible with disconnected deployment” language unless a real environment is already proven.**  
Application to V2: do not let “offline-friendly” drift into “restricted-ready” on stage.

Source note: Microsoft Foundry + Microsoft Sovereignty + Red Hat disconnected-environment materials.

---

## Patterns To Reject

### Reject 1

**Reject the 10-query buffet.**  
Reason: enterprise demo guidance favors modularity, outcomes, and recovery room, not maximum click count.

### Reject 2

**Reject audience-choice early in the session.**  
Reason: it burns trust before the canaries have proven the system.

### Reject 3

**Reject aggregation-first sequencing.**  
Reason: the highest-risk capability should not be the first impression.

### Reject 4

**Reject “free AI” chest-beating.**  
Reason: procurement audiences think in portability, support, security standards, and lifecycle cost.

### Reject 5

**Reject “offline” as a hand-wave.**  
Reason: the current market language is more precise, and buyers will expect the same precision.

### Reject 6

**Reject public on-stage debugging.**  
Reason: it turns a recoverable miss into a trust collapse.

---

## Questions That Need User Judgment

### Question 1

How procurement-heavy will the May 2 audience actually be?

Why research cannot answer it: the right balance between cost/deployment slides and live query time depends on who is in the room.

### Question 2

Does the user want to position V2 against named platforms or against categories?

Why research cannot answer it: naming Bedrock/Azure/Red Hat raises the evidence bar and invites comparison on features the audience may not even care about.

### Question 3

How much should the May 2 demo emphasize offline/GovCloud/restricted future-state versus current local workstation proof?

Why research cannot answer it: this is partly a political/organizational decision, not just a technical one.

### Question 4

Should the demo include any live audience-choice segment at all?

Why research cannot answer it: the tradeoff is between excitement and controllability, and the right answer depends on the room and the speaker’s risk tolerance.

### Question 5

How aggressive should the cost story be?

Why research cannot answer it: some rooms respond to savings, others react better to control, portability, and reduced vendor dependence.

---

## Recommended Application To V2’s May 2 Demo

If V2 wants to align with the current published pattern, the May 2 demo should look like this:

1. Start with one business-outcome query from a known-safe persona.
2. Run two or three canary queries that are already production-validated.
3. Run one or two breadth queries from distinct personas.
4. Show one deliberate trust-boundary moment.
5. End with a cost/deployment/portability slide and then Q&A.

What that means operationally:

- **Do not** open with aggregation.
- **Do not** promise “ask anything.”
- **Do not** let the architecture take over the first half of the meeting.
- **Do** carry written fallback language.
- **Do** talk about portability, local control, and lifecycle cost in procurement terms.

---

## Final Synthesis

The best published pattern for enterprise RAG demos in 2025-2026 is not a magic-query pattern. It is a **control pattern**:

- control the sequence
- control the claims
- control the backup paths
- control the procurement narrative
- control the trust boundary

V2 is actually well-suited to that pattern if the team resists the urge to prove everything at once.

Signed: reviewer
