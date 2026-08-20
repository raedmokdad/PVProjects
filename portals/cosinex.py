from __future__ import annotations

import re
import time
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from portals.base import Notice, SearchPage
from portals.dates import USER_AGENT

CPV_LINE_RE = re.compile(r"(\d{8}-\d)\s+(.+)")
DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")
PAGE_RE = re.compile(r"Seite:\s*(\d+)\s*von\s*(\d+)", re.I)
PID_RE = re.compile(r"[?&]pid=(\d+)")
AWARDED_MARKERS = ("ergebnis", "expost", "vergeben", "zuschlag", "auftrag erteilt")


def parse_de_date(value: str) -> str:
    """Return ISO date YYYY-MM-DD from DD.MM.YYYY, or empty."""
    if not value:
        return ""
    m = DATE_RE.search(value)
    if not m:
        return ""
    day, month, year = m.group(1).split(".")
    return f"{year}-{month}-{day}"


def is_awarded(notice_type: str) -> bool:
    text = (notice_type or "").lower()
    return any(marker in text for marker in AWARDED_MARKERS)


class CosinexPortal:
    """Shared session, token (JSON) and detail parsing for cosinex VMP."""

    name = "cosinex"
    base = ""
    prefix = "/VMPCenter"
    delay_seconds = 1.2

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )
        self._jwt = ""
        self._jwt_fetched_at = 0.0

    @property
    def welcome_url(self) -> str:
        return f"{self.base}{self.prefix}/company/welcome.do"

    @property
    def search_page_url(self) -> str:
        return f"{self.base}{self.prefix}/company/announcements/categoryOverview.do?method=show"

    @property
    def search_api_url(self) -> str:
        return f"{self.base}{self.prefix}/api/v2/project/search"

    @property
    def forward_url(self) -> str:
        return f"{self.base}{self.prefix}/public/company/projectForwarding.do"

    def fetch_detail(self, notice: Notice) -> Notice:
        time.sleep(self.delay_seconds)
        last_html = ""
        last_url = ""
        process_html = ""
        overview_url = ""
        for url in self._detail_urls(notice):
            resp = self.session.get(url, timeout=45, allow_redirects=True)
            if not resp.ok or self._is_auth_url(resp.url):
                continue
            last_html, last_url = resp.text, resp.url
            if self._is_auth_html(last_html):
                continue
            overview_html = last_html
            overview_url = last_url
            process_url = self._processdata_url(overview_url)
            process_html = overview_html
            if process_url and process_url.rstrip("/") != overview_url.rstrip("/"):
                time.sleep(self.delay_seconds)
                proc = self.session.get(process_url, timeout=45)
                if proc.ok and not self._is_auth_url(proc.url) and not self._is_auth_html(proc.text):
                    process_html = proc.text
                    notice.project_url = process_url
                else:
                    notice.project_url = overview_url
            else:
                notice.project_url = overview_url
            break
        if not process_html:
            if not notice.project_url or self._is_auth_url(notice.project_url):
                notice.project_url = self._click_url(notice)
            if last_html:
                process_html = last_html
            else:
                return notice

        text = self._visible_text(process_html)
        notice.detail_text = text
        notice.cpv = self._cpv_block(text)
        notice.city = self._field(text, ("Ort", "Haupterfüllungsort"))
        if not notice.organisation:
            notice.organisation = self._field(text, ("Offizielle Bezeichnung", "Auftraggeber"))
        notice.excerpt = self._excerpt(text)
        if not notice.deadline:
            notice.deadline = parse_de_date(
                self._field(text, ("Schlusstermin für den Eingang der Angebote", "Abgabefrist"))
            )
        from filter.facts import extract_facts

        facts = extract_facts(notice.title, notice.city, text)
        notice.completion_on = self._execution_end(text) or facts.completion_on
        if facts.capacity_kwp is not None:
            notice.capacity_kwp = facts.capacity_kwp
        if facts.area_m2 is not None:
            notice.area_m2 = facts.area_m2
        if not notice.project_url or self._is_auth_url(notice.project_url):
            notice.project_url = self._click_url(notice)
        notice.source_platform = urlparse(notice.project_url or self.base).netloc
        return notice

    def _from_search_item(self, item: dict) -> Notice:
        pid = str(item.get("projectId") or "")
        links = item.get("links") or {}
        href = links.get("ENTER_PROJECTROOM") or links.get("enterprojectroom") or ""
        if href and href.startswith("/"):
            href = urljoin(self.base, href)
        if self._is_auth_url(href):
            href = ""
        if not href and pid:
            href = self._click_url(Notice(portal=self.name, pid=pid, title="", published_on=""))
        pub = item.get("publishingDate") or ""
        deadline = item.get("relevantDate") or ""
        pub_type = BeautifulSoup(str(item.get("publicationType") or ""), "lxml").get_text(" ", strip=True)
        rule = BeautifulSoup(str(item.get("contractingRule") or ""), "lxml").get_text(" ", strip=True)
        return Notice(
            portal=self.name,
            pid=pid,
            title=unescape(item.get("title") or "").strip(),
            published_on=parse_de_date(pub),
            deadline=parse_de_date(deadline) if deadline and deadline.lower() != "nv" else "",
            notice_type=pub_type,
            contracting_rule=rule,
            organisation=unescape(item.get("organisationName") or "").strip(),
            project_url=href,
            source_platform=urlparse(self.base).netloc,
        )

    def _click_url(self, notice: Notice) -> str:
        from portals.click import notice_click_url

        return notice_click_url(self.name, notice.pid, "")

    def _detail_urls(self, notice: Notice) -> list[str]:
        urls: list[str] = []
        raw = notice.project_url or ""
        if raw and not self._is_auth_url(raw):
            urls.append(raw)
        if notice.pid:
            urls.append(f"{self.forward_url}?pid={notice.pid}")
            if self.prefix == "/Center":
                urls.append(f"{self.base}/Satellite/public/company/projectForwarding.do?pid={notice.pid}")
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    @staticmethod
    def _is_auth_url(url: str) -> bool:
        lower = (url or "").lower()
        return any(marker in lower for marker in ("openid-connect", "id.dtvp.de", "/auth?", "/login"))

    @staticmethod
    def _is_auth_html(html: str) -> bool:
        text = (html or "").lower()
        return "anmelden" in text and ("passwort" in text or "openid" in text) and len(text) < 8000

    @staticmethod
    def _processdata_url(current_url: str) -> str:
        if "/processdata/" in current_url:
            return current_url
        if "/overview" in current_url:
            return re.sub(r"/overview.*$", "/processdata/generic", current_url)
        if "/project/" in current_url and "/de/" in current_url:
            return re.sub(r"/de/.*$", "/de/processdata/generic", current_url)
        return current_url

    @staticmethod
    def _visible_text(html: str) -> str:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return unescape(soup.get_text("\n", strip=True))

    @staticmethod
    def _cpv_block(text: str) -> str:
        lines = []
        for match in CPV_LINE_RE.finditer(text):
            lines.append(f"{match.group(1)} {match.group(2).splitlines()[0].strip()}")
        seen: set[str] = set()
        out = []
        for line in lines:
            key = line[:10]
            if key not in seen:
                seen.add(key)
                out.append(line)
        return "; ".join(out[:12])

    @staticmethod
    def _field(text: str, labels: tuple[str, ...]) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            for label in labels:
                if line.rstrip(":") == label:
                    if i + 1 < len(lines):
                        nxt = lines[i + 1]
                        if len(nxt) < 200:
                            return nxt
        return ""

    @staticmethod
    def _execution_end(text: str) -> str:
        """Cosinex Verfahrensangaben: Beginn/Ende as consecutive labels."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for i, line in enumerate(lines):
            if line.rstrip(":") != "Ende":
                continue
            if i + 1 >= len(lines) or not DATE_RE.search(lines[i + 1]):
                continue
            nearby = lines[max(0, i - 8) : i]
            if any(ln.rstrip(":") in ("Beginn", "Beginn/Ende", "Laufzeit bzw. Dauer") for ln in nearby):
                return parse_de_date(lines[i + 1])
        return ""

    @staticmethod
    def _excerpt(text: str, limit: int = 800) -> str:
        markers = (
            "Art und Umfang der Leistung",
            "Umfang der Beschaffung",
            "Kurzbeschreibung",
            "Auftragsgegenstand",
        )
        start = -1
        for marker in markers:
            start = text.find(marker)
            if start >= 0:
                break
        chunk = text[start:] if start >= 0 else text
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) > limit:
            return chunk[: limit - 1].rstrip() + "…"
        return chunk


class CosinexJsonPortal(CosinexPortal):
    """evergabe.nrw / DTVP: erweiterte Suche über JSON-API."""

    search_texts: tuple[str, ...] = ()

    def _refresh_token(self) -> str:
        self.session.get(self.welcome_url, timeout=45)
        resp = self.session.get(self.search_page_url, timeout=45)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        el = soup.find("input", id="token")
        value = (el.get("value") if el else "") or ""
        if not value:
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            raise RuntimeError(
                f"Kein Such-Token auf {self.name} gefunden (HTTP {resp.status_code}, Titel: {title!r})."
            )
        self._jwt = value
        self._jwt_fetched_at = time.time()
        return self._jwt

    def _auth_token(self) -> str:
        if not self._jwt or time.time() - self._jwt_fetched_at > 480:
            return self._refresh_token()
        return self._jwt

    def search_page(
        self,
        page: int,
        publication_types: list[str] | None = None,
        search_text: str = "",
    ) -> SearchPage:
        types = publication_types or ["ExAnte", "Tender"]
        payload = {
            "cpvCodes": [],
            "contractingRules": ["VOL", "VOB", "VSVGV", "SEKTVO", "OTHER"],
            "publicationTypes": types,
            "location": {},
            "pageNumber": page,
            "searchText": search_text,
            "sort": {
                "order": [{"property": "PROJECT_PUBLICATION_DATE_LNG", "direction": "DESC"}]
            },
        }

        def _post(token: str) -> requests.Response:
            return self.session.post(
                self.search_api_url,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json; charset=utf-8",
                    "X-JWT": token,
                },
                timeout=45,
            )

        token = self._auth_token()
        resp = _post(token)
        if resp.status_code in (401, 403):
            token = self._refresh_token()
            resp = _post(token)
        resp.raise_for_status()
        data = resp.json()
        notices = [self._from_search_item(item) for item in data.get("projects") or []]
        return SearchPage(
            page=int(data.get("searchParameter", {}).get("page") or page),
            total_pages=int(data.get("allPages") or 1),
            total=int(data.get("countOfAllDataSets") or len(notices)),
            notices=notices,
        )

    def list_for_date(self, iso_date: str, publication_types: list[str] | None = None) -> list[Notice]:
        texts = self.search_texts or ("",)
        by_pid: dict[str, Notice] = {}
        for text in texts:
            for notice in self._list_newest_until(iso_date, publication_types, text):
                if notice.pid:
                    by_pid.setdefault(notice.pid, notice)
            time.sleep(self.delay_seconds)
        return list(by_pid.values())

    def _list_newest_until(
        self,
        iso_date: str,
        publication_types: list[str] | None,
        search_text: str,
    ) -> list[Notice]:
        found: list[Notice] = []
        page = 1
        while True:
            result = self.search_page(page, publication_types, search_text=search_text)
            if not result.notices:
                break
            dates = [n.published_on for n in result.notices if n.published_on]
            for notice in result.notices:
                if notice.published_on == iso_date and not is_awarded(notice.notice_type):
                    found.append(notice)
            reached_older = bool(dates) and any(d < iso_date for d in dates)
            if reached_older or page >= result.total_pages:
                break
            page += 1
            time.sleep(self.delay_seconds)
        return found


class CosinexHtmlPortal(CosinexPortal):
    """VMP-Satelliten ohne JSON-API: HTML-Tabelle, neueste zuerst."""

    def list_for_date(self, iso_date: str, publication_types: list[str] | None = None) -> list[Notice]:
        del publication_types
        found: list[Notice] = []
        page = 1
        total_pages = 1
        self.session.get(self.welcome_url, timeout=45)
        while page <= total_pages:
            html, total_pages = self._fetch_table_page(page)
            notices = parse_html_table(html, portal=self.name, base=self.base, prefix=self.prefix)
            if not notices:
                break
            dates = [n.published_on for n in notices if n.published_on]
            for notice in notices:
                if notice.published_on == iso_date and not is_awarded(notice.notice_type):
                    found.append(notice)
            reached_older = bool(dates) and any(d < iso_date for d in dates)
            if reached_older or page >= total_pages:
                break
            page += 1
            time.sleep(self.delay_seconds)
        return found

    def _fetch_table_page(self, page: int) -> tuple[str, int]:
        if page <= 1:
            url = self.welcome_url
        else:
            url = (
                f"{self.welcome_url}?method=showTable&fromSearch=1"
                f"&selectedTablePagePROJECT_RESULT={page}"
            )
        resp = self.session.get(url, timeout=45)
        resp.raise_for_status()
        match = PAGE_RE.search(BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True))
        total = int(match.group(2)) if match else page
        return resp.text, total


def parse_html_table(html: str, portal: str, base: str, prefix: str) -> list[Notice]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.csx-new-table")
    if not table:
        return []
    notices: list[Notice] = []
    host = urlparse(base).netloc
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 5:
            continue
        link = row.find("a", href=PID_RE)
        href = link.get("href") if link else ""
        pid = ""
        if href:
            pid = (parse_qs(urlparse(href).query).get("pid") or [""])[0]
            if href.startswith("/"):
                href = urljoin(base, href)
        if not pid:
            continue
        notices.append(
            Notice(
                portal=portal,
                pid=str(pid),
                title=cells[2],
                published_on=parse_de_date(cells[0]),
                deadline=parse_de_date(cells[1]) if cells[1].lower() != "nv" else "",
                notice_type=cells[3],
                organisation=cells[4],
                project_url=href or f"{base}{prefix}/public/company/projectForwarding.do?pid={pid}",
                source_platform=host,
            )
        )
    return notices
