"""
Tests for on_msg() behaviors beyond streak/daily-stats:
  - appeal task is created when warned member @mentions bot with ai_appeal=True
  - no appeal task when ai_appeal=False
  - no appeal task when member is not warned
  - no appeal task when bot_self_id is not set
  - group_name is stored when event carries it
  - _appeal() sends approval when AI judge returns True
  - _appeal() sends rejection when AI judge returns False
  - _appeal() handles AI exception gracefully
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_mock_event, make_config


# ── helpers ───────────────────────────────────────────────────────────────────

class _FakeAt:
    """Minimal stand-in for Comp.At that passes isinstance() checks."""
    def __init__(self, qq):
        self.qq = qq


def _make_warned_event(plugin, gid, sid, nick, bot_id, mention_bot=True):
    """Seed a warned member and return an event that optionally @mentions the bot."""
    import astrbot_plugin_group_activity.main as m

    now = int(time.time())
    plugin.activity_data["groups"][gid] = {
        "members": {
            sid: {
                "last_active": now - 86400,
                "warned_at": now - 3600,
                "nickname": nick,
                "join_time": now - 30 * 86400,
                "role": "member",
                "streak": 0,
                "last_active_date": "",
            }
        },
        "daily_stats": {},
    }
    plugin._bot_self_id = bot_id

    event = make_mock_event(gid, sid, nick, message_str="请给我一次机会！")
    event.message_obj.self_id = bot_id

    # Patch Comp.At to our real class so isinstance() works in on_msg
    m.Comp.At = _FakeAt

    if mention_bot:
        event.message_obj.message = [_FakeAt(bot_id)]
    else:
        event.message_obj.message = []

    return event


# ── appeal task creation via on_msg ──────────────────────────────────────────

class TestAppealTaskCreation:

    async def test_appeal_task_created_for_warned_member_mentioning_bot(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = _make_warned_event(plugin, "1234", "u1", "Alice", "9999", mention_bot=True)

        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        # Close any coroutines to avoid leaks
        for c in created:
            if hasattr(c, "close"):
                c.close()

        appeal_tasks = [c for c in created if "_appeal" in getattr(c, "__qualname__", "")]
        assert len(appeal_tasks) >= 1

    async def test_no_appeal_task_when_ai_appeal_disabled(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = _make_warned_event(plugin, "1234", "u1", "Alice", "9999", mention_bot=True)

        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        for c in created:
            if hasattr(c, "close"):
                c.close()

        appeal_tasks = [c for c in created if "_appeal" in getattr(c, "__qualname__", "")]
        assert len(appeal_tasks) == 0

    async def test_no_appeal_task_when_member_not_warned(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._bot_self_id = "9999"
        event = make_mock_event("1234", "u1", "Alice", message_str="hello")
        # Not a warned member

        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        for c in created:
            if hasattr(c, "close"):
                c.close()

        appeal_tasks = [c for c in created if "_appeal" in getattr(c, "__qualname__", "")]
        assert len(appeal_tasks) == 0

    async def test_no_appeal_when_member_does_not_mention_bot(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = _make_warned_event(plugin, "1234", "u1", "Alice", "9999", mention_bot=False)

        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        for c in created:
            if hasattr(c, "close"):
                c.close()

        appeal_tasks = [c for c in created if "_appeal" in getattr(c, "__qualname__", "")]
        assert len(appeal_tasks) == 0


# ── group_name persistence ────────────────────────────────────────────────────

class TestGroupNamePersistence:

    async def test_group_name_stored_on_first_message(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        event = make_mock_event("9876", "u1", "Alice")
        event.message_obj.group_name = "我的测试群"

        await plugin.on_msg(event)

        gd = plugin.activity_data.get("groups", {}).get("9876", {})
        assert gd.get("group_name") == "我的测试群"

    async def test_empty_group_name_not_overwritten(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin.activity_data["groups"]["9876"] = {
            "group_name": "旧名称",
            "members": {},
            "daily_stats": {},
        }
        event = make_mock_event("9876", "u1", "Alice")
        event.message_obj.group_name = ""   # no name in this event

        await plugin.on_msg(event)

        gd = plugin.activity_data.get("groups", {}).get("9876", {})
        # Should not overwrite with empty string
        assert gd.get("group_name") == "旧名称"


# ── _appeal coroutine ─────────────────────────────────────────────────────────

class TestAppeal:

    async def _run_appeal(self, plugin, gid, sid, nick, reason, outcome):
        """
        Run _appeal directly, mocking _ai_judge to return `outcome`.
        Returns the list of texts passed to event.send / event.plain_result.
        """
        sent = []
        event = MagicMock()

        async def _send(result):
            sent.append(result)

        event.send = _send
        event.plain_result = MagicMock(side_effect=lambda t: f"plain:{t}")
        event.unified_msg_origin = "test_origin"

        wa = int(time.time()) - 3600   # warned an hour ago
        plugin._ai_judge = AsyncMock(return_value=(outcome, "AI 评语"))
        await plugin._appeal(event, gid, sid, nick, reason, wa)
        return sent

    async def test_approved_appeal_sends_pass_message(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_appeal(plugin, "1234", "u1", "Alice", "我最近很忙", outcome=True)
        assert sent
        combined = " ".join(str(s) for s in sent)
        assert "通过" in combined or "pass" in combined.lower()

    async def test_rejected_appeal_sends_reject_message(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_appeal(plugin, "1234", "u1", "Alice", "理由不充分", outcome=False)
        assert sent
        combined = " ".join(str(s) for s in sent)
        assert "驳回" in combined or "reject" in combined.lower()

    async def test_appeal_exception_does_not_propagate(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = MagicMock()
        event.send = AsyncMock()
        event.unified_msg_origin = "test_origin"
        plugin._ai_judge = AsyncMock(side_effect=RuntimeError("AI down"))
        wa = int(time.time()) - 3600
        # Should not raise
        await plugin._appeal(event, "1234", "u1", "Alice", "reason", wa)

    async def test_appeal_calls_ai_judge_with_correct_args(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_appeal=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = MagicMock()
        event.send = AsyncMock()
        event.plain_result = MagicMock(return_value="result")
        event.unified_msg_origin = "origin_x"
        wa = int(time.time()) - 7200   # warned 2 hours ago
        plugin._ai_judge = AsyncMock(return_value=(True, "good"))
        await plugin._appeal(event, "1234", "u1", "TestUser", "I was busy", wa)
        plugin._ai_judge.assert_called_once()
        args = plugin._ai_judge.call_args[0]
        assert args[0] == "TestUser"      # nick
        assert args[1] == "I was busy"    # reason
        # days ≥ 1
        assert args[2] >= 1
