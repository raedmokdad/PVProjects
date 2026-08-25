from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "filter.yaml"

CPV_RE = re.compile(r"\b(\d{8})(?:-\d)?\b")
WORD_PV_RE = re.compile(r"(?<!\w)pv(?!\w)", re.IGNORECASE)
BESS_RE = re.compile(r"(?<!\w)bess(?!\w)", re.IGNORECASE)
MIT_STORAGE_RE = re.compile(
    r"(?:mit|inkl(?:usive|\.)?|einschlie(?:ß|ss)lich|plus|und)\s+"
    r"(?:einem\s+|eines\s+|einer\s+)?"
    r"(?:batterie-?|strom-?|solar-?|lithium-?)?speicher\b",
    re.IGNORECASE,
)
STORAGE_FALSE = (
    "speichersee",
    "speicherbecken",
    "speicherstadt",
    "wärmespeicher",
    "waermespeicher",
    "wasserspeicher",
    "aktenspeicher",
)


def load_filter_config(path: Path | None = None) -> dict:
    with (path or DEFAULT_CONFIG).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _normalize(text: str) -> str:
    return (text or "").replace("\u00a0", " ").lower()


def _cpv_codes(text: str) -> list[str]:
    return CPV_RE.findall(text or "")


def _prefix_hit(codes: list[str], prefixes: list[str]) -> str | None:
    """Match CPV codes. xxxx0000 = class (4 digits). Other codes match 6+ digits, not siblings."""
    for code in codes:
        for prefix in prefixes:
            p = re.sub(r"\D", "", prefix)[:8].ljust(8, "0")
            if p.endswith("0000"):
                stem = p[:4]
            elif p.endswith("00"):
                stem = p[:6]
            else:
                stem = p
            if code.startswith(stem):
                return code
    return None


def _keyword_hit(text: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        if kw.lower() in text:
            return kw
    return None


PLANNING_KEYWORDS = (
    "planungsleistung",
    "objektplanung",
    "fachplanung",
    "generalplaner",
    "generalplanung",
    "tragwerksplanung",
    "elektroplanung",
    "vorplanung",
    "entwurfsplanung",
    "genehmigungsplanung",
    "ausführungsplanung",
    "ausfuehrungsplanung",
    "ingenieurleistung",
    "ingenieurdienstleistung",
    "planungsbüro",
    "planungsbuero",
    "hoai",
    "machbarkeitsstudie",
    "konzeptstudie",
    "potenzialanalyse",
    "potentialanalyse",
)
# CPV 71 = Architektur-, Bau-, Ingenieur- und Inspektionsdienstleistungen.
PLANNING_CPV_RE = re.compile(r"\b71\d{6}\b")


def is_planning(title: str, detail_text: str, cpv_field: str = "") -> bool:
    """Erkennt Planungs- und Ingenieurleistungen statt Bau- oder Lieferleistungen."""
    blob = _normalize(" ".join(part for part in (title, detail_text) if part))
    if any(kw in blob for kw in PLANNING_KEYWORDS):
        return True
    codes = _cpv_codes(title) + _cpv_codes(detail_text) + _cpv_codes(cpv_field)
    return any(PLANNING_CPV_RE.fullmatch(code) for code in codes)


def classify(title: str, detail_text: str, cpv_field: str = "", config: dict | None = None) -> tuple[str, str]:
    """Return (category, reason). Category is PV, Speicher, PV+Speicher or empty."""
    cfg = config or load_filter_config()
    blob = _normalize(" ".join(part for part in (title, detail_text, cpv_field) if part))
    codes = _cpv_codes(title) + _cpv_codes(detail_text) + _cpv_codes(cpv_field)

    pv_reasons: list[str] = []
    st_reasons: list[str] = []

    hit = _prefix_hit(codes, cfg["pv"]["cpv_prefixes"])
    if hit:
        pv_reasons.append(f"CPV {hit}")
    hit = _keyword_hit(blob, cfg["pv"]["keywords"])
    if hit:
        pv_reasons.append(f"Stichwort „{hit}“")
    if WORD_PV_RE.search(blob) and not any("Stichwort" in r and "pv" in r.lower() for r in pv_reasons):
        pv_reasons.append("Stichwort „PV“")

    only_thermal = any(x in blob for x in cfg.get("exclude_if_only", []))
    if not pv_reasons:
        for kw in cfg.get("pv_ambiguous", []):
            if kw.lower() in blob and not only_thermal:
                pv_reasons.append(f"Stichwort „{kw}“")
                break

    hit = _prefix_hit(codes, cfg["storage"]["cpv_prefixes"])
    if hit:
        st_reasons.append(f"CPV {hit}")
    hit = _keyword_hit(blob, cfg["storage"]["keywords"])
    if hit:
        st_reasons.append(f"Stichwort „{hit}“")
    if BESS_RE.search(blob):
        st_reasons.append("Stichwort „BESS“")
    if pv_reasons and MIT_STORAGE_RE.search(blob) and not any(x in blob for x in STORAGE_FALSE):
        if not any("speicher" in r.lower() or "bess" in r.lower() for r in st_reasons):
            st_reasons.append("Stichwort „Speicher“")

    if pv_reasons and st_reasons:
        return "PV+Speicher", "; ".join(pv_reasons + st_reasons)
    if pv_reasons:
        return "PV", "; ".join(pv_reasons)
    if st_reasons:
        return "Speicher", "; ".join(st_reasons)
    return "", ""
