from __future__ import annotations

import re
from dataclasses import dataclass

from portals.dates import DATE_RE, parse_de_date

AREA_RE = re.compile(
    r"(?<!\w)(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(?:m²|m2|qm|quadratmeter)\b",
    re.IGNORECASE,
)
KWP_RE = re.compile(
    r"(?<!\w)(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)\s*kwp\b",
    re.IGNORECASE,
)
BEGIN_END_RE = re.compile(
    r"\bBeginn\s+(\d{2}[./]\d{2}[./]\d{2,4})\s+Ende\s+(\d{2}[./]\d{2}[./]\d{2,4})\b",
    re.IGNORECASE,
)
RANGE_RE = re.compile(
    r"(?:leistungszeitraum|ausführungszeit|ausfuehrungszeit|bauzeit|"
    r"zeitraum der leistung(?:serbringung)?)"
    r".{0,200}?(\d{2}[./]\d{2}[./]\d{2,4})\s*(?:bis|-|–|und)\s*(\d{2}[./]\d{2}[./]\d{2,4})",
    re.IGNORECASE | re.DOTALL,
)
FERTIG_LEISTUNG_RE = re.compile(
    r"fertigstellung\s+der\s+leistung\s*:?\s*(\d{2}[./]\d{2}[./]\d{2,4})",
    re.IGNORECASE,
)
LAUFZEIT_END_RE = re.compile(
    r"enddatum\s+der\s+laufzeit\s*:?\s*(\d{2}[./]\d{2}[./]\d{2,4})",
    re.IGNORECASE,
)
FERTIG_BLOCK_RE = re.compile(
    r"fertigstellung(?:stermin|szeitpunkt)?\s*:?\s*(.{0,180})",
    re.IGNORECASE | re.DOTALL,
)
COMPLETION_RE = re.compile(
    r"(?:fertig\s*bis|inbetriebnahme|vertragsende)"
    r".{0,120}?(\d{2}[./]\d{2}[./]\d{2,4})",
    re.IGNORECASE | re.DOTALL,
)
AMOUNT = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)"
# Betrag hinter dem Schlagwort: „Geschätzter Gesamtwert: 1.250.000,00 EUR“.
VALUE_AFTER_RE = re.compile(
    r"(?:gesch(?:ä|ae)tzter\s+(?:gesamt)?wert|auftragswert|auftragsvolumen|gesamtwert|"
    r"verg(?:ü|ue)tung|honorar|kostensch(?:ä|ae)tzung|bauvolumen|"
    r"wert\s+ohne\s+(?:mwst|umsatzsteuer))"
    r"[^0-9]{0,60}?" + AMOUNT + r"\s*(?:€|eur\b|euro\b)",
    re.IGNORECASE | re.DOTALL,
)
# Betrag vor dem Schlagwort: „1.250.000 € geschätzter Auftragswert“.
VALUE_BEFORE_RE = re.compile(
    AMOUNT + r"\s*(?:€|eur\b|euro\b)[^0-9]{0,40}?"
    r"(?:gesch(?:ä|ae)tzter\s+(?:gesamt)?wert|auftragswert|auftragsvolumen|gesamtwert|"
    r"verg(?:ü|ue)tung|honorar|kostensch(?:ä|ae)tzung|bauvolumen)",
    re.IGNORECASE | re.DOTALL,
)


def parse_de_number(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        # Mehrere Punkte sind immer Tausenderzeichen: 1.100.000
        raw = raw.replace(".", "")
    elif raw.count(".") == 1 and len(raw.split(".")[1]) == 3:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _latest_date(text: str) -> str:
    dates = [parse_de_date(m.group(0)) for m in DATE_RE.finditer(text or "")]
    dates = [d for d in dates if d]
    return max(dates) if dates else ""


def extract_value_eur(text: str) -> float | None:
    """Auftragswert/Vergütung in Euro. Bei mehreren Angaben der größte Betrag."""
    blob = text or ""
    found: list[float] = []
    for pattern in (VALUE_AFTER_RE, VALUE_BEFORE_RE):
        for match in pattern.finditer(blob):
            amount = parse_de_number(match.group(1))
            if amount is not None and amount > 0:
                found.append(amount)
    return max(found) if found else None


@dataclass
class Facts:
    area_m2: float | None = None
    capacity_kwp: float | None = None
    completion_on: str = ""
    value_eur: float | None = None


def extract_facts(*parts: str) -> Facts:
    blob = " ".join(part for part in parts if part)
    facts = Facts()
    areas = [parse_de_number(m.group(1)) for m in AREA_RE.finditer(blob)]
    areas = [n for n in areas if n is not None]
    if areas:
        facts.area_m2 = max(areas)
    kwps = [parse_de_number(m.group(1)) for m in KWP_RE.finditer(blob)]
    kwps = [n for n in kwps if n is not None]
    if kwps:
        facts.capacity_kwp = max(kwps)
    facts.value_eur = extract_value_eur(blob)

    begin_end = BEGIN_END_RE.search(blob)
    fertig_leistung = FERTIG_LEISTUNG_RE.search(blob)
    laufzeit_end = LAUFZEIT_END_RE.search(blob)
    range_match = RANGE_RE.search(blob)
    fertig_block = FERTIG_BLOCK_RE.search(blob)
    if begin_end:
        facts.completion_on = parse_de_date(begin_end.group(2))
    elif fertig_leistung:
        facts.completion_on = parse_de_date(fertig_leistung.group(1))
    elif laufzeit_end:
        facts.completion_on = parse_de_date(laufzeit_end.group(1))
    elif range_match:
        facts.completion_on = parse_de_date(range_match.group(2))
    elif fertig_block:
        facts.completion_on = _latest_date(fertig_block.group(1))
    if not facts.completion_on:
        hit = COMPLETION_RE.search(blob)
        if hit:
            facts.completion_on = parse_de_date(hit.group(1))
    return facts


def apply_facts(notice) -> None:
    facts = extract_facts(notice.title, notice.city, notice.excerpt, notice.detail_text)
    if facts.area_m2 is not None:
        notice.area_m2 = facts.area_m2
    if facts.capacity_kwp is not None:
        notice.capacity_kwp = facts.capacity_kwp
    if facts.completion_on:
        notice.completion_on = facts.completion_on
    if facts.value_eur is not None and notice.value_eur is None:
        notice.value_eur = facts.value_eur


def _as_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def facts_from_row(row: dict) -> dict:
    extracted = extract_facts(row.get("title") or "", row.get("city") or "", row.get("excerpt") or "")
    return {
        "area_m2": _as_float(row.get("area_m2")) if row.get("area_m2") not in (None, "") else extracted.area_m2,
        "capacity_kwp": _as_float(row.get("capacity_kwp"))
        if row.get("capacity_kwp") not in (None, "")
        else extracted.capacity_kwp,
        "completion_on": (row.get("completion_on") or "") or extracted.completion_on,
        "value_eur": _as_float(row.get("value_eur"))
        if row.get("value_eur") not in (None, "")
        else extracted.value_eur,
    }


def format_eur(value) -> str:
    """1250000.0 -> '1.250.000 €'. Leere Werte ergeben ''."""
    amount = _as_float(value)
    if amount is None:
        return ""
    return f"{amount:,.0f}".replace(",", ".") + " €"
