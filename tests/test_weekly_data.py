"""
Tests for _weekly_data – the data-aggregation layer behind 群周报.

All AI calls are mocked to return empty strings so the tests focus purely
on the arithmetic and structural correctness of the returned dict.
"""
import time
import datetime
import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock


# ── fixtures / helpers ────────────────────────────────────────────────────────

def _seed(plugin, members, daily_stats=None):
    """Populate activity_data for group '12345'."""
    gid = "12345"
    if daily_stats is None:
        daily_stats = {}
    plugin.activity_data = {
        "groups": {
            gid: {
                "group_name": "测试群",
                "members": members,
                "daily_stats": daily_stats,
            }
        }
    }
    return gid


def _member(uid, last_active_offset_days=1, warned=False, streak=0):
    """Return a member dict with last_active = now - offset_days."""
    now = int(time.time())
    return {
        "last_active": now - last_active_offset_days * 86400,
        "warned_at": (now - 3600) if warned else None,
        "nickname": f"User{uid}",
        "join_time": now - 60 * 86400,
        "role": "member",
        "streak": streak,
        "last_active_date": "",
    }


# ── result structure ──────────────────────────────────────────────────────────

class TestWeeklyDataStructure:

    async def test_contains_all_required_keys(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        members = {"1": _member("1")}
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        required = {
            "date", "style",
            "this_week_msgs", "last_week_msgs", "change_pct",
            "active_count", "total", "warned",
            "chart", "top3", "bot3",
            "ai1", "ai2", "ai3", "ai4",
        }
        assert required.issubset(result.keys())

    async def test_chart_has_exactly_7_entries(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        gid = _seed(plugin, {"1": _member("1")})

        result = await plugin._weekly_data(gid)

        assert len(result["chart"]) == 7

    async def test_chart_entry_has_required_fields(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        gid = _seed(plugin, {"1": _member("1")})

        result = await plugin._weekly_data(gid)

        for entry in result["chart"]:
            assert "label" in entry
            assert "v" in entry
            assert "pct" in entry

    async def test_chart_pct_minimum_is_3(self, plugin):
        """Even zero-message days should have pct >= 3 (visual floor)."""
        plugin._ai = AsyncMock(return_value="")
        gid = _seed(plugin, {"1": _member("1")}, daily_stats={})

        result = await plugin._weekly_data(gid)

        for entry in result["chart"]:
            assert entry["pct"] >= 3


# ── message counting ──────────────────────────────────────────────────────────

class TestMessageCounting:

    def _build_stats(self, this_week_count, last_week_count):
        today = datetime.date.today()
        stats = {}
        for i in range(7):
            stats[(today - datetime.timedelta(days=i)).isoformat()] = this_week_count
        for i in range(7, 14):
            stats[(today - datetime.timedelta(days=i)).isoformat()] = last_week_count
        return stats

    async def test_this_week_vs_last_week_counts(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        stats = self._build_stats(this_week_count=10, last_week_count=5)
        gid = _seed(plugin, {"1": _member("1")}, daily_stats=stats)

        result = await plugin._weekly_data(gid)

        assert result["this_week_msgs"] == 70  # 7 * 10
        assert result["last_week_msgs"] == 35  # 7 * 5

    async def test_change_pct_increase(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        stats = self._build_stats(10, 5)
        gid = _seed(plugin, {"1": _member("1")}, daily_stats=stats)

        result = await plugin._weekly_data(gid)

        # (70-35)/35 * 100 = 100 %
        assert result["change_pct"] == 100

    async def test_change_pct_decrease(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        stats = self._build_stats(this_week_count=5, last_week_count=10)
        gid = _seed(plugin, {"1": _member("1")}, daily_stats=stats)

        result = await plugin._weekly_data(gid)

        # (35-70)/70 * 100 = -50 %
        assert result["change_pct"] == -50

    async def test_change_pct_zero_last_week_with_messages(self, plugin):
        """If last week had 0 messages and this week has some, pct = 100."""
        plugin._ai = AsyncMock(return_value="")
        stats = self._build_stats(this_week_count=5, last_week_count=0)
        gid = _seed(plugin, {"1": _member("1")}, daily_stats=stats)

        result = await plugin._weekly_data(gid)

        assert result["change_pct"] == 100

    async def test_change_pct_both_zero(self, plugin):
        """If both weeks had 0 messages, pct = 0."""
        plugin._ai = AsyncMock(return_value="")
        gid = _seed(plugin, {"1": _member("1")}, daily_stats={})

        result = await plugin._weekly_data(gid)

        assert result["change_pct"] == 0

    async def test_missing_days_default_to_zero(self, plugin):
        """Days with no daily_stats entry count as 0 messages."""
        plugin._ai = AsyncMock(return_value="")
        today = datetime.date.today().isoformat()
        gid = _seed(plugin, {"1": _member("1")},
                    daily_stats={today: 20})   # only today has data

        result = await plugin._weekly_data(gid)

        assert result["this_week_msgs"] == 20


# ── member aggregation ────────────────────────────────────────────────────────

class TestMemberAggregation:

    async def test_total_member_count(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        members = {str(i): _member(str(i)) for i in range(5)}
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        assert result["total"] == 5

    async def test_warned_count(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        members = {
            "1": _member("1", warned=False),
            "2": _member("2", warned=True),
            "3": _member("3", warned=True),
        }
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        assert result["warned"] == 2

    async def test_active_count_within_7_days(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        members = {
            "1": _member("1", last_active_offset_days=1),   # active (1 day)
            "2": _member("2", last_active_offset_days=6),   # active (6 days)
            "3": _member("3", last_active_offset_days=8),   # inactive (8 days)
        }
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        assert result["active_count"] == 2

    async def test_top3_most_recently_active(self, plugin):
        """top3 should be the 3 members with the smallest last_active offset."""
        plugin._ai = AsyncMock(return_value="")
        members = {
            "1": _member("1", last_active_offset_days=1),
            "2": _member("2", last_active_offset_days=2),
            "3": _member("3", last_active_offset_days=3),
            "4": _member("4", last_active_offset_days=20),
        }
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        top_names = {m["n"] for m in result["top3"]}
        assert "User1" in top_names
        assert "User2" in top_names
        assert "User3" in top_names
        assert "User4" not in top_names

    async def test_bot3_most_silent_members(self, plugin):
        """bot3 contains members silent > 3 days, sorted least-active first."""
        plugin._ai = AsyncMock(return_value="")
        members = {
            "1": _member("1", last_active_offset_days=1),    # active – excluded
            "2": _member("2", last_active_offset_days=10),   # silent
            "3": _member("3", last_active_offset_days=20),   # silent
            "4": _member("4", last_active_offset_days=30),   # most silent
        }
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        bot_names = {m["n"] for m in result["bot3"]}
        assert "User1" not in bot_names   # active, not silent
        assert "User4" in bot_names

    async def test_bot3_empty_when_no_silent_members(self, plugin):
        plugin._ai = AsyncMock(return_value="")
        members = {str(i): _member(str(i), last_active_offset_days=1) for i in range(3)}
        gid = _seed(plugin, members)

        result = await plugin._weekly_data(gid)

        assert result["bot3"] == []


# ── AI commentary ─────────────────────────────────────────────────────────────

class TestAiCommentary:

    async def test_four_ai_comments_returned(self, plugin):
        plugin._ai = AsyncMock(return_value="测试评语")
        gid = _seed(plugin, {"1": _member("1")})

        result = await plugin._weekly_data(gid)

        for key in ("ai1", "ai2", "ai3", "ai4"):
            assert result[key] == "测试评语"

    async def test_ai_comment_truncated_at_60_chars(self, plugin):
        plugin._ai = AsyncMock(return_value="X" * 100)
        gid = _seed(plugin, {"1": _member("1")})

        result = await plugin._weekly_data(gid)

        for key in ("ai1", "ai2", "ai3", "ai4"):
            assert len(result[key]) <= 60

    async def test_ai_failure_returns_empty_string(self, plugin):
        plugin._ai = AsyncMock(return_value=None)
        gid = _seed(plugin, {"1": _member("1")})

        result = await plugin._weekly_data(gid)

        for key in ("ai1", "ai2", "ai3", "ai4"):
            assert result[key] == ""

    async def test_ai_exception_returns_empty_string(self, plugin):
        plugin._ai = AsyncMock(side_effect=RuntimeError("oops"))
        gid = _seed(plugin, {"1": _member("1")})

        # Should not raise; each AI call is wrapped in try/except
        result = await plugin._weekly_data(gid)

        for key in ("ai1", "ai2", "ai3", "ai4"):
            assert result[key] == ""
