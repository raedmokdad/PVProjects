from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filter.pv_storage import classify, load_filter_config


class FilterTests(unittest.TestCase):
    def test_pv_from_title(self):
        cat, reason = classify("Photovoltaikanlage Schule Musterstadt", "", "")
        self.assertEqual(cat, "PV")
        self.assertIn("photovoltaik", reason.lower())

    def test_storage_from_keyword(self):
        cat, reason = classify("Lieferung Batteriespeicher 200 kWh", "", "")
        self.assertEqual(cat, "Speicher")
        self.assertIn("batteriespeicher", reason.lower())

    def test_both(self):
        cat, _ = classify("PV-Anlage inkl. Stromspeicher auf dem Rathaus", "", "")
        self.assertEqual(cat, "PV+Speicher")

    def test_cpv_pv(self):
        cat, reason = classify(
            "Dacharbeiten Gymnasium",
            "Auftragsgegenstand 09331200-0 Photovoltaische Solarmodule",
            "",
        )
        self.assertEqual(cat, "PV")
        self.assertIn("09331200", reason)

    def test_ignore_roofer(self):
        cat, reason = classify("Dachdeckerarbeiten Schwimmbadsanierungen", "Ziegel und Abdichtung", "")
        self.assertEqual(cat, "")
        self.assertEqual(reason, "")

    def test_solarthermie_not_pv(self):
        cat, _ = classify("Solarthermie Kollektoren Turnhalle", "Sonnenkollektoren für Warmwasser", "")
        self.assertEqual(cat, "")

    def test_solaranlage_counts_as_pv(self):
        cat, _ = classify("Solaranlage Feuerwache", "Lieferung und Montage einer Solaranlage", "")
        self.assertEqual(cat, "PV")

    def test_bess_standalone(self):
        cat, _ = classify("Lieferung BESS 200 kWh", "", "")
        self.assertEqual(cat, "Speicher")

    def test_besser_not_storage(self):
        cat, _ = classify(
            "Transport und Verwertung von Rechengut",
            "gewaschenem Rechengut, verbessert und selbst zu verwerten, besser sortiert",
            "",
        )
        self.assertEqual(cat, "")

    def test_pv_with_speicher_in_title(self):
        cat, reason = classify(
            "Installation einer Photovoltaikanlage mit Speicher mit einer Leistung von mindestens 18 kWp",
            "",
            "",
        )
        self.assertEqual(cat, "PV+Speicher")
        self.assertIn("Speicher", reason)

    def test_config_loads(self):
        cfg = load_filter_config()
        self.assertIn("pv", cfg)
        self.assertIn("storage", cfg)


if __name__ == "__main__":
    unittest.main()
