"""
Tests for the check-in / sign-in feature:
  - daily_checkins data collection in on_msg (first-message-of-day logic)
  - streak title assignment (_streak_title)
  - _cleanup_old_stats purges daily_checkins after 30 days
  - milestone broadcast conditions
"""
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_mock_event


# ── _streak_title ─────────────────────────────────────────────────────────────

class TestStreakTitle:

    def test_new_member(self, plugin):
        assert plugin._streak_title(1) == "🌱 新萌"
        assert plugin._streak_title(2) == "🌱 新萌"

    def test_active(self, plugin):
        assert plugin._streak_title(3) == "🌿 活跃中"
        assert plugin._streak_title(6) == "🌿 活跃中"

    def test_silver(self, plugin):
        assert plugin._streak_title(7) == "🥈 银牌常客"
        assert plugin._streak_title(13) == "🥈 银牌常客"

    def test_gold(self, plugin):
        assert plugin._streak_title(14) == "🥇 金牌驻场"
        assert plugin._streak_title(29) == "🥇 金牌驻场"

    def test_legend(self, plugin):
        assert plugin._streak_title(30) == "👑 传奇守护者"
        assert plugin._streak_title(100) == "👑 传奇守护者"


# ── daily_checkins data collection ───────────────────────────────────────────

class TestCheckinCollection:

    async def test_first_message_registers_checkin(self, plugin):
        """First message of the day adds user to daily_checkins."""
        event = make_mock_event(group_id="5001", sender_id="u1")
        async for _ in plugin.on_msg(event): pass

        today = datetime.date.today().isoformat()
        checkins = plugin.activity_data["groups"]["5001"]["daily_checkins"][today]
        assert "u1" in checkins

    async def test_second_message_does_not_duplicate(self, plugin):
        """Subsequent messages same day don't add duplicate checkin entries."""
        event = make_mock_event(group_id="5002", sender_id="u1")
        async for _ in plugin.on_msg(event): pass
        async for _ in plugin.on_msg(event): pass
        async for _ in plugin.on_msg(event): pass

        today = datetime.date.today().isoformat()
        checkins = plugin.activity_data["groups"]["5002"]["daily_checkins"][today]
        assert checkins.count("u1") == 1

    async def test_checkin_order_preserved(self, plugin):
        """Check-in order reflects order of first messages."""
        for uid in ("u1", "u2", "u3"):
            async for _ in plugin.on_msg(make_mock_event(group_id="5003", sender_id=uid)): pass

        today = datetime.date.today().isoformat()
        checkins = plugin.activity_data["groups"]["5003"]["daily_checkins"][today]
        assert checkins == ["u1", "u2", "u3"]

    async def test_backfill_user_already_active_today(self, plugin):
        """User whose last_active_date is already today (pre-upgrade) is still registered."""
        gid = "5005"
        today = datetime.date.today().isoformat()
        plugin.activity_data["groups"][gid] = {
            "members": {"u1": {"last_active": 0, "last_active_date": today,
                                "streak": 3, "nickname": "Alice", "join_time": 0,
                                "role": "member", "warned_at": None}},
            "daily_stats": {},
            "daily_checkins": {},
        }
        event = make_mock_event(group_id=gid, sender_id="u1")
        async for _ in plugin.on_msg(event): pass

        checkins = plugin.activity_data["groups"][gid]["daily_checkins"].get(today, [])
        assert "u1" in checkins

    async def test_new_day_starts_fresh(self, plugin):
        """Checkins on different days are stored separately."""
        gid = "5004"
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        today = datetime.date.today().isoformat()

        # Pre-seed yesterday's checkin
        plugin.activity_data["groups"][gid] = {
            "members": {},
            "daily_stats": {},
            "daily_checkins": {yesterday: ["u1"]},
        }

        event = make_mock_event(group_id=gid, sender_id="u2")
        async for _ in plugin.on_msg(event): pass

        checkins = plugin.activity_data["groups"][gid]["daily_checkins"]
        assert yesterday in checkins   # yesterday's data still there
        assert today in checkins       # today's data added
        assert "u2" in checkins[today]
        assert "u2" not in checkins[yesterday]


# ── _cleanup_old_stats for daily_checkins ────────────────────────────────────

class TestCheckinCleanup:

    def test_removes_checkins_older_than_30_days(self, plugin):
        old = (datetime.date.today() - datetime.timedelta(days=31)).isoformat()
        plugin.activity_data = {
            "groups": {
                "6001": {"daily_checkins": {old: ["u1", "u2"]}}
            }
        }
        plugin._cleanup_old_stats()
        assert old not in plugin.activity_data["groups"]["6001"]["daily_checkins"]

    def test_keeps_checkins_within_30_days(self, plugin):
        recent = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        plugin.activity_data = {
            "groups": {
                "6002": {"daily_checkins": {recent: ["u1"]}}
            }
        }
        plugin._cleanup_old_stats()
        assert recent in plugin.activity_data["groups"]["6002"]["daily_checkins"]

    def test_daily_stats_still_kept_60_days(self, plugin):
        """daily_stats uses 60-day cutoff; daily_checkins uses 30-day cutoff."""
        day45 = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
        plugin.activity_data = {
            "groups": {
                "6003": {
                    "daily_stats": {day45: 10},
                    "daily_checkins": {day45: ["u1"]},
                }
            }
        }
        plugin._cleanup_old_stats()
        gd = plugin.activity_data["groups"]["6003"]
        # 45 days: kept in daily_stats (60d cutoff), removed from daily_checkins (30d cutoff)
        assert day45 in gd["daily_stats"]
        assert day45 not in gd.get("daily_checkins", {})


# ── milestone broadcast trigger ──────────────────────────────────────────────

class TestMilestoneBroadcast:

    async def test_milestone_fires_at_7_days(self, plugin):
        """Streak of 7 on first message of the day triggers milestone."""
        gid = "7001"
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        plugin.activity_data["groups"][gid] = {
            "members": {
                "u1": {"last_active": 0, "warned_at": None, "nickname": "Alice",
                       "join_time": 0, "role": "member",
                       "streak": 6, "last_active_date": yesterday}
            },
            "daily_stats": {},
        }
        plugin.config["enabled"] = True
        plugin._announce_milestone = AsyncMock()

        created_tasks = []
        def fake_create_task(coro, **kw):
            created_tasks.append(coro)
            if hasattr(coro, "close"):
                coro.close()
            return MagicMock()

        with patch("asyncio.create_task", side_effect=fake_create_task):
            async for _ in plugin.on_msg(make_mock_event(group_id=gid, sender_id="u1")): pass

        # streak should now be 7; milestone should have been scheduled
        streak = plugin.activity_data["groups"][gid]["members"]["u1"]["streak"]
        assert streak == 7
        assert len(created_tasks) >= 1

    async def test_milestone_does_not_fire_for_non_milestone_streak(self, plugin):
        """Streak of 5 does not trigger milestone."""
        gid = "7002"
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        plugin.activity_data["groups"][gid] = {
            "members": {
                "u1": {"last_active": 0, "warned_at": None, "nickname": "Bob",
                       "join_time": 0, "role": "member",
                       "streak": 4, "last_active_date": yesterday}
            },
            "daily_stats": {},
        }
        plugin.config["enabled"] = True

        created_tasks = []
        def fake_create_task(coro, **kw):
            created_tasks.append(coro)
            if hasattr(coro, "close"):
                coro.close()
            return MagicMock()

        with patch("asyncio.create_task", side_effect=fake_create_task):
            async for _ in plugin.on_msg(make_mock_event(group_id=gid, sender_id="u1")): pass

        streak = plugin.activity_data["groups"][gid]["members"]["u1"]["streak"]
        assert streak == 5
        assert len(created_tasks) == 0


# ── CHECKIN template ─────────────────────────────────────────────────────────

class TestCheckinTemplate:
    import astrbot_plugin_group_activity.templates as T
    ALL_THEMES = ["清新蓝", "活力橙", "优雅紫", "暗夜模式"]

    @pytest.mark.parametrize("theme", ["清新蓝", "活力橙", "优雅紫", "暗夜模式"])
    def test_returns_html(self, theme):
        import astrbot_plugin_group_activity.templates as T
        result = T.CHECKIN(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ["清新蓝", "活力橙", "优雅紫", "暗夜模式"])
    def test_contains_checkin_sections(self, theme):
        import astrbot_plugin_group_activity.templates as T
        result = T.CHECKIN(theme)
        assert "今日打卡榜" in result
        assert "连续活跃称号" in result
        assert "今日已打卡" in result
