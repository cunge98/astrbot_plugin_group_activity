"""
Tests for the /每日一问 daily topic feature:
  - _gen_topic() returns fallback when AI disabled
  - _gen_topic() returns AI text and is_ai=True when AI enabled
  - fallback topic cycles deterministically by day-of-year
  - cmd_daily_topic renders image card
  - cmd_daily_topic caches result for the day
  - cmd_daily_topic plain fallback on render error
"""
import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from helpers import make_plugin, make_mock_event, make_config


@pytest.fixture
def plugin(tmp_path):
    return make_plugin(tmp_path=str(tmp_path))


def get_daily_topics():
    import astrbot_plugin_group_activity.main as m
    return m.DAILY_TOPICS


# ── _gen_topic unit tests ────────────────────────────────────────────────────

class TestGenTopic:

    async def test_returns_fallback_when_ai_disabled(self, tmp_path):
        cfg = make_config(ai_enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        topic, is_ai = await plugin._gen_topic()
        assert isinstance(topic, str)
        assert len(topic) > 0
        assert is_ai is False

    async def test_fallback_topic_in_known_list(self, tmp_path):
        cfg = make_config(ai_enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        topic, _ = await plugin._gen_topic()
        assert topic in get_daily_topics()

    async def test_fallback_is_deterministic_for_same_day(self, tmp_path):
        cfg = make_config(ai_enabled=False)
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        t1, _ = await plugin._gen_topic()
        t2, _ = await plugin._gen_topic()
        assert t1 == t2

    async def test_ai_topic_returned_when_ai_enabled(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test_provider")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value="  今天你最近玩了什么游戏？  ")
        topic, is_ai = await plugin._gen_topic("测试群")
        assert is_ai is True
        assert topic == "今天你最近玩了什么游戏？"

    async def test_ai_failure_falls_back_to_preset(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test_provider")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value=None)
        topic, is_ai = await plugin._gen_topic()
        assert is_ai is False
        assert topic in get_daily_topics()

    async def test_ai_topic_truncated_to_200_chars(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test_provider")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value="x" * 500)
        topic, is_ai = await plugin._gen_topic()
        assert len(topic) <= 200
        assert is_ai is True


# ── cmd_daily_topic integration tests ────────────────────────────────────────

class TestCmdDailyTopic:

    async def test_renders_image_with_topic_data(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"fake_png"

        plugin._img = fake_img
        event = make_mock_event(group_id="9999", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")
        results = []
        async for r in plugin.cmd_daily_topic(event):
            results.append(r)

        assert results
        assert "topic" in captured
        assert "date" in captured
        assert captured["date"] == datetime.date.today().isoformat()

    async def test_caches_topic_for_same_day(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        gen_calls = []
        original_gen = plugin._gen_topic

        async def counting_gen(*args, **kwargs):
            gen_calls.append(1)
            return await original_gen(*args, **kwargs)

        plugin._gen_topic = counting_gen
        plugin._img = AsyncMock(return_value=b"fake")

        event = make_mock_event(group_id="8888", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")

        # First call — generates
        async for _ in plugin.cmd_daily_topic(event):
            pass
        # Second call — should use cache
        async for _ in plugin.cmd_daily_topic(event):
            pass

        assert len(gen_calls) == 1

    async def test_same_topic_returned_from_cache(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        topics_rendered = []

        async def fake_img(tmpl, data, **kw):
            topics_rendered.append(data["topic"])
            return b"fake"

        plugin._img = fake_img
        event = make_mock_event(group_id="7777", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")

        async for _ in plugin.cmd_daily_topic(event):
            pass
        async for _ in plugin.cmd_daily_topic(event):
            pass

        assert len(topics_rendered) == 2
        assert topics_rendered[0] == topics_rendered[1]

    async def test_plain_fallback_on_render_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(side_effect=RuntimeError("render fail"))
        event = make_mock_event(group_id="6666", sender_id="u1")
        event.plain_result = MagicMock(return_value="plain_result")
        results = []
        async for r in plugin.cmd_daily_topic(event):
            results.append(r)
        assert results
        event.plain_result.assert_called_once()
        call_text = event.plain_result.call_args[0][0]
        assert "今日一问" in call_text

    async def test_is_ai_flag_stored_and_passed(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="test_provider")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value="AI生成的话题问题")
        captured = {}

        async def fake_img(tmpl, data, **kw):
            captured.update(data)
            return b"fake"

        plugin._img = fake_img
        event = make_mock_event(group_id="5555", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")
        async for _ in plugin.cmd_daily_topic(event):
            pass

        assert captured.get("is_ai") is True


# ── auto-send scheduling tests ───────────────────────────────────────────────

class TestAutoTopicSchedule:

    def test_is_topic_day_every_day(self, plugin):
        # "每天" should always return True
        plugin.config["auto_topic_day"] = "每天"
        assert plugin._is_topic_day() is True

    def test_is_topic_day_specific_day_match(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        # Find today's weekday name
        day_names = ["周一","周二","周三","周四","周五","周六","周日"]
        today_name = day_names[datetime.date.today().weekday()]
        plugin.config["auto_topic_day"] = today_name
        assert plugin._is_topic_day() is True

    def test_is_topic_day_specific_day_no_match(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        day_names = ["周一","周二","周三","周四","周五","周六","周日"]
        # Pick a day that is NOT today
        today_idx = datetime.date.today().weekday()
        other_day = day_names[(today_idx + 1) % 7]
        plugin.config["auto_topic_day"] = other_day
        assert plugin._is_topic_day() is False

    def test_topic_time_parses_hhmm(self, plugin):
        plugin.config["auto_topic_time"] = "08:30"
        assert plugin._topic_time() == (8, 30)

    def test_topic_time_default_fallback(self, plugin):
        plugin.config["auto_topic_time"] = ""
        assert plugin._topic_time() == (9, 0)

    def test_topic_time_leading_zero(self, plugin):
        plugin.config["auto_topic_time"] = "09:05"
        assert plugin._topic_time() == (9, 5)


# ── _send_auto_topic tests ───────────────────────────────────────────────────

class TestSendAutoTopic:

    async def test_send_stores_msg_id_in_cache(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        from tests.helpers import make_mock_client
        cl = make_mock_client()

        async def _call_action(action, **kwargs):
            if action == "get_group_list":
                return [{"group_id": 1234}]
            if action == "send_group_msg":
                return {"message_id": 9001}
            return None

        cl.api.call_action = _call_action
        plugin._bot_client = cl
        plugin._img = AsyncMock(return_value=b"fake_img")

        await plugin._send_auto_topic()

        today = datetime.date.today().isoformat()
        cached = plugin.activity_data.get("groups", {}).get("1234", {}).get("daily_topics", {}).get(today)
        assert cached is not None
        assert cached["msg_id"] == "9001"
        assert "topic" in cached

    async def test_send_skips_when_no_client(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._bot_client = None
        plugin.context.get_platform = MagicMock(return_value=None)
        # Should not raise
        await plugin._send_auto_topic()


# ── reply detection & AI response tests ─────────────────────────────────────

class TestTopicReplyDetection:

    def _make_reply_event(self, group_id, sender_id, reply_id, text="好问题"):
        from tests.helpers import make_mock_event
        event = make_mock_event(group_id=group_id, sender_id=sender_id,
                                message_str=f"[CQ:reply,id={reply_id}] {text}")
        # Also put a dict-style segment in message list
        event.message_obj.message = [
            {"type": "reply", "data": {"id": str(reply_id)}},
            {"type": "text", "data": {"text": text}},
        ]
        return event

    def test_get_reply_id_from_dict_segment(self, plugin):
        event = self._make_reply_event("1", "u1", 9001)
        assert plugin._get_reply_id(event) == "9001"

    def test_get_reply_id_from_cq_code_fallback(self, plugin):
        from tests.helpers import make_mock_event
        event = make_mock_event(group_id="1", sender_id="u1",
                                message_str="[CQ:reply,id=42] 我觉得...")
        event.message_obj.message = []
        assert plugin._get_reply_id(event) == "42"

    def test_get_reply_id_none_when_no_reply(self, plugin):
        from tests.helpers import make_mock_event
        event = make_mock_event(group_id="1", sender_id="u1", message_str="普通消息")
        event.message_obj.message = []
        assert plugin._get_reply_id(event) is None

    async def test_ai_topic_reply_sends_at_mention(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="p")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value="很有趣的想法！")
        sent_msgs = []

        async def fake_call(action, **kwargs):
            sent_msgs.append((action, kwargs))
            return {"message_id": 1}

        from unittest.mock import MagicMock
        cl = MagicMock()
        cl.api.call_action = fake_call
        plugin._bot_client = cl

        await plugin._ai_topic_reply("1234", "u99", "Alice", "如果你有超能力？", "飞行！", None)

        assert any(a == "send_group_msg" for a, _ in sent_msgs)
        msg_text = sent_msgs[0][1].get("message", "")
        assert "[CQ:at,qq=u99]" in msg_text

    async def test_ai_topic_reply_skips_empty_message(self, tmp_path):
        cfg = make_config(ai_enabled=True, ai_provider="p")
        plugin = make_plugin(config=cfg, tmp_path=str(tmp_path))
        plugin._ai = AsyncMock(return_value="回复")
        sent_msgs = []
        from unittest.mock import MagicMock
        cl = MagicMock()
        async def fake_call(action, **kwargs): sent_msgs.append(action)
        cl.api.call_action = fake_call
        plugin._bot_client = cl

        # CQ码会被清除，只剩空字符串
        await plugin._ai_topic_reply("1234", "u99", "Alice", "话题", "[CQ:image,file=x]", None)
        assert not sent_msgs  # 无文字内容，不应发送


# ── idempotency (bug #2 fix) ─────────────────────────────────────────────────

class TestSendAutoTopicIdempotency:

    async def test_no_double_send_when_msg_id_already_cached(self, tmp_path):
        """_send_auto_topic must skip groups that already have a msg_id today."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        today = datetime.date.today().isoformat()
        # Pre-populate cache as if already sent
        plugin.activity_data["groups"]["2222"] = {
            "daily_topics": {today: {"topic": "旧话题", "is_ai": False, "msg_id": "8888"}}
        }
        sent = []

        async def _call_action(action, **kwargs):
            sent.append(action)
            if action == "get_group_list":
                return [{"group_id": 2222}]
            return {"message_id": 9999}

        from unittest.mock import MagicMock
        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl
        plugin._img = AsyncMock(return_value=b"fake")

        await plugin._send_auto_topic()

        # send_group_msg must NOT have been called
        assert "send_group_msg" not in sent

    async def test_sends_when_no_cache_for_today(self, tmp_path):
        """_send_auto_topic must send when today has no cached msg_id."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        sent = []

        async def _call_action(action, **kwargs):
            sent.append(action)
            if action == "get_group_list":
                return [{"group_id": 3333}]
            return {"message_id": 7777}

        from unittest.mock import MagicMock
        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl
        plugin._img = AsyncMock(return_value=b"fake")

        await plugin._send_auto_topic()

        assert "send_group_msg" in sent
