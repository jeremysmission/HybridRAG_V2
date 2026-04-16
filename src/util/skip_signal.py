"""Runtime keypress signal for aborting in-process retry loops.

Why this exists
---------------
Several hot paths in V2 retry on failure: CRAG verification loops through
AMBIGUOUS grades, entity extraction retries on JSON truncation, the embedder
halves batch size on CUDA OOM. When an operator is watching a long run and
sees the same retry failing repeatedly, they should be able to press any key
to short-circuit the remaining retries and move on to the next work unit -
instead of waiting out 2-3 attempts they already know are going to fail.

Design
------
- Windows-only (``msvcrt.kbhit``). Non-TTY / non-Windows is a no-op, so code
  using this module stays safe in headless contexts and CI.
- Between-attempts abort, not hard-interrupt. A retry in flight (e.g. a
  blocking LLM HTTP call) finishes before the skip takes effect. Hard
  interrupt would require wrapping every network call in a cancellable
  worker thread, which is a much bigger refactor.
- Context manager arms a background daemon thread for the duration of a
  retry phase, resets the flag on exit. One keypress only affects one
  ``watching`` block - the operator does not accidentally skip downstream
  retries in unrelated code.
- Instructions print once per process so long runs do not spam the log.

Usage
-----
.. code-block:: python

    from src.util import skip_signal

    with skip_signal.watching("CRAG retry loop"):
        while retries < max_retries:
            if skip_signal.pressed():
                logger.info("CRAG: skip requested, exiting retry loop")
                break
            do_one_attempt()
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

try:
    import msvcrt  # type: ignore[import-not-found]
    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False

_lock = threading.Lock()
_pressed = False
_stop_event: threading.Event | None = None
_poll_thread: threading.Thread | None = None
_instructions_shown = False


def _is_interactive_tty() -> bool:
    """True only on Windows with an attached console stdin."""
    if not _HAS_MSVCRT:
        return False
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


def _poll_loop(label: str, stop_event: threading.Event) -> None:
    """Daemon loop: set the pressed flag on the first key hit."""
    global _pressed
    while not stop_event.is_set():
        try:
            if msvcrt.kbhit():  # type: ignore[union-attr]
                try:
                    msvcrt.getch()  # type: ignore[union-attr]  # consume the key
                except Exception:
                    pass
                with _lock:
                    _pressed = True
                logger.info(
                    "[skip-signal] key pressed during %s - remaining retries will be skipped "
                    "after the current attempt finishes",
                    label,
                )
                return
        except Exception:
            return
        time.sleep(0.1)


@contextmanager
def watching(label: str) -> Iterator[None]:
    """Arm the keypress watcher for a retry phase.

    Starts a daemon thread polling ``msvcrt.kbhit`` and clears the pressed
    flag on entry and exit so each phase starts clean. On non-interactive
    or non-Windows environments this is a no-op.
    """
    global _pressed, _stop_event, _poll_thread, _instructions_shown

    if not _is_interactive_tty():
        yield
        return

    with _lock:
        _pressed = False

    if not _instructions_shown:
        print(
            "[skip-signal] Press any key during a retry to skip the remaining retries "
            "after the current attempt. This message shows once per process.",
            flush=True,
        )
        _instructions_shown = True

    _stop_event = threading.Event()
    _poll_thread = threading.Thread(
        target=_poll_loop,
        args=(label, _stop_event),
        daemon=True,
        name=f"skip_signal:{label}",
    )
    _poll_thread.start()
    try:
        yield
    finally:
        if _stop_event is not None:
            _stop_event.set()
        if _poll_thread is not None and _poll_thread.is_alive():
            _poll_thread.join(timeout=0.5)
        with _lock:
            _pressed = False
        _stop_event = None
        _poll_thread = None


def pressed() -> bool:
    """Return True if a key was pressed during the current ``watching`` phase."""
    with _lock:
        return _pressed
