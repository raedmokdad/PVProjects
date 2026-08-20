from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portals.cosinex import is_awarded, parse_de_date, parse_html_table


SAMPLE = """
<table class="csx-new-table">
<tr><th>Veröffentlicht</th><th>Frist</th><th>Bezeichnung</th><th>Typ</th><th>Stelle</th></tr>
<tr>
  <td>18.08.2026</td>
  <td>09.09.2026</td>
  <td>PV-Anlage Schule</td>
  <td>VOB/A Ausschreibung</td>
  <td>Stadt Muster</td>
  <td><a href="/VMPSatellite/public/company/projectForwarding.do?pid=56334917">öffnen</a></td>
</tr>
<tr>
  <td>18.08.2026</td>
  <td>nv</td>
  <td>Vergabeergebnis Kanal</td>
  <td>Vergabeergebnis</td>
  <td>Kreis Test</td>
  <td><a href="/VMPSatellite/public/company/projectForwarding.do?pid=1">öffnen</a></td>
</tr>
</table>
"""


class CosinexParseTests(unittest.TestCase):
    def test_parse_de_date(self):
        self.assertEqual(parse_de_date("18.08.2026"), "2026-08-18")

    def test_html_table_rows(self):
        notices = parse_html_table(
            SAMPLE,
            portal="vergabe_westfalen",
            base="https://www.vergabe-westfalen.de",
            prefix="/VMPSatellite",
        )
        self.assertEqual(len(notices), 2)
        self.assertEqual(notices[0].pid, "56334917")
        self.assertEqual(notices[0].published_on, "2026-08-18")
        self.assertEqual(notices[0].title, "PV-Anlage Schule")
        self.assertTrue(notices[0].project_url.endswith("pid=56334917"))

    def test_click_url_dtvp(self):
        from portals.click import notice_click_url

        url = notice_click_url("dtvp", "2587679", "")
        self.assertIn("pid=2587679", url)
        self.assertIn("dtvp.de", url)
        self.assertEqual(
            notice_click_url("dtvp", "1", "https://id.dtvp.de/realms/vmp_dtvp_prod/protocol/openid-connect/auth"),
            "https://www.dtvp.de/Center/secured/company/projectForwarding.do?pid=1",
        )

    def test_awarded_marker(self):
        self.assertTrue(is_awarded("Vergabeergebnis"))
        self.assertFalse(is_awarded("VOB/A Ausschreibung"))


if __name__ == "__main__":
    unittest.main()
