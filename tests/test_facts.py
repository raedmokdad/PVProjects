from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filter.facts import extract_facts, parse_de_number


class NumberTests(unittest.TestCase):
    def test_comma_decimal(self):
        self.assertEqual(parse_de_number("72,5"), 72.5)

    def test_thousands(self):
        self.assertEqual(parse_de_number("1.200"), 1200.0)


class ExtractTests(unittest.TestCase):
    def test_area_and_kwp(self):
        facts = extract_facts("Dach-PV 72,5 kWp auf ca. 450 m² Südseite")
        self.assertEqual(facts.area_m2, 450.0)
        self.assertEqual(facts.capacity_kwp, 72.5)

    def test_completion_range(self):
        facts = extract_facts("Leistungszeitraum: 01.09.2026 bis 15.12.2026")
        self.assertEqual(facts.completion_on, "2026-12-15")

    def test_cosinex_begin_ende(self):
        facts = extract_facts(
            "Ausführungsfristen Laufzeit bzw. Dauer Beginn/Ende Beginn 19.10.2026 Ende 10.03.2027"
        )
        self.assertEqual(facts.completion_on, "2027-03-10")

    def test_cosinex_begin_ende_newlines(self):
        facts = extract_facts(
            "Ausführungsfristen\nLaufzeit bzw. Dauer\nBeginn/Ende\nBeginn\n19.10.2026\nEnde\n10.03.2027"
        )
        self.assertEqual(facts.completion_on, "2027-03-10")

    def test_cosinex_execution_end_labels(self):
        from portals.cosinex import CosinexPortal

        text = (
            "Ausführungsfristen\nLaufzeit bzw. Dauer\nLaufzeit in Monaten\n"
            "Laufzeit in Tagen\nBeginn/Ende\nBeginn\n19.10.2026\nEnde\n10.03.2027"
        )
        self.assertEqual(CosinexPortal._execution_end(text), "2027-03-10")

    def test_fertigstellung_der_leistung(self):
        facts = extract_facts(
            "Ausführungsfristen Zeitraum der Leistungserbringung "
            "Beginn der Leistung: 19.10.2026 Fertigstellung der Leistung: 13.11.2026"
        )
        self.assertEqual(facts.completion_on, "2026-11-13")

    def test_fertigstellung_multiple_buildings(self):
        facts = extract_facts(
            "Ausführungsfrist Beginn: 19.10.2026 Fertigstellung: "
            "Gymnasium am Waldhof: 09.04.2027 Grundschule Ummeln: 26.05.2027"
        )
        self.assertEqual(facts.completion_on, "2027-05-26")

    def test_enddatum_der_laufzeit(self):
        facts = extract_facts("Geschätzte Laufzeit Datum des Beginns: 01.04.2027 Enddatum der Laufzeit: 31.03.2031")
        self.assertEqual(facts.completion_on, "2031-03-31")

    def test_slash_dates(self):
        facts = extract_facts("Datum des Beginns : 01/12/2026 Enddatum der Laufzeit : 30/11/2027")
        self.assertEqual(facts.completion_on, "2027-11-30")

    def test_ausfuehrungsfrist_does_not_take_start(self):
        facts = extract_facts("Ausführungsfristen Beginn der Ausführung 02.11.2026 Fertigstellung März 2027")
        self.assertEqual(facts.completion_on, "")

    def test_kwp_dot_decimal(self):
        facts = extract_facts("PV-Anlage 72.9kWp einschl. Verkabelung")
        self.assertEqual(facts.capacity_kwp, 72.9)

    def test_empty(self):
        facts = extract_facts("Beschaffung von Servern")
        self.assertIsNone(facts.area_m2)
        self.assertIsNone(facts.capacity_kwp)
        self.assertEqual(facts.completion_on, "")


if __name__ == "__main__":
    unittest.main()
