"""
Tests for the /群氛围 (group vibe) feature:
  - _calc_vibe() metric calculations
  - _calc_vibe() anomaly signal detection
  - _calc_vibe() overall status determination
  - _calc_vibe() 14-day chart generation
  - cmd_vibe() renders image card
  - cmd_vibe() plain fallback on render error
  - cmd_vibe() AI suggestion (enabled / disabled)
  - cmd_vibe() empty data guard
"""
import datetime
import time
import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_mock_event, make_config


@pytest.fixture
def plugin(tmp_path):
    return make_plugin(tmp_path=str(tmp_path))


def _seed_daily_stats(plugin, gid, offsets_and_counts):
    """Seed daily_stats for a group.

    offsets_and_counts: list of (days_ago, count) tuples.
    """
    today = datetime.date.today()
    gs = plugin.activity_data.setdefault("groups", {}).setdefault(gid, {})
    ds = gs.setdefault("daily_stats", {})
    for days_ago, count in offsets_and_counts:
        d = (today - datetime.timedelta(days=days_ago)).isoformat()
        ds[d] = count


def _seed_members(plugin, gid, members):
    """Seed member records.

    members: list of (uid, last_active_date) tuples.
    """
    today = datetime.date.today()
    gs = plugin.activity_data.setdefault("groups", {}).setdefault(gid, {})
    ms = gs.setdefault("members", {})
    for uid, last_active_date in members:
        ms[str(uid)] = {
            "last_active": int(time.time()),
            "warned_at": None,
            "nickname": f"User{uid}",
            "join_time": int(time.time()) - 30 * 86400,
            "role": "member",
            "streak": 1,
            "last_active_date": last_active_date,
        }


# ── _calc_vibe unit tests ─────────────────────────────────────────────────────

class TestCalcVibeMetrics:

    def test_message_counts_this_and_last_week(self, plugin):
        """this_week_msgs and last_week_msgs sum correctly."""
        import astrbot_plugin_group_activity.main as m
        gid = "100"
        # This week: days 0-6 = 10 msgs each = 70 total
        this_week = [(i, 10) for i in range(7)]
        # Last week: days 7-13 = 5 msgs each = 35 total
        last_week = [(i, 5) for i in range(7, 14)]
        _seed_daily_stats(plugin, gid, this_week + last_week)
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["this_week_msgs"] == 70
        assert result["last_week_msgs"] == 35

    def test_msg_delta_positive_growth(self, plugin):
        """msg_delta is positive when this week > last week."""
        import astrbot_plugin_group_activity.main as m
        gid = "101"
        _seed_daily_stats(plugin, gid, [(i, 20) for i in range(7)] + [(i, 10) for i in range(7, 14)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["msg_delta"] == 100  # 140 vs 70 = +100%

    def test_msg_delta_zero_when_both_zero(self, plugin):
        """msg_delta is 0 when both weeks have 0 messages."""
        import astrbot_plugin_group_activity.main as m
        gid = "102"
        plugin.activity_data.setdefault("groups", {})[gid] = {"members": {"1": {
            "last_active": int(time.time()), "warned_at": None, "nickname": "U",
            "join_time": int(time.time()), "role": "member", "streak": 0,
            "last_active_date": "2020-01-01",
        }}, "daily_stats": {}}

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["msg_delta"] == 0

    def test_active_member_count_this_week(self, plugin):
        """this_week_active counts members active in last 7 days."""
        import astrbot_plugin_group_activity.main as m
        gid = "103"
        today = datetime.date.today().isoformat()
        three_days_ago = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        twenty_days_ago = (datetime.date.today() - datetime.timedelta(days=20)).isoformat()
        _seed_members(plugin, gid, [
            ("1", today),           # active this week
            ("2", three_days_ago),  # active this week
            ("3", twenty_days_ago), # not active this week
        ])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["this_week_active"] == 2

    def test_silent_pct_calculation(self, plugin):
        """silent_pct = (total - this_active) / total * 100."""
        import astrbot_plugin_group_activity.main as m
        gid = "104"
        today = datetime.date.today().isoformat()
        old_date = "2020-01-01"
        # 4 members, 1 active this week → 75% silent
        _seed_members(plugin, gid, [
            ("1", today),
            ("2", old_date),
            ("3", old_date),
            ("4", old_date),
        ])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["silent_pct"] == 75

    def test_chart_has_14_entries(self, plugin):
        """chart always contains exactly 14 data points."""
        import astrbot_plugin_group_activity.main as m
        gid = "105"
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert len(result["chart"]) == 14

    def test_chart_labels_are_day_of_month(self, plugin):
        """chart labels are 2-digit day strings."""
        import astrbot_plugin_group_activity.main as m
        gid = "106"
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        for entry in result["chart"]:
            assert len(entry["label"]) == 2  # e.g. "01", "28"
            assert entry["label"].isdigit()

    def test_chart_entries_have_required_keys(self, plugin):
        """Each chart entry contains height_px, count, color, label, highlight."""
        import astrbot_plugin_group_activity.main as m
        gid = "107"
        _seed_daily_stats(plugin, gid, [(i, 10) for i in range(14)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        for entry in result["chart"]:
            assert "height_px" in entry
            assert "count" in entry
            assert "color" in entry
            assert "label" in entry
            assert "highlight" in entry

    def test_chart_height_px_proportional_to_max(self, plugin):
        """The day with the highest count gets the maximum height_px."""
        import astrbot_plugin_group_activity.main as m
        gid = "108"
        # Today = max, all others much smaller
        _seed_daily_stats(plugin, gid, [(0, 100), (1, 10), (2, 5)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        heights = [e["height_px"] for e in result["chart"]]
        max_height = max(heights)
        # Today's bar should be tallest
        assert result["chart"][-1]["height_px"] == max_height

    def test_chart_zero_days_have_small_height(self, plugin):
        """Days with 0 messages get a stub bar (height_px == 3)."""
        import astrbot_plugin_group_activity.main as m
        gid = "109"
        # Only today has messages
        _seed_daily_stats(plugin, gid, [(0, 50)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        zero_entries = [e for e in result["chart"] if e["count"] == 0]
        for entry in zero_entries:
            assert entry["height_px"] == 3


class TestCalcVibeSignals:

    def test_signal_full_silence_when_this_week_zero(self, plugin):
        """Detects 群聊完全冷场 when this week is 0 and last week > 0."""
        import astrbot_plugin_group_activity.main as m
        gid = "200"
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7, 14)])
        _seed_members(plugin, gid, [("1", "2020-01-01")])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        titles = [s["title"] for s in result["signals"]]
        assert any("冷场" in t for t in titles)

    def test_signal_sharp_drop_at_50pct(self, plugin):
        """Detects 消息量骤降 when drop >= 50%."""
        import astrbot_plugin_group_activity.main as m
        gid = "201"
        # this week: 10, last week: 100 → -90%
        _seed_daily_stats(plugin, gid,
            [(i, 1) for i in range(7)] + [(i, 10) for i in range(7, 14)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        titles = [s["title"] for s in result["signals"]]
        assert any("骤降" in t for t in titles)

    def test_signal_ok_when_no_issues(self, plugin):
        """Reports 群氛围良好 when no anomalies detected."""
        import astrbot_plugin_group_activity.main as m
        gid = "202"
        # Stable week-over-week
        _seed_daily_stats(plugin, gid,
            [(i, 10) for i in range(7)] + [(i, 10) for i in range(7, 14)])
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [
            (str(i), today) for i in range(5)
        ])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        titles = [s["title"] for s in result["signals"]]
        assert any("良好" in t for t in titles)

    def test_signal_explosion_at_200pct(self, plugin):
        """Detects 消息量暴增 when growth >= 200%."""
        import astrbot_plugin_group_activity.main as m
        gid = "203"
        # this week: 300, last week: 10 → +2900%
        _seed_daily_stats(plugin, gid,
            [(i, 30) for i in range(7)] + [(i, 1) for i in range(7, 14)])
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        titles = [s["title"] for s in result["signals"]]
        assert any("暴增" in t for t in titles)


class TestCalcVibeStatus:

    def test_status_danger_on_full_silence(self, plugin):
        """status = 'danger' when group has members but zero messages this week."""
        import astrbot_plugin_group_activity.main as m
        gid = "300"
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7, 14)])
        _seed_members(plugin, gid, [("1", "2020-01-01")])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["status"] == "danger"

    def test_status_ok_on_normal_activity(self, plugin):
        """status = 'ok' when everything is stable."""
        import astrbot_plugin_group_activity.main as m
        gid = "301"
        today = datetime.date.today().isoformat()
        _seed_daily_stats(plugin, gid,
            [(i, 10) for i in range(7)] + [(i, 10) for i in range(7, 14)])
        _seed_members(plugin, gid, [(str(i), today) for i in range(5)])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        assert result["status"] == "ok"

    def test_result_contains_required_keys(self, plugin):
        """_calc_vibe() always returns all required template keys."""
        import astrbot_plugin_group_activity.main as m
        gid = "302"
        _seed_members(plugin, gid, [("1", datetime.date.today().isoformat())])

        result = m.GroupActivityPlugin._calc_vibe(gid, plugin.activity_data)

        required = {
            "group_name", "date_range", "total_members",
            "this_week_msgs", "last_week_msgs", "msg_delta", "msg_color",
            "this_week_active", "last_week_active", "active_delta", "active_color",
            "this_silent", "last_week_silent", "silent_pct", "silent_delta", "silent_color",
            "status", "status_icon", "status_label", "status_desc",
            "status_color", "status_bg",
            "signals", "chart", "suggestion",
        }
        assert required.issubset(result.keys())


# ── cmd_vibe command tests ────────────────────────────────────────────────────

class TestCmdVibe:

    async def test_renders_image_on_success(self, plugin):
        """cmd_vibe yields image_result when rendering succeeds."""
        gid = "400"
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [("1", today)])
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7)])

        plugin._img = AsyncMock(return_value=b"PNG")
        event = make_mock_event(gid, "1", "User1")
        results = [r async for r in plugin.cmd_vibe(event)]

        assert len(results) == 1
        plugin._img.assert_called_once()

    async def test_plain_fallback_on_render_error(self, plugin):
        """cmd_vibe falls back to plain text when _img raises."""
        gid = "401"
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [("1", today)])
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7)])

        plugin._img = AsyncMock(side_effect=RuntimeError("render fail"))
        event = make_mock_event(gid, "1", "User1")
        results = [r async for r in plugin.cmd_vibe(event)]

        assert len(results) == 1
        # plain_result is called with the fallback text
        call_text = event.plain_result.call_args[0][0]
        assert "群氛围" in call_text or "状态" in call_text or "消息" in call_text

    async def test_empty_data_guard(self, plugin):
        """cmd_vibe returns early message when group has no members."""
        gid = "402"
        plugin.activity_data.setdefault("groups", {})[gid] = {
            "members": {}, "daily_stats": {}
        }
        event = make_mock_event(gid, "1", "User1")
        results = [r async for r in plugin.cmd_vibe(event)]

        assert len(results) == 1
        call_text = event.plain_result.call_args[0][0]
        assert "暂无" in call_text or "数据" in call_text

    async def test_ai_suggestion_appended_when_enabled(self, plugin):
        """When AI is enabled, suggestion is fetched and included in data."""
        import astrbot_plugin_group_activity.main as m
        gid = "403"
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [("1", today)])
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7)])

        plugin.config["ai_enabled"] = True
        plugin._ai = AsyncMock(return_value="多发话题活跃群聊")
        plugin._persona = MagicMock(return_value="傲娇萌妹")

        captured_data = {}

        async def _fake_img(tmpl, data, **kw):
            captured_data.update(data)
            return b"PNG"

        plugin._img = _fake_img
        event = make_mock_event(gid, "1", "User1")
        results = [r async for r in plugin.cmd_vibe(event)]

        assert captured_data.get("suggestion") == "多发话题活跃群聊"

    async def test_ai_suggestion_skipped_when_disabled(self, plugin):
        """When AI is disabled, suggestion remains empty string."""
        gid = "404"
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [("1", today)])
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7)])

        plugin.config["ai_enabled"] = False
        plugin._ai = AsyncMock(return_value="should not be called")

        captured_data = {}

        async def _fake_img(tmpl, data, **kw):
            captured_data.update(data)
            return b"PNG"

        plugin._img = _fake_img
        event = make_mock_event(gid, "1", "User1")
        [r async for r in plugin.cmd_vibe(event)]

        plugin._ai.assert_not_called()
        assert captured_data.get("suggestion") == ""

    async def test_ai_failure_does_not_crash_command(self, plugin):
        """AI suggestion error is caught and command still renders."""
        gid = "405"
        today = datetime.date.today().isoformat()
        _seed_members(plugin, gid, [("1", today)])
        _seed_daily_stats(plugin, gid, [(i, 5) for i in range(7)])

        plugin.config["ai_enabled"] = True
        plugin._ai = AsyncMock(side_effect=RuntimeError("AI down"))
        plugin._persona = MagicMock(return_value="傲娇萌妹")
        plugin._img = AsyncMock(return_value=b"PNG")

        event = make_mock_event(gid, "1", "User1")
        results = [r async for r in plugin.cmd_vibe(event)]

        # Should still yield one image result despite AI failure
        assert len(results) == 1
        plugin._img.assert_called_once()
