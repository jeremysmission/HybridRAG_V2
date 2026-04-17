# Operation Freeload Tiering And Reassembly

Date: 2026-04-06

## Current Facts

- Current HybridRAG3 backlog due for enrichment: about `6.9M` chunks
- Desired reduced target after recovery dedup: about `3.0M` chunks
- `3.0M` should be treated as an aggressive goal, not the base planning assumption
- Current V1 chunk sample shows average `text_length` around `996` characters, with median around `1085`

## Grounded Throughput Baseline

The only hard local extraction rate we have right now is the overnight run:

- `2000` chunks processed
- `66406` seconds elapsed
- average `33.2` seconds per chunk
- average `1.81` chunks per minute
- average `10.14` entities per chunk
- average `2.31` relationships per chunk

This means local `phi4:14b` extraction is useful for sampling, shard testing, and background progress, but not for full-corpus one-pass enrichment at current speed.

## What The Current Math Looks Like

Using the observed `33.2s/chunk` rate:

### If the reduced corpus is `3.0M` chunks

- `1` extraction lane: about `1153` days
- `2` lanes: about `576` days
- `4` lanes: about `288` days

### If recovery dedup lands closer to `4.0M-5.0M`

- `4.0M` chunks on `4` lanes: about `384` days
- `5.0M` chunks on `4` lanes: about `480` days

## Conclusion

- Recovery dedup is mandatory
- Tiering is mandatory
- Local-only `phi4:14b` cannot be the sole enrichment strategy for the full backlog
- The install blocker matters because every extra workstation lane materially changes the schedule

## Immediate Priority

The first operational production step becomes recovery dedup as soon as the full source folder is available.

At the same time, workstation installation stays active as a parallel enablement thread.

Reason:

- dedup is the highest-leverage immediate action once the source tree is in hand
- workstation installs still matter because they are needed for the later background assembly line
- model selection only matters after the reduced corpus and shard plan exist

Operational rule:

- start recovery dedup first when the source folder arrives
- keep workstation install recovery moving in parallel
- then benchmark shard lanes against the reduced corpus
- then lock the tiering policy

## Offline Model Strategy

### Workstation-safe candidates

These are the practical local candidates currently worth testing:

- `phi4-mini`
  - Microsoft
  - Ollama size about `2.5GB`
  - best fit for memory-constrained and latency-bound Tier 1 work
  - source: https://ollama.com/library/phi4-mini

- `gemma3:4b`
  - Google
  - Ollama size about `3.3GB`
  - good candidate for fast local Tier 1 extraction attempts
  - source: https://ollama.com/library/gemma3

- `gemma3:12b`
  - Google
  - Ollama size about `8.1GB`
  - stronger but heavier Tier 2 candidate
  - source: https://ollama.com/library/gemma3

- `llama3.1:8b`
  - Meta
  - Ollama size about `4.9GB` for `Q4_K_M`
  - plausible Tier 2 candidate
  - source: https://ollama.com/library/llama3.1:8b

### primary workstation-only candidates

If local-only execution is acceptable and exported artifacts stay machine-neutral:

- `Qwen2.5-3B-Instruct`
  - strong structured output / JSON reputation
  - `Q4_K_M` size about `2.1GB`
  - source: https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF

- `Qwen2.5-7B-Instruct`
  - stronger structured output / table handling candidate
  - `Q4_K_M` size about `4.68GB`
  - source: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF

## Important Reality Check On "More Small Models"

More loaded models only helps if aggregate useful throughput beats fewer stronger lanes.

The metric is:

- chunks per hour at acceptable extraction quality

Not:

- how many model copies fit in VRAM

If four small models each produce bad JSON, weak relationships, or poor table recovery, they lose even if they are easy to load.

## Official Ollama Constraints That Matter

Ollama supports concurrent model loads only if models fully fit in VRAM.

Important rules from the official docs:

- new GPU-loaded models must completely fit in available VRAM to allow concurrent model loads
- `OLLAMA_MAX_LOADED_MODELS` sets how many models may stay loaded if they fit
- `OLLAMA_NUM_PARALLEL` increases memory use by scaling effective context
- parallel requests for one model increase context memory roughly by `parallel * context`
- larger context lengths also increase memory use materially

Sources:

- https://docs.ollama.com/faq
- https://docs.ollama.com/context-length

## Practical Implication For primary workstation

Do not assume:

- `2` models per GPU automatically means `4` useful workers

Safer first benchmark order:

1. `1` model per GPU
2. `OLLAMA_NUM_PARALLEL=2`
3. reduced context for extraction workloads
4. only then test multiple concurrent loaded models per GPU

For a `24GB` GPU, two `4-5GB` class models are much more realistic than two `8GB+` class models once context and KV cache overhead are included.

## Practical Implication For The Workstation Desktop

The workstation desktop should first be treated as:

- one reliable repo install
- one reliable background extraction lane

After that, test:

- `phi4-mini + gemma3:4b`
or
- `phi4-mini + llama3.1:8b-text-q3_K_M`

Do not assume two larger models are worth it until measured.

## Recommended Tiering Plan

### Tier 0: Deterministic only

Use regex / deterministic extraction for:

- empty or near-empty chunks
- obvious contacts
- obvious part numbers
- obvious dates
- obvious tabular rows

No LLM calls here.

### Tier 1: Fast local model

Use for easy narrative chunks:

- `phi4-mini`
- `gemma3:4b`
- `Qwen2.5-3B` on the high-capacity local machine if allowed

Goal:

- fast pass
- cheap pass
- acceptable JSON

### Tier 2: Stronger local model

Use for harder chunks:

- `llama3.1:8b`
- `gemma3:12b`
- `Qwen2.5-7B`
- existing `phi4:14b` lanes where justified

Goal:

- better entity and relationship quality
- stronger table and structured recovery

### Tier 3: Remote OSS

Reserve for:

- failures
- low-confidence outputs
- high-value shards
- quality-sensitive retries

Default remote lane:

- `OSS20`

Escalation lane:

- `OSS120`

## Shard And Reassembly Plan

### Shard rule

Shard by manifest, not by machine-specific folders.

Each manifest row should carry:

- `chunk_id`
- `source_path`
- `shard_id`
- `tier`
- `assigned_model`
- `status`
- `attempt_count`
- `priority`

### Worker outputs

Each worker writes:

- `results_<shard>.jsonl`
- `failures_<shard>.jsonl`
- `metrics_<shard>.json`

### Merge rule

Merge by `chunk_id`.

If multiple successful outputs exist for the same chunk, keep:

1. highest successful tier
2. then highest confidence
3. then latest successful run

### Import dedup rule

At import:

- entity dedup key: `(chunk_id, entity_type, normalized_text)`
- relationship dedup key: `(chunk_id, subject_text, predicate, object_text)`

### Machine-neutral artifact rule

Shared outputs must not include:

- hostname
- GPU name
- local username
- local absolute machine-specific paths beyond approved source-path normalization

Keep machine logs local and keep exported shard artifacts host-neutral.

## Benchmark Order Before Large-Scale Rollout

Run the same `100-200` representative chunks through each candidate lane and compare:

- chunks per minute
- valid JSON rate
- entities per chunk
- relationships per chunk
- table-row recovery
- retry rate
- failure rate
- VRAM footprint from `ollama ps` and `nvidia-smi`

Compare at least:

- `2 x stronger model`
- `4 x smaller model`
- `1 strong + 1 small` mixed lane

## Current Planning Bottom Line

- `3.0M` chunks is a good aggressive recovery target, but not yet the base assumption
- local `phi4:14b` alone is far too slow for the full backlog
- the fastest meaningful win is:
  - run dedup recovery
  - keep workstation install recovery moving in parallel
  - benchmark small and medium local models on real shard samples
  - reserve remote OSS for the hard tail

## Chronology And Dependencies

This work has to happen in order. Some slices can overlap, but the dependency chain is real.

### Phase 1: Recovery dedup on the high-capacity local machine

Goal:

- run document-level recovery dedup against the full source corpus
- produce `canonical_files.txt`
- shrink the rebuild input set as much as credibly possible

Why first:

- this is the highest-leverage size reduction step
- every downstream stage becomes cheaper and faster if the corpus is reduced first

Dependency status:

- blocks final rebuild sizing
- blocks final shard counts
- blocks realistic AWS token budgeting

### Parallel enablement thread: Workstation install recovery

Goal:

- get CorpusForge and V2 installed and runnable on the workstation laptop and workstation desktop

Why in parallel:

- without working installs, those machines cannot contribute background shard work
- the assembly-line plan assumes they become continuous local workers after dedup and rebuild begin

Dependency status:

- blocks workstation-side shard generation
- blocks workstation-side local extraction
- blocks background preprocessing on the work machines

### Phase 2: Rebuild the reduced corpus

Goal:

- rechunk and re-index from the canonical file list
- create the reduced chunk corpus for Operation Freeload

Why third:

- AWS enrichment should consume the reduced corpus, not the pre-recovery one
- this is the point where the real chunk count becomes known

Dependency status:

- blocks final shard manifests
- blocks final AWS throughput estimate
- blocks final per-tier routing ratios

### Phase 3: Shard and benchmark

Goal:

- build shard manifests
- benchmark Tier 1 and Tier 2 local models on representative shard samples
- benchmark the remote OSS lane on a controlled sample

Why fourth:

- tiering should be chosen from measured shard performance, not from model-size guesses

Dependency status:

- blocks final local-vs-remote routing policy
- blocks stable assembly-line settings

### Phase 4: Assembly-line enrichment

Goal:

- keep local lanes and AWS busy continuously
- ensure there is always another shard ready for the next available worker

Why fifth:

- this is where throughput wins accumulate
- the system should behave like a production line, not a sequence of manual one-offs

## Assembly-Line Rule

The target operating mode is:

- dedup and rebuild create the reduced corpus
- shard generation keeps a ready queue
- local machines process their assigned tiers continuously
- AWS always has another prepared shard waiting
- finished shards are merged and imported continuously

Do not wait for one whole global batch to finish before preparing the next one.

## Practical Assembly-Line Flow

### Station 1: Dedup and canonicalization

Runs on the high-capacity local machine.

Output:

- `canonical_files.txt`
- duplicate review reports
- dedup metrics

### Station 2: Reduced rebuild

Runs on the high-capacity local machine first, with workstations helping once installs are stable.

Output:

- reduced chunk corpus
- reduced index
- shard-ready manifests

### Station 3: Shard packaging

Can run on the toaster or any CPU helper machine.

Output:

- shard manifests
- priority queues
- routing assignments by tier

### Station 4: Local Tier 0 / Tier 1 / Tier 2 processing

Runs continuously on:

- workstation desktop
- workstation laptop
- high-capacity local machine

Output:

- local extraction results
- retry queue for harder shards

### Station 5: AWS Tier 3 processing

Consumes the hard tail continuously.

Output:

- remote extraction results
- final retry queue for only the real failures

### Station 6: Merge and import

Can run on the toaster or another helper lane.

Output:

- merged results by `chunk_id`
- deduplicated entity and relationship imports
- progress dashboards

## Keep AWS Fed

The correct AWS pattern is not:

- prepare everything
- send everything at once
- wait

The correct AWS pattern is:

- keep a small ready queue of validated shard manifests
- submit shards in controlled batches
- collect results while the next shards are already being prepared
- use local lanes to drain easy work so AWS sees the hard tail, not the whole corpus

Operationally:

- AWS should always have another shard ready
- but the queue should stay controlled enough to respect the rate ceiling and permit rerouting

## Dependency Summary

### Hard dependencies

- workstation install recovery before workstation background processing
- recovery dedup before final reduced rebuild
- reduced rebuild before final shard count and realistic AWS sizing
- shard benchmark before final tier routing policy

### Overlap allowed

- workstation install recovery can happen while the high-capacity local machine runs dedup
- shard packaging logic can be prepared before the reduced corpus is fully done
- local model benchmarking can begin on representative samples before the full reduced rebuild finishes
- AWS tooling can be prepared before the final endpoint policy is locked

## What To Avoid

- do not start full AWS processing from the unreduced corpus unless forced
- do not wait for every local lane to finish before feeding AWS
- do not choose tier routing only from VRAM fit guesses
- do not let install work drift behind while the plan assumes workstation participation
