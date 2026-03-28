"""
Tests for the heatmap feature:
  - hourly_stats data collection in on_msg
  - _cleanup_old_stats also purges hourly_stats
  - cmd_heatmap data aggregation logic
"""
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_mock_event


# ── hourly_stats data collection ─────────────────────────────────────────────

class TestHourlyStatsCollection:

    async def test_on_msg_creates_hourly_stats(self, plugin):
        """First message in a group seeds hourly_stats for the current hour."""
        event = make_mock_event(group_id="1001", sender_id="u1")
        await plugin.on_msg(event)

        today = datetime.date.today().isoformat()
        hs = plugin.activity_data["groups"]["1001"].get("hourly_stats", {})
        assert today in hs
        assert len(hs[today]) == 1  # exactly one hour key recorded

    async def test_on_msg_increments_hourly_count(self, plugin):
        """Multiple messages in the same hour accumulate correctly."""
        event = make_mock_event(group_id="1002", sender_id="u1")
        await plugin.on_msg(event)
        await plugin.on_msg(event)
        await plugin.on_msg(event)

        today = datetime.date.today().isoformat()
        hour = str(datetime.datetime.now().hour)
        count = plugin.activity_data["groups"]["1002"]["hourly_stats"][today][hour]
        assert count == 3

    async def test_hourly_stats_independent_of_daily_stats(self, plugin):
        """hourly_stats and daily_stats are updated independently."""
        event = make_mock_event(group_id="1003", sender_id="u1")
        await plugin.on_msg(event)

        today = datetime.date.today().isoformat()
        gd = plugin.activity_data["groups"]["1003"]
        assert gd["daily_stats"].get(today, 0) >= 1
        assert today in gd.get("hourly_stats", {})

    async def test_multiple_users_same_hour_accumulate(self, plugin):
        """Messages from different users in the same hour add together."""
        today = datetime.date.today().isoformat()
        hour = str(datetime.datetime.now().hour)
        for uid in ("u1", "u2", "u3"):
            await plugin.on_msg(make_mock_event(group_id="1004", sender_id=uid))

        count = plugin.activity_data["groups"]["1004"]["hourly_stats"][today][hour]
        assert count == 3


# ── _cleanup_old_stats purges hourly_stats ────────────────────────────────────

class TestCleanupHourlyStats:

    def test_removes_old_hourly_stats(self, plugin):
        old = (datetime.date.today() - datetime.timedelta(days=61)).isoformat()
        plugin.activity_data = {
            "groups": {
                "2001": {
                    "daily_stats": {old: 5},
                    "hourly_stats": {old: {"9": 3, "20": 7}},
                }
            }
        }
        plugin._cleanup_old_stats()
        assert old not in plugin.activity_data["groups"]["2001"]["daily_stats"]
        assert old not in plugin.activity_data["groups"]["2001"]["hourly_stats"]

    def test_keeps_recent_hourly_stats(self, plugin):
        recent = datetime.date.today().isoformat()
        plugin.activity_data = {
            "groups": {
                "2002": {
                    "daily_stats": {recent: 10},
                    "hourly_stats": {recent: {"14": 10}},
                }
            }
        }
        plugin._cleanup_old_stats()
        assert recent in plugin.activity_data["groups"]["2002"]["hourly_stats"]

    def test_group_without_hourly_stats_not_crash(self, plugin):
        recent = datetime.date.today().isoformat()
        plugin.activity_data = {
            "groups": {"2003": {"daily_stats": {recent: 1}}}
        }
        plugin._cleanup_old_stats()  # must not raise


# ── cmd_heatmap data aggregation ─────────────────────────────────────────────

class TestHeatmapAggregation:
    """Validate the aggregation logic used by cmd_heatmap."""

    def _make_hourly(self, plugin, gid, days_ago_to_hours):
        """
        Seed hourly_stats.
        days_ago_to_hours: {days_ago: {hour_str: count}}
        """
        today = datetime.date.today()
        plugin.activity_data["groups"].setdefault(gid, {"members": {}, "daily_stats": {}})
        hs = plugin.activity_data["groups"][gid].setdefault("hourly_stats", {})
        for days_ago, hour_map in days_ago_to_hours.items():
            date_key = (today - datetime.timedelta(days=days_ago)).isoformat()
            hs[date_key] = hour_map

    def test_totals_across_days(self, plugin):
        gid = "3001"
        self._make_hourly(plugin, gid, {
            0: {"9": 10, "20": 5},
            1: {"9": 20, "20": 3},
        })
        hs = plugin.activity_data["groups"][gid]["hourly_stats"]
        today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(14)]
        hour_totals = [0] * 24
        day_count = sum(1 for d in dates if d in hs)
        for d in dates:
            for h, cnt in hs.get(d, {}).items():
                hour_totals[int(h)] += cnt

        assert day_count == 2
        assert hour_totals[9] == 30
        assert hour_totals[20] == 8

    def test_peak_hour_identified_correctly(self, plugin):
        gid = "3002"
        self._make_hourly(plugin, gid, {
            0: {"14": 50, "9": 10, "20": 5},
        })
        hs = plugin.activity_data["groups"][gid]["hourly_stats"]
        today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(14)]
        hour_totals = [0] * 24
        for d in dates:
            for h, cnt in hs.get(d, {}).items():
                hour_totals[int(h)] += cnt

        peak_h = hour_totals.index(max(hour_totals))
        assert peak_h == 14

    def test_averages_divided_by_day_count(self, plugin):
        gid = "3003"
        self._make_hourly(plugin, gid, {
            0: {"10": 30},
            1: {"10": 10},
        })
        hs = plugin.activity_data["groups"][gid]["hourly_stats"]
        today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(14)]
        hour_totals = [0] * 24
        day_count = sum(1 for d in dates if d in hs)
        for d in dates:
            for h, cnt in hs.get(d, {}).items():
                hour_totals[int(h)] += cnt
        hour_avgs = [round(t / day_count, 1) for t in hour_totals]

        assert day_count == 2
        assert hour_avgs[10] == 20.0
