# Workstation Manual Install And Workday Actions 2026-04-13

## Purpose

This is the practical fallback guide for the workstation laptop and workstation desktop if the batch installer does not complete cleanly.

It also lists the productive, safe work that can be done on those workstations today without interfering with the current primary workstation-side Tier 1 cleanup path.

## Bottom Line

If `INSTALL_WORKSTATION.bat` works, use it.

If it fails, do **not** guess. Use the manual steps below in order.

## Repo Update First

In `C:\HybridRAG_V2` on the workstation:

```powershell
git pull origin master
```

In `C:\CorpusForge` on the workstation:

```powershell
git pull origin master
```

## Preferred Installer Path

From `C:\HybridRAG_V2`:

```powershell
cmd /k INSTALL_WORKSTATION.bat -NoPause
```

If you only want inventory / dry-run:

```powershell
cmd /k INSTALL_WORKSTATION.bat -DryRun -NoPause
```

The active launcher chain is:

- `INSTALL_WORKSTATION.bat`
- `tools\setup_workstation_2026-04-12.bat`
- `tools\setup_workstation_2026-04-12.ps1`

## Manual V2 Install Fallback

Run these from `C:\HybridRAG_V2`.

### 1. Create the venv if needed

```powershell
if (!(Test-Path .venv)) { py -3.12 -m venv .venv }
```

### 2. Upgrade pip and install cert handling

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install pip-system-certs
```

### 3. Install CUDA torch lane

```powershell
.venv\Scripts\python.exe -m pip install torch==2.7.1 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

### 4. Install requirements

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5. If requirements fail on `gliner==0.2.26`, use the known fallback

```powershell
.venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org huggingface_hub onnxruntime sentencepiece tqdm "transformers>=4.51.3,<5.2.0"
.venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org --no-deps gliner==0.2.26
```

### 5b. If the `--trusted-host` fallback still connection-errors (fully proxy-hardened)

When even the `--trusted-host` fallback cannot reach pypi.org (proxy strips the
connection), install gliner from a pre-built offline bundle. No pip network
call, no HuggingFace network call.

**On a builder machine with internet access** (e.g. primary workstation):

```powershell
cd C:\HybridRAG_V2
git pull origin master
.\tools\build_gliner_offline_bundle.ps1
```

This produces `C:\HybridRAG_V2\vendor\gliner_offline.zip` containing:

- `wheels\` — gliner 0.2.26 + huggingface_hub, onnxruntime, sentencepiece, tqdm, transformers
- `hf_home\` — snapshot of `urchade/gliner_medium-v2.1`
- `manifest.json` — builder host, Python version, wheel count

**On the proxy-hardened workstation**:

1. Copy the zip to `C:\HybridRAG_V2\vendor\gliner_offline.zip`
2. Run the offline installer:

```powershell
cd C:\HybridRAG_V2
.\INSTALL_GLINER_OFFLINE.bat
```

The installer unpacks the zip, does `pip install --no-index --find-links` against
the local wheels directory, imports gliner to confirm, runs `scripts\verify_install.py`,
and writes `vendor\gliner_offline\env.cmd` — a small helper that sets `HF_HOME`
to the bundled model cache.

**Important**: at runtime, extraction will try to fetch the model from
`huggingface.co` unless `HF_HOME` is set. Any bat/script that runs gliner on
the workstation must either:

- `call vendor\gliner_offline\env.cmd` before launching Python, or
- have the operator pre-export `HF_HOME=C:\HybridRAG_V2\vendor\gliner_offline\hf_home`

The Python minor version on the builder and workstation must match (both 3.12);
otherwise the wheels won't be `--no-index`-installable.

### 6. Verify the install

```powershell
.venv\Scripts\python.exe scripts\verify_install.py
```

### 7. Optional direct checks

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
.venv\Scripts\python.exe -c "import gliner; print(gliner.__version__)"
```

## Manual CorpusForge Install Fallback

From `C:\CorpusForge`:

```powershell
if (!(Test-Path .venv)) { py -3.12 -m venv .venv }
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install pip-system-certs
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then verify the required external tools:

- Tesseract
- Poppler `pdftoppm`

Optional CUDA embedding verification:

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe scripts\verify_cuda_embedding.py
```

## Safe Workstation Actions For Today

These are productive and safe while primary workstation is handling the Tier 1 critical path.

### Safe Action 1: Get both repos current

- `git pull` in `HybridRAG_V2`
- `git pull` in `CorpusForge`

### Safe Action 2: Get the installs green

- run the batch installer first
- if it fails, use the manual fallback above
- finish by running:

```powershell
.venv\Scripts\python.exe scripts\verify_install.py
```

### Safe Action 3: Confirm V2 import readiness

If you have a Forge export directory available:

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe scripts\import_embedengine.py --source "<export_dir>" --dry-run
```

If dry-run passes and you intend to populate the workstation store:

```powershell
.venv\Scripts\python.exe scripts\import_embedengine.py --source "<export_dir>" --create-index
```

### Safe Action 4: Confirm FTS works after import

```powershell
cd C:\HybridRAG_V2
.venv\Scripts\python.exe -c "from src.store.lance_store import LanceStore; s=LanceStore('data/index/lancedb'); print(s._table.search('maintenance', query_type='fts').limit(3).to_list())"
```

### Safe Action 5: Confirm the current launcher path

These should all work:

```powershell
cmd /k INSTALL_WORKSTATION.bat -DryRun -NoPause
cmd /k tools\setup_workstation_2026-04-12.bat -DryRun -NoPause
cmd /k tools\setup_workstation_2026-04-06.bat -DryRun -NoPause
```

### Safe Action 6: Get Forge install green and run the desktop precheck

Preferred installer:

```powershell
cd C:\CorpusForge
cmd /k INSTALL_WORKSTATION.bat -NoPause
```

Then run:

```powershell
cd C:\CorpusForge
.\PRECHECK_WORKSTATION_700GB.bat
```

Required result:

```text
RESULT: PASS
```

### Safe Action 7: If the desktop is healthy, run the approved Forge Phase 1 rerun

This is the productive Forge-side work worth doing on the desktop if install correctness is green.

From `C:\CorpusForge`:

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = "logs\desktop_rerun_$ts.log"
.\.venv\Scripts\python.exe .\scripts\run_pipeline.py `
  --config .\config\config.yaml `
  --input "ProductionSource\verified\source\verified\IGS" `
  --full-reindex `
  --log-file $log
Write-Host "Log path: $log"
```

After the rerun:

1. capture the newest `data\production_output\export_YYYYMMDD_HHMM`
2. run:

```powershell
cd C:\CorpusForge
.\.venv\Scripts\python.exe .\scripts\check_export_integrity.py --export "<export_dir>"
```

3. from `C:\HybridRAG_V2`, run dry-run import only:

```powershell
cd C:\HybridRAG_V2
.\.venv\Scripts\python.exe .\scripts\import_embedengine.py --source "<export_dir>" --dry-run
```

Do **not** do a real V2 import on that export unless the dry-run passes.

## Do Not Do On The Workstations Today

Do **not** do these unless explicitly told to:

- do not run a blind full Tier 1 rerun
- do not run full Tier 2 GLiNER on a dirty store
- do not mutate the authoritative primary workstation store assumptions
- do not improvise regex changes locally

The current primary workstation-side critical path is:

1. run Tier 1 regex gate
2. run shadow Tier 1 slice
3. approve or reject the full clean rerun

## Best Use Of Workstation Time Today

If time is limited, the best order is:

1. update both repos
2. get `HybridRAG_V2` install green
3. get `CorpusForge` install green
4. run `PRECHECK_WORKSTATION_700GB.bat` in Forge
5. if desktop is healthy, run the approved Forge Phase 1 rerun
6. verify V2 import dry-run works
7. if possible, import the current Forge export and verify FTS

## Short Troubleshooting Notes

- If the batch window closes, rerun with `cmd /k ... -NoPause`.
- If `gliner` fails, use the fallback commands above.
- If `torch.cuda.is_available()` is `False`, stop and verify the CUDA/driver side before assuming V2 is ready.
- If the import succeeds but FTS query fails, rebuild/verify the LanceDB store before moving on.
- If the Forge desktop precheck does not return `RESULT: PASS`, do not start the full rerun.

## One-Paragraph Summary

The workstations are useful today for install, verification, Forge rerun work, import readiness, and index verification. They should not be used to improvise extraction changes or launch a blind full Tier 1 rerun. If the batch installer fails, use the manual pip/torch/GLiNER fallback in this document, finish with `scripts/verify_install.py`, get Forge install correctness green, and then focus on the approved Forge rerun plus V2 import/FTS readiness.
