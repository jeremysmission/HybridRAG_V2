# Tier D: Human Button Smash Script

**For:** A non-developer testing the HybridRAG V2 GUI
**Duration:** 10 minutes
**Goal:** Try to crash, freeze, or confuse the application
**Tolerance:** Zero crashes, zero freezes > 3 seconds

---

## Before You Start

1. Open a terminal, navigate to `C:\HybridRAG_V2`
2. Run: `.venv\Scripts\python.exe -m src.gui.app`
3. Wait for the window to appear and the status bar to say "Ready"
4. Have a stopwatch or timer handy (phone is fine)
5. Keep this script open on a second monitor or printed out

---

## Phase 1: Break It First (5 minutes)

Do these as fast as you can. The goal is chaos.

### Query Panel Smash (2 minutes)

| # | What to do | What should happen |
|---|------------|-------------------|
| 1 | Click Submit with nothing typed | Error message appears, no crash |
| 2 | Click Submit 20 times as fast as you can | Only one query runs, or they queue -- no freeze |
| 3 | Type "test" and click Submit, then immediately click Submit again | First query completes or cancels, second runs |
| 4 | Paste this entire paragraph into the query box and Submit | Handles long input -- truncates or processes, no freeze |
| 5 | Type: `'; DROP TABLE chunks; --` and Submit | Normal response, no error, no data loss |
| 6 | Type a mix of emoji and foreign characters and Submit | No encoding crash, responds or says "no results" |
| 7 | Start a query, then click Cancel before it finishes | Query stops, status returns to "Ready" |
| 8 | Double-click the Submit button | Only one query fires |

### Window Smash (1 minute)

| # | What to do | What should happen |
|---|------------|-------------------|
| 9 | Drag the window as small as possible | Widgets reflow or scroll, nothing overlaps |
| 10 | Maximize the window | Everything scales up, no gaps |
| 11 | While a query is running, resize the window | Query continues, text reflows, no freeze |
| 12 | Minimize the window, wait 10 seconds, restore | Query finished in background, result is visible |
| 13 | If you have two monitors, drag the window between them | Renders on both, no DPI glitch |

### Tab/Panel Smash (2 minutes)

| # | What to do | What should happen |
|---|------------|-------------------|
| 14 | Click every tab 10 times fast | All tabs render, no blank panels |
| 15 | Start a query, switch to the Entity tab, switch back | Query still running, result appears when done |
| 16 | Go to Settings, change top_k to 1, save, run a query | Fewer results returned -- setting took effect |
| 17 | Go to Settings, type "-5" for top_k, try to save | Validation error shown, setting not saved |
| 18 | Click Save in Settings 10 times fast | Single save, no corruption |
| 19 | Click the X button to close during startup | Clean exit, no zombie process in Task Manager |

---

## Phase 2: Use It Normally (3 minutes)

Now try to use the app the way a real person would.

| # | What to do | What should happen |
|---|------------|-------------------|
| 20 | Ask: "What is the transmitter power at Riverside?" | Answer mentions 1.2 kW, with a source citation |
| 21 | Ask: "Who is the field technician for Riverside?" | Answer mentions Mike Torres |
| 22 | Ask: "What parts are backordered?" | Answer mentions PS-800 and/or Granite Peak |
| 23 | Ask: "What is the status of PO-2024-0501?" | Answer mentions IN TRANSIT, FM-220, Cedar Ridge |
| 24 | Click on a source link/reference | It opens or displays the source content |
| 25 | Check that the Entity panel shows entities if available | Entity list populates for relevant queries |

---

## Phase 3: Break It Again (2 minutes)

After the happy path, try to break it one more time.

| # | What to do | What should happen |
|---|------------|-------------------|
| 26 | Submit 10 queries as fast as you can (type anything) | Queues or debounces, no crash |
| 27 | While a query is running, go to Settings and change something | Current query not affected |
| 28 | Close the app and immediately reopen it 3 times | Clean startup each time, no leftover state |
| 29 | Unplug your network cable (if online) or disable WiFi, then submit a query | Graceful error: "LLM unavailable" or similar, no crash |
| 30 | Plug network back in, submit another query | Should work again |

---

## Report Template

Fill this out when done:

```
Date: ________
Tester name: ________
Duration: ________ minutes

CRASHES (application exited unexpectedly):
  Count: ____
  Details: ________

FREEZES (unresponsive > 3 seconds):
  Count: ____
  Which step: ________

VISUAL GLITCHES (overlapping text, missing widgets, blank panels):
  Count: ____
  Details: ________

DATA ISSUES (wrong answer, stale display, missing results):
  Count: ____
  Details: ________

VERDICT:
  [ ] PASS -- Ready for demo
  [ ] FAIL -- Issues found (list above)

Signed: ________________
```

---

Jeremy Randall | HybridRAG_V2 | 2026-04-08 MDT
