# RAG Outsourcing Estimates sensitive data 700GB 2026-04-12

## Purpose

This note gives three realistic estimate scenarios for outsourcing a Retrieval-Augmented Generation (RAG) system for a enterprise program with:

- about `700 GB` of mixed-format historical data
- about `15 years` of accumulated content
- sensitive data handling requirements
- design/build work, hardware or cloud capacity, and recurring maintenance

These are not vendor-issued quotes. Public Colorado-region, sensitive data-capable fixed-price quotes are generally not posted online. These scenarios are therefore built from public rate cards, public cloud pricing, and public platform pricing so there is at least a defensible back-pocket benchmark.

## Important Framing

- sensitive data and enterprise constraints usually push prices up, not down.
- Colorado/Front Range does not materially change the economics in your favor; the better public benchmark is national AI consulting rates plus government-style labor categories.
- For this kind of problem, the hard part is not just "standing up a chatbot." It is data preparation, chunking, indexing, extraction, evaluation, security handling, and operational support.

## Public Inputs Used

### AI labor benchmarks

- Upwork ML engineer guide:
  - beginner: `$50-$80/hour`
  - intermediate: `$80-$120/hour`
  - advanced: `$120-$200+/hour`
  - Source: https://www.upwork.com/hire/machine-learning-experts/cost/

- GSA schedule example:
  - Cloud Business Integration Consultant I: `$145.48/hour`
  - Cloud Business Integration Consultant II: `$163.59/hour`
  - Cloud Business Integration Consultant III: `$180.81/hour`
  - Cloud Business Integration Consultant IV: `$198.04/hour`
  - Solutions Architect: `$332.62/hour`
  - Source: https://www.gsaadvantage.gov/ref_text/47QTCA22D0028/0Z5GZV.3UVTUJ_47QTCA22D0028_IFSS60047QTCA22D0028INNOVATECATALOG030724.PDF

### Broad AI project benchmark

- Clutch AI pricing guide:
  - average AI development project cost: `$120,594.55`
  - typical timeline: `10 months`
  - average hourly range: `$25-$49/hour`
  - Source: https://clutch.co/developers/artificial-intelligence/pricing

### AWS public RAG pricing benchmark

- AWS Generative AI Application Builder official cost page:
  - RAG-enabled use case with Bedrock Nova Pro: about `$1,300/month`
  - Bedrock Nova Pro component at `8,000` interactions/day: `$487.80/month`
  - Titan embeddings at that scale: `$9.00/month`
  - OpenSearch Serverless sample usage with 4 OCU minimum: `$691.20/month`
  - Source: https://docs.aws.amazon.com/solutions/latest/generative-ai-application-builder-on-aws/cost.html

### Red Hat public platform pricing signals

- Red Hat FAQ:
  - OpenShift AI is layered on top of OpenShift
  - OpenShift must be purchased separately
  - Source: https://www.redhat.com/en/resources/10-questions-about-openshift-ai-faq

- Red Hat public price list example:
  - OpenShift AI bare metal full support: `$13,860/year` or `$1,271/month`
  - OpenShift Container Platform bare metal full support: `$23,760/year` or `$2,178/month`
  - OpenShift Platform Plus bare metal full support: `$29,700-$39,600/year` or `$2,723-$3,630/month`
  - Source: https://www.cloudingenuity.com/contracts/5272/5272_Red_Hat.pdf

### Hardware pricing signal

- Carahsoft Dell AI workstation brochure:
  - Precision 5860, 128 GB RAM, RTX 6000 48 GB, 2 TB: `$20,000`
  - Precision 7875, 256 GB RAM, RTX 6000 48 GB, 4 TB: `$36,000`
  - Source: https://static.carahsoft.com/concrete/files/2617/5440/7871/9_-_End_of_Year_Pricing_-_July_2025_v1.1_-_Just_Brochures.pdf

## Three Estimate Scenarios

## Quote 1: Lean specialist / boutique build on one on-prem AI workstation

Best fit:

- small program
- trying to stay cost-controlled
- willing to accept a narrower support model
- heavy preprocessing done on owned hardware

Assumptions:

- `160-240` hours of senior ML/RAG engineering
- advanced specialist rate: `$120-$200+/hour`
- one AI workstation similar to the `$20,000` Carahsoft example
- ongoing support: `10-20` hours/month

Estimated one-time design/build:

- labor: about `$19,200-$48,000`
- hardware: about `$20,000`
- total one-time startup: about `$39,000-$68,000`

Estimated monthly maintenance:

- support labor: about `$1,200-$4,000/month`
- cloud/API/query costs: additional, depending on model usage

Estimated first-year total:

- about `$53,000-$116,000+`

Interpretation:

- This is the cheapest plausible outsourced path.
- It is still a serious five-figure effort.
- For sensitive data handling, this is the low-end scenario, not the conservative one.

## Quote 2: Government-style integrator on AWS managed RAG

Best fit:

- organization wants AWS-native architecture
- cloud is acceptable
- prefers managed retrieval/inference infrastructure over local control

Assumptions:

- `200-300` hours consultant labor at GSA-like cloud/business integration rates
- `20-40` hours solutions architect time
- AWS managed RAG infrastructure roughly in line with the official AWS `$1,300/month` sample at moderate usage
- support `10-20` hours/month at GSA-like rates

Estimated one-time design/build:

- consultant labor: about `$29,000-$59,000`
- architect labor: about `$6,600-$13,300`
- total one-time startup: about `$35,000-$73,000`

Estimated monthly maintenance:

- AWS RAG infrastructure: about `$1,300/month` at moderate usage
- support labor: about `$1,450-$3,960/month`
- total monthly: about `$2,750-$5,300/month`

Estimated first-year total:

- about `$68,000-$137,000`

Interpretation:

- This is more realistic than Quote 1 if the buyer wants cloud-managed services and sensitive data-compatible discipline from day one.
- It still does not include every possible security, accreditation, or custom integration surcharge.

## Quote 3: Red Hat / OpenShift AI platform-first enterprise stack

Best fit:

- organization wants enterprise platform support
- expects stronger vendor-backed operations posture
- is willing to pay a substantial recurring platform premium

Assumptions:

- one bare-metal OpenShift AI node plus required underlying OpenShift subscription
- Red Hat OpenShift AI FAQ requirement that OpenShift AI sits on top of OpenShift
- one AI workstation/server footprint similar to the `$20,000` Carahsoft benchmark
- `200-300` hours consultant labor plus `20-40` hours architect labor
- support `10-20` hours/month at GSA-like rates

Estimated one-time design/build:

- consultant + architect labor: about `$35,000-$73,000`
- hardware: about `$20,000`
- total one-time startup: about `$55,000-$93,000`

Estimated monthly maintenance, option A:

- Red Hat OpenShift AI bare metal full support: about `$1,271/month`
- Red Hat OpenShift Container Platform bare metal full support: about `$2,178/month`
- combined platform floor: about `$3,449/month`
- support labor: about `$1,450-$3,960/month`
- total monthly: about `$4,900-$7,400/month`

Estimated monthly maintenance, option B:

- Red Hat OpenShift AI bare metal full support: about `$1,271/month`
- Red Hat OpenShift Platform Plus bare metal full support: about `$2,723-$3,630/month`
- combined platform floor: about `$3,994-$4,901/month`
- support labor: about `$1,450-$3,960/month`
- total monthly: about `$5,400-$8,900/month`

Estimated first-year total:

- about `$114,000-$200,000+`

Interpretation:

- This is the most enterprise-shaped option.
- It is also the most expensive of the three.
- Red Hat gives you platform and support posture, but it does not remove the need for custom chunking, retrieval design, extraction rules, evaluation, and domain adaptation.

## What These Estimates Mean For Current Internal Work

Current internal effort estimate:

- about `10 hours/week`
- over about `8 weeks`
- about `80 hours` invested so far

If that same effort were billed at public specialist rates:

- at Upwork advanced ML rates: about `$9,600-$16,000+`
- at GSA-like consultant rates: about `$11,600-$15,800`

That means the current internal effort is already equivalent to a meaningful outside-services bill, but it is still well below what a full outsourced design/build plus monthly support model would likely cost.

## Suggested One-Paragraph Talking Point

"For a 700 GB, 15-year, mixed-format corpus with sensitive data handling requirements, the public market data points to a serious outside-services cost, not a small software purchase. A lean specialist build with one AI workstation is still roughly a $50K-$100K first-year effort. A cloud-managed AWS path is more like roughly $70K-$140K in year one. A Red Hat/OpenShift AI enterprise stack can push into the low six figures in year one once platform subscriptions, hardware, and support are included. By comparison, the work done in-house so far is roughly equivalent to a low five-figure specialist-services bill, while also aiming at a much cheaper long-term maintenance model." 

