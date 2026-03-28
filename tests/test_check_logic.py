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

pytestmark = pytest.mark.asyncio
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


# ── departed member cleanup in _check ─────────────────────────────────────────

class TestDepartedMemberCleanup:
    """
    When a member is manually kicked or leaves the group outside the plugin,
    _check should detect they are no longer in the API member list and remove
    their record from activity_data.
    """

    async def test_removes_member_not_in_api_list(self, plugin):
        """Member in activity_data but absent from get_group_member_list is removed."""
        now = int(time.time())
        gid = "30001"
        staying_uid = "3001"
        departed_uid = "3002"   # manually kicked — not in API list

        _add_member(plugin, gid, staying_uid, now - 86400)
        _add_member(plugin, gid, departed_uid, now - 86400)

        # API only returns the staying member
        cl = make_mock_client(member_list=[_make_ml_member(int(staying_uid))])
        await plugin._check(cl, gid, **_check_params(plugin))

        members = plugin.activity_data["groups"][gid]["members"]
        assert departed_uid not in members
        assert staying_uid in members

    async def test_departed_member_removed_and_staying_member_intact(self, plugin):
        now = int(time.time())
        gid = "30002"
        staying_uid = "3003"
        departed_uid = "3099"
        _add_member(plugin, gid, staying_uid, now - 86400)
        _add_member(plugin, gid, departed_uid, now - 86400)

        # Only staying member is returned by API; departed member should be cleaned up
        cl = make_mock_client(member_list=[_make_ml_member(int(staying_uid))])
        await plugin._check(cl, gid, **_check_params(plugin))

        members = plugin.activity_data["groups"][gid]["members"]
        assert departed_uid not in members
        assert staying_uid in members

    async def test_no_dirty_flag_when_no_departures(self, plugin):
        now = int(time.time())
        gid = "30003"
        uid = "3004"
        _add_member(plugin, gid, uid, now - 86400)

        plugin._dirty = False
        cl = make_mock_client(member_list=[_make_ml_member(int(uid))])
        await plugin._check(cl, gid, **_check_params(plugin))

        # _save() is always called but _dirty was False before, so it stays False
        assert plugin._dirty is False

    async def test_multiple_departed_members_all_removed(self, plugin):
        now = int(time.time())
        gid = "30004"
        for uid in ["4001", "4002", "4003"]:
            _add_member(plugin, gid, uid, now - 86400)

        # Only 4001 remains
        cl = make_mock_client(member_list=[_make_ml_member(4001)])
        await plugin._check(cl, gid, **_check_params(plugin))

        members = plugin.activity_data["groups"][gid]["members"]
        assert "4001" in members
        assert "4002" not in members
        assert "4003" not in members

    async def test_staying_members_data_preserved(self, plugin):
        """Cleanup must not corrupt data of members who are still in the group."""
        now = int(time.time())
        gid = "30005"
        uid = "5001"
        _add_member(plugin, gid, uid, now - 86400, warned_at=now - 1000)
        _add_member(plugin, gid, "5002", now - 86400)  # will be removed

        cl = make_mock_client(member_list=[_make_ml_member(int(uid))])
        await plugin._check(cl, gid, **_check_params(plugin))

        ud = plugin.activity_data["groups"][gid]["members"].get(uid)
        assert ud is not None
        assert "5002" not in plugin.activity_data["groups"][gid]["members"]


# ── welcome_pending population in _check ──────────────────────────────────────

class TestCheckWelcomePending:
    """_check() must add genuinely-new members to _welcome_pending so that the
    welcome fires even if _check runs before their first message."""

    async def test_recent_new_member_added_to_welcome_pending(self, plugin):
        """A member whose join_time is within the last hour gets added to
        _welcome_pending when first seen by _check."""
        import time
        now = int(time.time())
        gid = "60001"
        # Member is brand-new (joined 5 minutes ago) and not yet in md
        ml = [_make_ml_member(uid=7001, join_time=now - 300)]
        cl = make_mock_client(member_list=ml)

        await plugin._check(cl, gid, **_check_params(plugin))

        assert (gid, "7001") in plugin._welcome_pending

    async def test_old_member_not_added_to_welcome_pending(self, plugin):
        """A member who joined 2 days ago is NOT added to _welcome_pending —
        prevents spurious welcomes when the system sees them for the first time."""
        import time
        now = int(time.time())
        gid = "60002"
        ml = [_make_ml_member(uid=7002, join_time=now - 2 * 86400)]
        cl = make_mock_client(member_list=ml)

        await plugin._check(cl, gid, **_check_params(plugin))

        assert (gid, "7002") not in plugin._welcome_pending

    async def test_existing_member_not_added_to_welcome_pending(self, plugin):
        """A member already tracked in md with the same join_time is not added to
        _welcome_pending by the new-member path (only by the rejoin path)."""
        import time
        now = int(time.time())
        gid = "60003"
        uid = "7003"
        old_join = now - 30 * 86400   # joined 30 days ago
        # Store with same join_time the API will return → no rejoin detection
        plugin.activity_data.setdefault("groups", {})[gid] = {
            "members": {uid: {
                "last_active": now - 86400, "warned_at": None, "nickname": "User7003",
                "join_time": old_join, "role": "member", "streak": 0, "last_active_date": "",
            }},
            "daily_stats": {},
        }
        ml = [_make_ml_member(uid=int(uid), join_time=old_join)]
        cl = make_mock_client(member_list=ml)

        await plugin._check(cl, gid, **_check_params(plugin))

        assert (gid, uid) not in plugin._welcome_pending

    async def test_check_then_message_still_triggers_welcome(self, plugin):
        """End-to-end: _check runs first (adds to welcome_pending), then
        on_msg fires → _ai_welcome task is created."""
        import time
        import asyncio
        from unittest.mock import patch
        from helpers import make_mock_event, make_config
        import astrbot_plugin_group_activity.main as m

        cfg = make_config(ai_welcome=True, welcome_style="简洁清爽")
        plugin2 = __import__("helpers", fromlist=["make_plugin"]).make_plugin(
            config=cfg, tmp_path=plugin.data_file.parent
        )

        now = int(time.time())
        gid = "60004"
        uid = "7004"

        # Step 1: _check detects new member and adds to welcome_pending
        ml = [_make_ml_member(uid=int(uid), join_time=now - 120)]
        cl = make_mock_client(member_list=ml)
        await plugin2._check(cl, gid, **_check_params(plugin2))
        assert (gid, uid) in plugin2._welcome_pending

        # Step 2: member sends first message
        event = make_mock_event(group_id=gid, sender_id=uid, sender_name="PAM")
        created = []
        with patch("asyncio.create_task",
                   side_effect=lambda c, **kw: created.append(c) or MagicMock()):
            await plugin2.on_msg(event)

        for c in created:
            if hasattr(c, "close"):
                c.close()

        welcome = [c for c in created if "_ai_welcome" in getattr(c, "__qualname__", "")]
        assert len(welcome) >= 1
        assert (gid, uid) not in plugin2._welcome_pending
