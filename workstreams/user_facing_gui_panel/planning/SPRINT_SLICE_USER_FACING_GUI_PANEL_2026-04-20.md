# Sprint Slice: User Facing GUI Panel

Date: 2026-04-20

## Objective
Build a polished V2 user-facing query panel that feels modern and simple by default, while preserving advanced operator controls behind an admin surface.

## Scope
In scope:
- main query panel UX
- source/citation rendering
- admin drawer behavior
- readiness and startup messaging
- responsive small-window behavior
- real GUI harness and button-smash coverage
- visual polish items that improve usability without re-cluttering the screen

Out of scope:
- substrate logic changes unless needed for GUI wiring
- core retrieval/extraction/store changes
- config/schema changes unrelated to GUI presentation

## Design Principles
1. User surface first.
2. Advanced knobs hidden, not removed.
3. Evidence beats vibes.
4. Real GUI QA, not just static inspection.
5. V1 is a feature mine, not a design to copy wholesale.

## Slice Breakdown

### Slice 0: Foundation
Acceptance:
- clean chat-style panel
- ask/stop/answer/sources/actions/feedback visible
- admin clutter removed from default surface

### Slice 1: Admin Surface
Acceptance:
- gear/admin drawer exists
- endpoint, Top-K, IBIT, retrieval knobs live there
- open/close behavior is stable

### Slice 2: Citation and Source UX
Acceptance:
- clickable inline citations
- source-card expansion
- highlight matching source card
- user-facing numbering is readable and sequential

### Slice 3: Live Harness
Acceptance:
- one-command real harness for the main app surface
- JSON + text evidence output
- nonzero exit on failure

### Slice 4: Boot / Readiness UX
Acceptance:
- visible boot phases
- clear ready state
- meaningful degraded/failure messaging
- Ask remains disabled until the app is actually ready

### Slice 5: Responsive Layout
Acceptance:
- right-side scroll behavior preserved
- small-window usability is acceptable
- long questions remain usable
- no control becomes unreachable at narrow widths

### Slice 6: Interaction Polish
Acceptance:
- useful hover affordances
- action buttons behave consistently
- source and footnote interactions feel intentional

### Slice 7: Theme / Visual Options
Acceptance:
- evaluate dark/light mode as a contained feature
- no visual regressions in default theme
- theming does not break readability or evidence emphasis

### Slice 8: V1 Harvest Pass
Acceptance:
- explicit keep/move/reject decisions for V1 ideas
- only proven UX wins move forward
- no reintroduction of default-screen clutter

### Slice 9: Beta Hardening
Acceptance:
- live harness pass
- manual QA pass
- resize/smash/no-traceback coverage
- known-good screenshots and operator notes

## Recommended Parallelism
Can run in parallel:
- Slice 2
- Slice 3
- Slice 4

Should usually follow after the above:
- Slice 5
- Slice 6
- Slice 7

Should be integration-gated:
- Slice 8
- Slice 9

## Current Active Round
- Agent 1: Slice 3
- Agent 2: Slice 4
- Agent 3: Slice 2
- Agent D: integration pass after slice QA

## Release Rule
No integrated GUI bundle is considered ready until:
- each slice passes individual QA
- the integrated bundle passes real-hardware GUI QA
- resize and button-smash checks pass
