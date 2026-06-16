"""Phase 5: 推送层测试 — 消息格式化逻辑。

运行方式:
  PYTHONPATH=. python -m pytest tests/test_signal_pusher.py -v
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.services.signal_pusher import format_signal_message, SIGNAL_META


def _make_signal(**overrides):
    """构造一个模拟 DailySignal 对象。"""
    defaults = dict(
        signal_date=datetime(2024, 1, 15),
        target_name="沪深300指数",
        target_symbol="000300.SH",
        final_signal="strong_buy",
        confidence=78.5,
        blogger_consensus_score=0.35,
        news_sentiment_score=0.2,
        participating_bloggers=5,
        analyzed_news_count=12,
        reasoning="多位博主看好短期反弹，新闻情绪偏正面。",
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


class TestFormatSignalMessagePremium:
    """付费版消息格式化测试。"""

    def test_contains_fund_radar_brand(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "FundRadar" in msg

    def test_contains_date(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "2024年01月15日" in msg

    def test_contains_signal_label(self):
        msg = format_signal_message(_make_signal(signal="strong_buy"), is_premium=True)
        assert "强烈买入" in msg

    def test_contains_target(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "沪深300指数" in msg
        assert "000300.SH" in msg

    def test_contains_confidence(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "78.5" in msg

    def test_contains_reasoning(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "博主看好" in msg

    def test_contains_disclaimer(self):
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "不构成投资建议" in msg

    def test_html_tags(self):
        """消息使用 Telegram HTML 格式。"""
        msg = format_signal_message(_make_signal(), is_premium=True)
        assert "<b>" in msg
        assert "</b>" in msg

    def test_all_signal_types(self):
        """所有信号类型都应该能格式化不崩溃。"""
        for sig_key in SIGNAL_META:
            msg = format_signal_message(_make_signal(final_signal=sig_key), is_premium=True)
            assert len(msg) > 50

    def test_unknown_signal_type(self):
        """未知信号类型用 fallback emoji。"""
        msg = format_signal_message(_make_signal(final_signal="unknown_xyz"), is_premium=True)
        assert "❓" in msg or "未知" in msg


class TestFormatSignalMessageFree:
    """免费版消息格式化测试。"""

    def test_contains_signal(self):
        msg = format_signal_message(_make_signal(), is_premium=False)
        assert "FundRadar" in msg

    def test_hides_confidence(self):
        """免费版不显示置信度。"""
        msg = format_signal_message(_make_signal(), is_premium=False)
        assert "78.5" not in msg

    def test_hides_reasoning(self):
        """免费版不显示分析说明。"""
        msg = format_signal_message(_make_signal(), is_premium=False)
        assert "博主看好" not in msg

    def test_shows_upgrade_hint(self):
        """免费版显示升级提示。"""
        msg = format_signal_message(_make_signal(), is_premium=False)
        assert "升级" in msg

    def test_shows_disclaimer(self):
        msg = format_signal_message(_make_signal(), is_premium=False)
        assert "不构成投资建议" in msg


class TestBloggerConsensusDisplay:
    """测试博主共识方向显示。"""

    def test_bullish_consensus(self):
        msg = format_signal_message(_make_signal(blogger_consensus_score=0.5), is_premium=True)
        assert "偏多" in msg

    def test_bearish_consensus(self):
        msg = format_signal_message(_make_signal(blogger_consensus_score=-0.5), is_premium=True)
        assert "偏空" in msg

    def test_neutral_consensus(self):
        msg = format_signal_message(_make_signal(blogger_consensus_score=0.0), is_premium=True)
        assert "中性" in msg


class TestNewsSentimentDisplay:
    """测试新闻情绪方向显示。"""

    def test_positive_news(self):
        msg = format_signal_message(_make_signal(news_sentiment_score=0.5), is_premium=True)
        assert "正面" in msg

    def test_negative_news(self):
        msg = format_signal_message(_make_signal(news_sentiment_score=-0.5), is_premium=True)
        assert "负面" in msg

    def test_neutral_news(self):
        msg = format_signal_message(_make_signal(news_sentiment_score=0.0), is_premium=True)
        assert "中性" in msg


class TestTelegramPushIntegration:
    """Telegram Bot 实际推送测试。"""

    @pytest.mark.network
    @pytest.mark.asyncio
    async def test_send_message(self):
        """测试真实 Telegram Bot 发消息。"""
        from app.services.telegram_bot import bot
        ok = await bot.send_message(
            "5591128702",
            "<b>🧪 FundRadar 测试</b>\n这是一条测试消息，验证推送链路正常。"
        )
        assert ok is True
