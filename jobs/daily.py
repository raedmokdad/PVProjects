from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# .env lokal laden (lokal nützlich; auf Railway kommen Variablen direkt aus dem Dashboard).
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from filter.ai_extract import ai_extract
from filter.facts import apply_facts
from filter.pv_storage import classify, load_filter_config
from jobs.scrape_state import acquire_lock, iso_now, release_lock, touch_lock, write_status
from portals import ALIASES, DEFAULT_PORTALS, PORTALS
from store.db import Store
from store.export import export_excel

try:
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = datetime.now().astimezone().tzinfo


def yesterday() -> date:
    return datetime.now(TZ).date() - timedelta(days=1)


def target_date(args: argparse.Namespace) -> date:
    if args.date:
        return date.fromisoformat(args.date)
    if args.today:
        return datetime.now(TZ).date()
    return yesterday()


def selected_portals(names: list[str] | None) -> list[str]:
    if not names or names == ["default"]:
        return list(DEFAULT_PORTALS)
    if "all" in names:
        return list(PORTALS)
    resolved = []
    for name in names:
        key = ALIASES.get(name, name)
        if key not in PORTALS:
            raise SystemExit(f"Unbekanntes Portal: {name}. Möglich: {', '.join(PORTALS)} (oder all)")
        if key not in resolved:
            resolved.append(key)
    return resolved


def run_portal(portal, iso: str, cfg: dict, store: Store) -> tuple[int, int, int]:
    types = cfg.get("publication_types") or ["ExAnte", "Tender"]
    print(f"Suche {portal.name} für {iso} …")
    try:
        listed = portal.list_for_date(iso, publication_types=types)
    except Exception as exc:  # noqa: BLE001 — ein Portal darf den Gesamtlauf nicht abbrechen
        print(f"  Portal fehlgeschlagen: {exc}")
        return 0, 0, 1
    print(f"{len(listed)} Bekanntmachungen nach Suche (ohne vergebene Aufträge).")

    matched = 0
    errors = 0
    seen: set[str] = set()
    for i, notice in enumerate(listed, start=1):
        if notice.pid in seen:
            continue
        seen.add(notice.pid)
        print(f"[{i}/{len(listed)}] {notice.title[:80]}")
        try:
            portal.fetch_detail(notice)
        except Exception as exc:  # noqa: BLE001 — ein Projekt darf den Lauf nicht abbrechen
            errors += 1
            print(f"  Detail fehlgeschlagen: {exc}")
        category, reason = classify(notice.title, notice.detail_text, notice.cpv, cfg)
        notice.category = category
        notice.match_reason = reason
        notice.is_match = bool(category)
        apply_facts(notice)
        if notice.is_match:
            ai_extract(notice)
        if notice.detail_text and len(notice.excerpt or "") < 1200:
            notice.excerpt = re.sub(r"\s+", " ", notice.detail_text).strip()[:2500]
        store.upsert_notice(notice, iso)
        if notice.is_match:
            matched += 1
            print(f"  TREFFER {category}: {reason}")
    return len(seen), matched, errors


def run(day: date, portal_names: list[str] | None = None) -> int:
    iso = day.isoformat()
    if not acquire_lock():
        print("Ein Lauf läuft bereits.")
        return 2
    write_status(
        state="running",
        run_date=iso,
        started_at=iso_now(),
        finished_at=None,
        listed=None,
        matched=None,
        errors=None,
        error=None,
        portal=None,
    )
    try:
        cfg = load_filter_config()
        store = Store()
        run_id = store.start_run(iso)

        listed_total = 0
        matched_total = 0
        errors_total = 0
        for name in selected_portals(portal_names):
            touch_lock()
            write_status(portal=name)
            portal = PORTALS[name]()
            listed, matched, errors = run_portal(portal, iso, cfg, store)
            listed_total += listed
            matched_total += matched
            errors_total += errors

        xlsx = export_excel(store, iso)
        store.finish_run(run_id, listed=listed_total, matched=matched_total, errors=errors_total)
        write_status(
            state="done",
            finished_at=iso_now(),
            listed=listed_total,
            matched=matched_total,
            errors=errors_total,
            error=None,
            portal=None,
        )
        print(f"Fertig. {matched_total} PV/Speicher-Treffer. Excel: {xlsx}")
        print("Liste anzeigen: python app.py")
        return 0
    except Exception as exc:  # noqa: BLE001 — Status für den Button, danach weiterreichen
        write_status(state="error", finished_at=iso_now(), error=str(exc))
        raise
    finally:
        release_lock()


def main() -> int:
    parser = argparse.ArgumentParser(description="PV- und Batteriespeicher-Projekte vom Vortag holen.")
    parser.add_argument("--date", help="Stichtag YYYY-MM-DD (Standard: gestern, Europe/Berlin)")
    parser.add_argument("--today", action="store_true", help="Heute statt gestern (zum Testen)")
    parser.add_argument(
        "--portal",
        action="append",
        help="Standard: alle Portale. z. B. oeffentlichevergabe, dtvp, nrw, berlin, hessen, bw, eo, aumass, st, th, sl, all.",
    )
    args = parser.parse_args()
    return run(target_date(args), args.portal)


if __name__ == "__main__":
    raise SystemExit(main())
