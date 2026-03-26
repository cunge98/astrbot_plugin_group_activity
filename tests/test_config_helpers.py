"""
Tests for pure configuration and utility helper methods:
  _dur, _nk, _ls, _wl/_bl caching, _mon, _mode, _theme, _persona
"""
import time
import pytest
from helpers import make_config, make_plugin


# ── _dur ─────────────────────────────────────────────────────────────────────

class TestDur:
    """_dur converts elapsed seconds to a Chinese human-readable string."""

    def test_zero_seconds(self, plugin):
        assert plugin._dur(0) == "刚刚"

    def test_59_seconds(self, plugin):
        assert plugin._dur(59) == "刚刚"

    def test_exactly_one_minute(self, plugin):
        assert plugin._dur(60) == "1分钟前"

    def test_two_and_a_half_minutes(self, plugin):
        assert plugin._dur(150) == "2分钟前"

    def test_boundary_just_under_hour(self, plugin):
        # 3599 s → 59 min
        assert plugin._dur(3599) == "59分钟前"

    def test_exactly_one_hour(self, plugin):
        assert plugin._dur(3600) == "1小时前"

    def test_two_hours(self, plugin):
        assert plugin._dur(7200) == "2小时前"

    def test_boundary_just_under_day(self, plugin):
        # 86399 s → 23 h
        assert plugin._dur(86399) == "23小时前"

    def test_exactly_one_day(self, plugin):
        assert plugin._dur(86400) == "1天前"

    def test_seven_days(self, plugin):
        assert plugin._dur(7 * 86400) == "7天前"

    def test_large_value(self, plugin):
        assert plugin._dur(30 * 86400) == "30天前"


# ── _nk ──────────────────────────────────────────────────────────────────────

class TestNk:
    """_nk returns a safe display nickname, truncated at 12 chars."""

    def test_normal_name(self, plugin):
        assert plugin._nk("Alice", 123) == "Alice"

    def test_name_exactly_12_chars(self, plugin):
        name = "A" * 12
        assert plugin._nk(name, 1) == name

    def test_name_longer_than_12_chars(self, plugin):
        name = "A" * 20
        assert plugin._nk(name, 1) == "A" * 12

    def test_empty_name_falls_back_to_uid(self, plugin):
        assert plugin._nk("", 9876) == "9876"

    def test_whitespace_only_name_falls_back_to_uid(self, plugin):
        assert plugin._nk("   ", 9876) == "9876"

    def test_none_name_falls_back_to_uid(self, plugin):
        assert plugin._nk(None, 9876) == "9876"

    def test_uid_is_stringified(self, plugin):
        result = plugin._nk("", 42)
        assert result == "42"
        assert isinstance(result, str)

    def test_chinese_name_truncation(self, plugin):
        name = "这是一个超过十二个字的昵称哦哦哦"
        result = plugin._nk(name, 1)
        assert result == name[:12]


# ── _ls ──────────────────────────────────────────────────────────────────────

class TestLs:
    """_ls parses list-or-newline-separated config values."""

    def test_list_of_strings(self, plugin):
        plugin.config["whitelist_groups"] = ["111", "222", "333"]
        assert plugin._ls("whitelist_groups") == ["111", "222", "333"]

    def test_list_of_ints_converted_to_strings(self, plugin):
        plugin.config["whitelist_groups"] = [111, 222]
        assert plugin._ls("whitelist_groups") == ["111", "222"]

    def test_empty_list(self, plugin):
        plugin.config["whitelist_groups"] = []
        assert plugin._ls("whitelist_groups") == []

    def test_list_filters_blank_entries(self, plugin):
        plugin.config["whitelist_groups"] = ["111", "", "  ", "222"]
        assert plugin._ls("whitelist_groups") == ["111", "222"]

    def test_newline_separated_string(self, plugin):
        plugin.config["whitelist_groups"] = "111\n222\n333"
        assert plugin._ls("whitelist_groups") == ["111", "222", "333"]

    def test_newline_string_strips_whitespace(self, plugin):
        plugin.config["whitelist_groups"] = "  111  \n  222  "
        assert plugin._ls("whitelist_groups") == ["111", "222"]

    def test_newline_string_filters_blank_lines(self, plugin):
        plugin.config["whitelist_groups"] = "111\n\n222"
        assert plugin._ls("whitelist_groups") == ["111", "222"]

    def test_missing_key_returns_empty(self, plugin):
        assert plugin._ls("nonexistent_key") == []


# ── _wl / _bl caching ────────────────────────────────────────────────────────

class TestWhitelistBlacklistCache:
    """_wl and _bl cache their results for _cache_ttl seconds."""

    def test_wl_returns_configured_groups(self, plugin):
        plugin.config["whitelist_groups"] = ["100", "200"]
        plugin._wl_cache = None           # force refresh
        assert plugin._wl() == ["100", "200"]

    def test_bl_returns_configured_groups(self, plugin):
        plugin.config["blacklist_groups"] = ["999"]
        plugin._bl_cache = None
        plugin._wl_cache = None
        assert plugin._bl() == ["999"]

    def test_wl_uses_cache_within_ttl(self, plugin):
        plugin.config["whitelist_groups"] = ["100"]
        plugin._wl_cache = None
        plugin._wl()                       # prime cache
        plugin.config["whitelist_groups"] = ["999"]  # change config
        # Should still return cached value
        assert plugin._wl() == ["100"]

    def test_wl_refreshes_after_ttl(self, plugin):
        plugin.config["whitelist_groups"] = ["100"]
        plugin._wl_cache = None
        plugin._wl()                       # prime cache
        plugin._cache_time = time.time() - plugin._cache_ttl - 1  # expire it
        plugin.config["whitelist_groups"] = ["999"]
        assert plugin._wl() == ["999"]

    def test_bl_triggers_wl_refresh(self, plugin):
        plugin.config["blacklist_groups"] = ["500"]
        plugin._bl_cache = None
        plugin._wl_cache = None
        result = plugin._bl()
        assert result == ["500"]


# ── _mon ─────────────────────────────────────────────────────────────────────

class TestMon:
    """_mon decides whether a group should be monitored."""

    def _fresh(self, tmp_path, **cfg):
        p = make_plugin(config=make_config(**cfg), tmp_path=tmp_path)
        p._wl_cache = None
        p._bl_cache = None
        return p

    def test_disabled_plugin_never_monitors(self, tmp_path):
        p = self._fresh(tmp_path, enabled=False)
        assert p._mon("12345") is False

    def test_blacklisted_group_not_monitored(self, tmp_path):
        p = self._fresh(tmp_path, blacklist_groups=["12345"])
        assert p._mon("12345") is False

    def test_blacklist_takes_priority_over_whitelist(self, tmp_path):
        p = self._fresh(tmp_path,
                        whitelist_groups=["12345"],
                        blacklist_groups=["12345"])
        assert p._mon("12345") is False

    def test_group_in_whitelist_is_monitored(self, tmp_path):
        p = self._fresh(tmp_path, whitelist_groups=["12345"])
        assert p._mon("12345") is True

    def test_group_not_in_whitelist_skipped(self, tmp_path):
        p = self._fresh(tmp_path, whitelist_groups=["99999"])
        assert p._mon("12345") is False

    def test_empty_whitelist_monitors_all(self, tmp_path):
        p = self._fresh(tmp_path, whitelist_groups=[])
        assert p._mon("12345") is True

    def test_gid_is_coerced_to_string(self, tmp_path):
        p = self._fresh(tmp_path, whitelist_groups=["12345"])
        assert p._mon(12345) is True


# ── _mode ─────────────────────────────────────────────────────────────────────

class TestMode:
    def test_global_mode_when_no_whitelist(self, plugin):
        plugin.config["whitelist_groups"] = []
        plugin._wl_cache = None
        assert plugin._mode() == "全局模式"

    def test_whitelist_mode_when_whitelist_set(self, plugin):
        plugin.config["whitelist_groups"] = ["123"]
        plugin._wl_cache = None
        assert plugin._mode() == "白名单模式"


# ── _theme ────────────────────────────────────────────────────────────────────

class TestTheme:
    def test_returns_configured_theme(self, plugin):
        plugin.config["theme"] = "活力橙"
        assert plugin._theme() == "活力橙"

    def test_default_theme(self, plugin):
        plugin.config.pop("theme", None)
        assert plugin._theme() == "清新蓝"


# ── _persona ──────────────────────────────────────────────────────────────────

class TestPersona:
    def test_returns_custom_prompt_when_set(self, plugin):
        plugin.config["ai_custom_prompt"] = "你是一只可爱的小猫。"
        assert plugin._persona() == "你是一只可爱的小猫。"

    def test_ignores_whitespace_only_custom_prompt(self, plugin):
        plugin.config["ai_custom_prompt"] = "   "
        plugin.config["ai_style"] = "严苛群管"
        persona = plugin._persona()
        # Should fall back to the style persona, not the blank custom prompt
        assert "群管理" in persona or "严肃" in persona

    def test_returns_named_style_persona(self, plugin):
        plugin.config["ai_custom_prompt"] = ""
        plugin.config["ai_style"] = "古风仙人"
        assert "仙人" in plugin._persona() or "修真" in plugin._persona()

    def test_unknown_style_falls_back_to_default(self, plugin):
        from astrbot_plugin_group_activity.main import AI_PERSONAS
        plugin.config["ai_custom_prompt"] = ""
        plugin.config["ai_style"] = "不存在的风格"
        assert plugin._persona() == AI_PERSONAS["傲娇萌妹"]
