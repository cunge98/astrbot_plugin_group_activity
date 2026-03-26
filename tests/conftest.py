"""
Shared test fixtures and AstrBot framework mocks.

All astrbot.* modules are stubbed out here at module-import time, before
any test file (or the plugin itself) is imported. This lets us exercise the
plugin's pure Python logic without installing the full AstrBot runtime.
"""
import sys
import time
import asyncio
import datetime
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ── 1. Ensure the package parent is on sys.path ──────────────────────────────
# conftest.py lives at:  <pkg>/tests/conftest.py
# package lives at:      <pkg>/
# parent lives at:       <pkg>/../  (= /home/user)
_PACKAGE_ROOT = Path(__file__).parent.parent          # …/astrbot_plugin_group_activity
_PARENT_DIR   = _PACKAGE_ROOT.parent                  # …/home/user
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# ── 2. Build lightweight astrbot stubs ───────────────────────────────────────

class _MockFilter:
    """Drop-in for astrbot.api.event.filter – decorators become no-ops."""
    class EventMessageType:
        GROUP_MESSAGE = "group"
    class PlatformAdapterType:
        AIOCQHTTP = "aiocqhttp"
    class PermissionType:
        ADMIN = "admin"

    @staticmethod
    def event_message_type(*a, **kw): return lambda fn: fn
    @staticmethod
    def platform_adapter_type(*a, **kw): return lambda fn: fn
    @staticmethod
    def command(*a, **kw): return lambda fn: fn
    @staticmethod
    def permission_type(*a, **kw): return lambda fn: fn
    @staticmethod
    def llm_tool(*a, **kw): return lambda fn: fn

_filter_stub = _MockFilter()

# astrbot.api.event
_api_event_stub = MagicMock()
_api_event_stub.filter = _filter_stub

# astrbot.api.star  –  Star is the plugin base class
class _FakeStar:
    def __init__(self, context):
        self.context = context
    async def html_render(self, tmpl, data, options=None):
        return b"fake_rendered_image"

_api_star_stub = MagicMock()
_api_star_stub.Star = _FakeStar
_api_star_stub.register = lambda *a, **kw: (lambda cls: cls)
_api_star_stub.Context = MagicMock

# astrbot.api
_api_stub = MagicMock()
_api_stub.logger = MagicMock()
_api_stub.AstrBotConfig = dict

# astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event
class _FakeAiocqhttpEvent:
    pass

_aiocqhttp_event_stub = MagicMock()
_aiocqhttp_event_stub.AiocqhttpMessageEvent = _FakeAiocqhttpEvent

# astrbot.core.utils.astrbot_path  –  point DATA_DIR at a temp folder
_module_tmpdir = tempfile.mkdtemp()
_path_stub = MagicMock()
_path_stub.get_astrbot_data_path = lambda: _module_tmpdir

sys.modules.update({
    "astrbot":                       MagicMock(),
    "astrbot.api":                   _api_stub,
    "astrbot.api.event":             _api_event_stub,
    "astrbot.api.star":              _api_star_stub,
    "astrbot.api.message_components": MagicMock(),
    "astrbot.core":                  MagicMock(),
    "astrbot.core.platform":         MagicMock(),
    "astrbot.core.platform.sources": MagicMock(),
    "astrbot.core.platform.sources.aiocqhttp": MagicMock(),
    "astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event":
        _aiocqhttp_event_stub,
    "astrbot.core.utils":            MagicMock(),
    "astrbot.core.utils.astrbot_path": _path_stub,
})

# ── 3. Helper factories (re-exported from helpers.py) ────────────────────────
# helpers.py lives in the same directory; with pythonpath = tests in pytest.ini
# it is importable as a plain module.  All package imports inside helpers.py
# are deferred to function bodies so the import is safe here.

from helpers import make_config, make_plugin, make_mock_event, make_mock_client  # noqa: F401

# ── 4. Pytest fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def plugin(tmp_path):
    """Fresh GroupActivityPlugin with default config and isolated data dir."""
    return make_plugin(tmp_path=tmp_path)


@pytest.fixture
def plugin_with_data(tmp_path):
    """Plugin pre-loaded with a sample group containing members in mixed states."""
    p = make_plugin(tmp_path=tmp_path)
    now = int(time.time())
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    p.activity_data = {
        "groups": {
            "12345": {
                "group_name": "测试群",
                "members": {
                    # active today
                    "1001": {
                        "last_active": now - 3600,
                        "warned_at": None,
                        "nickname": "活跃甲",
                        "join_time": now - 30 * 86400,
                        "role": "member",
                        "streak": 5,
                        "last_active_date": today,
                    },
                    # inactive 10 days
                    "1002": {
                        "last_active": now - 10 * 86400,
                        "warned_at": None,
                        "nickname": "潜水乙",
                        "join_time": now - 60 * 86400,
                        "role": "member",
                        "streak": 0,
                        "last_active_date": "",
                    },
                    # warned 25 h ago, still inactive
                    "1003": {
                        "last_active": now - 10 * 86400,
                        "warned_at": now - 25 * 3600,
                        "nickname": "警告丙",
                        "join_time": now - 60 * 86400,
                        "role": "member",
                        "streak": 0,
                        "last_active_date": "",
                    },
                    # admin – should be exempt
                    "9001": {
                        "last_active": now - 15 * 86400,
                        "warned_at": None,
                        "nickname": "管理员",
                        "join_time": now - 90 * 86400,
                        "role": "admin",
                        "streak": 0,
                        "last_active_date": "",
                    },
                },
                "daily_stats": {
                    (datetime.date.today() - datetime.timedelta(days=i)).isoformat(): 10 + i
                    for i in range(14)
                },
            }
        }
    }
    return p
