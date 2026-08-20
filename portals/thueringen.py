from __future__ import annotations

import re
import time
from datetime import date, datetime
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

PORTLET = "de_thueringen_tlrz_liferay_evergabe_EVergabePortlet"
MAX_PAGES = 30
EO_ID_RE = re.compile(r"[?&]id=(\d+)")


def select_time_filter(iso_date: str, today: date | None = None) -> str:
    current = today or datetime.now().astimezone().date()
    target = date.fromisoformat(iso_date)
    delta = (current - target).days
    if delta <= 0:
        return "today"
    if delta <= 7:
        return "lastSeven"
    if delta <= 30:
        return "lastThirty"
    return "all"


def pid_from_href(href: str) -> str:
    match = EO_ID_RE.search(href)
    if match:
        return match.group(1)
    query_id = (parse_qs(urlparse(href).query).get("id") or [""])[0]
    if query_id:
        return query_id
    path = urlparse(href).path.rstrip("/").split("/")[-1]
    return path or href[-40:]


def parse_search_rows(html: str, portal: str, page_url: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc
    container = soup.select_one("[id$='SearchContainerSearchContainer']") or soup
    notices: list[Notice] = []
    for row in container.select("table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        link = row.find("a", href=True)
        if not link:
            continue
        href = urljoin(page_url, link.get("href") or "")
        if "p_p_id=" in href and "tenderdetails" not in href:
            continue
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        pid = pid_from_href(href)
        if not pid:
            continue
        published = parse_de_date(cells[0].get_text(" ", strip=True))
        contracting_rule = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
        deadline = parse_de_date(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""
        notice_type = cells[4].get_text(" ", strip=True) if len(cells) > 4 else ""
        city = cells[5].get_text(" ", strip=True) if len(cells) > 5 else ""
        notices.append(
            Notice(
                portal=portal,
                pid=str(pid),
                title=title,
                published_on=published,
                deadline=deadline,
                notice_type=notice_type,
                contracting_rule=contracting_rule,
                city=city,
                project_url=href.split("&")[0] if "tenderdetails" in href else href,
                source_platform=host,
            )
        )
    return notices


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class ThueringenPortal:
    """Öffentliche Liferay-Liste der Thüringer Ausschreibungen."""

    name = "thueringen"
    base = "https://verwaltung.thueringen.de/evergabe"
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
        time_filter = select_time_filter(iso_date)
        found: list[Notice] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            params = {
                "p_p_id": PORTLET,
                "p_p_lifecycle": "0",
                "p_p_state": "normal",
                "p_p_mode": "view",
                f"_{PORTLET}_selectTime": time_filter,
                f"_{PORTLET}_selectContractingConditions": "all",
                f"_{PORTLET}_delta": "20",
                f"_{PORTLET}_orderByCol": "release",
                f"_{PORTLET}_orderByType": "desc",
                f"_{PORTLET}_cur": str(page),
            }
            resp = self.session.get(self.base, params=params, timeout=45)
            resp.raise_for_status()
            notices = parse_search_rows(resp.text, self.name, resp.url)
            if not notices:
                break
            for notice in notices:
                if notice.published_on == iso_date and notice.pid not in seen:
                    seen.add(notice.pid)
                    found.append(notice)
            if page < MAX_PAGES:
                time.sleep(self.delay_seconds)
        return found

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        url = notice.project_url
        if not url:
            return notice
        resp = self.session.get(url, timeout=45, allow_redirects=True)
        resp.raise_for_status()
        notice.project_url = resp.url
        notice.detail_text = visible_text(resp.text)
        if not notice.excerpt:
            notice.excerpt = re.sub(r"\s+", " ", notice.detail_text).strip()[:800]
        notice.source_platform = urlparse(resp.url).netloc
        return notice
