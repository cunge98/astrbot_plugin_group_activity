"""
Tests for time-based scheduling helpers:
  _is_weekly_day, _weekly_time, _cleanup_old_stats
"""
import datetime
import pytest


# ── _is_weekly_day ────────────────────────────────────────────────────────────

class TestIsWeeklyDay:
    """
    _is_weekly_day maps 周一-周日 to weekday() indices 0-6 and compares
    against today.  We avoid mocking by configuring the plugin to today's
    actual day (and tomorrow's day), which is always deterministic.
    """

    _DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def test_returns_true_for_todays_day(self, plugin):
        today_idx = datetime.date.today().weekday()   # 0=Mon … 6=Sun
        plugin.config["auto_weekly_day"] = self._DAY_NAMES[today_idx]
        assert plugin._is_weekly_day() is True

    def test_returns_false_for_tomorrows_day(self, plugin):
        tomorrow_idx = (datetime.date.today().weekday() + 1) % 7
        plugin.config["auto_weekly_day"] = self._DAY_NAMES[tomorrow_idx]
        assert plugin._is_weekly_day() is False

    def test_returns_false_for_day_two_ahead(self, plugin):
        idx = (datetime.date.today().weekday() + 2) % 7
        plugin.config["auto_weekly_day"] = self._DAY_NAMES[idx]
        assert plugin._is_weekly_day() is False

    def test_all_day_names_are_recognised(self, plugin):
        """Every Chinese day name maps to a valid weekday without raising."""
        today_idx = datetime.date.today().weekday()
        for i, name in enumerate(self._DAY_NAMES):
            plugin.config["auto_weekly_day"] = name
            result = plugin._is_weekly_day()
            assert result == (i == today_idx)

    def test_unknown_day_defaults_to_sunday(self, plugin):
        """Unknown auto_weekly_day falls back to weekday 6 (Sunday)."""
        plugin.config["auto_weekly_day"] = "周X"   # not a valid key
        sunday_idx = 6
        today_idx = datetime.date.today().weekday()
        assert plugin._is_weekly_day() == (today_idx == sunday_idx)


# ── _weekly_time ──────────────────────────────────────────────────────────────

class TestWeeklyTime:

    def test_parses_hh_mm_format(self, plugin):
        plugin.config["auto_weekly_time"] = "20:30"
        h, m = plugin._weekly_time()
        assert h == 20
        assert m == 30

    def test_parses_midnight(self, plugin):
        plugin.config["auto_weekly_time"] = "00:00"
        h, m = plugin._weekly_time()
        assert h == 0
        assert m == 0

    def test_parses_end_of_day(self, plugin):
        plugin.config["auto_weekly_time"] = "23:59"
        h, m = plugin._weekly_time()
        assert h == 23
        assert m == 59

    def test_fallback_to_legacy_hour_key(self, plugin):
        """Empty auto_weekly_time falls back to auto_weekly_hour."""
        plugin.config["auto_weekly_time"] = ""
        plugin.config["auto_weekly_hour"] = 15
        h, m = plugin._weekly_time()
        assert h == 15
        assert m == 0

    def test_fallback_default_20_00(self, plugin):
        """If neither key is set, defaults to 20:00."""
        plugin.config["auto_weekly_time"] = ""
        plugin.config.pop("auto_weekly_hour", None)
        h, m = plugin._weekly_time()
        assert h == 20
        assert m == 0

    def test_none_time_falls_back(self, plugin):
        plugin.config["auto_weekly_time"] = None
        plugin.config["auto_weekly_hour"] = 8
        h, m = plugin._weekly_time()
        assert h == 8
        assert m == 0

    def test_single_digit_values(self, plugin):
        plugin.config["auto_weekly_time"] = "9:05"
        h, m = plugin._weekly_time()
        assert h == 9
        assert m == 5


# ── _cleanup_old_stats ────────────────────────────────────────────────────────

class TestCleanupOldStats:

    def _make_stats(self, plugin, gid, days_list):
        """Seed daily_stats with {today-N: 10} for each N in days_list."""
        today = datetime.date.today()
        stats = {
            (today - datetime.timedelta(days=n)).isoformat(): 10
            for n in days_list
        }
        plugin.activity_data["groups"][gid] = {"daily_stats": stats}
        return stats

    def test_removes_entries_older_than_60_days(self, plugin):
        old_date = (datetime.date.today() - datetime.timedelta(days=61)).isoformat()
        plugin.activity_data = {
            "groups": {
                "1": {"daily_stats": {old_date: 5}}
            }
        }
        plugin._cleanup_old_stats()
        assert old_date not in plugin.activity_data["groups"]["1"]["daily_stats"]

    def test_keeps_entries_within_60_days(self, plugin):
        recent = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        plugin.activity_data = {
            "groups": {"1": {"daily_stats": {recent: 5}}}
        }
        plugin._cleanup_old_stats()
        assert recent in plugin.activity_data["groups"]["1"]["daily_stats"]

    def test_boundary_exactly_60_days_is_kept(self, plugin):
        """
        cutoff = today - 60 days.  The condition is k < cutoff, so an entry
        dated exactly 60 days ago equals cutoff and is NOT deleted.
        """
        boundary = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
        plugin.activity_data = {
            "groups": {"1": {"daily_stats": {boundary: 7}}}
        }
        plugin._cleanup_old_stats()
        assert boundary in plugin.activity_data["groups"]["1"]["daily_stats"]

    def test_sets_dirty_flag_when_entries_removed(self, plugin):
        old = (datetime.date.today() - datetime.timedelta(days=61)).isoformat()
        plugin.activity_data = {
            "groups": {"1": {"daily_stats": {old: 1}}}
        }
        plugin._dirty = False
        plugin._cleanup_old_stats()
        assert plugin._dirty is True

    def test_does_not_set_dirty_when_nothing_removed(self, plugin):
        recent = datetime.date.today().isoformat()
        plugin.activity_data = {
            "groups": {"1": {"daily_stats": {recent: 1}}}
        }
        plugin._dirty = False
        plugin._cleanup_old_stats()
        assert plugin._dirty is False

    def test_cleans_across_multiple_groups(self, plugin):
        old = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
        recent = datetime.date.today().isoformat()
        plugin.activity_data = {
            "groups": {
                "g1": {"daily_stats": {old: 1, recent: 2}},
                "g2": {"daily_stats": {old: 3, recent: 4}},
            }
        }
        plugin._cleanup_old_stats()
        for gid in ("g1", "g2"):
            ds = plugin.activity_data["groups"][gid]["daily_stats"]
            assert old not in ds
            assert recent in ds

    def test_empty_stats_does_not_crash(self, plugin):
        plugin.activity_data = {
            "groups": {"1": {"daily_stats": {}}}
        }
        plugin._cleanup_old_stats()   # should not raise

    def test_group_without_daily_stats_key_skipped(self, plugin):
        plugin.activity_data = {
            "groups": {"1": {}}   # no 'daily_stats' key
        }
        plugin._cleanup_old_stats()   # should not raise
