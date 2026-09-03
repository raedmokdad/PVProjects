from __future__ import annotations

import os
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Lokale .env-Datei laden (lokal nützlich; auf Railway kommen Variablen direkt aus dem Dashboard).
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

from filter.facts import facts_from_row, format_eur
from filter.geo import bundesland_for, city_for, ort_facets
from filter.pv_storage import classify, is_planning
from jobs import scheduler
from jobs.daily import run as run_daily, yesterday
from jobs.scrape_state import heal_stale_run, is_running, read_status, secret_configured, secret_ok
from portals import portal_catalog, portal_home, portal_label
from portals.click import notice_click_url
from store.db import Store

app = Flask(__name__, template_folder="ui/templates", static_folder=None)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.jinja_env.cache = None


def enrich_rows(rows) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item.update(facts_from_row(item))
        item["open_url"] = notice_click_url(item.get("portal") or "", item.get("pid") or "", item.get("project_url") or "")
        cat, reason = classify(item.get("title") or "", item.get("excerpt") or "", item.get("cpv") or "")
        if cat:
            item["category"] = cat
            item["match_reason"] = reason
        if is_planning(item.get("title") or "", item.get("excerpt") or "", item.get("cpv") or ""):
            item["category"] = "Planung"
        item["bundesland"] = bundesland_for(item)
        item["city_label"] = city_for(item)
        item["value_label"] = format_eur(item.get("value_eur"))
        item["area_label"] = format_de(item.get("area_m2"), "m²")
        item["kwp_label"] = format_de(item.get("capacity_kwp"), "kWp", decimals=1)
        item["published_label"] = format_date_de(item.get("published_on"))
        item["deadline_label"] = format_date_de(item.get("deadline"))
        item["completion_label"] = format_date_de(item.get("completion_on"))
        item["portal_label"] = portal_label(item.get("portal") or "")
        item["portal_home"] = portal_home(item.get("portal") or "")
        out.append(item)
    return out


def format_de(value, unit: str, decimals: int = 0) -> str:
    """1200.0 -> '1.200 m²'. Leere Werte ergeben ''."""
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if decimals and number != int(number):
        text = f"{number:,.{decimals}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    else:
        text = f"{number:,.0f}".replace(",", ".")
    return f"{text} {unit}".strip()


def format_date_de(iso) -> str:
    """'2026-08-21' -> '21.08.2026'."""
    raw = str(iso or "").strip()[:10]
    try:
        return date.fromisoformat(raw).strftime("%d.%m.%Y")
    except ValueError:
        return ""


def date_span(lo: str, hi: str) -> str:
    a, b = format_date_de(lo), format_date_de(hi)
    if a and b:
        return a if a == b else f"{a} – {b}"
    return a or b


def numeric_bounds(rows: list[dict], key: str) -> tuple[float | None, float | None]:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None, None
    return min(values), max(values)


def fmt_bound(value: float | None) -> str:
    if value is None:
        return ""
    if float(value) == int(value):
        return str(int(value))
    return str(value)


def date_bounds(rows: list[dict], key: str) -> tuple[str, str]:
    values = [str(row.get(key) or "").strip() for row in rows]
    values = [v for v in values if v]
    if not values:
        return "", ""
    return min(values), max(values)


def city_options(rows: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        city = (row.get("city_label") or row.get("city") or "").strip().split("\n")[0].strip()
        if city and city not in seen:
            seen.add(city)
            out.append(city)
    return sorted(out, key=str.lower)


def category_counts(rows: list[dict]) -> dict[str, int]:
    counts = {"PV": 0, "Speicher": 0, "PV+Speicher": 0, "Planung": 0}
    for row in rows:
        key = row.get("category") or "PV"
        if key in counts:
            counts[key] += 1
    return counts


def page_context(
    rows: list[dict],
    last,
    run_date=None,
    show_all: bool = False,
    view: str = "latest",
    relevant_count: int = 0,
) -> dict:
    area_min, area_max = numeric_bounds(rows, "area_m2")
    kwp_min, kwp_max = numeric_bounds(rows, "capacity_kwp")
    pub_min, pub_max = date_bounds(rows, "published_on")
    deadline_min, deadline_max = date_bounds(rows, "deadline")
    end_min, end_max = date_bounds(rows, "completion_on")
    cats = category_counts(rows)
    count_noun = "relevante Anzeigen" if view == "relevant" else "Ausschreibungen gefunden"
    return {
        "rows": rows,
        "last": last,
        "run_date": run_date,
        "show_all": show_all,
        "view": view,
        "relevant_count": relevant_count,
        "count_noun": count_noun,
        "area_min": fmt_bound(area_min),
        "area_max": fmt_bound(area_max),
        "kwp_min": fmt_bound(kwp_min),
        "kwp_max": fmt_bound(kwp_max),
        "pub_min": pub_min,
        "pub_max": pub_max,
        "deadline_min": deadline_min,
        "deadline_max": deadline_max,
        "deadline_span": date_span(deadline_min, deadline_max),
        "end_min": end_min,
        "end_max": end_max,
        "end_span": date_span(end_min, end_max),
        "cities": city_options(rows),
        "ort_facets": ort_facets(rows),
        "total": len(rows),
        "n_pv": cats["PV"],
        "n_speicher": cats["Speicher"],
        "n_both": cats["PV+Speicher"],
        "n_planung": cats["Planung"],
        "run_secret_required": secret_configured(),
        "scrape": heal_stale_run(),
        "portals": portal_catalog(),
    }


def _render_list(view: str, show_all: bool = False):
    store = Store()
    try:
        last = store.last_run()
        last = dict(last) if last else None
        relevant_count = len(store.relevant_unique())
        if view == "relevant":
            rows = enrich_rows(store.relevant_unique())
            run_date = None
        elif show_all:
            rows = enrich_rows(store.matches_unique())
            run_date = None
        else:
            run_date = last["run_date"] if last else None
            rows = enrich_rows(store.matches_unique(run_date) if run_date else [])
    finally:
        store.close()
    return render_template(
        "index.html",
        **page_context(
            rows,
            last,
            run_date=run_date,
            show_all=show_all,
            view=view,
            relevant_count=relevant_count,
        ),
    )


@app.route("/")
def index():
    return _render_list("latest")


@app.route("/alle")
def alle():
    return _render_list("all", show_all=True)


@app.route("/relevant")
def relevant():
    return _render_list("relevant")


MAX_BACKFILL_DAYS = 60


def _scrape_in_background(day: date) -> None:
    try:
        run_daily(day)
    except Exception as exc:  # noqa: BLE001 — Status steht in scrape_status.json
        print(f"Manueller Lauf fehlgeschlagen: {exc}")


def parse_run_date(raw: str | None) -> tuple[date | None, str]:
    """Optionales Datum aus dem Button. Leer -> gestern. Gibt (Datum, Fehler) zurück."""
    value = (raw or "").strip()
    if not value:
        return yesterday(), ""
    try:
        chosen = date.fromisoformat(value)
    except ValueError:
        return None, "Datum bitte im Format JJJJ-MM-TT angeben."
    today = yesterday() + timedelta(days=1)
    if chosen > today:
        return None, "Datum darf nicht in der Zukunft liegen."
    if chosen < today - timedelta(days=MAX_BACKFILL_DAYS):
        return None, f"Datum liegt zu weit zurück (max. {MAX_BACKFILL_DAYS} Tage)."
    return chosen, ""


if scheduler.enabled():
    scheduler.start(lambda: run_daily(yesterday()))



@app.route("/run/status")
def run_status():
    return jsonify(heal_stale_run())


@app.route("/run", methods=["POST"])
def start_run():
    payload = request.get_json(silent=True) or {}
    secret = payload.get("secret") or request.form.get("secret") or request.headers.get("X-Run-Secret")
    if not secret_ok(secret):
        return jsonify(ok=False, error="Geheimnis falsch oder fehlt."), 403
    heal_stale_run()
    raw_date = payload.get("date") or request.form.get("date")
    day, err = parse_run_date(raw_date)
    if err:
        return jsonify(ok=False, error=err), 400
    if is_running():
        return jsonify(ok=False, error="Ein Lauf läuft bereits.", scrape=read_status()), 409
    threading.Thread(
        target=_scrape_in_background, args=(day,), name="pv-scrape", daemon=True
    ).start()
    return jsonify(ok=True, message=f"Suche gestartet (Stichtag {day.isoformat()})."), 202


def _notice_ids():
    payload = request.get_json(silent=True) or {}
    secret = payload.get("secret") or request.form.get("secret") or request.headers.get("X-Run-Secret")
    if not secret_ok(secret):
        return None, (jsonify(ok=False, error="Geheimnis falsch oder fehlt."), 403)
    portal = str(payload.get("portal") or request.form.get("portal") or "").strip()
    pid = str(payload.get("pid") or request.form.get("pid") or "").strip()
    if not portal or not pid:
        return None, (jsonify(ok=False, error="Portal und ID fehlen."), 400)
    return (payload, portal, pid), None


@app.route("/notice", methods=["DELETE"])
def delete_notice():
    parsed, err = _notice_ids()
    if err:
        return err
    _payload, portal, pid = parsed
    store = Store()
    try:
        deleted = store.delete_notice(portal, pid)
    finally:
        store.close()
    if not deleted:
        return jsonify(ok=False, error="Eintrag nicht gefunden."), 404
    return jsonify(ok=True)


@app.route("/notice/relevant", methods=["POST"])
def mark_relevant():
    parsed, err = _notice_ids()
    if err:
        return err
    _payload, portal, pid = parsed
    store = Store()
    try:
        moved = store.mark_relevant(portal, pid)
    finally:
        store.close()
    if not moved:
        return jsonify(ok=False, error="Eintrag nicht gefunden oder schon relevant."), 404
    return jsonify(ok=True)


@app.route("/notice/inbox", methods=["POST"])
def mark_inbox():
    parsed, err = _notice_ids()
    if err:
        return err
    _payload, portal, pid = parsed
    store = Store()
    try:
        moved = store.mark_inbox(portal, pid)
    finally:
        store.close()
    if not moved:
        return jsonify(ok=False, error="Eintrag nicht gefunden oder schon in der Liste."), 404
    return jsonify(ok=True)


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Lokale Liste: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
