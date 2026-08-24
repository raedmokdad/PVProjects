from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portals.cosuno import CosunoPortal, _berlin_date

LIST_HTML = """
<div>
  <article data-cy-bid-package-summary="uuid-1" class="x">
    <header>
      <div><a data-cy-bid-package-summary-title="true" href="/de/marketplace/gm-tuningen-pv-3p35">
        <h2>AC-Arbeiten Freiflächen Photovoltaik</h2></a></div>
      <div>GM Tuningen</div>
    </header>
    <time dateTime="2026-08-20T08:49:00.000Z">20.08.2026 um 10:49</time>
    <section>
      <div><svg data-cy-icon="project-1"></svg>Vergabephase</div>
      <div><svg data-cy-icon="location"></svg>78609 Tuningen</div>
      <div>Angebot abzugeben bis 31.08.2026</div>
      <div>MaxSolar GmbH</div>
    </section>
  </article>
  <article data-cy-bid-package-summary="uuid-2" class="x">
    <header>
      <div><a data-cy-bid-package-summary-title="true" href="/de/marketplace/aufzuege-751">
        <h2>Aufzüge</h2></a></div>
      <div>Wohnpark Nobilis</div>
    </header>
    <time dateTime="2026-08-19T22:30:00.000Z">20.08.2026 um 00:30</time>
    <section><div><svg data-cy-icon="location"></svg>65549 Limburg</div></section>
  </article>
</div>
"""

DETAIL_TEXT = (
    "AC-Arbeiten Freiflächen Photovoltaik\nGM Tuningen\nBauort\n78609 Tuningen\n"
    "Ausschreibendes Unternehmen\nMaxSolar GmbH\nAngebot abzugeben bis 31.08.2026\n"
    "Bauzeit\n21.09.2026 - 23.10.2026\nProjektbeschreibung\n"
    "6 MW Tracker-PV Park, 1x Trafostation.\nWeitere Informationen anzeigen\nrest"
)


class CosunoParseTests(unittest.TestCase):
    def setUp(self):
        self.p = CosunoPortal()

    def test_berlin_date_from_utc(self):
        self.assertEqual(_berlin_date("2026-08-20T08:49:00.000Z"), "2026-08-20")
        # 22:30 UTC = 00:30 Berlin next day (Sommerzeit +2)
        self.assertEqual(_berlin_date("2026-08-19T22:30:00.000Z"), "2026-08-20")
        self.assertEqual(_berlin_date(""), "")

    def test_parse_cards(self):
        cards = self.p._parse_cards(LIST_HTML)
        self.assertEqual(len(cards), 2)
        first = cards[0]
        self.assertEqual(first.pid, "uuid-1")
        self.assertIn("Photovoltaik", first.title)
        self.assertIn("GM Tuningen", first.title)
        self.assertEqual(first.published_on, "2026-08-20")
        self.assertEqual(first.deadline, "2026-08-31")
        self.assertEqual(first.notice_type, "Vergabephase")
        self.assertTrue(first.project_url.startswith("https://www.cosuno.com/de/marketplace/"))

    def test_detail_extraction_helpers(self):
        self.assertEqual(self.p._field_after(DETAIL_TEXT, "Ausschreibendes Unternehmen"), "MaxSolar GmbH")
        self.assertEqual(self.p._completion(DETAIL_TEXT), "2026-10-23")
        excerpt = self.p._excerpt(DETAIL_TEXT)
        self.assertIn("Tracker-PV Park", excerpt)
        self.assertNotIn("Weitere Informationen", excerpt)


if __name__ == "__main__":
    unittest.main()
