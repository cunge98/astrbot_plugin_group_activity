"""
Tests for command handler methods:
  cmd_help, cmd_status, cmd_rank, cmd_query, cmd_inactive,
  cmd_weekly, cmd_stats, cmd_trend, cmd_manual, cmd_init, cmd_clear

All handlers are async generators; results are collected with _collect().
"""
import time
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from helpers import make_plugin, make_mock_event, make_config, make_mock_client


# ── helpers ───────────────────────────────────────────────────────────────────

async def _collect(gen):
    """Drive an async-generator command and return the list of yielded results."""
    results = []
    async for r in gen:
        results.append(r)
    return results


def _make_event(gid="12345", sid="u1", name="Alice"):
    e = make_mock_event(gid, sid, name)
    e.image_result = MagicMock(side_effect=lambda x: f"img:{x!r}")
    e.plain_result = MagicMock(side_effect=lambda x: f"plain:{x}")
    return e


def _seed_group(plugin, gid="12345", n_members=3):
    """Seed plugin with a group containing `n_members` members."""
    now = int(time.time())
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    plugin.activity_data["groups"][gid] = {
        "group_name": "测试群",
        "members": {
            f"u{i}": {
                "last_active": now - i * 86400,
                "warned_at": None,
                "nickname": f"User{i}",
                "join_time": now - 30 * 86400,
                "role": "member",
                "streak": max(0, 5 - i),
                "last_active_date": today if i == 0 else yesterday,
            }
            for i in range(n_members)
        },
        "daily_stats": {
            (datetime.date.today() - datetime.timedelta(days=j)).isoformat(): 10 + j
            for j in range(14)
        },
    }


# ── cmd_help ──────────────────────────────────────────────────────────────────

class TestCmdHelp:

    async def test_yields_image_result(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event()
        results = await _collect(plugin.cmd_help(event))
        assert results
        event.image_result.assert_called_once()

    async def test_falls_back_to_plain_on_render_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(side_effect=RuntimeError("render error"))
        event = _make_event()
        results = await _collect(plugin.cmd_help(event))
        assert results
        event.plain_result.assert_called_once()
        call_text = event.plain_result.call_args[0][0]
        # Should mention some commands
        assert "/" in call_text


# ── cmd_status ────────────────────────────────────────────────────────────────

class TestCmdStatus:

    async def test_yields_image_result(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event()
        results = await _collect(plugin.cmd_status(event))
        assert results
        event.image_result.assert_called_once()

    async def test_falls_back_to_plain_on_render_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(side_effect=RuntimeError("render error"))
        event = _make_event()
        results = await _collect(plugin.cmd_status(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_counts_warned_members(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        now = int(time.time())
        # Mark one member as warned
        plugin.activity_data["groups"]["12345"]["members"]["u2"]["warned_at"] = now - 3600
        captured_data = {}

        async def fake_img(tmpl, data, **kw):
            captured_data.update(data)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_status(event))
        assert captured_data.get("tw") == 1


# ── cmd_rank ──────────────────────────────────────────────────────────────────

class TestCmdRank:

    async def test_no_data_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event(gid="99999")
        results = await _collect(plugin.cmd_rank(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_with_data_yields_image(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        event = _make_event()
        results = await _collect(plugin.cmd_rank(event))
        assert results
        event.image_result.assert_called_once()

    async def test_members_sorted_by_last_active(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin, n_members=5)
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_rank(event))
        members = captured.get("ms", [])
        assert members
        # First member should be rank 1 (most recently active)
        assert members[0]["i"] == 1

    async def test_render_failure_yields_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        plugin._img = AsyncMock(side_effect=RuntimeError("render error"))
        event = _make_event()
        results = await _collect(plugin.cmd_rank(event))
        assert results
        event.plain_result.assert_called_once()


# ── cmd_query ─────────────────────────────────────────────────────────────────

class TestCmdQuery:

    async def test_no_member_data_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event(gid="12345", sid="nobody")
        results = await _collect(plugin.cmd_query(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_found_member_yields_image(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        event = _make_event(gid="12345", sid="u0")
        results = await _collect(plugin.cmd_query(event))
        assert results
        event.image_result.assert_called_once()

    async def test_warned_member_shows_remaining_time(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        now = int(time.time())
        plugin.activity_data["groups"]["12345"]["members"]["u0"]["warned_at"] = now - 3600
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"img"

        plugin._img = fake_img
        event = _make_event(gid="12345", sid="u0")
        await _collect(plugin.cmd_query(event))
        assert captured.get("wa") is True
        assert captured.get("rem", "") != ""

    async def test_render_failure_yields_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        plugin._img = AsyncMock(side_effect=RuntimeError("render error"))
        event = _make_event(gid="12345", sid="u0")
        results = await _collect(plugin.cmd_query(event))
        assert results
        event.plain_result.assert_called_once()


# ── cmd_inactive ──────────────────────────────────────────────────────────────

class TestCmdInactive:

    async def test_no_data_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event(gid="empty_group")
        results = await _collect(plugin.cmd_inactive(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_no_inactive_members_yields_all_ok(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        today = datetime.date.today().isoformat()
        plugin.activity_data["groups"]["12345"] = {
            "members": {
                "u1": {"last_active": now - 3600, "warned_at": None,
                       "nickname": "ActiveUser", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 3, "last_active_date": today},
            },
            "daily_stats": {},
        }
        captured_templates = []

        async def fake_img(tmpl_fn, data, **kw):
            captured_templates.append(tmpl_fn)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_inactive(event))
        import astrbot_plugin_group_activity.main as m
        assert any(fn == m.T.ALL_OK for fn in captured_templates)

    async def test_has_inactive_members_yields_inactive_list(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        plugin.activity_data["groups"]["12345"] = {
            "members": {
                "u1": {"last_active": now - 10 * 86400, "warned_at": None,
                       "nickname": "InactiveUser", "join_time": now - 90 * 86400,
                       "role": "member", "streak": 0, "last_active_date": ""},
            },
            "daily_stats": {},
        }
        captured_templates = []

        async def fake_img(tmpl_fn, data, **kw):
            captured_templates.append(tmpl_fn)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_inactive(event))
        import astrbot_plugin_group_activity.main as m
        assert any(fn == m.T.INACTIVE for fn in captured_templates)


# ── cmd_weekly ────────────────────────────────────────────────────────────────

class TestCmdWeekly:

    async def test_ai_disabled_yields_error_plain(self, tmp_path):
        cfg = make_config(ai_enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = _make_event()
        results = await _collect(plugin.cmd_weekly(event))
        assert results
        event.plain_result.assert_called()
        text = event.plain_result.call_args_list[0][0][0]
        assert "AI" in text or "❌" in text

    async def test_ai_enabled_yields_image(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        _seed_group(plugin)
        plugin._ai = AsyncMock(return_value="短评文字")
        event = _make_event()
        results = await _collect(plugin.cmd_weekly(event))
        assert results
        event.image_result.assert_called_once()

    async def test_weekly_yields_loading_message_first(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        _seed_group(plugin)
        plugin._ai = AsyncMock(return_value="")
        event = _make_event()
        results = await _collect(plugin.cmd_weekly(event))
        # First yielded result should be the "loading..." plain message
        assert len(results) >= 2
        assert event.plain_result.call_args_list[0][0][0].startswith("正在")


# ── cmd_stats ─────────────────────────────────────────────────────────────────

class TestCmdStats:

    async def test_no_data_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event(gid="empty_group")
        results = await _collect(plugin.cmd_stats(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_with_data_yields_image(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        event = _make_event()
        results = await _collect(plugin.cmd_stats(event))
        assert results
        event.image_result.assert_called_once()

    async def test_data_includes_activity_distribution(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin, n_members=4)
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_stats(event))
        # Should have activity distribution fields
        assert "d1" in captured
        assert "total" in captured
        assert captured["total"] == 4


# ── cmd_trend ─────────────────────────────────────────────────────────────────

class TestCmdTrend:

    async def test_no_daily_stats_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin.activity_data["groups"]["12345"] = {"members": {}, "daily_stats": {}}
        event = _make_event()
        results = await _collect(plugin.cmd_trend(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_with_data_yields_image(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        event = _make_event()
        results = await _collect(plugin.cmd_trend(event))
        assert results
        event.image_result.assert_called_once()

    async def test_trend_data_has_14_entries(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        _seed_group(plugin)
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"img"

        plugin._img = fake_img
        event = _make_event()
        await _collect(plugin.cmd_trend(event))
        assert captured.get("days") == 14
        assert len(captured.get("data", [])) == 14


# ── cmd_manual ────────────────────────────────────────────────────────────────

class TestCmdManual:

    async def test_disabled_yields_error(self, tmp_path):
        cfg = make_config(enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = _make_event()
        results = await _collect(plugin.cmd_manual(event))
        assert results

    async def test_enabled_runs_check_and_yields_result(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._check_all = AsyncMock()
        event = _make_event()
        results = await _collect(plugin.cmd_manual(event))
        assert results
        plugin._check_all.assert_called_once()
        # Should yield loading message + result image
        assert len(results) >= 2


# ── cmd_clear ─────────────────────────────────────────────────────────────────

class TestCmdClear:

    async def test_no_data_returns_plain(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = _make_event(gid="empty")
        results = await _collect(plugin.cmd_clear(event))
        assert results
        event.plain_result.assert_called_once()

    async def test_clears_all_warnings(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        plugin.activity_data["groups"]["12345"] = {
            "members": {
                "u1": {"last_active": now, "warned_at": now - 3600,
                       "nickname": "Alice", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 0, "last_active_date": ""},
                "u2": {"last_active": now, "warned_at": now - 7200,
                       "nickname": "Bob", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 0, "last_active_date": ""},
            }
        }
        event = _make_event()
        await _collect(plugin.cmd_clear(event))
        ms = plugin.activity_data["groups"]["12345"]["members"]
        assert ms["u1"]["warned_at"] is None
        assert ms["u2"]["warned_at"] is None

    async def test_clears_specific_member_warning(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        plugin.activity_data["groups"]["12345"] = {
            "members": {
                "u1": {"last_active": now, "warned_at": now - 3600,
                       "nickname": "Alice", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 0, "last_active_date": ""},
                "u2": {"last_active": now, "warned_at": now - 3600,
                       "nickname": "Bob", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 0, "last_active_date": ""},
            }
        }
        event = _make_event()
        # Clear only u1's warning
        event.get_sender_id.return_value = "u1"
        await _collect(plugin.cmd_clear(event, tid="u1"))
        ms = plugin.activity_data["groups"]["12345"]["members"]
        assert ms["u1"]["warned_at"] is None
        # u2 still warned
        assert ms["u2"]["warned_at"] is not None

    async def test_clear_unknown_tid_returns_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        plugin.activity_data["groups"]["12345"] = {
            "members": {
                "u1": {"last_active": now, "warned_at": None,
                       "nickname": "Alice", "join_time": now,
                       "role": "member", "streak": 0, "last_active_date": ""},
            }
        }
        event = _make_event()
        results = await _collect(plugin.cmd_clear(event, tid="nonexistent"))
        assert results
        event.plain_result.assert_called_once()
        assert "❌" in event.plain_result.call_args[0][0]


# ── cmd_init ──────────────────────────────────────────────────────────────────

class TestCmdInit:

    async def test_no_client_returns_plain_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._bot_client = None
        plugin.context.get_platform = MagicMock(return_value=None)
        event = _make_event()
        results = await _collect(plugin.cmd_init(event))
        assert results
        # Should yield plain error about client
        plain_calls = [c[0][0] for c in event.plain_result.call_args_list]
        assert any("❌" in t or "bot" in t.lower() or "未获取" in t for t in plain_calls)

    async def test_initialises_members_from_api(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        now = int(time.time())
        member_list = [
            {"user_id": 1001, "card": "AliceCard", "nickname": "alice",
             "role": "member", "last_sent_time": now - 3600, "join_time": now - 30 * 86400},
            {"user_id": 1002, "card": "", "nickname": "bob",
             "role": "member", "last_sent_time": 0, "join_time": now - 10 * 86400},
        ]

        async def _call_action(action, **kwargs):
            if action == "get_group_member_list":
                return member_list
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        event = _make_event()
        await _collect(plugin.cmd_init(event))

        ms = plugin.activity_data.get("groups", {}).get("12345", {}).get("members", {})
        assert "1001" in ms
        assert "1002" in ms
        assert ms["1001"]["nickname"] == "AliceCard"
