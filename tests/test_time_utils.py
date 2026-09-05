"""Unit tests for time parsing, boundary calculation, and filter resolution."""

from __future__ import annotations

import datetime
import time
import unittest

from chid.time_utils import (
    get_today_range,
    get_yesterday_range,
    parse_time_boundary,
    parse_time_range,
    resolve_time_filters,
)


class TestTimeUtils(unittest.TestCase):
    """Test suite for time parsing and range utilities."""

    def test_parse_relative_durations(self) -> None:
        now_ms = int(time.time() * 1000)

        # 30 seconds
        val_30s = parse_time_boundary("30s")
        self.assertAlmostEqual(val_30s, now_ms - 30 * 1000, delta=2000)

        # 15 minutes
        val_15m = parse_time_boundary("15m")
        self.assertAlmostEqual(val_15m, now_ms - 15 * 60 * 1000, delta=2000)

        # 2 hours
        val_2h = parse_time_boundary("2h")
        self.assertAlmostEqual(val_2h, now_ms - 2 * 3600 * 1000, delta=2000)

        # 1 day
        val_1d = parse_time_boundary("1d")
        self.assertAlmostEqual(val_1d, now_ms - 86400 * 1000, delta=2000)

        # 1 week
        val_1w = parse_time_boundary("1w")
        self.assertAlmostEqual(val_1w, now_ms - 7 * 86400 * 1000, delta=2000)

    def test_parse_keywords_and_iso_dates(self) -> None:
        # Keywords
        today_start, today_end = get_today_range()
        self.assertEqual(parse_time_boundary("today", is_end=False), today_start)
        self.assertEqual(parse_time_boundary("today", is_end=True), today_end)

        yest_start, yest_end = get_yesterday_range()
        self.assertEqual(parse_time_boundary("yesterday", is_end=False), yest_start)
        self.assertEqual(parse_time_boundary("yesterday", is_end=True), yest_end)

        # ISO date YYYY-MM-DD
        d_start = parse_time_boundary("2026-09-01", is_end=False)
        d_end = parse_time_boundary("2026-09-01", is_end=True)
        self.assertTrue(d_start < d_end)
        self.assertEqual(d_end - d_start, 86400000 - 1)

        # Time of day HH:MM
        t_val = parse_time_boundary("14:30", is_end=False)
        dt = datetime.datetime.fromtimestamp(t_val / 1000)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)

    def test_parse_time_range(self) -> None:
        # Date range
        start_ms, end_ms = parse_time_range("2026-09-01..2026-09-05")
        self.assertTrue(start_ms < end_ms)

        # Relative range 2h..30m
        start_rel, end_rel = parse_time_range("2h..30m")
        self.assertTrue(start_rel < end_rel)

        # Inverted relative range 30m..2h gets auto-swapped
        start_inv, end_inv = parse_time_range("30m..2h")
        self.assertTrue(start_inv < end_inv)

        # Invalid format without ..
        with self.assertRaises(ValueError):
            parse_time_range("2026-09-01 to 2026-09-05")

    def test_resolve_time_filters(self) -> None:
        # None specified
        since, until, label = resolve_time_filters()
        self.assertIsNone(since)
        self.assertIsNone(until)
        self.assertIsNone(label)

        # Today
        since, until, label = resolve_time_filters(today=True)
        today_start, today_end = get_today_range()
        self.assertEqual(since, today_start)
        self.assertEqual(until, today_end)
        self.assertEqual(label, "today")

        # Yesterday
        since, until, label = resolve_time_filters(yesterday=True)
        yest_start, yest_end = get_yesterday_range()
        self.assertEqual(since, yest_start)
        self.assertEqual(until, yest_end)
        self.assertEqual(label, "yesterday")

        # Last
        since, until, label = resolve_time_filters(last="1h")
        self.assertIsNotNone(since)
        self.assertIsNone(until)
        self.assertEqual(label, "last 1h")

        # Since + Until
        since, until, label = resolve_time_filters(since="2h", until="30m")
        self.assertIsNotNone(since)
        self.assertIsNotNone(until)
        self.assertTrue(since < until)
        self.assertEqual(label, "since 2h, until 30m")

        # Range
        since, until, label = resolve_time_filters(range_str="2h..30m")
        self.assertTrue(since < until)
        self.assertEqual(label, "range 2h..30m")

    def test_resolve_time_filters_conflicts(self) -> None:
        # Multiple presets
        with self.assertRaises(ValueError):
            resolve_time_filters(today=True, yesterday=True)

        with self.assertRaises(ValueError):
            resolve_time_filters(today=True, last="1h")

        # Preset combined with since/until
        with self.assertRaises(ValueError):
            resolve_time_filters(today=True, since="1h")

        with self.assertRaises(ValueError):
            resolve_time_filters(range_str="2h..30m", until="10m")

        # Invalid start after end
        with self.assertRaises(ValueError):
            resolve_time_filters(since="2026-09-05", until="2026-09-01")

        # Invalid time string format
        with self.assertRaises(ValueError):
            resolve_time_filters(since="invalid_date_xyz")


if __name__ == "__main__":
    unittest.main()
