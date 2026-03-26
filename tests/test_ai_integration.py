"""
Tests for AI integration helpers: _ai_warn, _ai_judge, _ai (gate).

All LLM calls are mocked so these tests run without an actual AI provider.
"""
import pytest
from unittest.mock import AsyncMock
from astrbot_plugin_group_activity.main import FALLBACK, AI_PERSONAS


# ── _ai (gate) ────────────────────────────────────────────────────────────────

class TestAiGate:

    async def test_returns_none_when_ai_disabled(self, plugin):
        plugin.config["ai_enabled"] = False
        result = await plugin._ai("test prompt")
        assert result is None

    async def test_returns_none_when_no_provider(self, plugin):
        plugin.config["ai_enabled"] = True
        plugin.config["ai_provider"] = ""
        plugin.context.get_current_chat_provider_id = AsyncMock(return_value=None)
        result = await plugin._ai("test prompt")
        assert result is None

    async def test_returns_completion_text_on_success(self, plugin):
        plugin.config["ai_enabled"] = True
        plugin.config["ai_provider"] = "test_provider"

        mock_response = AsyncMock()
        mock_response.completion_text = "AI says hello"
        plugin.context.llm_generate = AsyncMock(return_value=mock_response)

        result = await plugin._ai("hello")
        assert result == "AI says hello"

    async def test_returns_none_on_exception(self, plugin):
        plugin.config["ai_enabled"] = True
        plugin.config["ai_provider"] = "test_provider"
        plugin.context.llm_generate = AsyncMock(side_effect=RuntimeError("boom"))

        result = await plugin._ai("hello")
        assert result is None


# ── _ai_warn ──────────────────────────────────────────────────────────────────

class TestAiWarn:

    async def test_uses_ai_response_when_available(self, plugin):
        plugin._ai = AsyncMock(return_value="你已经潜水太久了！")
        result = await plugin._ai_warn("张三", 10, 24)
        assert result == "你已经潜水太久了！"

    async def test_strips_whitespace_from_ai_response(self, plugin):
        plugin._ai = AsyncMock(return_value="  请快快发言！  ")
        result = await plugin._ai_warn("张三", 10, 24)
        assert result == "请快快发言！"

    async def test_truncates_ai_response_at_200_chars(self, plugin):
        long_msg = "A" * 300
        plugin._ai = AsyncMock(return_value=long_msg)
        result = await plugin._ai_warn("张三", 10, 24)
        assert len(result) == 200

    async def test_falls_back_to_template_when_ai_returns_none(self, plugin):
        plugin._ai = AsyncMock(return_value=None)
        result = await plugin._ai_warn("李四", 7, 24)
        # Must contain the nickname, days, and hours from the FALLBACK templates
        assert "李四" in result
        assert "7" in result
        assert "24" in result

    async def test_fallback_message_is_from_fallback_list(self, plugin):
        plugin._ai = AsyncMock(return_value=None)
        result = await plugin._ai_warn("王五", 3, 12)
        # The fallback must be one of the formatted FALLBACK strings
        expected_texts = [
            f.format(nickname="王五", days=3, hours=12) for f in FALLBACK
        ]
        assert result in expected_texts


# ── _ai_judge ─────────────────────────────────────────────────────────────────

class TestAiJudge:

    async def test_pass_with_comment(self, plugin):
        plugin._ai = AsyncMock(return_value="通过\n你的理由很充分！")
        ok, comment = await plugin._ai_judge("甲", "我在上班", 7)
        assert ok is True
        assert comment == "你的理由很充分！"

    async def test_reject_with_comment(self, plugin):
        plugin._ai = AsyncMock(return_value="驳回\n理由不够充分。")
        ok, comment = await plugin._ai_judge("乙", "忘了", 7)
        assert ok is False
        assert comment == "理由不够充分。"

    async def test_pass_single_line_returns_default_comment(self, plugin):
        plugin._ai = AsyncMock(return_value="通过")
        ok, comment = await plugin._ai_judge("丙", "有事", 7)
        assert ok is True
        assert comment == "赦免~"

    async def test_reject_single_line_returns_default_comment(self, plugin):
        plugin._ai = AsyncMock(return_value="驳回")
        ok, comment = await plugin._ai_judge("丁", "懒", 7)
        assert ok is False
        assert comment == "理由太敷衍！"

    async def test_returns_false_when_ai_unavailable(self, plugin):
        plugin._ai = AsyncMock(return_value=None)
        ok, comment = await plugin._ai_judge("戊", "理由", 7)
        assert ok is False
        assert "离线" in comment

    async def test_comment_truncated_at_150_chars(self, plugin):
        long_comment = "很好" * 100   # 200 chars
        plugin._ai = AsyncMock(return_value=f"通过\n{long_comment}")
        ok, comment = await plugin._ai_judge("己", "理由", 7)
        assert ok is True
        assert len(comment) <= 150

    async def test_pass_requires_通过_in_first_line(self, plugin):
        """'通过' must appear in line[0]; other lines don't affect the verdict."""
        plugin._ai = AsyncMock(return_value="这次通过了\n很好")
        ok, _ = await plugin._ai_judge("庚", "理由", 7)
        assert ok is True

    async def test_reject_when_通过_not_in_first_line(self, plugin):
        plugin._ai = AsyncMock(return_value="驳回你的请求\n再想想")
        ok, _ = await plugin._ai_judge("辛", "理由", 7)
        assert ok is False


# ── _persona ──────────────────────────────────────────────────────────────────

class TestPersonaIntegration:

    def test_all_built_in_styles_have_persona(self, plugin):
        """Every style key in AI_PERSONAS is retrievable via _persona."""
        plugin.config["ai_custom_prompt"] = ""
        for style in AI_PERSONAS:
            plugin.config["ai_style"] = style
            assert plugin._persona() == AI_PERSONAS[style]

    def test_custom_prompt_overrides_style(self, plugin):
        plugin.config["ai_style"] = "严苛群管"
        plugin.config["ai_custom_prompt"] = "自定义人设"
        assert plugin._persona() == "自定义人设"
