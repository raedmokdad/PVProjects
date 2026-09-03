"""Tests für filter/ai_extract.py — laufen ohne echten OpenAI-Key."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from portals.base import Notice


def _make_notice(**kwargs) -> Notice:
    defaults = dict(portal="test", pid="1", title="PV-Anlage Neubau Kita", published_on="2026-09-03")
    defaults.update(kwargs)
    return Notice(**defaults)


class AiExtractNoKeyTests(unittest.TestCase):
    """Ohne API-Key passiert gar nichts."""

    def test_no_key_does_nothing(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            from filter.ai_extract import ai_extract
            notice = _make_notice()
            ai_extract(notice)
            self.assertIsNone(notice.capacity_kwp)
            self.assertIsNone(notice.is_new_build)
            self.assertIsNone(notice.has_transformer)

    def test_all_fields_set_skips_api(self):
        """Wenn alle Felder schon gesetzt sind, wird kein API-Call gemacht."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            from filter import ai_extract as ai_mod
            notice = _make_notice(
                capacity_kwp=50.0,
                start_on="2026-10-01",
                completion_on="2027-03-31",
                area_m2=400.0,
                is_new_build=True,
                has_transformer=False,
            )
            with patch.object(ai_mod, "_is_configured", return_value=True):
                with patch("openai.OpenAI") as mock_openai:
                    ai_mod.ai_extract(notice)
                    mock_openai.assert_not_called()


class AiExtractMockedTests(unittest.TestCase):
    """API-Antwort gemockt — prüft, ob Felder korrekt übernommen werden."""

    def _run_with_response(self, response_data: dict, notice: Notice | None = None) -> Notice:
        if notice is None:
            notice = _make_notice(excerpt="Neubau einer PV-Anlage 75 kWp. Trafostation vorhanden.")
        raw_json = json.dumps(response_data)

        mock_choice = MagicMock()
        mock_choice.message.content = raw_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            from filter import ai_extract as ai_mod
            with patch.object(ai_mod, "_is_configured", return_value=True):
                with patch("filter.ai_extract.OpenAI", return_value=mock_client):
                    ai_mod.ai_extract(notice)
        return notice

    def test_fills_missing_fields(self):
        notice = self._run_with_response({
            "capacity_kwp": 75.0,
            "start_on": "2026-10-01",
            "completion_on": "2027-04-30",
            "area_m2": 500.0,
            "is_new_build": True,
            "has_transformer": True,
            "evidence": "Neubau PV 75 kWp, Trafostation",
        })
        self.assertEqual(notice.capacity_kwp, 75.0)
        self.assertEqual(notice.start_on, "2026-10-01")
        self.assertEqual(notice.completion_on, "2027-04-30")
        self.assertEqual(notice.area_m2, 500.0)
        self.assertTrue(notice.is_new_build)
        self.assertTrue(notice.has_transformer)

    def test_null_fields_stay_none(self):
        notice = self._run_with_response({
            "capacity_kwp": None,
            "start_on": None,
            "completion_on": None,
            "area_m2": None,
            "is_new_build": None,
            "has_transformer": None,
            "evidence": "",
        })
        self.assertIsNone(notice.capacity_kwp)
        self.assertIsNone(notice.is_new_build)
        self.assertIsNone(notice.has_transformer)

    def test_does_not_overwrite_existing_regex_value(self):
        """KI darf Regex-Werte nicht überschreiben."""
        notice = _make_notice(capacity_kwp=50.0)  # von Regex gesetzt
        self._run_with_response({
            "capacity_kwp": 999.0,  # KI liefert anderen Wert
            "start_on": None,
            "completion_on": None,
            "area_m2": None,
            "is_new_build": None,
            "has_transformer": None,
            "evidence": "999 kWp",
        }, notice=notice)
        self.assertEqual(notice.capacity_kwp, 50.0)  # Regex-Wert bleibt

    def test_api_error_does_not_raise(self):
        """Fehler der API darf den Lauf nicht abbrechen."""
        notice = _make_notice()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            from filter import ai_extract as ai_mod
            with patch.object(ai_mod, "_is_configured", return_value=True):
                with patch("filter.ai_extract.OpenAI", return_value=mock_client):
                    ai_mod.ai_extract(notice)  # darf nicht werfen
        self.assertIsNone(notice.capacity_kwp)


if __name__ == "__main__":
    unittest.main()
