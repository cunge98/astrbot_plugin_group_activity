"""
Tests for the _calc_score() static method and cmd_score command:
  - score dimensions are clamped to their maximum values
  - grade thresholds (S/A/B/C/D) are correct
  - grade_color is included in the result
  - empty group data returns zero scores
  - cmd_score renders image or falls back to plain text
"""
import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from helpers import make_plugin, make_mock_event, make_config


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin(tmp_path):
    return make_plugin(tmp_path=str(tmp_path))


# ── _calc_score unit tests ────────────────────────────────────────────────────

class TestCalcScore:

    def _make_gd(self, msgs_per_day=100, active_members=8, total_members=10,
                 streak3=5, warned=0):
        """Build a minimal group-data dict for _calc_score."""
        today = datetime.date.today()
        days7 = [(today - datetime.timedelta(days=i)).isoformat() for i in range(7)]
        daily_stats = {d: msgs_per_day for d in days7}
        daily_checkins = {}
        for i, d in enumerate(days7):
            daily_checkins[d] = [f"u{j}" for j in range(active_members)]
        members = {}
        for j in range(total_members):
            uid = f"u{j}"
            members[uid] = {
                "last_active": 0, "warned_at": "2024-01-01" if j < warned else None,
                "nickname": uid, "join_time": 1000, "role": "member",
                "streak": 5 if j < streak3 else 0, "last_active_date": "",
            }
        return {"members": members, "daily_stats": daily_stats,
                "daily_checkins": daily_checkins}

    def test_empty_group_returns_zero_msg_and_activity(self, plugin):
        result = plugin._calc_score({})
        # msg/active/streak dims are 0; health is 20 (no warned members = full health)
        dims = {d["name"]: d for d in result["dims"]}
        assert dims["日均发言量"]["score"] == 0
        assert dims["活跃成员占比"]["score"] == 0
        assert dims["连续打卡率"]["score"] == 0
        assert result["grade"] == "D"
        assert result["total_members"] == 0

    def test_max_scores_clamp(self, plugin):
        gd = self._make_gd(msgs_per_day=10000, active_members=10, total_members=10,
                           streak3=10, warned=0)
        result = plugin._calc_score(gd)
        dims = {d["name"]: d for d in result["dims"]}
        assert dims["日均发言量"]["score"] == 35
        assert dims["活跃成员占比"]["score"] == 25
        assert dims["连续打卡率"]["score"] == 20
        assert dims["成员健康度"]["score"] == 20
        assert result["total"] == 100

    def test_grade_s_at_90(self, plugin):
        gd = self._make_gd(msgs_per_day=10000, active_members=10, total_members=10,
                           streak3=10, warned=0)
        result = plugin._calc_score(gd)
        assert result["total"] >= 90
        assert result["grade"] == "S"
        assert result["label"] == "传说级活跃群"
        assert result["icon"] == "🏆"

    def test_grade_d_empty(self, plugin):
        result = plugin._calc_score({})
        assert result["grade"] == "D"
        assert result["label"] == "需要振兴"

    def test_grade_color_present(self, plugin):
        result = plugin._calc_score({})
        assert "grade_color" in result
        assert result["grade_color"].startswith("#")

    def test_grade_color_varies_by_grade(self, plugin):
        low = plugin._calc_score({})
        high = plugin._calc_score(self._make_gd(msgs_per_day=10000, active_members=10,
                                                total_members=10, streak3=10, warned=0))
        # D grade and S grade should have different colors
        assert low["grade_color"] != high["grade_color"]

    def test_warned_members_reduce_health_score(self, plugin):
        gd_clean = self._make_gd(total_members=10, warned=0)
        gd_warned = self._make_gd(total_members=10, warned=5)
        r_clean = plugin._calc_score(gd_clean)
        r_warned = plugin._calc_score(gd_warned)
        dims_clean = {d["name"]: d for d in r_clean["dims"]}
        dims_warned = {d["name"]: d for d in r_warned["dims"]}
        assert dims_clean["成员健康度"]["score"] > dims_warned["成员健康度"]["score"]

    def test_msgs7_and_avg7_correct(self, plugin):
        gd = self._make_gd(msgs_per_day=70)
        result = plugin._calc_score(gd)
        assert result["msgs7"] == 70 * 7
        assert result["avg7"] == 70.0

    def test_dims_pct_clamped_to_100(self, plugin):
        gd = self._make_gd(msgs_per_day=10000, active_members=10, total_members=10,
                           streak3=10, warned=0)
        result = plugin._calc_score(gd)
        for d in result["dims"]:
            assert 0 <= d["pct"] <= 100


# ── cmd_score integration tests ───────────────────────────────────────────────

class TestCmdScore:

    async def _run_cmd_score(self, plugin, gid="1234"):
        event = make_mock_event(group_id=gid, sender_id="u1", sender_name="Alice")
        results = []
        async for r in plugin.cmd_score(event):
            results.append(r)
        return results

    async def test_cmd_score_renders_image(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        fake_img = b"\x89PNG..."
        plugin._img = AsyncMock(return_value=fake_img)
        event = make_mock_event(group_id="1234", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")
        results = []
        async for r in plugin.cmd_score(event):
            results.append(r)
        assert results
        plugin._img.assert_called_once()
        call_args = plugin._img.call_args
        # First positional arg should be T.SCORE callable
        import astrbot_plugin_group_activity.templates as T
        assert call_args[0][0] is T.SCORE

    async def test_cmd_score_plain_fallback_on_error(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin._img = AsyncMock(side_effect=RuntimeError("render failed"))
        event = make_mock_event(group_id="1234", sender_id="u1")
        event.plain_result = MagicMock(return_value="plain_result")
        results = []
        async for r in plugin.cmd_score(event):
            results.append(r)
        assert results
        event.plain_result.assert_called_once()
        assert "渲染失败" in str(event.plain_result.call_args)

    async def test_cmd_score_includes_date_and_group_name(self, tmp_path):
        plugin = make_plugin(tmp_path=str(tmp_path))
        plugin.activity_data["groups"]["5678"] = {
            "group_name": "测试群",
            "members": {},
            "daily_stats": {},
            "daily_checkins": {},
        }
        captured_data = {}

        async def fake_img(tmpl, data, **kw):
            captured_data.update(data)
            return b"fake"

        plugin._img = fake_img
        event = make_mock_event(group_id="5678", sender_id="u1")
        event.image_result = MagicMock(return_value="img_result")
        async for _ in plugin.cmd_score(event):
            pass
        assert "date" in captured_data
        assert captured_data["group_name"] == "测试群"
