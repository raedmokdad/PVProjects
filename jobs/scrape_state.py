from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from store.db import data_dir

STALE_SEC = 45 * 60
LOCK_NAME = "scrape.lock"
STATUS_NAME = "scrape_status.json"


def lock_path() -> Path:
    return data_dir() / LOCK_NAME


def status_path() -> Path:
    return data_dir() / STATUS_NAME


def idle_status() -> dict[str, Any]:
    return {
        "state": "idle",
        "run_date": None,
        "started_at": None,
        "finished_at": None,
        "listed": None,
        "matched": None,
        "errors": None,
        "error": None,
        "portal": None,
    }


def read_status() -> dict[str, Any]:
    path = status_path()
    if not path.is_file():
        return idle_status()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return idle_status()
    out = idle_status()
    out.update(data if isinstance(data, dict) else {})
    return out


def write_status(**fields: Any) -> dict[str, Any]:
    current = read_status()
    current.update(fields)
    path = status_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return current


def touch_lock() -> None:
    path = lock_path()
    try:
        path.touch(exist_ok=True)
    except OSError:
        pass


def acquire_lock() -> bool:
    path = lock_path()
    now = time.time()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = now - path.stat().st_mtime
        except OSError:
            return False
        if age <= STALE_SEC:
            return False
        path.unlink(missing_ok=True)
        return acquire_lock()
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(str(now))
    return True


def release_lock() -> None:
    lock_path().unlink(missing_ok=True)


def is_running() -> bool:
    path = lock_path()
    if not path.is_file():
        return False
    try:
        return time.time() - path.stat().st_mtime <= STALE_SEC
    except OSError:
        return True


def heal_stale_run() -> dict[str, Any]:
    """Wenn Status 'running' ist, der Lauf aber tot (Lock weg/alt), Status freigeben."""
    status = read_status()
    if status.get("state") != "running":
        return status
    if is_running():
        return status
    release_lock()
    return write_status(
        state="error",
        finished_at=iso_now(),
        error="Lauf abgebrochen (hängengeblieben / Timeout). Bitte erneut starten.",
        portal=None,
    )


_FLAG_VALUES = {"true", "false", "1", "0", "yes", "no", "on", "off"}


def run_secret() -> str:
    return (os.environ.get("RUN_SECRET") or os.environ.get("run_secret") or "").strip()


def on_railway() -> bool:
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))


def is_real_secret() -> bool:
    value = run_secret()
    return bool(value) and value.lower() not in _FLAG_VALUES


def secret_configured() -> bool:
    return is_real_secret()


def run_needs_setup() -> bool:
    return False


def secret_ok(provided: str | None) -> bool:
    expected = run_secret()
    if not is_real_secret():
        return True
    got = (provided or "").strip()
    if len(got) != len(expected):
        return False
    return secrets_equal(got, expected)


def secrets_equal(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def iso_now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat(sep=" ")
