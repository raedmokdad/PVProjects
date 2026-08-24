from __future__ import annotations

import re
import time
from datetime import datetime
from html import unescape
from urllib.parse import quote, urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

try:
    TZ = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover — Fallback ohne tzdata
    TZ = datetime.now().astimezone().tzinfo

DEADLINE_RE = re.compile(r"Angebot abzugeben bis\s*(\d{2}\.\d{2}\.\d{4})")
BAUZEIT_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})")


def _berlin_date(iso_utc: str) -> str:
    """'2026-08-21T08:43:55.000Z' -> lokales Datum 'YYYY-MM-DD' (Europe/Berlin)."""
    value = (iso_utc or "").strip()
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return dt.astimezone(TZ).date().isoformat()


class CosunoPortal:
    """Öffentlicher Cosuno-Marktplatz für privat-gewerbliche Bauausschreibungen.

    Ohne Login abrufbar unter /de/marketplace?query=…&sortBy=publishDate.
    """

    name = "cosuno"
    base = "https://www.cosuno.com"
    delay_seconds = 1.0
    max_pages = 5
    # Cosuno-Volltextsuche wie im Beispiel /de/marketplace?query=PV&sortBy=publishDate.
    # "PV" findet dort auch "Photovoltaik"; Speicher-Begriffe separat.
    search_texts = (
        "PV",
        "Batteriespeicher",
        "Stromspeicher",
        "Solarmodul",
        "kWp",
    )

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )

    def list_for_date(self, iso_date: str, publication_types: list[str] | None = None) -> list[Notice]:
        del publication_types
        by_pid: dict[str, Notice] = {}
        for query in self.search_texts:
            for notice in self._list_query(query, iso_date):
                if notice.pid:
                    by_pid.setdefault(notice.pid, notice)
            time.sleep(self.delay_seconds)
        return list(by_pid.values())

    def _list_query(self, query: str, iso_date: str) -> list[Notice]:
        found: list[Notice] = []
        page = 1
        while page <= self.max_pages:
            url = (
                f"{self.base}/de/marketplace?query={quote(query)}"
                f"&sortBy=publishDate&page={page}"
            )
            resp = self.session.get(url, timeout=45)
            resp.raise_for_status()
            cards = self._parse_cards(resp.text)
            if not cards:
                break
            dates = [c.published_on for c in cards if c.published_on]
            for card in cards:
                if card.published_on == iso_date:
                    found.append(card)
            if dates and min(dates) < iso_date:
                break
            page += 1
            time.sleep(self.delay_seconds)
        return found

    def _parse_cards(self, html: str) -> list[Notice]:
        soup = BeautifulSoup(html, "lxml")
        notices: list[Notice] = []
        for article in soup.select("article[data-cy-bid-package-summary]"):
            pid = (article.get("data-cy-bid-package-summary") or "").strip()
            link = article.select_one("a[data-cy-bid-package-summary-title]")
            if not pid or not link:
                continue
            gewerk = link.get_text(" ", strip=True)
            href = link.get("href") or ""
            project_url = urljoin(self.base, href) if href else self.base
            project = ""
            wrapper = link.find_parent("div")
            sibling = wrapper.find_next_sibling("div") if wrapper else None
            if sibling:
                project = sibling.get_text(" ", strip=True)
            title = " – ".join(part for part in (gewerk, project) if part)
            time_el = article.find("time")
            raw_dt = ""
            if time_el:
                raw_dt = time_el.get("datetime") or time_el.get("dateTime") or ""
            published_on = _berlin_date(raw_dt)
            card_text = article.get_text(" ", strip=True)
            deadline_m = DEADLINE_RE.search(card_text)
            notices.append(
                Notice(
                    portal=self.name,
                    pid=pid,
                    title=title or gewerk or project,
                    published_on=published_on,
                    deadline=parse_de_date(deadline_m.group(1)) if deadline_m else "",
                    notice_type=self._phase(article),
                    city=self._location(article),
                    project_url=project_url,
                    source_platform=urlparse(self.base).netloc,
                )
            )
        return notices

    @staticmethod
    def _phase(article) -> str:
        icon = article.select_one('svg[data-cy-icon="project-1"]')
        holder = icon.find_parent("div") if icon else None
        return holder.get_text(" ", strip=True) if holder else ""

    @staticmethod
    def _location(article) -> str:
        icon = article.select_one('svg[data-cy-icon="location"]')
        holder = icon.find_parent("div") if icon else None
        return holder.get_text(" ", strip=True) if holder else ""

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url or self.base
        resp = self.session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
        notice.project_url = resp.url
        notice.source_platform = urlparse(resp.url).netloc or notice.source_platform
        text = self._visible_text(resp.text)
        notice.detail_text = text

        if not notice.deadline:
            m = DEADLINE_RE.search(text)
            if m:
                notice.deadline = parse_de_date(m.group(1))
        org = self._field_after(text, "Ausschreibendes Unternehmen")
        if org:
            notice.organisation = org
        notice.excerpt = self._excerpt(text)
        completion = self._completion(text)
        if completion:
            notice.completion_on = completion

        from filter.facts import extract_facts

        facts = extract_facts(notice.title, notice.city, text)
        if not notice.completion_on and facts.completion_on:
            notice.completion_on = facts.completion_on
        if facts.capacity_kwp is not None:
            notice.capacity_kwp = facts.capacity_kwp
        if facts.area_m2 is not None:
            notice.area_m2 = facts.area_m2
        return notice

    @staticmethod
    def _visible_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return unescape(soup.get_text("\n", strip=True))

    @staticmethod
    def _field_after(text: str, label: str) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            if line == label and i + 1 < len(lines):
                nxt = lines[i + 1]
                if 0 < len(nxt) < 160:
                    return nxt
        return ""

    @staticmethod
    def _completion(text: str) -> str:
        idx = text.find("Bauzeit")
        chunk = text[idx : idx + 120] if idx >= 0 else ""
        m = BAUZEIT_RE.search(chunk)
        return parse_de_date(m.group(2)) if m else ""

    @staticmethod
    def _excerpt(text: str, limit: int = 800) -> str:
        start = text.find("Projektbeschreibung")
        if start >= 0:
            start += len("Projektbeschreibung")
        chunk = text[start:] if start >= 0 else text
        for marker in ("Weitere Informationen", "benutzt zur einfachen", "Leistungsverzeichnis"):
            cut = chunk.find(marker)
            if cut > 0:
                chunk = chunk[:cut]
                break
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) > limit:
            return chunk[: limit - 1].rstrip() + "…"
        return chunk
