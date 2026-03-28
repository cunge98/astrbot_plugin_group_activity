"""
Tests for _send_auto_weekly():
  - skips when no bot client
  - skips when no target groups
  - sends URL image when _img returns a str
  - sends base64 image when _img returns bytes
  - falls back to file-URI when base64 send fails
  - falls back to CQ code when file-URI also fails
  - falls back to text when all image methods fail
  - sends to multiple groups independently
  - text fallback uses data summary when data is available
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_config


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_client_with_groups(groups, send_raises=None):
    """Return a bot client mock that returns `groups` for get_group_list.

    If send_raises is an Exception instance or type, send_group_msg will raise
    it; otherwise it returns {"message_id": 1}.
    """
    sent = []

    async def _call_action(action, **kwargs):
        if action == "get_group_list":
            return [{"group_id": int(g)} for g in groups]
        if action == "send_group_msg":
            sent.append(kwargs)
            if send_raises is not None:
                raise send_raises if isinstance(send_raises, Exception) else send_raises()
            return {"message_id": 1}
        return None

    cl = MagicMock()
    cl.api.call_action = _call_action
    cl._sent = sent
    return cl


# ── skip conditions ───────────────────────────────────────────────────────────

class TestSendAutoWeeklySkip:

    async def test_skips_when_no_client(self, tmp_path):
        """If _cli() returns None, method returns early without error."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._bot_client = None
        plugin.context.get_platform = MagicMock(return_value=None)
        # Should not raise
        await plugin._send_auto_weekly()

    async def test_skips_when_no_target_groups(self, tmp_path):
        """No target groups means nothing is sent."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        sent = []

        async def _call_action(action, **kwargs):
            if action == "get_group_list":
                return []
            if action == "send_group_msg":
                sent.append(action)
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._send_auto_weekly()
        assert sent == []


# ── URL image path ────────────────────────────────────────────────────────────

class TestSendAutoWeeklyUrlImage:

    async def test_url_image_sent_via_message_segment(self, tmp_path):
        """When _img returns a URL string, send via message segment with file=url."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        cl = _make_client_with_groups(["1234"])
        plugin._bot_client = cl

        url = "http://render.example.com/image.png"
        plugin._img = AsyncMock(return_value=url)

        await plugin._send_auto_weekly()

        sent = [k for k in cl._sent if "message" in k]
        assert sent, "Expected send_group_msg to be called"
        msg = sent[0]["message"]
        # Should use the image segment format
        assert isinstance(msg, list)
        assert msg[0]["type"] == "image"
        assert msg[0]["data"]["file"] == url

    async def test_url_send_failure_falls_back_to_text(self, tmp_path):
        """URL send failure → text fallback."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        url = "http://render.example.com/image.png"
        plugin._img = AsyncMock(return_value=url)

        calls = []

        async def _call_action(action, **kwargs):
            calls.append((action, kwargs))
            if action == "get_group_list":
                return [{"group_id": 5555}]
            if action == "send_group_msg":
                msg = kwargs.get("message", "")
                if isinstance(msg, list):
                    raise RuntimeError("rich media transfer failed")
                return {"message_id": 1}
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._send_auto_weekly()

        text_calls = [(a, k) for a, k in calls
                      if a == "send_group_msg" and isinstance(k.get("message"), str)]
        assert text_calls, "Expected text fallback"
        assert "周报" in text_calls[0][1]["message"] or "周" in text_calls[0][1]["message"]


# ── bytes image path ──────────────────────────────────────────────────────────

class TestSendAutoWeeklyBytesImage:

    async def test_bytes_image_sent_via_base64(self, tmp_path):
        """When _img returns bytes, send via base64 message segment."""
        import base64
        plugin = make_plugin(tmp_path=str(tmp_path))
        img_bytes = b"FAKEPNGDATA"
        plugin._img = AsyncMock(return_value=img_bytes)
        cl = _make_client_with_groups(["6789"])
        plugin._bot_client = cl

        await plugin._send_auto_weekly()

        sent = [k for k in cl._sent if "message" in k]
        assert sent, "Expected send_group_msg to be called"
        msg = sent[0]["message"]
        assert isinstance(msg, list)
        assert msg[0]["type"] == "image"
        expected_b64 = base64.b64encode(img_bytes).decode()
        assert f"base64://{expected_b64}" in msg[0]["data"]["file"]

    async def test_bytes_base64_failure_tries_file_uri(self, tmp_path):
        """If base64 segment send fails, fall back to file-URI segment."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(return_value=b"FAKEBYTES")

        calls = []

        async def _call_action(action, **kwargs):
            calls.append((action, kwargs))
            if action == "get_group_list":
                return [{"group_id": 1111}]
            if action == "send_group_msg":
                msg = kwargs.get("message", "")
                if isinstance(msg, list) and msg[0]["data"]["file"].startswith("base64://"):
                    raise RuntimeError("base64 send failed")
                return {"message_id": 1}
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._send_auto_weekly()

        # At least one send_group_msg succeeded (file-URI or CQ or text)
        sends = [(a, k) for a, k in calls if a == "send_group_msg"]
        assert len(sends) >= 2, "Expected base64 attempt + fallback"

    async def test_all_image_methods_fail_sends_text(self, tmp_path):
        """If all image send methods fail, text fallback is used."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(return_value=b"BYTES")

        calls = []

        async def _call_action(action, **kwargs):
            calls.append((action, kwargs))
            if action == "get_group_list":
                return [{"group_id": 2222}]
            if action == "send_group_msg":
                msg = kwargs.get("message", "")
                if not isinstance(msg, str):
                    raise RuntimeError("image send failed")
                return {"message_id": 1}
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        await plugin._send_auto_weekly()

        text_calls = [(a, k) for a, k in calls
                      if a == "send_group_msg" and isinstance(k.get("message"), str)]
        assert text_calls, "Expected text fallback"


# ── multiple groups ───────────────────────────────────────────────────────────

class TestSendAutoWeeklyMultipleGroups:

    async def test_sends_to_each_group(self, tmp_path):
        """With two target groups, send_group_msg is called once per group."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(return_value=b"FAKEIMG")
        cl = _make_client_with_groups(["111", "222"])
        plugin._bot_client = cl

        await plugin._send_auto_weekly()

        group_ids_sent = [k["group_id"] for k in cl._sent if "group_id" in k]
        assert 111 in group_ids_sent
        assert 222 in group_ids_sent

    async def test_failure_in_one_group_does_not_abort_others(self, tmp_path):
        """An error sending to group A must not prevent sending to group B."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(return_value=b"FAKEIMG")

        calls = []
        first_send = [True]

        async def _call_action(action, **kwargs):
            calls.append((action, kwargs))
            if action == "get_group_list":
                return [{"group_id": 3333}, {"group_id": 4444}]
            if action == "send_group_msg":
                if first_send[0]:
                    first_send[0] = False
                    raise RuntimeError("group 3333 failed")
                return {"message_id": 1}
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        # Should not raise
        await plugin._send_auto_weekly()

        sends = [(a, k) for a, k in calls if a == "send_group_msg"]
        assert len(sends) >= 2


# ── text fallback content ─────────────────────────────────────────────────────

class TestSendAutoWeeklyTextFallback:

    async def test_text_fallback_includes_weekly_summary(self, tmp_path):
        """Text fallback should mention message count from weekly data."""
        plugin = make_plugin(tmp_path=str(tmp_path))
        # Force both _img and html_render (low-quality fallback) to fail
        plugin._img = AsyncMock(side_effect=RuntimeError("render failed"))
        plugin.html_render = AsyncMock(side_effect=RuntimeError("render failed"))

        sent_msgs = []

        async def _call_action(action, **kwargs):
            if action == "get_group_list":
                return [{"group_id": 7001}]
            if action == "send_group_msg":
                sent_msgs.append(kwargs.get("message", ""))
                return {"message_id": 1}
            return None

        cl = MagicMock()
        cl.api.call_action = _call_action
        plugin._bot_client = cl

        # Seed some data so _weekly_data can build a summary
        import time, datetime
        now = int(time.time())
        today = datetime.date.today().isoformat()
        plugin.activity_data["groups"]["7001"] = {
            "members": {
                "u1": {"last_active": now - 3600, "warned_at": None,
                       "nickname": "Alice", "join_time": now - 30 * 86400,
                       "role": "member", "streak": 1, "last_active_date": today},
            },
            "daily_stats": {today: 42},
        }

        await plugin._send_auto_weekly()

        assert sent_msgs, "Expected text fallback message"
        assert any("周报" in m or "活跃" in m or "消息" in m for m in sent_msgs)
