# Demo Day Checklist — 2026-05-02

**Author:** Jeremy Randall (CoPilot+)
**System:** HybridRAG V2 on Beast (dual 3090, 64GB RAM)

---

## Pre-Demo (30 min before)

### Hardware
- [ ] Check GPU: `nvidia-smi` -- both 3090s visible, < 2GB used
- [ ] Check disk: `df -h /c/HybridRAG_V2` -- > 10GB free
- [ ] Close unnecessary apps (browser, Slack, etc.)

### Environment
- [ ] Activate venv: `cd C:\HybridRAG_V2 && .venv\Scripts\activate`
- [ ] Verify torch CUDA: `python -c "import torch; assert torch.cuda.is_available()"`
- [ ] Set single GPU: `set CUDA_VISIBLE_DEVICES=0`
- [ ] Set API key: `set OPENAI_API_KEY=sk-...`

### Data Verification
- [ ] Run: `python scripts/health_check.py`
- [ ] Verify store: `python -c "from src.store.lance_store import LanceStore; s=LanceStore('data/index/lancedb'); print(s.count()); s.close()"` -- expect 17,707
- [ ] Verify entities: `python -c "from src.store.entity_store import EntityStore; e=EntityStore('data/index/entities.sqlite3'); print(e.count_entities())"` -- expect 40,981

### Smoke Test
- [ ] Run golden eval: `python scripts/run_golden_eval.py --retrieval-only` -- expect 25/25
- [ ] Start API: `python -m src.api.server` -- should show port 8000
- [ ] Quick query: `curl -X POST localhost:8000/query -H "Content-Type: application/json" -d "{\"query\": \"What is the transmitter power at Riverside?\"}"`

---

## Demo Flow (10 queries)

| # | Type | Query | Expected | Budget |
|---|------|-------|----------|--------|
| 1 | SEMANTIC | Transmitter output power at Riverside? | 1.2 kW | < 5s |
| 2 | ENTITY | Field technician for Riverside? | Mike Torres | < 5s |
| 3 | AGGREGATE | Parts replaced at Riverside March 2024? | WR-4471, RF Connector, SN-2901, SN-2902 | < 5s |
| 4 | TABULAR | Status of PO-2024-0501? | IN TRANSIT, FM-220, Cedar Ridge | < 5s |
| 5 | COMPLEX | Compare Riverside vs Cedar Ridge issues? | SN-2847, noise floor, CH3, corrosion | < 15s |
| 6 | MESSY | CH3 noise workaround? | attenuation, 2 steps, +6dB | < 5s |
| 7 | REFUSAL | Fort Wainwright maintenance 2024? | NOT_FOUND (trust moment) | < 5s |
| 8 | CRAG | General equipment condition? | maintenance, repair | < 20s |
| 9 | V1vsV2 | Parts currently backordered? | PS-800, Granite Peak | < 5s |
| 10 | AUDIENCE | Let them ask anything | -- | -- |

---

## Recovery Plays

### API won't start
```bash
python -m src.api.server --port 8001  # try alternate port
netstat -an | findstr 8000            # check if port in use
```

### Query returns no results
```bash
python scripts/health_check.py        # verify stores
python scripts/run_golden_eval.py --query GQ-008  # test one query
```

### GPU OOM
```bash
set CUDA_VISIBLE_DEVICES=1            # switch to other GPU
# or restart with CPU reranker only
```

### Slow queries (> 10s)
- Check nvidia-smi for GPU contention
- Kill Ollama if running: `taskkill /im ollama.exe /f`
- Restart API server

---

## Post-Demo

- [ ] Save demo logs
- [ ] Note any audience questions for follow-up
- [ ] Screenshot results for report

---

Jeremy Randall | HybridRAG_V2 | 2026-04-07 MDT
