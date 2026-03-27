"""
Shared test helper functions.

Imports from astrbot_plugin_group_activity are done lazily (inside function
bodies) so this module is safe to import before conftest.py has installed the
AstrBot stubs.
"""
import time
import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


def make_config(**overrides) -> dict:
    """Return a default plugin config dict, optionally overriding any key."""
    defaults = {
        "enabled": True,
        "inactive_days": 7,
        "kick_hours": 24,
        "new_member_grace_days": 3,
        "check_interval_minutes": 60,
        "whitelist_groups": [],
        "blacklist_groups": [],
        "exclude_admins": True,
        "rank_count": 20,
        "ai_enabled": False,
        "ai_provider": "",
        "ai_style": "傲娇萌妹",
        "ai_appeal": False,
        "ai_custom_prompt": "",
        "auto_weekly": False,
        "auto_weekly_day": "周日",
        "auto_weekly_time": "20:00",
        "auto_weekly_hour": 20,
        "theme": "清新蓝",
        "kick_message": "成员 {nickname} 因超过 {days} 天未发言已被移出群聊。",
        "ai_welcome": False,
        "welcome_style": "AI生成",
        "welcome_message": "欢迎 {nickname} 加入本群！有什么不懂的尽管问～ 😊",
    }
    defaults.update(overrides)
    return defaults


def make_plugin(config=None, tmp_path=None):
    """
    Instantiate GroupActivityPlugin with mocked dependencies.

    DATA_DIR is redirected to tmp_path so tests never touch the real
    filesystem.  asyncio.create_task is patched to avoid needing a live
    event loop at construction time.
    """
    import astrbot_plugin_group_activity.main as m   # lazy – stubs already in place

    if config is None:
        config = make_config()

    context = MagicMock()
    context.llm_generate = AsyncMock(return_value=None)
    context.get_current_chat_provider_id = AsyncMock(return_value=None)
    context.get_platform = MagicMock(return_value=None)

    original_data_dir = m.DATA_DIR
    if tmp_path is not None:
        test_dir = Path(tmp_path) / "plugin_data"
        test_dir.mkdir(parents=True, exist_ok=True)
        m.DATA_DIR = test_dir

    def _fake_create_task(coro, **kw):
        # Close the coroutine immediately so it doesn't leak as unawaited
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()

    with patch("asyncio.create_task", side_effect=_fake_create_task):
        plugin = m.GroupActivityPlugin(context, config)

    if tmp_path is not None:
        plugin.data_file = Path(tmp_path) / "plugin_data" / "activity_data.json"
        m.DATA_DIR = original_data_dir

    return plugin


def make_mock_event(group_id, sender_id, sender_name="", message_str="",
                    self_id="99999", message_id="100"):
    """Return a minimal AstrMessageEvent mock for on_msg tests."""
    event = MagicMock()
    event.message_obj.group_id = group_id
    event.message_obj.self_id = self_id
    event.message_obj.message = []
    event.message_obj.group_name = ""
    event.message_obj.message_id = message_id
    event.get_sender_id.return_value = str(sender_id)
    event.get_sender_name.return_value = sender_name
    event.message_str = message_str
    event.unified_msg_origin = "test_origin"
    return event


def make_mock_client(member_list=None):
    """
    Return a bot client mock whose call_action returns member_list for
    'get_group_member_list' and None for everything else.
    """
    if member_list is None:
        member_list = []

    async def _call_action(action, **kwargs):
        if action == "get_group_member_list":
            return member_list
        return None

    cl = MagicMock()
    cl.api.call_action = _call_action
    return cl
