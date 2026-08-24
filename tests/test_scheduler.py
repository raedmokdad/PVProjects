from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobs import scheduler


def berlin(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=scheduler.TZ)


class SchedulerLogicTests(unittest.TestCase):
    def test_fires_after_time_when_not_done_today(self):
        now = berlin(2026, 8, 25, 0, 5)
        self.assertTrue(scheduler.should_run(now, last_done=date(2026, 8, 24)))

    def test_does_not_fire_before_time(self):
        now = berlin(2026, 8, 25, 0, 4)
        self.assertFalse(scheduler.should_run(now, last_done=date(2026, 8, 24)))

    def test_does_not_fire_twice_same_day(self):
        now = berlin(2026, 8, 25, 15, 0)
        self.assertFalse(scheduler.should_run(now, last_done=date(2026, 8, 25)))

    def test_fires_later_in_day_if_missed(self):
        now = berlin(2026, 8, 25, 8, 0)
        self.assertTrue(scheduler.should_run(now, last_done=None))

    def test_enabled_flag(self):
        with patch.dict(os.environ, {"ENABLE_SCHEDULER": "1"}):
            self.assertTrue(scheduler.enabled())
        with patch.dict(os.environ, {"ENABLE_SCHEDULER": "0"}):
            self.assertFalse(scheduler.enabled())
        with patch.dict(os.environ, {"ENABLE_SCHEDULER": ""}):
            self.assertFalse(scheduler.enabled())


if __name__ == "__main__":
    unittest.main()
