from __future__ import annotations

import base64
import re
import time
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice
from portals.dates import USER_AGENT, parse_de_date

PID_RE = re.compile(r"tsaid_p040t00=(\d+)")
MAX_PAGES = 40


def pid_from_href(href: str) -> str:
    idp = (parse_qs(urlparse(href).query).get("idp") or [""])[0]
    if not idp:
        return ""
    padded = idp + "=" * ((4 - len(idp) % 4) % 4)
    try:
        decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return idp[:80]
    match = PID_RE.search(decoded)
    return match.group(1) if match else idp[:80]


def parse_search_table(html: str, portal: str, page_url: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc
    notices: list[Notice] = []
    for row in soup.select("#tsaid_ListeAusschreibungen_01 table tbody tr"):
        link = row.select_one("a[href*='idp=']")
        if not link:
            continue
        href = urljoin(page_url, link.get("href") or "")
        pid = pid_from_href(href)
        if not pid:
            continue
        title = link.get_text(" ", strip=True)
        city_el = row.select_one("td.tsaid_AREA")
        published_el = row.select_one("td.tsaid_RELEASEDATE")
        deadline_el = row.select_one("td.tsaid_DEADLINE")
        city = city_el.get_text(" ", strip=True) if city_el else ""
        published = parse_de_date(published_el.get_text(" ", strip=True) if published_el else "")
        deadline = parse_de_date(deadline_el.get_text(" ", strip=True) if deadline_el else "")
        notices.append(
            Notice(
                portal=portal,
                pid=pid,
                title=title,
                published_on=published,
                deadline=deadline,
                city=city,
                project_url=href,
                source_platform=host,
            )
        )
    return notices


def next_page_url(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    link = soup.select_one("a.tsaid_next[href]")
    if not link:
        return ""
    href = (link.get("href") or "").strip()
    if not href or href.startswith("#") or href.startswith("javascript:"):
        return ""
    return urljoin(page_url, href)


def form_payload(html: str) -> tuple[str, dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    form = soup.select_one("form[id*='SuchformularEVergabe']") or soup.select_one(
        "form[action*='recherche-aktueller-vergaben']"
    )
    if not form:
        return "", {}
    data: dict[str, str] = {}
    for el in form.find_all(["input", "select"]):
        name = el.get("name")
        if not name:
            continue
        if el.name == "select":
            selected = el.find("option", selected=True) or el.find("option")
            data[name] = (selected.get("value") if selected else "") or ""
        elif (el.get("type") or "").lower() in {"submit", "button", "image"}:
            continue
        else:
            data[name] = el.get("value") or ""
    action = form.get("action") or "/recherche-aktueller-vergaben"
    return action, data


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return unescape(soup.get_text("\n", strip=True))


class SachsenAnhaltPortal:
    """eVergabe-Portal Sachsen-Anhalt, öffentliche BUS-Suche ohne Login."""

    name = "sachsen_anhalt"
    base = "https://evergabe.sachsen-anhalt.de"
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
        home = self.session.get(self.base + "/", timeout=45)
        home.raise_for_status()
        action, payload = form_payload(home.text)
        if not payload:
            return []
        search_url = urljoin(self.base + "/", action)
        resp = self.session.post(search_url, data=payload, timeout=45)
        resp.raise_for_status()
        html, page_url = resp.text, resp.url
        found: list[Notice] = []
        seen: set[str] = set()
        for _ in range(MAX_PAGES):
            notices = parse_search_table(html, self.name, page_url)
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
            resp = self.session.get(nxt, timeout=45)
            resp.raise_for_status()
            html, page_url = resp.text, resp.url
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
        notice.source_platform = urlparse(self.base).netloc
        return notice
