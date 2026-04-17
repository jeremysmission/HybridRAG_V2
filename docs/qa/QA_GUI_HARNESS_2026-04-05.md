# HybridRAG V2 — GUI QA Harness & Button Smash Protocol

**Author:** Jeremy Randall (CoPilot+)
**Date:** 2026-04-05 MDT
**Applies to:** Every sprint that includes GUI work (Sprint 3+)

---

## Philosophy

A GUI that works when you click politely is not a shipped GUI. Users click fast, double-click everything, resize mid-operation, switch tabs while indexing, and close windows during streaming. If the GUI survives a methodical button smash, it survives production.

---

## 1. Test Tiers

### Tier A: Scripted Functional Tests (Automated)
Programmatic tests that simulate user actions via Tkinter event injection. Run headless where possible.

### Tier B: Smart Monkey Tests (Automated)
Targeted chaos — rapid clicks on known high-risk areas (query submit, index start/cancel, mode switches).

### Tier C: Dumb Monkey Tests (Automated)
Random widget interaction with no domain knowledge. Finds crashes, freezes, and unhandled exceptions.

### Tier D: Human Button Smash (Manual)
A real person deliberately trying to break the GUI. This is the final gate before demo.

---

## 2. Automated GUI Test Harness

The harness lives at `src/gui/testing/` and provides:

### Event Injection Helpers
```python
# Simulate click on a widget
def click(widget):
    widget.event_generate("<Button-1>")
    widget.update_idletasks()

# Simulate rapid double-click
def double_click(widget, delay_ms=50):
    widget.event_generate("<Button-1>")
    widget.after(delay_ms, lambda: widget.event_generate("<Double-Button-1>"))
    widget.update_idletasks()

# Simulate key press
def type_text(widget, text, delay_ms=20):
    for char in text:
        widget.event_generate("<Key>", keysym=char)
        widget.update_idletasks()

# Simulate rapid repeated clicks (button smash)
def rapid_click(widget, count=20, delay_ms=30):
    for _ in range(count):
        widget.event_generate("<Button-1>")
        widget.update_idletasks()
```

### Smart Monkey (targeted chaos)
```python
def smart_monkey_query_panel(app, rounds=50):
    """Rapid-fire the query panel — submit, cancel, resize, switch tabs."""
    for i in range(rounds):
        action = random.choice([
            "submit_empty",       # Submit with no text
            "submit_rapid",       # Submit 5 times in 200ms
            "type_and_submit",    # Type partial query, submit
            "resize_mid_query",   # Resize window while streaming
            "switch_tab_mid",     # Switch to Index tab while query running
            "cancel_stream",      # Cancel streaming mid-response
            "double_click_submit",# Double-click submit button
        ])
        execute_action(app, action)
```

### Dumb Monkey (random chaos)
```python
def dumb_monkey(app, duration_seconds=60):
    """Click random widgets, type random text, resize randomly."""
    widgets = collect_all_widgets(app)
    end_time = time.time() + duration_seconds
    crashes = []
    while time.time() < end_time:
        widget = random.choice(widgets)
        action = random.choice(["click", "double_click", "type_garbage", "focus", "resize"])
        try:
            execute_random(widget, action)
        except Exception as e:
            crashes.append((widget, action, str(e)))
    return crashes
```

---

## 3. Button Smash Test Cases

### 3.1 Query Panel Smash

| # | Test | How | Expected |
|---|------|-----|----------|
| Q1 | Rapid submit (20x in 1s) | Click Submit 20 times fast | Queues or debounces — no duplicate queries, no freeze |
| Q2 | Submit with empty query | Click Submit with blank text field | Validation message, no crash, no API call |
| Q3 | Submit during streaming | Start a query, immediately submit another | First query completes or cancels cleanly, second queues |
| Q4 | Cancel mid-stream | Start streaming query, click Cancel | Stream stops, UI returns to ready state, no orphan threads |
| Q5 | Paste 10KB into query field | Paste huge text block | Truncated or rejected with message, no freeze |
| Q6 | Special characters | Query: `'; DROP TABLE chunks; --` | Sanitized, no SQL injection, normal response |
| Q7 | Unicode flood | Query: emoji + CJK + RTL mix | No encoding crash, renders or rejects gracefully |
| Q8 | Double-click Submit | Double-click the submit button | Single query fires, not two |

### 3.2 Index Panel Smash

| # | Test | How | Expected |
|---|------|-----|----------|
| I1 | Start/Cancel rapid toggle | Click Start, Cancel, Start, Cancel 10x fast | State machine stays consistent, no orphan processes |
| I2 | Start indexing, close window | Start index, click X to close | Indexing cancels cleanly, no zombie threads, temp files cleaned |
| I3 | Start indexing, switch tabs | Start index, switch to Query tab, switch back | Progress still updating, no desync |
| I4 | Re-index while indexing | Click Start while already indexing | Blocked with message, or queued — never dual-index |
| I5 | Index with no source files | Point to empty directory | Clear "no files found" message, returns to ready |

### 3.3 Settings Panel Smash

| # | Test | How | Expected |
|---|------|-----|----------|
| S1 | Save with invalid values | Set top_k to -1, temperature to 999 | Validation error shown, settings not saved |
| S2 | Rapid save (10x in 1s) | Click Save 10 times fast | Single save, no corruption, no race |
| S3 | Change settings mid-query | Modify top_k while a query is streaming | Current query unaffected, new settings apply to next query |

### 3.4 Window Smash

| # | Test | How | Expected |
|---|------|-----|----------|
| W1 | Resize to minimum | Drag window to smallest possible | Widgets reflow or scroll, no overlap, no crash |
| W2 | Resize during streaming | Resize while tokens are streaming in | Text area reflows, streaming continues |
| W3 | Minimize during query | Minimize while query running, restore | Query completes in background, result visible on restore |
| W4 | Multi-monitor drag | Drag window between monitors | Renders correctly on both, DPI scaling intact |
| W5 | Close during boot | Click X during startup splash/loading | Clean exit, no orphan processes |

### 3.5 Threading & Race Conditions

| # | Test | How | Expected |
|---|------|-----|----------|
| T1 | Query + Index simultaneous | Start indexing, immediately submit query | Both run or one blocks with message — no deadlock |
| T2 | Rapid tab switching | Switch tabs 30 times in 5 seconds | All panels render, no uninitialized widgets |
| T3 | Status bar consistency | Check status bar after every smash test | Always reflects actual system state, never stale |
| T4 | Memory leak check | Run 50 queries, check process memory | Memory growth < 100MB (no unbounded accumulation) |

---

## 4. Dumb Monkey Parameters

Run for each QA pass:

| Parameter | Value |
|-----------|-------|
| Duration | 60 seconds |
| Click frequency | 10-30 per second |
| Action mix | 40% click, 20% double-click, 15% type garbage, 15% resize, 10% tab switch |
| Crash tolerance | 0 unhandled exceptions |
| Freeze tolerance | 0 (UI must stay responsive — main loop never blocked > 500ms) |

---

## 5. Manual Button Smash Protocol (Human Tester)

This is the final demo gate. A human (not the developer) spends 10 minutes trying to break the GUI.

**Instructions for the tester:**

1. Open the app normally. Note startup time.
2. Before doing anything useful, try to break it:
   - Click everything you can see, fast
   - Double-click buttons that should only be single-clicked
   - Type random characters into every text field
   - Resize the window to absurdly small, then maximize
   - Submit queries while other operations are running
   - Close and reopen the app 3 times rapidly
3. Then do the happy path:
   - Submit a real query, get an answer
   - Start indexing, let it complete
   - Change a setting, verify it persists
4. Then try to break it again:
   - Submit 10 queries as fast as possible
   - Cancel operations mid-flight
   - Disconnect network (if online features), reconnect
5. Report:
   - Any crash (application exit)
   - Any freeze (unresponsive > 3 seconds)
   - Any visual glitch (overlapping text, missing widgets)
   - Any data issue (wrong results, stale display)

---

## 6. QA Report Addendum (GUI Section)

Add this to the Sprint QA Report when GUI is present:

```
## GUI QA

### Automated Tests
- [ ] Scripted functional (Tier A): [X]/[X] passing
- [ ] Smart monkey (Tier B): [X] rounds, [X] crashes
- [ ] Dumb monkey (Tier C): [X] seconds, [X] crashes, [X] freezes

### Button Smash (Manual)
- Tester: [name]
- Duration: [X] minutes
- Crashes: [count]
- Freezes: [count]
- Visual glitches: [count and description]
- Data issues: [count and description]

### Threading
- [ ] T1 Query + Index simultaneous: [PASS/FAIL]
- [ ] T2 Rapid tab switching: [PASS/FAIL]
- [ ] T3 Status bar consistency: [PASS/FAIL]
- [ ] T4 Memory leak (50 queries, delta): [X] MB

### Verdict
- [ ] GUI ready for demo
- [ ] GUI needs fixes: [list]
```

---

## 7. When to Run GUI QA

| Event | GUI QA Required |
|-------|----------------|
| Sprint with GUI changes | Full protocol (Tiers A-D) |
| Sprint without GUI changes | Tier A only (regression) |
| Demo gate | Full protocol + manual button smash by non-developer |
| Dependency upgrade (tkinter, Python) | Full protocol |

---

## References

- [Monkey Testing Complete Guide (testomat.io, 2026)](https://testomat.io/blog/what-is-monkey-testing-in-software-testing-a-complete-guide/)
- [Monkey Testing: Random Testing with Purpose (Substack)](https://ryancraventech.substack.com/p/monkey-testing-explained-random-testing)
- [Monkey Testing: Types, Benefits, Best Practices (aqua-cloud)](https://aqua-cloud.io/monkey-testing/)
- [Chaos Monkey Guide for Engineers (BrowserStack)](https://www.browserstack.com/guide/chaos-monkey-testing)
- [Testing Tkinter Applications (O'Reilly)](https://www.oreilly.com/library/view/python-gui-programming/9781788835886/c44a6d3f-4010-4bfa-9af2-d8489186050b.xhtml)

---

Jeremy Randall | HybridRAG_V2 | 2026-04-05 MDT
