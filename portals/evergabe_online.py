from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

PID_RE = re.compile(r"[?&]id=(\d+)")


def parse_search_rows(html: str, portal: str, page_url: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc
    notices: list[Notice] = []
    for row in soup.select("table tbody tr"):
        link = row.select_one("a[href*='tenderdetails']")
        if not link:
            continue
        href = urljoin(page_url, link.get("href") or "")
        pid = (parse_qs(urlparse(href).query).get("id") or [""])[0]
        if not pid:
            match = PID_RE.search(href)
            pid = match.group(1) if match else ""
        if not pid:
            continue
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        title = link.get_text(" ", strip=True)
        organisation = cells[2] if len(cells) > 2 else ""
        city = cells[3] if len(cells) > 3 else ""
        notice_type = cells[4] if len(cells) > 4 else ""
        deadline = parse_de_date(cells[5]) if len(cells) > 5 else ""
        published = parse_de_date(cells[6]) if len(cells) > 6 else ""
        notices.append(
            Notice(
                portal=portal,
                pid=str(pid),
                title=title,
                published_on=published,
                deadline=deadline,
                notice_type=notice_type,
                organisation=organisation,
                city=city,
                project_url=href.split("&")[0],
                source_platform=host,
            )
        )
    return notices


def next_page_url(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    link = soup.select_one("a.next[href], a[rel='next'][href]")
    if not link:
        return ""
    classes = " ".join(link.get("class") or [])
    if "disabled" in classes:
        return ""
    href = link.get("href") or ""
    if not href or href.startswith("#"):
        return ""
    return urljoin(page_url, href)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class EvergabeOnlinePortal:
    """e-Vergabe des Bundes, öffentliche Wicket-Suche (ohne Login)."""

    name = "evergabe_online"
    base = "https://www.evergabe-online.de"
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
        self.session.get(f"{self.base}/start.html?0&cookieCheck", timeout=45)
        resp = self._get(f"{self.base}/search.html", referer=f"{self.base}/start.html")
        if resp is None:
            return []
        html, page_url = resp.text, resp.url
        found: list[Notice] = []
        seen: set[str] = set()
        for _ in range(40):
            notices = parse_search_rows(html, self.name, page_url)
            if not notices:
                break
            dates = [n.published_on for n in notices if n.published_on]
            for notice in notices:
                if notice.published_on == iso_date and notice.pid not in seen:
                    seen.add(notice.pid)
                    found.append(notice)
            if dates and any(d < iso_date for d in dates):
                break
            nxt = next_page_url(html, page_url)
            if not nxt or nxt == page_url:
                break
            time.sleep(self.delay_seconds)
            resp = self._get(nxt, referer=page_url)
            if resp is None:
                break
            html, page_url = resp.text, resp.url
        return found

    def _get(self, url: str, referer: str = "") -> requests.Response | None:
        headers = {"Referer": referer} if referer else {}
        resp = self.session.get(url, timeout=45, headers=headers)
        if resp.status_code in (403, 404, 429):
            return None
        resp.raise_for_status()
        return resp

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url or f"{self.base}/tenderdetails.html?id={notice.pid}"
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
