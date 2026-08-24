from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filter.facts import facts_from_row
from filter.pv_storage import classify
from jobs import scheduler
from jobs.daily import run as run_daily, yesterday
from jobs.scrape_state import is_running, read_status, secret_configured, secret_ok
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
        out.append(item)
    return out


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
        city = (row.get("city") or "").strip().split("\n")[0].strip()
        if city and city not in seen:
            seen.add(city)
            out.append(city)
    return sorted(out, key=str.lower)


def category_counts(rows: list[dict]) -> dict[str, int]:
    counts = {"PV": 0, "Speicher": 0, "PV+Speicher": 0}
    for row in rows:
        key = row.get("category") or "PV"
        if key in counts:
            counts[key] += 1
    return counts


def page_context(rows: list[dict], last, run_date=None, show_all: bool = False) -> dict:
    area_min, area_max = numeric_bounds(rows, "area_m2")
    kwp_min, kwp_max = numeric_bounds(rows, "capacity_kwp")
    pub_min, pub_max = date_bounds(rows, "published_on")
    deadline_min, deadline_max = date_bounds(rows, "deadline")
    end_min, end_max = date_bounds(rows, "completion_on")
    cats = category_counts(rows)
    return {
        "rows": rows,
        "last": last,
        "run_date": run_date,
        "show_all": show_all,
        "area_min": fmt_bound(area_min),
        "area_max": fmt_bound(area_max),
        "kwp_min": fmt_bound(kwp_min),
        "kwp_max": fmt_bound(kwp_max),
        "pub_min": pub_min,
        "pub_max": pub_max,
        "deadline_min": deadline_min,
        "deadline_max": deadline_max,
        "end_min": end_min,
        "end_max": end_max,
        "cities": city_options(rows),
        "n_pv": cats["PV"],
        "n_speicher": cats["Speicher"],
        "n_both": cats["PV+Speicher"],
        "run_secret_required": secret_configured(),
        "scrape": read_status(),
    }


@app.route("/")
def index():
    store = Store()
    last = store.last_run()
    run_date = last["run_date"] if last else None
    rows = enrich_rows(store.matches_unique(run_date) if run_date else [])
    return render_template("index.html", **page_context(rows, last, run_date=run_date, show_all=False))


@app.route("/alle")
def alle():
    store = Store()
    last = store.last_run()
    rows = enrich_rows(store.matches_unique())
    return render_template("index.html", **page_context(rows, last, show_all=True))


def _scrape_in_background() -> None:
    try:
        run_daily(yesterday())
    except Exception as exc:  # noqa: BLE001 — Status steht in scrape_status.json
        print(f"Manueller Lauf fehlgeschlagen: {exc}")


if scheduler.enabled():
    scheduler.start(lambda: run_daily(yesterday()))


@app.route("/run/status")
def run_status():
    return jsonify(read_status())


@app.route("/run", methods=["POST"])
def start_run():
    payload = request.get_json(silent=True) or {}
    secret = payload.get("secret") or request.form.get("secret") or request.headers.get("X-Run-Secret")
    if not secret_ok(secret):
        return jsonify(ok=False, error="Geheimnis falsch oder fehlt."), 403
    if is_running():
        return jsonify(ok=False, error="Ein Lauf läuft bereits.", scrape=read_status()), 409
    threading.Thread(target=_scrape_in_background, name="pv-scrape", daemon=True).start()
    return jsonify(ok=True, message="Suche gestartet (Bekanntmachungen von gestern)."), 202


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Lokale Liste: http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
