# HybridRAG V2 — GUI Human Visual Checklist

**Tester:** _______________
**Date:** _______________
**Machine:** _______________
**Python:** _______________
**Display:** _______________ (resolution, DPI scaling %)

---

## How to Launch

```bash
cd C:\HybridRAG_V2
.venv\Scripts\activate
set CUDA_VISIBLE_DEVICES=0
set OPENAI_API_KEY=sk-...
python src/gui/launch_gui.py
```

---

## Section 1: First Launch (does it even open?)

- [ ] Window appears within 10 seconds
- [ ] No Python tracebacks in the terminal
- [ ] Window title says "HybridRAG V2" (or similar)
- [ ] Window is a reasonable size (not tiny, not fullscreen)
- [ ] Dark theme is applied (dark background, light text)
- [ ] No white flicker or unstyled flash before theme loads

**If any of the above fail, STOP and report. Nothing below matters.**

---

## Section 2: Layout and Theme

- [ ] Nav bar visible at top with tabs: Query, Entity, Settings
- [ ] Status bar visible at bottom
- [ ] Content area fills the space between nav and status
- [ ] Text is readable (not too small, not cut off)
- [ ] Font looks consistent (not mixing serif/sans-serif randomly)
- [ ] Colors are consistent dark theme (no random white panels)
- [ ] Buttons are visible and labeled
- [ ] No overlapping widgets or text
- [ ] Scrollbars appear where content overflows (not clipped)

---

## Section 3: Status Bar

- [ ] Shows chunk count (number, even if 0)
- [ ] Shows entity count (number, even if 0)
- [ ] Shows relationship count (number, even if 0)
- [ ] Shows LLM status ("available" or "not configured")
- [ ] Updates within a few seconds of launch (not stuck on "loading...")
- [ ] If no API key set: shows "not configured" clearly

---

## Section 4: Query Tab (main functionality)

### 4a: Empty State
- [ ] Input field is visible and accepts text
- [ ] Submit button is visible and clickable
- [ ] Top-k selector is visible (dropdown or spinner)
- [ ] Answer area is empty (no garbage text)
- [ ] No errors in terminal just from viewing this tab

### 4b: Submit a Query (requires API key + data)
Type: "Who is the field technician for Riverside?" and click Submit.

- [ ] Submit button responds to click (visual feedback — disabled, color change, or spinner)
- [ ] "Searching..." or similar status appears
- [ ] Answer text starts appearing (streaming tokens or full response)
- [ ] Query path badge appears (should say ENTITY or SEMANTIC)
- [ ] Badge is color-coded (not plain text)
- [ ] Confidence indicator appears (HIGH/PARTIAL/NOT_FOUND)
- [ ] Confidence has color (green/yellow/red)
- [ ] Source citations appear below the answer
- [ ] Latency or timing information visible
- [ ] After completion, Submit button re-enables

### 4c: Submit Empty Query
Click Submit with no text in the input field.

- [ ] Does NOT crash
- [ ] Shows validation message or does nothing
- [ ] Does NOT make an API call (check terminal for no network activity)

### 4d: Stop / Cancel (if available)
Start a query, then click Stop before it completes.

- [ ] Stop button exists and is visible during query
- [ ] Clicking Stop halts the response
- [ ] UI returns to ready state (Submit re-enabled)
- [ ] No orphan text keeps appearing after Stop

### 4e: Second Query
Submit another query after the first completes.

- [ ] Previous answer clears or new answer replaces it
- [ ] New path badge and confidence appear
- [ ] No leftover state from first query

---

## Section 5: Entity Tab

- [ ] Tab switches without crash
- [ ] Entity type summary visible (even if all zeros)
- [ ] Search/lookup fields visible
- [ ] If entities exist: lookup returns results
- [ ] If entities empty: shows "no results" or empty state (not error)
- [ ] Relationship search visible
- [ ] Can switch back to Query tab without issues

---

## Section 6: Settings Tab

- [ ] Tab switches without crash
- [ ] Shows config values (top_k, confidence, reranker, etc.)
- [ ] Values are readable (not truncated or overlapping)
- [ ] Read-only feel (no editable fields that shouldn't be editable)
- [ ] Can switch back to other tabs without issues

---

## Section 7: Tab Switching

- [ ] Query → Entity: no crash, Entity renders
- [ ] Entity → Settings: no crash, Settings renders
- [ ] Settings → Query: no crash, Query state preserved (previous answer still there?)
- [ ] Rapid tab switching (click all 3 tabs fast): no crash, no freeze

---

## Section 8: Window Behavior

- [ ] Resize window smaller: widgets reflow or scroll, no overlap
- [ ] Resize window larger: content fills space reasonably
- [ ] Minimize and restore: content still there, no blank screen
- [ ] Maximize: fills screen properly

---

## Section 9: Close

- [ ] Click X to close window
- [ ] Window closes promptly (not hanging)
- [ ] Terminal shows clean exit (no tracebacks)
- [ ] No orphan Python processes left running (check Task Manager)

---

## Section 10: Edge Cases (try to break it)

- [ ] Paste a very long query (500+ characters): no crash
- [ ] Type special characters (quotes, backslashes, unicode): no crash
- [ ] Resize window to minimum possible: no crash
- [ ] Submit query while another is running: queues or blocks, no crash
- [ ] Double-click Submit: single query fires, not two
- [ ] Switch tabs while query is streaming: no crash

---

## Results Summary

| Section | Pass | Fail | Notes |
|---------|------|------|-------|
| 1. First Launch | __ / 6 | | |
| 2. Layout & Theme | __ / 9 | | |
| 3. Status Bar | __ / 6 | | |
| 4. Query Tab | __ / 20 | | |
| 5. Entity Tab | __ / 6 | | |
| 6. Settings Tab | __ / 5 | | |
| 7. Tab Switching | __ / 4 | | |
| 8. Window Behavior | __ / 4 | | |
| 9. Close | __ / 4 | | |
| 10. Edge Cases | __ / 6 | | |
| **TOTAL** | **__ / 70** | | |

**Verdict:**
- [ ] 70/70: Ship it
- [ ] 60-69: Minor cosmetic issues, fix before demo
- [ ] 50-59: Significant issues, needs work
- [ ] <50: GUI not demo-ready

**Screenshots attached:** (take screenshots of any failures)

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
