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

## Launch tab cheat sheet

| Field                  | What it is                                    | When to change it                                                         |
|------------------------|-----------------------------------------------|---------------------------------------------------------------------------|
| **Query pack**         | JSON of 400 questions + expected answers      | Only if you have a new pack                                               |
| **Config YAML**        | Retrieval + store config                      | Only when A/B testing a new retrieval config                              |
| **Report MD**          | Markdown output path                          | Change before each run so you do not overwrite a prior report             |
| **Results JSON**       | Machine-readable output path                  | Same as above                                                             |
| **CUDA_VISIBLE_DEVICES** | GPU index                                   | Leave at `0` on single-GPU workstations                                   |
| **Max queries**        | Cap on how many queries to run                | Set to `5` for a smoke test; leave blank for a real 400-query run         |

**Start** kicks off the run. **Stop** cancels at the end of the current query
(cooperative cancel, not a hard kill).

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
