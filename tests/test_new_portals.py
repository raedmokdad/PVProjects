from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datetime import date

from portals.aumass import parse_grid
from portals.dates import parse_de_date
from portals.evergabe_online import next_page_url, parse_search_rows
from portals.netserver import parse_search_table
from portals.saarland import parse_table as parse_saarland
from portals.sachsen_anhalt import next_page_url as st_next, parse_search_table as parse_st, pid_from_href
from portals.thueringen import parse_search_rows as parse_th, select_time_filter


BERLIN = """
<table class="table tableHorizontalHeader">
<tr class="tableRow clickable-row publicationDetail" data-oid="54321-NetTender-abc" data-category="InvitationToTender">
  <td>18.08.2026</td>
  <td class="tender">PV-Anlage Schule</td>
  <td class="tenderAuthority">Stadt Berlin</td>
  <td class="tenderType">Offenes Verfahren</td>
  <td class="tenderType">VOB</td>
  <td class="tenderDeadline">28.09.2026 10:00</td>
</tr>
<tr class="tableRow clickable-row publicationDetail" data-oid="54321-NetTender-old" data-category="ContractAward">
  <td>18.08.2026</td>
  <td class="tender">Zuschlag Kanal</td>
  <td class="tenderAuthority">Berliner Wasserbetriebe</td>
  <td class="tenderType">Vergebener Auftrag</td>
  <td class="tenderType">VOB</td>
  <td></td>
</tr>
</table>
"""

EO = """
<table>
<tbody>
<tr class="even">
  <td class="ev-result-col"><a class="text-wrap" href="./tenderdetails.html?id=884040">PV-Anlage Bund</a></td>
  <td class="ev-result-col"><div>GZ-1</div></td>
  <td class="ev-result-col"><div>Bundesanstalt</div></td>
  <td class="ev-result-col"><div>10115 Berlin</div></td>
  <td class="ev-result-col"><div>National Öffentliche Ausschreibung</div></td>
  <td class="result_col_deadline"><div>29.09.26, 06:00</div></td>
  <td class="result_col_releaseDate"><div>18.08.26</div></td>
</tr>
</tbody>
</table>
<a rel="next" class="next icon" href="./search.html?page=2">nächste</a>
"""

AUMASS = """
<table>
<tr class="publication-header" data-aumassid="AV284B35">
  <td>AV284B35</td>
  <td class="showDetailsButton">PV-Anlage Turnhalle</td>
  <td><a href="/Veroeffentlichung/av284b35">Details</a></td>
</tr>
<tr class="publication-info">
  <td></td>
  <td>
    <span title="Ausführungsort">80331 München</span>
    <span title="NUTS-CODE">DE212</span>
    Angebotsfrist: 02.10.2026 10:00
    <span title="Öffentliche Ausschreibung">Verfahren: NÖ</span>
  </td>
</tr>
<tr class="ondemand-row">
  <td></td>
  <td>
    <table>
      <tr><td class="a-r">Veröffentlichungsdatum</td><td class="a-l">18.08.2026</td></tr>
      <tr><td class="a-r">Beschreibung</td><td class="a-l">Dach-PV 50 kWp</td></tr>
      <tr><td class="a-r">CPV-Codes</td><td class="a-l">09331200-0</td></tr>
    </table>
  </td>
</tr>
</table>
"""


class DateTests(unittest.TestCase):
    def test_four_digit_year(self):
        self.assertEqual(parse_de_date("18.08.2026 10:00"), "2026-08-18")

    def test_two_digit_year(self):
        self.assertEqual(parse_de_date("18.08.26"), "2026-08-18")


class NetServerParseTests(unittest.TestCase):
    def test_skips_awards_and_builds_detail_url(self):
        notices = parse_search_table(
            BERLIN,
            portal="berlin",
            base="https://vergabekooperation.berlin",
            prefix="/NetServer",
        )
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "54321-NetTender-abc")
        self.assertEqual(notices[0].title, "PV-Anlage Schule")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertIn("TOID=54321-NetTender-abc", notices[0].project_url)
        self.assertIn("function=Detail", notices[0].project_url)


class EvergabeOnlineParseTests(unittest.TestCase):
    def test_rows_and_next_link(self):
        notices = parse_search_rows(EO, "evergabe_online", "https://www.evergabe-online.de/search.html")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "884040")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertTrue(notices[0].project_url.endswith("tenderdetails.html?id=884040"))
        nxt = next_page_url(EO, "https://www.evergabe-online.de/search.html")
        self.assertTrue(nxt.endswith("search.html?page=2"))


ST = """
<div id="tsaid_ListeAusschreibungen_01">
  <table>
    <tbody>
      <tr class="tsaid_odd">
        <td class="tsaid_TOPIC">
          <a href="/recherche-aktueller-vergaben?idp=LzIxNTA4NTQwNT90c2FpZF9wMDQwdDAwPTExNTMwMTMxOSZ0c2FpZF9jPTAyJnRzYWlkX3M9MDQmdHNhaWRfcDAxMHMwNj0mQ0hBUlNFVD0mdHNhaWRfcDAxMHMwMD0mdHNhaWRfcDAxMHMwMT0mdHNhaWRfcWlkPTIxNTA4NTQwNSZ0c2FpZF9wMDEwczA0PSZ0c2FpZF9wMDEwczAzPQ==">PV-Anlage Halle</a>
        </td>
        <td class="tsaid_AREA">06108 Halle (Saale)</td>
        <td class="tsaid_RELEASEDATE">18.08.2026 07:39</td>
        <td class="tsaid_DEADLINE">03.09.2026 12:00</td>
      </tr>
    </tbody>
  </table>
  <a href="/recherche-aktueller-vergaben?idp=nextpage" class="tsaid_next">></a>
</div>
"""

TH = """
<div id="_de_thueringen_tlrz_liferay_evergabe_EVergabePortlet_eVergabeModelsSearchContainer">
  <table>
    <tbody>
      <tr>
        <td class="table-cell first">18.08.2026</td>
        <td class="table-cell"><a href="https://www.evergabe-online.de/tenderdetails.html?id=883924">PV-Anlage Erfurt</a></td>
        <td class="table-cell">UVgO</td>
        <td class="table-cell">09.09.2026 Angebotsfrist</td>
        <td class="table-cell">Lieferauftrag</td>
        <td class="table-cell last">99094 Erfurt</td>
      </tr>
    </tbody>
  </table>
</div>
"""

SL = """
<table class="textualData links">
  <thead><tr><th>Datum</th><th>Frist</th><th>Titel</th><th>Ort</th><th>Art</th><th>Nr</th></tr></thead>
  <tbody>
    <tr>
      <td>14.08.2026</td>
      <td>05.10.2026 10:00 Uhr</td>
      <td><a href="/mibs/DE/portale/ausschreibungen/26E09301-03">Fachplanung TGA</a></td>
      <td>HIL GmbH</td>
      <td>Verhandlungsverfahren</td>
      <td>26E09301/03</td>
    </tr>
  </tbody>
</table>
"""


class AumassParseTests(unittest.TestCase):
    def test_grid_group(self):
        notices = parse_grid(AUMASS, "aumass", "https://plattform.aumass.de")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "AV284B35")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertEqual(notices[0].city, "80331 München")
        self.assertEqual(notices[0].cpv, "09331200-0")
        self.assertTrue(notices[0].project_url.endswith("/Veroeffentlichung/av284b35"))


class SachsenAnhaltParseTests(unittest.TestCase):
    def test_row_pid_and_next(self):
        notices = parse_st(ST, "sachsen_anhalt", "https://evergabe.sachsen-anhalt.de/recherche-aktueller-vergaben")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "115301319")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertEqual(notices[0].city, "06108 Halle (Saale)")
        nxt = st_next(ST, "https://evergabe.sachsen-anhalt.de/recherche-aktueller-vergaben")
        self.assertIn("idp=nextpage", nxt)

    def test_pid_from_idp(self):
        href = (
            "/recherche-aktueller-vergaben?idp="
            "LzIxNTA4NTQwNT90c2FpZF9wMDQwdDAwPTExNTMwMTMxOSZ0c2FpZF9jPTAyJnRzYWlkX3M9MDQ="
        )
        self.assertEqual(pid_from_href(href), "115301319")


class ThueringenParseTests(unittest.TestCase):
    def test_rows_and_time_filter(self):
        notices = parse_th(TH, "thueringen", "https://verwaltung.thueringen.de/evergabe")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "883924")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertTrue(notices[0].project_url.endswith("tenderdetails.html?id=883924"))
        self.assertEqual(select_time_filter("2026-08-18", today=date(2026, 8, 18)), "today")
        self.assertEqual(select_time_filter("2026-08-17", today=date(2026, 8, 18)), "lastSeven")
        self.assertEqual(select_time_filter("2026-07-20", today=date(2026, 8, 18)), "lastThirty")
        self.assertEqual(select_time_filter("2026-07-01", today=date(2026, 8, 18)), "all")


class SaarlandParseTests(unittest.TestCase):
    def test_cms_row(self):
        notices = parse_saarland(SL, "saarland", "https://www.saarland.de/mibs/DE/portale/ausschreibungen/aktuelles/neue-veroeffentlichungen")
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].pid, "26E09301/03")
        self.assertEqual(notices[0].published_on, "2026-08-14")
        self.assertIn("26E09301-03", notices[0].project_url)


if __name__ == "__main__":
    unittest.main()
