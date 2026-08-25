from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from filter.facts import extract_facts, extract_value_eur, format_eur
from filter.geo import bundesland_for, clean_city, ort_facets
from filter.pv_storage import is_planning
from portals.oeffentlichevergabe import value_from_json


class ValueTest(unittest.TestCase):
    def test_label_after_amount(self):
        self.assertEqual(
            extract_value_eur("Geschätzter Gesamtwert: 1.250.000,00 EUR"), 1250000.0
        )

    def test_verguetung(self):
        self.assertEqual(extract_value_eur("Vergütung 85.000 €"), 85000.0)

    def test_amount_before_label(self):
        self.assertEqual(extract_value_eur("450.000 € geschätzter Auftragswert"), 450000.0)

    def test_largest_wins(self):
        text = "Kostenschätzung 90.000 EUR, Auftragswert 1.100.000 EUR"
        self.assertEqual(extract_value_eur(text), 1100000.0)

    def test_plain_amount_is_ignored(self):
        self.assertIsNone(extract_value_eur("Die Anlage kostet 500 € pro Modul im Einkauf."))

    def test_no_value(self):
        self.assertIsNone(extract_value_eur("PV-Anlage auf dem Schuldach"))

    def test_facts_carry_value(self):
        facts = extract_facts("Dach-PV 72,5 kWp", "Geschätzter Wert: 300.000 EUR")
        self.assertEqual(facts.value_eur, 300000.0)
        self.assertEqual(facts.capacity_kwp, 72.5)

    def test_format(self):
        self.assertEqual(format_eur(1250000.0), "1.250.000 €")
        self.assertEqual(format_eur(None), "")


class ValueFromJsonTest(unittest.TestCase):
    def test_nested_lot_value(self):
        data = {"lots": [{"value": {"estimatedValue": {"amount": 750000, "currencyId": "EUR"}}}]}
        self.assertEqual(value_from_json(data), 750000.0)

    def test_foreign_currency_ignored(self):
        data = {"estimatedValue": {"amount": 900000, "currencyId": "CHF"}}
        self.assertIsNone(value_from_json(data))

    def test_largest_of_several(self):
        data = {
            "lots": [
                {"estimatedValue": {"amount": 100000, "currencyId": "EUR"}},
                {"estimatedValue": {"amount": 250000, "currencyId": "EUR"}},
            ]
        }
        self.assertEqual(value_from_json(data), 250000.0)

    def test_missing(self):
        self.assertIsNone(value_from_json({"purpose": {"title": "PV-Anlage"}}))


class PlanningTest(unittest.TestCase):
    def test_keyword(self):
        self.assertTrue(is_planning("Objektplanung PV-Anlage Schulzentrum", ""))

    def test_hoai(self):
        self.assertTrue(is_planning("Ingenieurleistungen nach HOAI", ""))

    def test_cpv(self):
        self.assertTrue(is_planning("Beratung", "", "71310000"))

    def test_build_job_is_not_planning(self):
        self.assertFalse(is_planning("Lieferung und Montage einer PV-Anlage 300 kWp", ""))


class GeoTest(unittest.TestCase):
    def test_nuts(self):
        self.assertEqual(bundesland_for({"nuts": "DEA23"}), "Nordrhein-Westfalen")

    def test_plz_fallback(self):
        row = {"nuts": "", "city": "Pestalozzistraße 11, 10625 Berlin, Deutschland"}
        self.assertEqual(bundesland_for(row), "Berlin")

    def test_potsdam_is_brandenburg(self):
        self.assertEqual(bundesland_for({"city": "14467 Potsdam"}), "Brandenburg")

    def test_unknown(self):
        self.assertEqual(bundesland_for({"city": "irgendwo"}), "Ohne Angabe")

    def test_clean_city(self):
        self.assertEqual(clean_city("Musterweg 3, 50667 Köln-Innenstadt, Deutschland"), "Köln")
        self.assertEqual(clean_city("München"), "München")
        self.assertEqual(clean_city("Deutschland"), "")

    def test_facets(self):
        rows = [
            {"nuts": "DE212", "city": "80331 München"},
            {"nuts": "DE212", "city": "80331 München"},
            {"nuts": "DEA23", "city": "50667 Köln"},
            {"nuts": "", "city": "nirgends"},
        ]
        facets = ort_facets(rows)
        self.assertEqual(facets[0]["name"], "Bayern")
        self.assertEqual(facets[0]["count"], 2)
        self.assertEqual(facets[0]["cities"][0], {"name": "München", "count": 2})
        self.assertEqual(facets[-1]["name"], "Ohne Angabe")


class PortalCatalogTest(unittest.TestCase):
    def test_berlin_is_not_a_bare_city_name(self):
        from portals import portal_home, portal_label

        self.assertEqual(portal_label("berlin"), "Vergabekooperation Berlin")
        self.assertEqual(portal_home("berlin"), "https://vergabekooperation.berlin")

    def test_catalog_is_alphabetical_and_linked(self):
        from portals import portal_catalog

        catalog = portal_catalog()
        labels = [e["label"] for e in catalog]
        self.assertEqual(labels, sorted(labels, key=lambda s: s.lower().replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")))
        self.assertTrue(all(e["url"].startswith("http") for e in catalog))
        self.assertIn("Vergabekooperation Berlin", labels)
        self.assertNotIn("Berlin", labels)


if __name__ == "__main__":
    unittest.main()
