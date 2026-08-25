"""Ortsangaben der Treffer zu Bundesländern bündeln — für die Ort-Liste in der Seitenspalte.

Erste Wahl ist der NUTS-Code (liefern die Vergabeportale mit), Rückfall ist die
Postleitzahl aus der Adresse. Die Zuordnung über die Postleitzahl ist eine Näherung,
weil einige Leitzahlbereiche über Landesgrenzen reichen.
"""

from __future__ import annotations

import re

UNKNOWN = "Ohne Ort"

NUTS_PREFIX = {
    "DE1": "Baden-Württemberg",
    "DE2": "Bayern",
    "DE3": "Berlin",
    "DE4": "Brandenburg",
    "DE5": "Bremen",
    "DE6": "Hamburg",
    "DE7": "Hessen",
    "DE8": "Mecklenburg-Vorpommern",
    "DE9": "Niedersachsen",
    "DEA": "Nordrhein-Westfalen",
    "DEB": "Rheinland-Pfalz",
    "DEC": "Saarland",
    "DED": "Sachsen",
    "DEE": "Sachsen-Anhalt",
    "DEF": "Schleswig-Holstein",
    "DEG": "Thüringen",
}


def _plz_map() -> dict[str, str]:
    table: dict[str, str] = {
        "01": "Sachsen",
        "02": "Sachsen",
        "03": "Brandenburg",
        "04": "Sachsen",
        "06": "Sachsen-Anhalt",
        "07": "Thüringen",
        "08": "Sachsen",
        "09": "Sachsen",
        "10": "Berlin",
        "12": "Berlin",
        "13": "Berlin",
        "15": "Brandenburg",
        "16": "Brandenburg",
        "17": "Mecklenburg-Vorpommern",
        "18": "Mecklenburg-Vorpommern",
        "19": "Mecklenburg-Vorpommern",
        "20": "Hamburg",
        "21": "Hamburg",
        "22": "Hamburg",
        "23": "Schleswig-Holstein",
        "24": "Schleswig-Holstein",
        "25": "Schleswig-Holstein",
        "26": "Niedersachsen",
        "27": "Niedersachsen",
        "28": "Bremen",
        "29": "Niedersachsen",
        "30": "Niedersachsen",
        "31": "Niedersachsen",
        "32": "Nordrhein-Westfalen",
        "33": "Nordrhein-Westfalen",
        "34": "Hessen",
        "35": "Hessen",
        "36": "Hessen",
        "37": "Niedersachsen",
        "38": "Niedersachsen",
        "39": "Sachsen-Anhalt",
        "54": "Rheinland-Pfalz",
        "55": "Rheinland-Pfalz",
        "56": "Rheinland-Pfalz",
        "66": "Saarland",
        "67": "Rheinland-Pfalz",
        "88": "Baden-Württemberg",
        "98": "Thüringen",
        "99": "Thüringen",
    }
    for n in range(40, 60):
        table.setdefault(f"{n:02d}", "Nordrhein-Westfalen")
    for n in range(60, 66):
        table.setdefault(f"{n:02d}", "Hessen")
    for n in range(68, 80):
        table.setdefault(f"{n:02d}", "Baden-Württemberg")
    for n in range(80, 98):
        table.setdefault(f"{n:02d}", "Bayern")
    return table


PLZ_PREFIX = _plz_map()
PLZ_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")
CITY_AFTER_PLZ_RE = re.compile(r"(?<!\d)\d{5}(?!\d)\s+([^,;\n]+)")


def bundesland_from_nuts(nuts: str) -> str:
    code = (nuts or "").strip().upper()
    return NUTS_PREFIX.get(code[:3], "") if code.startswith("DE") else ""


def bundesland_from_plz(text: str) -> str:
    for match in PLZ_RE.finditer(text or ""):
        plz = match.group(1)
        # 14050–14199 ist Berlin, der Rest von 14 ist Brandenburg (Potsdam).
        if plz.startswith("14"):
            return "Berlin" if plz[2] in "01" else "Brandenburg"
        land = PLZ_PREFIX.get(plz[:2])
        if land:
            return land
    return ""


def bundesland_for(row: dict) -> str:
    land = bundesland_from_nuts(row.get("nuts") or "")
    if land:
        return land
    haystack = " ".join(
        str(row.get(key) or "") for key in ("city", "organisation", "title", "excerpt")
    )
    return bundesland_from_plz(haystack) or UNKNOWN


def clean_city(raw: str) -> str:
    """'Pestalozzistr. 11, 10625 Berlin-Charlottenburg, Deutschland' -> 'Berlin'."""
    text = re.sub(r"\s+", " ", str(raw or "")).strip().strip(",")
    if not text:
        return ""
    match = CITY_AFTER_PLZ_RE.search(text)
    city = match.group(1).strip() if match else text.split(",")[0].strip()
    city = re.sub(r"^\d{5}\s*", "", city)
    city = re.split(r"\s*[-–/]\s*", city)[0].strip()
    if city.lower() in {"deutschland", "germany", ""}:
        return ""
    return city[:60]


def city_for(row: dict) -> str:
    return clean_city(row.get("city") or "") or clean_city(row.get("nuts") or "")


def ort_facets(rows: list[dict], top_cities: int = 8) -> list[dict]:
    """Bundesländer mit Anzahl, je Land die häufigsten Städte mit Anzahl."""
    lands: dict[str, dict] = {}
    for row in rows:
        land = row.get("bundesland") or bundesland_for(row)
        city = row.get("city_label")
        if city is None:
            city = city_for(row)
        node = lands.setdefault(land, {"name": land, "count": 0, "_cities": {}})
        node["count"] += 1
        if city:
            node["_cities"][city] = node["_cities"].get(city, 0) + 1

    out: list[dict] = []
    for node in lands.values():
        cities = sorted(node.pop("_cities").items(), key=lambda kv: (-kv[1], kv[0].lower()))
        node["cities"] = [{"name": name, "count": count} for name, count in cities]
        node["top"] = node["cities"][:top_cities]
        node["rest"] = len(node["cities"]) - len(node["top"])
        out.append(node)
    out.sort(key=lambda n: (n["name"] == UNKNOWN, -n["count"], n["name"].lower()))
    return out
