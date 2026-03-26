"""
Tests for the inactivity-check state machine: _check, _warn, _kick.

State transitions under test
──────────────────────────────────────────────────────────────────────────────
 Normal     → Warned   : member inactive longer than inactive_days threshold
 Warned     → Kicked   : kick timeout expired AND member still inactive
 Warned     → Cleared  : kick timeout expired AND member active since warning
 Warned     → (skip)   : kick timeout not yet expired
 Any        → (skip)   : bot self / admin+exclude_admins / new-member grace
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_mock_client


# ── helpers ───────────────────────────────────────────────────────────────────

def _add_member(plugin, gid, uid, last_active, role="member",
                warned_at=None, join_time=None):
    """Insert a member directly into activity_data."""
    if gid not in plugin.activity_data["groups"]:
        plugin.activity_data["groups"][gid] = {"members": {}}
    now = int(time.time())
    plugin.activity_data["groups"][gid]["members"][str(uid)] = {
        "last_active": last_active,
        "warned_at": warned_at,
        "nickname": f"User{uid}",
        "join_time": join_time if join_time is not None else now - 30 * 86400,
        "role": role,
        "streak": 0,
        "last_active_date": "",
    }


def _make_ml_member(uid, role="member", last_sent=None, join_time=None):
    """Return a member-list dict as returned by the QQ API."""
    now = int(time.time())
    return {
        "user_id": uid,
        "role": role,
        "card": f"User{uid}",
        "nickname": f"Nick{uid}",
        "last_sent_time": last_sent if last_sent is not None else now - 86400,
        "join_time": join_time if join_time is not None else now - 30 * 86400,
    }


def _check_params(plugin):
    """Build the positional parameters _check_all passes to _check."""
    now = int(time.time())
    d  = max(plugin.config.get("inactive_days", 7), 1)
    kh = max(plugin.config.get("kick_hours", 24), 1)
    ea = plugin.config.get("exclude_admins", True)
    gd = max(plugin.config.get("new_member_grace_days", 3), 0)
    return dict(
        its=now - d * 86400,
        kh=kh,
        ea=ea,
        gts=now - gd * 86400,
        now=now,
    )


# ── normal → warned ───────────────────────────────────────────────────────────

class TestWarnTransition:

    async def test_inactive_member_is_warned(self, plugin):
        """Member inactive beyond threshold is warned and warned_at is set."""
        now = int(time.time())
        gid = "10001"
        uid = 1001
        ml = [_make_ml_member(uid, last_sent=now - 10 * 86400)]
        _add_member(plugin, gid, uid, last_active=now - 10 * 86400)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()
        p = _check_params(plugin)

        await plugin._check(make_mock_client(ml), gid, **p)

        plugin._warn.assert_called_once()
        call_args = plugin._warn.call_args[0]  # positional args
        assert call_args[1] == gid
        assert call_args[2] == str(uid)

        assert plugin.activity_data["groups"][gid]["members"][str(uid)]["warned_at"] == p["now"]
        plugin._kick.assert_not_called()

    async def test_active_member_not_warned(self, plugin):
        """Member active within threshold is left alone."""
        now = int(time.time())
        gid = "10002"
        uid = 1002
        ml = [_make_ml_member(uid, last_sent=now - 2 * 86400)]
        _add_member(plugin, gid, uid, last_active=now - 2 * 86400)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._warn.assert_not_called()
        plugin._kick.assert_not_called()


# ── warned → kicked ───────────────────────────────────────────────────────────

class TestKickTransition:

    async def test_warned_inactive_member_kicked_after_timeout(self, plugin):
        """Warned member who stays inactive past kick_hours is kicked."""
        now = int(time.time())
        gid = "10003"
        uid = 1003
        warned_at = now - 25 * 3600   # warned 25 h ago; threshold = 24 h
        last_active = now - 10 * 86400

        ml = [_make_ml_member(uid, last_sent=last_active)]
        _add_member(plugin, gid, uid, last_active=last_active, warned_at=warned_at)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._kick.assert_called_once()
        plugin._warn.assert_not_called()

    async def test_warned_member_not_kicked_before_timeout(self, plugin):
        """Warned member whose kick window hasn't elapsed is left alone."""
        now = int(time.time())
        gid = "10004"
        uid = 1004
        warned_at = now - 1 * 3600   # warned only 1 h ago; threshold = 24 h
        last_active = now - 10 * 86400

        ml = [_make_ml_member(uid, last_sent=last_active)]
        _add_member(plugin, gid, uid, last_active=last_active, warned_at=warned_at)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._kick.assert_not_called()
        plugin._warn.assert_not_called()


# ── warned → cleared ──────────────────────────────────────────────────────────

class TestWarnClearTransition:

    async def test_warned_member_active_after_warning_clears_warned_at(self, plugin):
        """If a warned member becomes active after warning, warned_at is cleared."""
        now = int(time.time())
        gid = "10005"
        uid = 1005
        warned_at = now - 25 * 3600        # 25 h ago
        last_active = now - 1 * 3600       # active 1 h ago (after warning)

        ml = [_make_ml_member(uid, last_sent=last_active)]
        _add_member(plugin, gid, uid, last_active=last_active, warned_at=warned_at)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._kick.assert_not_called()
        plugin._warn.assert_not_called()
        assert plugin.activity_data["groups"][gid]["members"][str(uid)]["warned_at"] is None


# ── skip conditions ───────────────────────────────────────────────────────────

class TestSkipConditions:

    async def test_admin_skipped_when_exclude_admins_true(self, plugin):
        """Admins are never warned when exclude_admins=True."""
        now = int(time.time())
        plugin.config["exclude_admins"] = True
        gid = "10006"
        uid = 1006
        ml = [_make_ml_member(uid, role="admin", last_sent=now - 30 * 86400)]
        _add_member(plugin, gid, uid, last_active=now - 30 * 86400, role="admin")

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._warn.assert_not_called()
        plugin._kick.assert_not_called()

    async def test_admin_checked_when_exclude_admins_false(self, plugin):
        """Admins are warned when exclude_admins=False."""
        now = int(time.time())
        plugin.config["exclude_admins"] = False
        gid = "10007"
        uid = 1007
        ml = [_make_ml_member(uid, role="admin", last_sent=now - 30 * 86400)]
        _add_member(plugin, gid, uid, last_active=now - 30 * 86400, role="admin")

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()
        p = _check_params(plugin)

        await plugin._check(make_mock_client(ml), gid, **p)

        plugin._warn.assert_called_once()

    async def test_owner_skipped_when_exclude_admins_true(self, plugin):
        """Owners are treated the same as admins."""
        now = int(time.time())
        plugin.config["exclude_admins"] = True
        gid = "10008"
        uid = 1008
        ml = [_make_ml_member(uid, role="owner", last_sent=now - 30 * 86400)]
        _add_member(plugin, gid, uid, last_active=now - 30 * 86400, role="owner")

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._warn.assert_not_called()

    async def test_new_member_within_grace_period_skipped(self, plugin):
        """New members whose join_time is within grace_days are not checked."""
        now = int(time.time())
        plugin.config["new_member_grace_days"] = 3
        gid = "10009"
        uid = 1009
        join_time = now - 1 * 86400   # joined 1 day ago; grace = 3 days
        ml = [_make_ml_member(uid, last_sent=join_time, join_time=join_time)]
        _add_member(plugin, gid, uid, last_active=join_time,
                    join_time=join_time)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._warn.assert_not_called()
        plugin._kick.assert_not_called()

    async def test_bot_self_skipped(self, plugin):
        """The bot's own account is never warned or kicked."""
        now = int(time.time())
        bot_uid = "99999"
        plugin._bot_self_id = bot_uid
        gid = "10010"
        ml = [_make_ml_member(int(bot_uid), last_sent=now - 30 * 86400)]
        _add_member(plugin, gid, bot_uid, last_active=now - 30 * 86400)

        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client(ml), gid, **_check_params(plugin))

        plugin._warn.assert_not_called()
        plugin._kick.assert_not_called()

    async def test_empty_member_list_does_nothing(self, plugin):
        """An empty member list from the bot API causes no warnings or kicks."""
        plugin._warn = AsyncMock()
        plugin._kick = AsyncMock()

        await plugin._check(make_mock_client([]), "10011", **_check_params(plugin))

        plugin._warn.assert_not_called()
        plugin._kick.assert_not_called()

    async def test_api_failure_does_not_crash(self, plugin):
        """If get_group_member_list raises, _check returns silently."""
        cl = MagicMock()
        cl.api.call_action = AsyncMock(side_effect=Exception("API error"))

        plugin._warn = AsyncMock()
        # Should not raise
        await plugin._check(cl, "10012", **_check_params(plugin))
        plugin._warn.assert_not_called()


# ── _kick removes member from activity_data ───────────────────────────────────

class TestKickSideEffect:

    async def test_kick_removes_member_from_data(self, plugin):
        """_kick deletes the member record from activity_data."""
        now = int(time.time())
        gid = "20001"
        uid = "2001"
        plugin.activity_data["groups"][gid] = {
            "members": {uid: {"last_active": now, "warned_at": None,
                              "nickname": "Del", "join_time": now,
                              "role": "member", "streak": 0,
                              "last_active_date": ""}},
        }

        cl = make_mock_client()
        await plugin._kick(cl, gid, uid, "Del")

        assert uid not in plugin.activity_data["groups"][gid]["members"]
