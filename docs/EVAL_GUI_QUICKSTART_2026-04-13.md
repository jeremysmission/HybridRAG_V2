# Eval GUI Quickstart (Operator)

**Purpose:** cold-start guide for running the 400-query production eval from the
HybridRAG V2 desktop GUI. Written for an operator who has never opened this
repo before. Reading time: ~3 minutes.

## What this tool does

Runs the standardized 400-query retrieval test against the HybridRAG V2 LanceDB
store and writes a pair of report files (markdown + JSON) to `docs/`. Also lets
you browse past reports, compare any two runs, and watch the run history over
time. Everything is local; no cloud services are involved beyond whatever
endpoint the query router is already configured to use.

## One-time install

1. Open a terminal at the repo root (`C:\HybridRAG_V2`).
2. Double-click `INSTALL_EVAL_GUI.bat`.
3. Wait for the `[OK] HybridRAG V2 Eval GUI install verified.` line. If it
   stops at a proxy error, set `HTTPS_PROXY` and `HTTP_PROXY` in your shell
   **before** running the bat again.

## Every run (3 steps)

1. Double-click `start_eval_gui.bat`.
2. Confirm the four tabs are visible: **Launch / Results / Compare / History**.
3. Go to **Launch** and press **Start**.

Everything else is optional tuning.

## Launch tab -- field-by-field walkthrough

The Launch tab has six fields. Most of them you never touch after the first
time. Here is what each one is, what gets selected by default, and when you
would change it.

### 1. Query pack (JSON)

- **What it is:** the list of standardized questions the eval runs, paired
  with the known-correct answer paths for each one. This is the "test" in
  "test suite."
- **Default:** `tests/golden_eval/production_queries_400_2026-04-12.json`
  (400 questions across three personas).
- **Browse button opens in:** `tests/golden_eval/` inside your checkout.
- **When to change it:** rarely. Only if a new frozen query pack has been
  generated for a later iteration. If you are writing a new pack yourself,
  save it under `tests/golden_eval/` and pick it here.
- **What happens if you pick something bad:** the runner refuses to start
  and pops `Query pack not found` or reports zero usable queries.

### 2. Config YAML

- **What it is:** the retrieval / routing / store configuration that the
  eval runs against. Contains the LanceDB path, reranker toggles, candidate
  pool size, router thresholds, etc.
- **Default:** `config/config.tier1_clean_2026-04-13.yaml` (the current
  frozen clean Tier 1 baseline).
- **Browse button opens in:** `config/` inside your checkout.
- **When to change it:** A/B testing -- you point baseline at the old
  config, candidate at the new config, and diff the runs in the Compare
  tab.
- **What happens if you pick something bad:** the runner refuses to start
  and pops `Config not found`, or fails at `LOAD_STORE` if the config
  points at a non-existent LanceDB path.

### 3. Report MD (output path)

- **What it is:** where the human-readable Markdown scorecard is written
  at the end of the run. This is the file you open to read the result.
- **Default:** `docs/PRODUCTION_EVAL_RESULTS_GUI_<timestamp>.md` -- a new
  timestamped filename every run, so back-to-back runs do not overwrite
  each other.
- **Browse button opens:** a save-as dialog in `docs/`.
- **When to change it:** if you want a custom filename to make the run
  easy to identify later (e.g.
  `docs/PRODUCTION_EVAL_RESULTS_CAP_PATCH_BASELINE.md`).
- **Not persisted by Save as defaults:** this field always refreshes to a
  new timestamped filename on every GUI launch. Saving defaults does not
  freeze it. A custom static filename has to be typed in each run.
- **Safety net:** if the path you pick already exists on disk, the GUI
  pops a yes/no overwrite confirmation before starting. Default is **No**.

### 4. Results JSON (output path)

- **What it is:** the machine-readable version of the same report.
  History / Results / Compare tabs all consume this file. Every new GUI
  run writes a `provenance` block here so repeated runs can be told apart.
- **Default:** `docs/production_eval_results_gui_<timestamp>.json` -- same
  timestamp convention as the MD.
- **Browse button opens:** a save-as dialog in `docs/`.
- **When to change it:** same rule as Report MD -- rename for clarity, or
  leave the timestamped default.
- **Not persisted by Save as defaults:** same rule as Report MD -- fresh
  timestamp every launch.
- **Safety net:** same overwrite confirmation as the MD.

### 5. CUDA_VISIBLE_DEVICES

- **What it is:** the GPU index Python should bind to before loading
  torch / the embedder.
- **Default:** `0` (the single GPU on a workstation).
- **When to change it:** very rarely -- only if your machine has multiple
  GPUs and you want to pin the eval to a specific one.
- **What happens if you pick something bad:** the runner fails at BOOT
  with `CUDA not available` or a torch device error.

### 6. Max queries (blank = all)

- **What it is:** a cap on how many queries from the pack to actually run.
  Blank (empty) means run every query in the pack.
- **Default:** blank (run the full 400).
- **When to change it:**
  - Set to `5` for a quick smoke test (~2 minutes).
  - Set to `25` for a slightly larger sanity check (~5-10 minutes).
  - Leave blank for a real regression run (~30-75 minutes).
- **What happens if you pick something bad:** a non-positive or
  non-numeric value is treated as blank and the full pack runs. No error.

---

## Start / Stop / Clear log / Save as defaults / Reset defaults

Five buttons sit right below the input fields:

- **Start** -- kicks off the run. Disabled while a run is in progress.
- **Stop** -- cooperatively cancels between queries (not a hard kill, so
  the current query finishes first, typically within 30-75 seconds).
- **Clear log** -- wipes the live log window without affecting output
  files or stored results.
- **Save as defaults** -- writes your input choices (query pack, config,
  GPU index, max queries) to `.eval_gui_defaults.json` at the repo root.
  Next time you launch the GUI, those saved values load automatically
  instead of the shipped ones. This is a per-checkout file -- it is
  gitignored and never pushed. The small status line under the buttons
  shows whether you are on `Defaults: shipped` or
  `Defaults: saved on <timestamp>`.

  **Note:** the output paths (Report MD / Results JSON) are deliberately
  NOT saved. They always refresh to a new timestamped filename on every
  launch so day-2 runs write to a new artifact instead of immediately
  hitting the overwrite guard on day-1's file. If you want a custom
  static output filename, type it in the field before clicking Start
  each run -- but that is the exception, not the default.
- **Reset defaults** -- restores every field to the shipped values and
  deletes the saved defaults file. Pops a yes/no confirmation first.

### Typical daily flow (after your first run)

1. Double-click `start_eval_gui.bat`.
2. Status line reads `Defaults: saved on <your last save>`.
3. Every field is pre-populated from your saved values.
4. Click **Start**.
5. Go get coffee.

You should only need to touch Browse on day one (to find and save your
preferred paths). After that, Start is the only button you click.

## What "done" looks like

- Phase label settles on `done (PASS)` or `done (STOPPED)`.
- Progress bar reaches `N / N`.
- Scorecard fills in (PASS / PARTIAL / MISS / Routing / p50 / p95 / elapsed).
- Two files appear in `docs/`:
  - `PRODUCTION_EVAL_RESULTS_GUI_<timestamp>.md`
  - `production_eval_results_gui_<timestamp>.json`

If the output filenames already exist, the GUI asks you to confirm overwrite
before starting. Default answer is **No** -- pick a new filename and retry.

## Results tab -- after a run

- **Browse** to any `production_eval_results*.json` in `docs/`.
- Click **Load Results**.
- The **Run Info** strip shows the query pack, config, store path, GPU,
  timestamp, run_id, status, and elapsed time so you know exactly which run
  you are looking at.
- Use the verdict / persona / family / query-type filters to focus on misses.
- Click any row to see the full query + expected vs. retrieved sources.

## Compare tab -- did my patch help?

1. Load the **baseline** JSON (pre-patch).
2. Load the **candidate** JSON (post-patch).
3. Click **Compare**.

The headline row shows delta for PASS / PARTIAL / MISS / Routing. Green means
better, red means worse. Lower is better for MISS, so a `MISS: 146 -> 96 (-50)`
delta renders green.

Each loaded file's status line shows the pack + config tag pulled from
provenance, so you always know which run is "baseline" vs "candidate".

## History tab -- all runs at a glance

- Auto-scans `docs/` for every `production_eval_results*.json`.
- Sortable table with `Run ID / Timestamp / Pack / Config / Total / PASS /
  PARTIAL / MISS / Routing / p50 / File`.
- The **Pack / Config** column is a short label (`production_queries_400 /
  config.tier1_clean`) pulled from each run's provenance block.
- Click a column header to sort. Double-click a row to open the JSON.
  Right-click for Open MD / Copy path.

## Troubleshooting

**GUI opens but History tab is empty.**
Check the `Docs directory` field at the top of the History tab. It should point
at this repo's `docs/` folder. Use **Browse** to correct it, then **Refresh**.

**Launch tab says `CUDA not available`.**
The environment is not seeing a GPU. Close the GUI, run `nvidia-smi` in a
terminal, and relaunch.

**First run takes a long time at `LOAD_EMBEDDER`.**
Normal -- the embedder and reranker models are being downloaded to
`%USERPROFILE%\.cache\huggingface`. Subsequent runs use the cache and skip
that step. If the download is failing, set `HTTPS_PROXY` and relaunch.

**Router errors about `openai` / `azure`.**
The query router needs to reach the configured LLM endpoint. Check that
`HTTPS_PROXY` is set and that your API key is present in Windows Credential
Manager under `hybridrag/azure_api_key` or equivalent.

**Stop button takes ~25 seconds to react.**
Expected -- cancel fires between queries. The current query finishes first.

## Where to look when things feel wrong

| Symptom                                 | First place to look                                |
|-----------------------------------------|----------------------------------------------------|
| History tab empty                       | History tab > Docs directory field                 |
| Results tab has no Run Info fields      | Older JSON without provenance -- rerun from GUI    |
| Compare MISS delta shows `+-50`         | You are on an old build; update + relaunch        |
| Overwrite dialog did not appear         | Older build without overwrite guard; update + relaunch |
| Proxy errors on first launch            | Set HTTPS_PROXY / HTTP_PROXY in shell env          |

## Signed

Jeremy Randall | HybridRAG_V2 | 2026-04-13 MDT
