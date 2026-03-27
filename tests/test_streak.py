"""
Tests for the consecutive-active-days (streak) logic embedded in on_msg,
plus related message-tracking side effects.
"""
import time
import datetime
import pytest
from helpers import make_mock_event


def _seed_member(plugin, gid, uid, streak, last_active_date, warned_at=None):
    """Seed a single member entry in activity_data."""
    if gid not in plugin.activity_data["groups"]:
        plugin.activity_data["groups"][gid] = {"members": {}, "daily_stats": {}}
    plugin.activity_data["groups"][gid]["members"][str(uid)] = {
        "last_active": int(time.time()) - 86400,
        "warned_at": warned_at,
        "nickname": f"User{uid}",
        "join_time": int(time.time()) - 30 * 86400,
        "role": "member",
        "streak": streak,
        "last_active_date": last_active_date,
    }


# ── streak calculation ────────────────────────────────────────────────────────

class TestStreak:

    async def test_streak_unchanged_for_same_day(self, plugin):
        """Second message on the same day keeps streak the same."""
        today = datetime.date.today().isoformat()
        _seed_member(plugin, "12345", "1001", streak=5, last_active_date=today)

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["streak"] == 5

    async def test_streak_increments_on_consecutive_day(self, plugin):
        """First message the day after the last active date increments streak."""
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        _seed_member(plugin, "12345", "1001", streak=3, last_active_date=yesterday)

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["streak"] == 4

    async def test_streak_resets_after_gap(self, plugin):
        """A gap of more than one day resets streak to 1."""
        two_days_ago = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        _seed_member(plugin, "12345", "1001", streak=10, last_active_date=two_days_ago)

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["streak"] == 1

    async def test_streak_resets_after_long_absence(self, plugin):
        """A gap of 30 days also resets streak to 1."""
        old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        _seed_member(plugin, "12345", "1001", streak=99, last_active_date=old_date)

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["streak"] == 1

    async def test_streak_starts_at_1_for_new_member(self, plugin):
        """Brand-new member (no prior record) gets streak=1 on first message."""
        plugin.activity_data["groups"]["12345"] = {"members": {}, "daily_stats": {}}

        event = make_mock_event("12345", "2001", "NewUser")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["2001"]["streak"] == 1


# ── warned_at cleared by message ─────────────────────────────────────────────

class TestWarnedAtClear:

    async def test_sending_message_clears_warned_at(self, plugin):
        """on_msg always sets warned_at=None (clears any pending warning)."""
        now = int(time.time())
        _seed_member(plugin, "12345", "1001", streak=0,
                     last_active_date="", warned_at=now - 3600)

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        member = plugin.activity_data["groups"]["12345"]["members"]["1001"]
        assert member["warned_at"] is None

    async def test_last_active_updated_to_now(self, plugin):
        """on_msg updates last_active to approximately now."""
        _seed_member(plugin, "12345", "1001", streak=0, last_active_date="")

        before = int(time.time())
        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass
        after = int(time.time())

        la = plugin.activity_data["groups"]["12345"]["members"]["1001"]["last_active"]
        assert before <= la <= after

    async def test_last_active_date_set_to_today(self, plugin):
        """on_msg records today's ISO date in last_active_date."""
        _seed_member(plugin, "12345", "1001", streak=0, last_active_date="1970-01-01")

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        today = datetime.date.today().isoformat()
        member = plugin.activity_data["groups"]["12345"]["members"]["1001"]
        assert member["last_active_date"] == today


# ── daily stats counter ───────────────────────────────────────────────────────

class TestDailyStats:

    async def test_daily_stats_incremented(self, plugin):
        """Each message increments the daily_stats counter for today."""
        plugin.activity_data["groups"]["12345"] = {"members": {}, "daily_stats": {}}

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass
        async for _ in plugin.on_msg(event): pass

        today = datetime.date.today().isoformat()
        count = plugin.activity_data["groups"]["12345"]["daily_stats"][today]
        assert count == 2

    async def test_new_group_initialised_on_first_message(self, plugin):
        """First message in an unknown group creates the group entry."""
        assert "99999" not in plugin.activity_data["groups"]

        event = make_mock_event("99999", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert "99999" in plugin.activity_data["groups"]
        assert "1001" in plugin.activity_data["groups"]["99999"]["members"]

    async def test_join_time_preserved_for_existing_member(self, plugin):
        """on_msg does not overwrite join_time for an existing member."""
        original_join = int(time.time()) - 90 * 86400
        _seed_member(plugin, "12345", "1001", streak=0, last_active_date="")
        plugin.activity_data["groups"]["12345"]["members"]["1001"]["join_time"] = original_join

        event = make_mock_event("12345", "1001", "User1001")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["join_time"] == original_join

    async def test_nickname_updated_on_message(self, plugin):
        """on_msg updates the stored nickname to match the latest event."""
        _seed_member(plugin, "12345", "1001", streak=0, last_active_date="")
        plugin.activity_data["groups"]["12345"]["members"]["1001"]["nickname"] = "OldName"

        event = make_mock_event("12345", "1001", "NewName")
        async for _ in plugin.on_msg(event): pass

        assert plugin.activity_data["groups"]["12345"]["members"]["1001"]["nickname"] == "NewName"
