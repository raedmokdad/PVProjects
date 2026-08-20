from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from portals.base import Notice

try:
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = datetime.now().astimezone().tzinfo

BASE = "https://oeffentlichevergabe.de"
SEARCH_URL = f"{BASE}/bkmk/searches"
NOTICE_URL = f"{BASE}/api/notices"


def notice_ui_url(notice_id: str, lot_id: str | None = None) -> str:
    """Working UI path is /ui/de/search/details?noticeId=…, not /search/notices/{id}."""
    if not notice_id:
        return BASE
    url = f"{BASE}/ui/de/search/details?noticeId={notice_id}"
    if lot_id:
        url += f"&lotId={lot_id}"
    return url

COMPETITION_TYPES = [
    "cn-standard",
    "cn-social",
    "cn-desg",
    "subco",
    "qu-sy",
    "pin-cfc-standard",
    "pin-cfc-social",
]

CPV_PREFIXES = ["0933", "45261215"]
# CONTAINS, nicht MATCH_ANY: „Photovoltaikanlage“ ist ein Wort und würde sonst fehlen.
# „BESS“ nur als Token (MATCH_ANY), sonst trifft CONTAINS „besser“.
CONTAINS_TERMS = [
    "Photovoltaik",
    "photovoltaic",
    "Solarmodul",
    "Batteriespeicher",
    "Stromspeicher",
    "PV-Anlage",
    "kWp",
]
TOKEN_TERMS = ["BESS"]


def code_value(item) -> str:
    if not item:
        return ""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("value") or "").strip()
    return str(item).strip()


def lang_text(items, prefer: str = "DEU") -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return items.strip()
    if isinstance(items, dict):
        return str(items.get("value") or "").strip()
    chosen = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        value = (item.get("value") or "").strip()
        if item.get("languageId") == prefer and value:
            return value
        if not chosen and value:
            chosen = value
    return chosen


def iso_day_bounds(day: date) -> tuple[str, str]:
    start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=TZ)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _to_iso_date(value: str) -> str:
    if not value:
        return ""
    return value[:10]


def union_by_notice_id(notices: list[Notice]) -> list[Notice]:
    by_id: dict[str, Notice] = {}
    for notice in notices:
        if notice.pid:
            by_id.setdefault(notice.pid, notice)
    return list(by_id.values())


class OeffentlichevergabePortal:
    name = "oeffentlichevergabe"
    delay_seconds = 1.2

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Wetenergy-Ausschreibungen/1.0 (PV/Speicher Recherche, intern)",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )

    def list_for_date(self, iso_date: str, publication_types: list[str] | None = None) -> list[Notice]:
        del publication_types
        day = date.fromisoformat(iso_date)
        start, end = iso_day_bounds(day)
        found: list[Notice] = []
        for extra in self._search_clauses():
            found.extend(self._search_all(start, end, extra))
            time.sleep(self.delay_seconds)
        return union_by_notice_id(
            [notice for notice in found if notice.published_on == iso_date]
        )

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        resp = self.session.get(
            f"{NOTICE_URL}/{notice.pid}",
            params={"format": "domain"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        notice.project_url = notice_ui_url(notice.pid)
        lots = data.get("lots") or []
        if lots:
            lot_id = lots[0].get("id")
            if lot_id:
                notice.project_url = notice_ui_url(notice.pid, str(lot_id))
        notice.source_platform = data.get("procurementPlatform") or notice.source_platform
        purpose = data.get("purpose") or {}
        title = lang_text(purpose.get("title")) or notice.title
        description = lang_text(purpose.get("description"))
        notice.title = title
        lot_bits: list[str] = []
        cpv_codes: list[str] = []
        deadline = notice.deadline
        for lot in lots:
            lot_purpose = lot.get("purpose") or {}
            lot_title = lang_text(lot_purpose.get("title"))
            lot_desc = lang_text(lot_purpose.get("description"))
            if lot_title:
                lot_bits.append(lot_title)
            if lot_desc:
                lot_bits.append(lot_desc)
            cpv_codes.extend(self._cpv_from_classification(lot.get("classification") or {}))
            terms = lot.get("submissionTerms") or {}
            deadline = deadline or _to_iso_date(
                terms.get("deadlineReceiptTenders") or terms.get("firstDeadline") or ""
            )
        cpv_codes.extend(self._cpv_from_classification(data.get("classification") or {}))
        notice.cpv = "; ".join(dict.fromkeys(c[:8] for c in cpv_codes if c))
        notice.organisation = self._buyer_name(data) or notice.organisation
        city, nuts = self._place(data)
        if not city or not nuts:
            lot_city, lot_nuts = self._place((data.get("lots") or [{}])[0] if data.get("lots") else {})
            city = city or lot_city
            nuts = nuts or lot_nuts
        notice.city = city or notice.city
        notice.nuts = nuts or notice.nuts
        notice.deadline = deadline
        notice.notice_type = code_value(data.get("noticeType")) or notice.notice_type
        notice.detail_text = "\n".join(part for part in [title, description, *lot_bits] if part)
        notice.excerpt = (description or notice.detail_text)[:800]
        ted = (data.get("tedPublication") or {}).get("publicationId")
        if ted:
            notice.contracting_rule = f"TED {ted}"
        elif not notice.contracting_rule:
            notice.contracting_rule = code_value(data.get("procedureLegalBasis"))
        from filter.facts import extract_facts

        facts = extract_facts(notice.title, notice.city, notice.detail_text)
        if facts.completion_on:
            notice.completion_on = facts.completion_on
        if facts.capacity_kwp is not None:
            notice.capacity_kwp = facts.capacity_kwp
        if facts.area_m2 is not None:
            notice.area_m2 = facts.area_m2
        return notice

    def _search_clauses(self) -> list[dict]:
        clauses = [
            {"fields": ["allCpvCodes"], "operator": "STARTS_WITH", "operands": CPV_PREFIXES},
        ]
        for term in CONTAINS_TERMS:
            clauses.append({"fields": ["allFreeText"], "operator": "CONTAINS", "operands": [term]})
        for term in TOKEN_TERMS:
            clauses.append({"fields": ["allFreeText"], "operator": "MATCH_ANY", "operands": [term]})
        return clauses

    def _base_where(self, start: str, end: str) -> list[dict]:
        return [
            {"fields": ["publicationDate"], "operator": ">=", "operands": [start]},
            {"fields": ["publicationDate"], "operator": "<", "operands": [end]},
            {"fields": ["noticeType"], "operator": "IN", "operands": COMPETITION_TYPES},
        ]

    def _search_all(self, start: str, end: str, extra: dict) -> list[Notice]:
        found: list[Notice] = []
        page = 0
        size = 50
        while True:
            payload = {
                "SELECT": "ALL",
                "FROM": "lots",
                "WHERE": [*self._base_where(start, end), extra],
                "PAGE": {"number": page, "size": size},
                "ORDER": {"field": "publicationDate", "direction": "DESC"},
            }
            resp = self.session.post(SEARCH_URL, json=payload, timeout=60)
            if resp.status_code >= 400:
                raise RuntimeError(f"Suche fehlgeschlagen ({resp.status_code}): {resp.text[:500]}")
            data = resp.json()
            elements = data.get("elements") or []
            total = int(data.get("totalElements") or 0)
            for item in elements:
                found.append(self._from_lot(item))
            if not elements or (page + 1) * size >= total:
                break
            page += 1
            time.sleep(self.delay_seconds)
        return found

    def _from_lot(self, item: dict) -> Notice:
        pid = str(item.get("noticeIdentifier") or "")
        published = _to_iso_date(item.get("publicationDate") or "")
        buyers = item.get("buyers") or []
        org = ""
        if buyers and isinstance(buyers[0], dict):
            org = (buyers[0].get("name") or "").strip()
        places = item.get("placesOfPerformance") or []
        nuts = ""
        city = ""
        if places and isinstance(places[0], dict):
            nuts = places[0].get("nutsCode") or ""
            city = places[0].get("city") or nuts
        return Notice(
            portal=self.name,
            pid=pid,
            title=lang_text(item.get("noticeTitle") or item.get("lotTitle")),
            published_on=published,
            deadline=_to_iso_date(item.get("firstDeadline") or item.get("deadlineReceiptTenders") or ""),
            notice_type=code_value(item.get("noticeType")),
            organisation=org,
            project_url=notice_ui_url(pid) if pid else BASE,
            city=city,
            cpv=code_value(item.get("mainCpvCode"))[:8],
            nuts=nuts,
        )

    @staticmethod
    def _cpv_from_classification(classification: dict) -> list[str]:
        codes: list[str] = []
        main = code_value(classification.get("mainClassificationCode"))
        if main:
            codes.append(main)
        extra = classification.get("additionalClassificationCode") or []
        if isinstance(extra, dict):
            extra = [extra]
        for item in extra:
            value = code_value(item)
            if value:
                codes.append(value)
        return codes

    @staticmethod
    def _buyer_name(data: dict) -> str:
        buyers = data.get("buyers") or []
        orgs = data.get("organisation") or {}
        ref = ""
        if buyers and isinstance(buyers[0], dict):
            ref = buyers[0].get("organisationReference") or ""
            name = buyers[0].get("name") or lang_text(buyers[0].get("officialName"))
            if name:
                return name
        if isinstance(orgs, dict) and ref:
            node = orgs.get(ref)
            if isinstance(node, dict):
                return lang_text(node.get("officialName") or node.get("name") or node.get("organisationName"))
        if isinstance(orgs, list):
            chosen = ""
            for node in orgs:
                if not isinstance(node, dict):
                    continue
                label = node.get("organisationName") or lang_text(node.get("officialName") or node.get("name"))
                if node.get("partyIdentification") == ref and label:
                    return label
                if not chosen and label:
                    chosen = label
            return chosen
        return ""

    @staticmethod
    def _place(data: dict) -> tuple[str, str]:
        places = data.get("placeOfPerformance") or data.get("placesOfPerformance") or []
        if isinstance(places, dict):
            places = [places]
        if not places:
            return "", ""
        first = places[0] if isinstance(places[0], dict) else {}
        nuts = (
            first.get("nutsCode")
            or first.get("nuts")
            or code_value(first.get("placePerformanceCountrySubdivision"))
        )
        city = (
            first.get("placePerformanceCity")
            or lang_text(first.get("city") or first.get("place"))
            or first.get("country")
            or nuts
        )
        return str(city or ""), str(nuts or "")
