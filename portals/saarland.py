from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date


def parse_table(html: str, portal: str, page_url: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc
    table = soup.select_one("table.textualData")
    if not table:
        return []
    notices: list[Notice] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        link = cells[2].find("a", href=True)
        title = (link.get_text(" ", strip=True) if link else cells[2].get_text(" ", strip=True))
        href = urljoin(page_url, link.get("href") or "") if link else page_url
        pid = cells[5].get_text(" ", strip=True)
        if not pid or not title:
            continue
        notices.append(
            Notice(
                portal=portal,
                pid=pid,
                title=title,
                published_on=parse_de_date(cells[0].get_text(" ", strip=True)),
                deadline=parse_de_date(cells[1].get_text(" ", strip=True)),
                city=cells[3].get_text(" ", strip=True),
                notice_type=cells[4].get_text(" ", strip=True),
                project_url=href,
                source_platform=host,
            )
        )
    return notices


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class SaarlandPortal:
    """Öffentliche CMS-Liste neuer Ausschreibungen des Saarlands."""

    name = "saarland"
    base = "https://www.saarland.de/mibs/DE/portale/ausschreibungen/aktuelles/neue-veroeffentlichungen"
    delay_seconds = 1.2

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
        resp = self.session.get(self.base, timeout=45)
        resp.raise_for_status()
        return [
            notice
            for notice in parse_table(resp.text, self.name, resp.url)
            if notice.published_on == iso_date
        ]

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url or self.base
        resp = self.session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
        notice.project_url = resp.url
        notice.detail_text = visible_text(resp.text)
        if not notice.excerpt:
            notice.excerpt = re.sub(r"\s+", " ", notice.detail_text).strip()[:800]
        notice.source_platform = urlparse(resp.url).netloc
        return notice
