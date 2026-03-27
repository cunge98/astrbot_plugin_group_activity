"""
Tests for the AI welcome feature:
  - welcome fires on new member's first message, not on subsequent messages
  - correct template is selected based on welcome_style config
  - AI generation is called when style=AI生成 and ai_enabled=True
  - fallback to 简洁清爽 when AI disabled or generation fails
  - custom template {nickname} interpolation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from helpers import make_plugin, make_mock_event, make_config


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin(tmp_path):
    return make_plugin(tmp_path=str(tmp_path))


@pytest.fixture
def welcome_plugin(tmp_path):
    """Plugin with ai_welcome enabled, AI disabled (fixed templates only)."""
    cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
    return make_plugin(config=cfg, tmp_path=str(tmp_path))


# ── trigger logic ─────────────────────────────────────────────────────────────

class TestWelcomeTrigger:

    async def test_welcome_fires_on_first_message(self, tmp_path):
        """_ai_welcome task is created on a brand-new member's first message."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = make_mock_event(group_id="7001", sender_id="u1", sender_name="Alice")

        created = []
        original_create_task = __import__("asyncio").create_task

        async def _noop(*a, **kw): pass

        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        # Close any lingering coroutines
        for c in created:
            if hasattr(c, "close"):
                c.close()

        assert len(created) >= 1
        names = [getattr(c, "__qualname__", "") for c in created]
        assert any("_ai_welcome" in n for n in names)

    async def test_welcome_not_fired_on_second_message(self, tmp_path):
        """No welcome task created after the member is already tracked."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = make_mock_event(group_id="7002", sender_id="u1", sender_name="Alice")

        # First message — member gets registered
        with patch("asyncio.create_task", return_value=MagicMock()) as ct:
            await plugin.on_msg(event)
            first_call_count = ct.call_count

        # Second message — member already exists
        welcome_tasks_second = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: welcome_tasks_second.append(c) or MagicMock()):
            await plugin.on_msg(event)

        for c in welcome_tasks_second:
            if hasattr(c, "close"):
                c.close()

        welcome_second = [c for c in welcome_tasks_second
                          if "_ai_welcome" in getattr(c, "__qualname__", "")]
        assert len(welcome_second) == 0

    async def test_welcome_fires_for_rejoined_member(self, tmp_path):
        """Member in _welcome_pending (rejoined) triggers welcome even if already in ms."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin.activity_data["groups"]["7004"] = {
            "members": {"u1": {"last_active": 0, "warned_at": None, "nickname": "Alice",
                                "join_time": 1000, "role": "member", "streak": 0,
                                "last_active_date": ""}},
            "daily_stats": {},
        }
        plugin._welcome_pending.add(("7004", "u1"))
        event = make_mock_event(group_id="7004", sender_id="u1", sender_name="Alice")
        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)
        for c in created:
            if hasattr(c, "close"):
                c.close()
        welcome = [c for c in created if "_ai_welcome" in getattr(c, "__qualname__", "")]
        assert len(welcome) >= 1
        assert ("7004", "u1") not in plugin._welcome_pending

    async def test_welcome_pending_consumed_after_trigger(self, tmp_path):
        """_welcome_pending entry is removed after welcome fires so it won't repeat."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin.activity_data["groups"]["7005"] = {
            "members": {"u1": {"last_active": 0, "warned_at": None, "nickname": "Alice",
                                "join_time": 1000, "role": "member", "streak": 0,
                                "last_active_date": ""}},
            "daily_stats": {},
        }
        plugin._welcome_pending.add(("7005", "u1"))
        event = make_mock_event(group_id="7005", sender_id="u1", sender_name="Alice")
        with patch("asyncio.create_task", return_value=MagicMock()):
            await plugin.on_msg(event)
        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)
        for c in created:
            if hasattr(c, "close"):
                c.close()
        welcome = [c for c in created if "_ai_welcome" in getattr(c, "__qualname__", "")]
        assert len(welcome) == 0

    async def test_welcome_not_fired_when_disabled(self, tmp_path):
        """No welcome task when ai_welcome=False."""
        cfg = make_config(ai_welcome=False, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        event = make_mock_event(group_id="7003", sender_id="u1", sender_name="Alice")

        created = []
        with patch("asyncio.create_task", side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin.on_msg(event)

        for c in created:
            if hasattr(c, "close"):
                c.close()

        welcome = [c for c in created if "_ai_welcome" in getattr(c, "__qualname__", "")]
        assert len(welcome) == 0


# ── template selection ────────────────────────────────────────────────────────

class TestWelcomeTemplates:

    async def _run_welcome(self, plugin, gid, sid, nick):
        """Run _ai_welcome and capture the message sent via call_action."""
        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._ai_welcome(gid, sid, nick)
        return sent

    async def test_style_活力热血(self, tmp_path):
        cfg = make_config(ai_welcome=True, welcome_style="活力热血")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome(plugin, "8001", "u1", "小明")
        assert sent
        assert "小明" in sent[0]
        assert "欢迎" in sent[0] or "入场" in sent[0]

    async def test_style_古风雅致(self, tmp_path):
        cfg = make_config(ai_welcome=True, welcome_style="古风雅致")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome(plugin, "8002", "u1", "小明")
        assert sent
        assert "小明" in sent[0]
        assert "缘" in sent[0] or "踏入" in sent[0]

    async def test_style_简洁清爽(self, tmp_path):
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome(plugin, "8003", "u1", "小明")
        assert sent
        assert "小明" in sent[0]
        assert "欢迎" in sent[0]

    async def test_style_自定义(self, tmp_path):
        cfg = make_config(ai_welcome=True, welcome_style="自定义",
                          welcome_message="嗨 {nickname}，欢迎来到这里！")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome(plugin, "8004", "u1", "小明")
        assert sent
        assert "嗨 小明，欢迎来到这里！" in sent[0]

    async def test_style_自定义_empty_falls_back(self, tmp_path):
        """Empty custom template falls back to 简洁清爽."""
        cfg = make_config(ai_welcome=True, welcome_style="自定义", welcome_message="")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome(plugin, "8005", "u1", "小明")
        assert sent
        assert "小明" in sent[0]


# ── AI generation ─────────────────────────────────────────────────────────────

class TestWelcomeAI:

    async def _run_welcome_with_ai(self, plugin, ai_response):
        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl
        plugin.context.llm_generate = AsyncMock(
            return_value=MagicMock(completion_text=ai_response)
        )
        plugin.context.get_current_chat_provider_id = AsyncMock(return_value="test_provider")

        await plugin._ai_welcome("9001", "u1", "小明", umo="test_origin")
        return sent

    async def test_ai_response_used_when_enabled(self, tmp_path):
        cfg = make_config(ai_welcome=True, welcome_style="AI生成", ai_enabled=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = await self._run_welcome_with_ai(plugin, "你好小明！欢迎加入本群～")
        assert sent
        assert "你好小明！欢迎加入本群～" in sent[0]

    async def test_ai_failure_falls_back_to_simple(self, tmp_path):
        """When AI returns None, fall back to 简洁清爽 template."""
        cfg = make_config(ai_welcome=True, welcome_style="AI生成", ai_enabled=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin.context.llm_generate = AsyncMock(return_value=None)
        plugin.context.get_current_chat_provider_id = AsyncMock(return_value="test_provider")

        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._ai_welcome("9002", "u1", "小明")
        assert sent
        assert "小明" in sent[0]

    async def test_ai_disabled_uses_simple_template(self, tmp_path):
        """style=AI生成 but ai_enabled=False → simple fallback."""
        cfg = make_config(ai_welcome=True, welcome_style="AI生成", ai_enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))

        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._ai_welcome("9003", "u1", "小明")
        assert sent
        assert "小明" in sent[0]

    async def test_message_contains_at_mention(self, tmp_path):
        """Sent message always starts with [CQ:at,qq=<sid>]."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._ai_welcome("9004", "u99", "小明")
        assert sent
        assert "[CQ:at,qq=u99]" in sent[0]

    async def test_nick_is_qq_number_uses_new_member_label(self, tmp_path):
        """When nick equals sid (no group card set), display as 新成员 to avoid QQ number in text."""
        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        sent = []

        async def _call_action(action, **kwargs):
            if action == "send_group_msg":
                sent.append(kwargs.get("message", ""))
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._ai_welcome("9005", "3154364875", "3154364875")
        assert sent
        assert "新成员" in sent[0]
        assert "3154364875" not in sent[0].replace("[CQ:at,qq=3154364875]", "")

    async def test_ai_prompt_includes_msg_text_and_group_name(self, tmp_path):
        """AI prompt should contain the member's first message and the group name."""
        cfg = make_config(ai_welcome=True, welcome_style="AI生成", ai_enabled=True)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        prompts_seen = []

        async def fake_llm_generate(chat_provider_id, prompt):
            prompts_seen.append(prompt)
            return MagicMock(completion_text="欢迎！")

        plugin.context.llm_generate = fake_llm_generate
        plugin.context.get_current_chat_provider_id = AsyncMock(return_value="test_provider")
        plugin._bot_client = MagicMock()
        plugin._bot_client.api.call_action = AsyncMock(return_value=None)

        await plugin._ai_welcome("9010", "u1", "小明", umo="test_origin",
                                 msg_text="大家好！", group_name="快乐群")
        assert prompts_seen
        full_prompt = prompts_seen[0]
        assert "大家好！" in full_prompt
        assert "快乐群" in full_prompt
