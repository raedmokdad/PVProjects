from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime
from typing import Callable
from zoneinfo import ZoneInfo

RUN_HOUR = 0
RUN_MINUTE = 5
POLL_SECONDS = 30

try:
    TZ = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover — Fallback ohne tzdata
    TZ = datetime.now().astimezone().tzinfo

_started = False
_start_lock = threading.Lock()

_TRUE = {"1", "true", "yes", "on"}


def enabled() -> bool:
    return (os.environ.get("ENABLE_SCHEDULER") or "").strip().lower() in _TRUE


def _past_time(now: datetime) -> bool:
    return (now.hour, now.minute) >= (RUN_HOUR, RUN_MINUTE)


def should_run(now: datetime, last_done: date | None) -> bool:
    if last_done == now.date():
        return False
    return _past_time(now)


def _worker(run_callable: Callable[[], object]) -> None:
    now = datetime.now(TZ)
    # Beim Start den heutigen Slot als erledigt markieren, wenn 00:05 schon vorbei ist,
    # damit ein Neustart am Nachmittag nicht sofort einen Lauf auslöst.
    last_done: date | None = now.date() if _past_time(now) else None
    while True:
        time.sleep(POLL_SECONDS)
        now = datetime.now(TZ)
        if not should_run(now, last_done):
            continue
        last_done = now.date()
        print(f"Geplanter Lauf 00:05 startet ({now.isoformat(timespec='seconds')}).")
        try:
            run_callable()
        except Exception as exc:  # noqa: BLE001 — ein Fehler darf den Scheduler nicht beenden
            print(f"Geplanter Lauf fehlgeschlagen: {exc}")


def start(run_callable: Callable[[], object]) -> bool:
    global _started
    with _start_lock:
        if _started:
            return False
        _started = True
    threading.Thread(target=_worker, args=(run_callable,), name="pv-scheduler", daemon=True).start()
    print("Scheduler aktiv: täglicher Lauf 00:05 Europe/Berlin.")
    return True
