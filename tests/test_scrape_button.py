from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobs import scrape_state


class ScrapeStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"DATA_DIR": self.tmp.name}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_acquire_and_release(self):
        self.assertTrue(scrape_state.acquire_lock())
        self.assertFalse(scrape_state.acquire_lock())
        self.assertTrue(scrape_state.is_running())
        scrape_state.release_lock()
        self.assertFalse(scrape_state.is_running())
        self.assertTrue(scrape_state.acquire_lock())
        scrape_state.release_lock()

    def test_secret_local_without_env(self):
        with patch.dict(os.environ, {"RUN_SECRET": "", "RAILWAY_ENVIRONMENT": "", "RAILWAY_PROJECT_ID": ""}, clear=False):
            os.environ.pop("RAILWAY_ENVIRONMENT", None)
            os.environ.pop("RAILWAY_PROJECT_ID", None)
            os.environ["RUN_SECRET"] = ""
            self.assertTrue(scrape_state.secret_ok(""))
            self.assertFalse(scrape_state.run_needs_setup())

    def test_secret_on_railway_without_config(self):
        with patch.dict(os.environ, {"RUN_SECRET": "", "RAILWAY_ENVIRONMENT": "production"}, clear=False):
            os.environ["RUN_SECRET"] = ""
            self.assertFalse(scrape_state.run_needs_setup())
            self.assertTrue(scrape_state.secret_ok(""))
            self.assertTrue(scrape_state.secret_ok("x"))

    def test_true_is_not_a_password(self):
        with patch.dict(os.environ, {"RUN_SECRET": "true", "RAILWAY_ENVIRONMENT": "production"}):
            self.assertFalse(scrape_state.secret_configured())
            self.assertTrue(scrape_state.secret_ok(""))

    def test_heal_stale_running_without_lock(self):
        scrape_state.write_status(
            state="running",
            started_at="2026-08-24 11:59:33+02:00",
            run_date="2026-08-20",
        )
        self.assertFalse(scrape_state.is_running())
        healed = scrape_state.heal_stale_run()
        self.assertEqual(healed["state"], "error")
        self.assertIn("abgebrochen", healed["error"])

    def test_heal_keeps_fresh_running(self):
        self.assertTrue(scrape_state.acquire_lock())
        scrape_state.write_status(state="running", started_at=scrape_state.iso_now())
        healed = scrape_state.heal_stale_run()
        self.assertEqual(healed["state"], "running")
        scrape_state.release_lock()

    def test_secret_match(self):
        with patch.dict(os.environ, {"RUN_SECRET": "wetenergy", "RAILWAY_ENVIRONMENT": "production"}):
            self.assertTrue(scrape_state.secret_ok("wetenergy"))
            self.assertFalse(scrape_state.secret_ok("wrong"))
            self.assertFalse(scrape_state.secret_ok(""))


class AppRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {"DATA_DIR": self.tmp.name, "RUN_SECRET": "test-secret", "RAILWAY_ENVIRONMENT": "production"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        import app as app_mod

        self.client = app_mod.app.test_client()

    def test_forbidden_without_secret(self):
        res = self.client.post("/run", json={})
        self.assertEqual(res.status_code, 403)

    def test_start_with_secret(self):
        import app as app_mod

        with patch("app.threading.Thread") as thread_cls:
            res = self.client.post("/run", json={"secret": "test-secret"})
            thread_cls.assert_called_once()
            self.assertEqual(thread_cls.call_args.kwargs.get("target"), app_mod._scrape_in_background)
        self.assertEqual(res.status_code, 202)
        self.assertTrue(res.get_json()["ok"])

    def test_status_json(self):
        res = self.client.get("/run/status")
        self.assertEqual(res.status_code, 200)
        self.assertIn("state", res.get_json())


class AppRunOpenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {"DATA_DIR": self.tmp.name, "RUN_SECRET": "true", "RAILWAY_ENVIRONMENT": "production"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        import app as app_mod

        self.client = app_mod.app.test_client()

    def test_start_without_password_when_flag(self):
        with patch("app.threading.Thread") as thread_cls:
            res = self.client.post("/run", json={})
            thread_cls.assert_called_once()
        self.assertEqual(res.status_code, 202)

    def test_optional_date_passed_to_worker(self):
        import app as app_mod
        from datetime import date

        with patch("app.threading.Thread") as thread_cls:
            res = self.client.post("/run", json={"date": "2026-08-21"})
            self.assertEqual(thread_cls.call_args.kwargs.get("args"), (date(2026, 8, 21),))
        self.assertEqual(res.status_code, 202)

    def test_empty_date_defaults_to_yesterday(self):
        import app as app_mod

        with patch("app.threading.Thread") as thread_cls:
            self.client.post("/run", json={})
            self.assertEqual(thread_cls.call_args.kwargs.get("args"), (app_mod.yesterday(),))

    def test_bad_date_rejected(self):
        res = self.client.post("/run", json={"date": "21.08.2026"})
        self.assertEqual(res.status_code, 400)

    def test_future_date_rejected(self):
        import app as app_mod
        from datetime import timedelta

        future = (app_mod.yesterday() + timedelta(days=3)).isoformat()
        res = self.client.post("/run", json={"date": future})
        self.assertEqual(res.status_code, 400)

    def test_today_allowed(self):
        import app as app_mod
        from datetime import timedelta

        today = (app_mod.yesterday() + timedelta(days=1)).isoformat()
        with patch("app.threading.Thread") as thread_cls:
            res = self.client.post("/run", json={"date": today})
            self.assertEqual(res.status_code, 202)
            self.assertEqual(
                thread_cls.call_args.kwargs.get("args"),
                (app_mod.yesterday() + timedelta(days=1),),
            )


class AppDeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {"DATA_DIR": self.tmp.name, "RUN_SECRET": "test-secret", "RAILWAY_ENVIRONMENT": "production"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        import app as app_mod

        self.client = app_mod.app.test_client()

    def test_delete_requires_secret(self):
        res = self.client.delete("/notice", json={"portal": "berlin", "pid": "1"})
        self.assertEqual(res.status_code, 403)

    def test_delete_missing_ids(self):
        res = self.client.delete("/notice", json={"secret": "test-secret"})
        self.assertEqual(res.status_code, 400)

    def test_delete_unknown(self):
        res = self.client.delete(
            "/notice", json={"secret": "test-secret", "portal": "berlin", "pid": "missing"}
        )
        self.assertEqual(res.status_code, 404)

    def test_delete_notice(self):
        from portals.base import Notice
        from store.db import Store

        store = Store()
        store.upsert_notice(
            Notice(
                portal="berlin",
                pid="abc",
                title="PV-Anlage",
                published_on="2026-08-01",
                is_match=True,
                category="PV",
            ),
            "2026-08-01",
        )
        res = self.client.delete(
            "/notice", json={"secret": "test-secret", "portal": "berlin", "pid": "abc"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["ok"])
        self.assertEqual(len(store.matches()), 0)
        store.close()


class AppRelevantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {"DATA_DIR": self.tmp.name, "RUN_SECRET": "test-secret", "RAILWAY_ENVIRONMENT": "production"},
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        import app as app_mod

        self.client = app_mod.app.test_client()

    def _insert(self, pid="abc"):
        from portals.base import Notice
        from store.db import Store

        store = Store()
        store.upsert_notice(
            Notice(
                portal="berlin",
                pid=pid,
                title="PV-Anlage",
                published_on="2026-08-01",
                is_match=True,
                category="PV",
            ),
            "2026-08-01",
        )
        store.close()

    def test_mark_requires_secret(self):
        res = self.client.post("/notice/relevant", json={"portal": "berlin", "pid": "1"})
        self.assertEqual(res.status_code, 403)

    def test_mark_unknown(self):
        res = self.client.post(
            "/notice/relevant",
            json={"secret": "test-secret", "portal": "berlin", "pid": "missing"},
        )
        self.assertEqual(res.status_code, 404)

    def test_mark_relevant_moves_notice(self):
        from store.db import Store

        self._insert()
        res = self.client.post(
            "/notice/relevant",
            json={"secret": "test-secret", "portal": "berlin", "pid": "abc"},
        )
        self.assertEqual(res.status_code, 200)
        store = Store()
        self.assertEqual(len(store.matches()), 0)
        self.assertEqual(len(store.relevant_unique()), 1)
        self.assertEqual(store.relevant_unique()[0]["pid"], "abc")
        store.close()

    def test_upsert_keeps_relevant(self):
        from portals.base import Notice
        from store.db import Store

        self._insert()
        store = Store()
        self.assertTrue(store.mark_relevant("berlin", "abc"))
        store.upsert_notice(
            Notice(
                portal="berlin",
                pid="abc",
                title="PV-Anlage neu",
                published_on="2026-08-01",
                is_match=True,
                category="PV",
            ),
            "2026-08-02",
        )
        self.assertEqual(len(store.matches()), 0)
        rows = store.relevant_unique()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "PV-Anlage neu")
        store.close()

    def test_relevant_page(self):
        self._insert()
        self.client.post(
            "/notice/relevant",
            json={"secret": "test-secret", "portal": "berlin", "pid": "abc"},
        )
        res = self.client.get("/relevant")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Relevante Anzeigen", html)
        self.assertIn("PV-Anlage", html)
        self.assertNotIn('class="btn-relevant"', html)

    def test_inbox_has_relevant_button(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn('href="/relevant"', res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
