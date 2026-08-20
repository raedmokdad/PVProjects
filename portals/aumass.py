from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

SEARCH_TEXTS = (
    "Photovoltaik",
    "PV-Anlage",
    "Batteriespeicher",
    "Stromspeicher",
    "Solarmodul",
    "kWp",
)
PV_TRADE = "4.17"


def _label_value(block, label: str) -> str:
    for row in block.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        if cells[0].get_text(" ", strip=True).rstrip(":") == label:
            return cells[1].get_text(" ", strip=True)
    return ""


def parse_grid(html: str, portal: str, base: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base).netloc
    notices: list[Notice] = []
    for header in soup.select("tr.publication-header"):
        pid = (header.get("data-aumassid") or "").strip()
        title_cell = header.find("td", class_="showDetailsButton")
        title = title_cell.get_text(" ", strip=True) if title_cell else ""
        link = header.find("a", href=True)
        href = urljoin(base, link.get("href")) if link else ""
        info = header.find_next_sibling("tr", class_="publication-info")
        extra = header.find_next_sibling("tr", class_="ondemand-row")
        city = ""
        nuts = ""
        deadline = ""
        notice_type = ""
        cpv = ""
        excerpt = ""
        published = ""
        if info:
            loc = info.select_one("span[title='Ausführungsort']")
            nuts_el = info.select_one("span[title='NUTS-CODE']")
            city = loc.get_text(" ", strip=True) if loc else ""
            nuts = nuts_el.get_text(" ", strip=True) if nuts_el else ""
            info_text = info.get_text(" ", strip=True)
            deadline = parse_de_date(info_text)
            type_el = info.select_one("td.a-l span[title]")
            if type_el and "Verfahren" in info_text:
                notice_type = (type_el.get("title") or type_el.get_text(" ", strip=True)).strip()
            if not notice_type:
                match = re.search(r"Verfahren:\s*(\S+)", info_text)
                notice_type = match.group(1) if match else ""
        if extra:
            published = parse_de_date(_label_value(extra, "Veröffentlichungsdatum"))
            excerpt = _label_value(extra, "Beschreibung")
            cpv = _label_value(extra, "CPV-Codes")
        if not pid:
            continue
        notices.append(
            Notice(
                portal=portal,
                pid=pid,
                title=title,
                published_on=published,
                deadline=deadline,
                notice_type=notice_type,
                city=city,
                nuts=nuts,
                cpv=cpv,
                excerpt=excerpt,
                project_url=href or f"{base}/Veroeffentlichung/{pid.lower()}",
                source_platform=host,
            )
        )
    return notices


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class AumassPortal:
    """aumass-Plattform (viele bayerische Kommunen), öffentliche Ausschreibungssuche."""

    name = "aumass"
    base = "https://plattform.aumass.de"
    delay_seconds = 1.2
    search_texts = SEARCH_TEXTS

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
        self.session.get(f"{self.base}/Tender/Search/0", timeout=45)
        queries: list[tuple[str, str]] = [("", PV_TRADE)]
        queries.extend((text, "") for text in self.search_texts)
        for text, trade in queries:
            for notice in self._search(text, trade=trade):
                if notice.published_on == iso_date and notice.pid:
                    by_pid.setdefault(notice.pid, notice)
            time.sleep(self.delay_seconds)
        return list(by_pid.values())

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url or f"{self.base}/Veroeffentlichung/{notice.pid.lower()}"
        resp = self.session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
        notice.project_url = resp.url
        notice.detail_text = visible_text(resp.text)
        if not notice.excerpt:
            notice.excerpt = re.sub(r"\s+", " ", notice.detail_text).strip()[:800]
        notice.source_platform = urlparse(self.base).netloc
        return notice

    def _search(self, search_text: str, trade: str = "") -> list[Notice]:
        found: list[Notice] = []
        seen: set[str] = set()
        for page in range(1, 21):
            payload = {
                "Id": 0,
                "GId": "",
                "Sort": "",
                "SortDir": "asc",
                "Page": page,
                "Rows": 60,
                "Filters": [
                    {"Code": "SearchKey", "Value": search_text},
                    {"Code": "Trade", "Value": trade},
                    {"Code": "IsAwarded", "Value": "0"},
                ],
            }
            resp = self.session.post(
                f"{self.base}/Home/TenderSearch",
                json=payload,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": f"{self.base}/Tender/Search/0",
                },
                timeout=45,
            )
            resp.raise_for_status()
            notices = parse_grid(resp.text, self.name, self.base)
            if not notices:
                break
            new = 0
            for notice in notices:
                if notice.pid and notice.pid not in seen:
                    seen.add(notice.pid)
                    found.append(notice)
                    new += 1
            if new == 0 or len(notices) < 60:
                break
            time.sleep(self.delay_seconds)
        return found
