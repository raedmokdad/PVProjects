from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

OPEN_CATEGORIES = {"InvitationToTender", "PriorInformation"}
START_RE = re.compile(r"[?&]Start=(\d+)")


def parse_search_table(html: str, portal: str, base: str, prefix: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.tableHorizontalHeader")
    if not table:
        return []
    host = urlparse(base).netloc
    notices: list[Notice] = []
    for row in table.select("tr.publicationDetail"):
        oid = (row.get("data-oid") or "").strip()
        category = (row.get("data-category") or "").strip()
        if not oid:
            continue
        if category and category not in OPEN_CATEGORIES:
            continue
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td", recursive=False)]
        if len(cells) < 2:
            continue
        title = cells[1]
        organisation = cells[2] if len(cells) > 2 else ""
        notice_type = cells[3] if len(cells) > 3 else category
        rule = cells[4] if len(cells) > 4 else ""
        deadline_raw = cells[5] if len(cells) > 5 else ""
        project_url = (
            f"{base}{prefix}/PublicationControllerServlet"
            f"?function=Detail&TOID={oid}&Category={category or 'InvitationToTender'}"
        )
        notices.append(
            Notice(
                portal=portal,
                pid=oid,
                title=title,
                published_on=parse_de_date(cells[0]),
                deadline=parse_de_date(deadline_raw),
                notice_type=notice_type,
                contracting_rule=rule,
                organisation=organisation,
                project_url=project_url,
                source_platform=host,
            )
        )
    return notices


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class NetServerPortal:
    """Healy Hudson / Vergabe@Net public search (Berlin, Hessen, Baden-Württemberg, …)."""

    name = "netserver"
    base = ""
    prefix = "/NetServer"
    delay_seconds = 1.2
    page_size = 50

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )

    @property
    def search_url(self) -> str:
        return f"{self.base}{self.prefix}/PublicationSearchControllerServlet"

    def list_for_date(self, iso_date: str, publication_types: list[str] | None = None) -> list[Notice]:
        del publication_types
        self.session.get(f"{self.base}{self.prefix}/", timeout=45)
        found: list[Notice] = []
        seen: set[str] = set()
        start = 0
        for _ in range(40):
            html = self._fetch_search(start)
            notices = parse_search_table(html, self.name, self.base, self.prefix)
            if not notices:
                break
            dates = [n.published_on for n in notices if n.published_on]
            for notice in notices:
                if notice.published_on == iso_date and notice.pid not in seen:
                    seen.add(notice.pid)
                    found.append(notice)
            if dates and any(d < iso_date for d in dates):
                break
            next_start = self._next_start(html, start)
            if next_start is None or next_start <= start:
                break
            start = next_start
            time.sleep(self.delay_seconds)
        return found

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url or (
            f"{self.base}{self.prefix}/PublicationControllerServlet"
            f"?function=Detail&TOID={notice.pid}&Category=InvitationToTender"
        )
        resp = self.session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
        notice.project_url = resp.url
        notice.detail_text = visible_text(resp.text)
        notice.excerpt = re.sub(r"\s+", " ", notice.detail_text).strip()[:800]
        notice.source_platform = urlparse(self.base).netloc
        from filter.facts import extract_facts

        facts = extract_facts(notice.title, notice.city, notice.detail_text)
        if facts.completion_on:
            notice.completion_on = facts.completion_on
        if facts.capacity_kwp is not None:
            notice.capacity_kwp = facts.capacity_kwp
        if facts.area_m2 is not None:
            notice.area_m2 = facts.area_m2
        return notice

    def _fetch_search(self, start: int) -> str:
        params = {
            "function": "Search",
            "Category": "",
            "TenderLaw": "All",
            "TenderKind": "All",
            "Order": "desc",
            "OrderBy": "Publishing",
            "Start": str(start),
            "Max": str(self.page_size),
        }
        resp = self.session.get(self.search_url, params=params, timeout=45)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _next_start(html: str, current: int) -> int | None:
        starts = [int(v) for v in START_RE.findall(html)]
        greater = [s for s in starts if s > current]
        if greater:
            return min(greater)
        return None


class BerlinPortal(NetServerPortal):
    name = "berlin"
    base = "https://vergabekooperation.berlin"


class HessenPortal(NetServerPortal):
    name = "hessen"
    base = "https://vergabe.hessen.de"
    page_size = 25


class LandbwPortal(NetServerPortal):
    name = "landbw"
    base = "https://vergabe.landbw.de"


class SachsenPortal(NetServerPortal):
    name = "sachsen"
    base = "https://evergabe.sachsen.de"


class BremenPortal(NetServerPortal):
    name = "bremen"
    base = "https://vergabe.bremen.de"
