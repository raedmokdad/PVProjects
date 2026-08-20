from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobs.daily import selected_portals
from portals.base import Notice
from portals.oeffentlichevergabe import (
    CONTAINS_TERMS,
    code_value,
    iso_day_bounds,
    lang_text,
    notice_ui_url,
    union_by_notice_id,
    OeffentlichevergabePortal,
)
from store.db import dedupe_notice_rows


class LangAndDateTests(unittest.TestCase):
    def test_prefers_deu(self):
        items = [
            {"value": "Solar farm", "languageId": "ENG"},
            {"value": "Photovoltaikanlage", "languageId": "DEU"},
        ]
        self.assertEqual(lang_text(items), "Photovoltaikanlage")

    def test_falls_back_to_first_value(self):
        items = [{"value": "Only English", "languageId": "ENG"}]
        self.assertEqual(lang_text(items), "Only English")

    def test_plain_string(self):
        self.assertEqual(lang_text("Hallo"), "Hallo")

    def test_code_value_object(self):
        self.assertEqual(code_value({"value": "cn-standard", "listName": "competition"}), "cn-standard")

    def test_contains_photovoltaik_for_compound_words(self):
        self.assertIn("Photovoltaik", CONTAINS_TERMS)
        self.assertIn("PV-Anlage", CONTAINS_TERMS)

    def test_iso_day_bounds_berlin(self):
        start, end = iso_day_bounds(date(2026, 8, 17))
        self.assertTrue(start.startswith("2026-08-17T00:00:00"))
        self.assertTrue(end.startswith("2026-08-18T00:00:00"))

    def test_notice_ui_url_uses_details_query(self):
        url = notice_ui_url("25719776")
        self.assertEqual(url, "https://oeffentlichevergabe.de/ui/de/search/details?noticeId=25719776")
        self.assertNotIn("/search/notices/", url)


class UnionTests(unittest.TestCase):
    def test_union_keeps_first_notice_id(self):
        a = Notice(portal="oeffentlichevergabe", pid="abc", title="A", published_on="2026-08-17")
        b = Notice(portal="oeffentlichevergabe", pid="abc", title="A Los 2", published_on="2026-08-17")
        c = Notice(portal="oeffentlichevergabe", pid="def", title="B", published_on="2026-08-17")
        merged = union_by_notice_id([a, b, c])
        self.assertEqual({n.pid for n in merged}, {"abc", "def"})
        self.assertEqual(next(n.title for n in merged if n.pid == "abc"), "A")


class DomainParseTests(unittest.TestCase):
    def test_buyer_and_place_from_domain(self):
        data = {
            "buyers": [{"organisationReference": "ORG-0001"}],
            "organisation": [
                {"partyIdentification": "ORG-0001", "organisationName": "Bauwerke Münster GmbH"},
                {"partyIdentification": "ORG-0002", "organisationName": "Stadt Münster"},
            ],
            "placeOfPerformance": [
                {
                    "placePerformanceCity": "Münster",
                    "placePerformanceCountrySubdivision": {"value": "DEA33", "listName": "nuts"},
                }
            ],
        }
        self.assertEqual(OeffentlichevergabePortal._buyer_name(data), "Bauwerke Münster GmbH")
        city, nuts = OeffentlichevergabePortal._place(data)
        self.assertEqual(city, "Münster")
        self.assertEqual(nuts, "DEA33")

    def test_cpv_from_nested_codes(self):
        codes = OeffentlichevergabePortal._cpv_from_classification(
            {
                "mainClassificationCode": {"value": "45000000", "listName": "cpv"},
                "additionalClassificationCode": [{"value": "45261215", "listName": "cpv"}],
            }
        )
        self.assertEqual(codes, ["45000000", "45261215"])


class DedupeDisplayTests(unittest.TestCase):
    def test_same_ted_id_is_merged(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE t (portal TEXT, pid TEXT, contracting_rule TEXT, title TEXT)"
        )
        conn.execute("INSERT INTO t VALUES ('oeffentlichevergabe','id-1','TED 1-2026','Eins')")
        conn.execute("INSERT INTO t VALUES ('evergabe_nrw','99','TED 1-2026','Eins NRW')")
        rows = list(conn.execute("SELECT * FROM t"))
        unique = dedupe_notice_rows(rows)
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0]["pid"], "id-1")


class PortalSelectionTests(unittest.TestCase):
    def test_default_includes_satellites_and_dtvp(self):
        names = selected_portals(None)
        self.assertIn("oeffentlichevergabe", names)
        self.assertIn("evergabe_nrw", names)
        self.assertIn("dtvp", names)
        self.assertIn("vergabe_ruhr", names)
        self.assertIn("vmp_rheinland", names)
        self.assertIn("vergabe_westfalen", names)
        self.assertIn("evergabe_blb", names)
        self.assertIn("vergabe_rlp", names)
        self.assertIn("vergabe_brandenburg", names)
        self.assertIn("evergabe_mv", names)
        self.assertIn("berlin", names)
        self.assertIn("hessen", names)
        self.assertIn("landbw", names)
        self.assertIn("vergabe_niedersachsen", names)
        self.assertIn("sachsen", names)
        self.assertIn("bremen", names)
        self.assertIn("evergabe_online", names)
        self.assertIn("aumass", names)
        self.assertIn("sachsen_anhalt", names)
        self.assertIn("thueringen", names)
        self.assertIn("saarland", names)

    def test_nrw_alias(self):
        self.assertEqual(selected_portals(["nrw"]), ["evergabe_nrw"])

    def test_ruhr_alias(self):
        self.assertEqual(selected_portals(["ruhr"]), ["vergabe_ruhr"])

    def test_rlp_alias(self):
        self.assertEqual(selected_portals(["rlp"]), ["vergabe_rlp"])

    def test_all(self):
        names = selected_portals(["all"])
        self.assertIn("oeffentlichevergabe", names)
        self.assertIn("evergabe_nrw", names)
        self.assertIn("berlin", names)
        self.assertIn("evergabe_online", names)

    def test_new_aliases(self):
        self.assertEqual(selected_portals(["berlin"]), ["berlin"])
        self.assertEqual(selected_portals(["bw"]), ["landbw"])
        self.assertEqual(selected_portals(["eo"]), ["evergabe_online"])
        self.assertEqual(selected_portals(["bayern"]), ["aumass"])
        self.assertEqual(selected_portals(["ni"]), ["vergabe_niedersachsen"])
        self.assertEqual(selected_portals(["sachsen"]), ["sachsen"])
        self.assertEqual(selected_portals(["st"]), ["sachsen_anhalt"])
        self.assertEqual(selected_portals(["th"]), ["thueringen"])
        self.assertEqual(selected_portals(["sl"]), ["saarland"])


if __name__ == "__main__":
    unittest.main()
