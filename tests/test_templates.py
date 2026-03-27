"""
Tests for templates.py – theme data, SLOGANS, and every template function.

Each template function is called with each of the four theme names and
validated for basic HTML correctness.  No rendering engine is involved;
we just check the string output.
"""
import pytest
import astrbot_plugin_group_activity.templates as T

ALL_THEMES = list(T.THEMES.keys())

# ── SLOGANS / get_slogan ──────────────────────────────────────────────────────

class TestSlogans:

    def test_slogans_list_is_nonempty(self):
        assert len(T.SLOGANS) > 0

    def test_all_slogans_are_nonempty_strings(self):
        for s in T.SLOGANS:
            assert isinstance(s, str)
            assert s.strip() != ""

    def test_get_slogan_returns_string(self):
        result = T.get_slogan()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_slogan_always_from_list(self):
        for _ in range(30):
            assert T.get_slogan() in T.SLOGANS


# ── THEMES dict ───────────────────────────────────────────────────────────────

class TestThemes:

    def test_four_themes_defined(self):
        assert set(T.THEMES.keys()) == {"清新蓝", "活力橙", "优雅紫", "暗夜模式"}

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_theme_has_required_color_keys(self, theme):
        required = {
            "hdr1", "hdr2",
            "bg", "text", "text2", "subtle",
            "sec_bg", "row_alt", "border", "sec_border",
            "sec_text", "ft_bg",
        }
        missing = required - set(T.THEMES[theme].keys())
        assert not missing, f"Theme '{theme}' missing: {missing}"

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_all_color_values_are_nonempty_strings(self, theme):
        for key, val in T.THEMES[theme].items():
            assert isinstance(val, str), f"{theme}.{key} is not a string"
            assert val.strip() != "", f"{theme}.{key} is blank"

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_color_values_start_with_hash_or_rgb(self, theme):
        """Spot-check that color values look like CSS colors."""
        for key, val in T.THEMES[theme].items():
            assert val.startswith("#") or val.startswith("rgb"), \
                f"{theme}.{key} = '{val}' doesn't look like a CSS color"


# ── _css base template ────────────────────────────────────────────────────────

class TestCss:

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_doctype_html(self, theme):
        result = T._css(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_opens_container_div(self, theme):
        result = T._css(theme)
        assert '<div class="container">' in result

    def test_unknown_theme_falls_back_to_default(self):
        result = T._css("不存在的主题")
        assert "<!DOCTYPE html>" in result
        # Should embed 清新蓝 bg color
        assert T.THEMES["清新蓝"]["bg"] in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_embeds_theme_bg_color(self, theme):
        result = T._css(theme)
        assert T.THEMES[theme]["bg"] in result


# ── Template functions return valid HTML ──────────────────────────────────────
# Each parametrized test calls the function with all four themes and
# verifies minimum HTML sanity.

class TestHelpTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_string_with_doctype(self, theme):
        result = T.HELP(theme)
        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_command_list(self, theme):
        result = T.HELP(theme)
        assert "活跃排行" in result
        assert "活跃查询" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_brand_footer(self, theme):
        result = T.HELP(theme)
        assert "群活跃检测" in result


class TestStatusTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.STATUS(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_config_labels(self, theme):
        result = T.STATUS(theme)
        assert "全局开关" in result
        assert "不活跃阈值" in result


class TestRankTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.RANK(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_table_structure(self, theme):
        result = T.RANK(theme)
        assert "<table" in result
        assert "<th" in result


class TestQueryTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.QUERY(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_progress_bar_class(self, theme):
        result = T.QUERY(theme)
        assert "pw" in result   # .pw = progress-wrapper class


class TestInactiveTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.INACTIVE(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_table(self, theme):
        result = T.INACTIVE(theme)
        assert "<table" in result


class TestAllOkTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.ALL_OK(theme)
        assert "<!DOCTYPE html>" in result


class TestWeeklyTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.WEEKLY(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_chart_structure(self, theme):
        result = T.WEEKLY(theme)
        assert "mini-bars" in result or "chart" in result.lower()

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_ai_blurb_placeholders(self, theme):
        result = T.WEEKLY(theme)
        assert "ai1" in result or "ai_blurb" in result


class TestResultTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.RESULT(theme)
        assert "<!DOCTYPE html>" in result


class TestStatsTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.STATS(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_donut_chart_class(self, theme):
        result = T.STATS(theme)
        assert "donut" in result


class TestTrendTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.TREND(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_bar_chart_structure(self, theme):
        result = T.TREND(theme)
        assert "mini-bar" in result or "bar" in result.lower()


class TestHeatmapTemplate:
    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_returns_html(self, theme):
        result = T.HEATMAP(theme)
        assert "<!DOCTYPE html>" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_24h_label(self, theme):
        result = T.HEATMAP(theme)
        assert "24小时热力图" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_svg_chart(self, theme):
        result = T.HEATMAP(theme)
        assert "<svg" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_peak_hour_placeholder(self, theme):
        result = T.HEATMAP(theme)
        assert "peak_hour" in result

    @pytest.mark.parametrize("theme", ALL_THEMES)
    def test_contains_time_slots(self, theme):
        result = T.HEATMAP(theme)
        assert "深夜" in result and "早间" in result and "晚间" in result
