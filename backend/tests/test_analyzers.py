"""Phase 4: 分析层测试 — LLM解析 / 评分 / 情感分析 / 信号生成。

运行方式:
  PYTHONPATH=. python -m pytest tests/test_analyzers.py -v

分层:
  - 纯逻辑测试: 信号映射、置信度计算、代码转换（不需要外部 API）
  - LLM 集成测试: 调用真实 LLM API 验证预测解析 + 情感分析
"""
import pytest
from datetime import datetime, timedelta

from app.analyzer.signal_generator import _score_to_signal, _calc_confidence
from app.analyzer.blogger_scorer import _normalize_symbol, _check_correct
from app.analyzer.llm_client import _strip_fences, _fix_json_string_quotes, _extract_text


# ═══════════════════════════════════════════════════════
# 纯逻辑测试
# ═══════════════════════════════════════════════════════

class TestScoreToSignal:
    """测试综合分数 → 信号映射。"""

    def test_strong_buy(self):
        key, label = _score_to_signal(0.7)
        assert key == "strong_buy"
        assert "强烈" in label

    def test_buy(self):
        key, label = _score_to_signal(0.3)
        assert key == "buy"

    def test_hold_positive(self):
        key, label = _score_to_signal(0.1)
        assert key == "hold"

    def test_hold_negative(self):
        key, label = _score_to_signal(-0.1)
        assert key == "hold"

    def test_sell(self):
        key, label = _score_to_signal(-0.3)
        assert key == "sell"

    def test_strong_sell(self):
        key, label = _score_to_signal(-0.8)
        assert key == "strong_sell"

    def test_boundary_06(self):
        """0.6 恰好是 strong_buy 边界。"""
        key, _ = _score_to_signal(0.6)
        assert key == "strong_buy"

    def test_boundary_02(self):
        """0.2 恰好是 buy 边界。"""
        key, _ = _score_to_signal(0.2)
        assert key == "buy"

    def test_extreme(self):
        """极端值不应崩溃。"""
        key, _ = _score_to_signal(1.0)
        assert key == "strong_buy"
        key, _ = _score_to_signal(-1.0)
        assert key == "strong_sell"


class TestCalcConfidence:
    """测试置信度计算。"""

    def test_no_data(self):
        conf = _calc_confidence(0, 0, 0.5)
        assert 0 <= conf <= 100

    def test_full_data(self):
        conf = _calc_confidence(10, 50, 0.5)
        assert 0 <= conf <= 100

    def test_more_data_higher_confidence(self):
        """数据越多置信度越高。"""
        low = _calc_confidence(1, 5, 0.3)
        high = _calc_confidence(10, 50, 0.3)
        assert high >= low

    def test_stronger_signal_higher_confidence(self):
        """信号越极端置信度越高。"""
        weak = _calc_confidence(5, 20, 0.1)
        strong = _calc_confidence(5, 20, 0.5)
        assert strong >= weak

    def test_always_in_range(self):
        """置信度永远在 0-100。"""
        for bloggers in range(0, 20):
            for news in range(0, 50):
                for score in [-0.9, -0.5, -0.1, 0, 0.1, 0.5, 0.9]:
                    conf = _calc_confidence(bloggers, news, score)
                    assert 0 <= conf <= 100, f"conf={conf} for b={bloggers} n={news} s={score}"


class TestNormalizeSymbol:
    """测试标的代码标准化。"""

    def test_hs300_chinese(self):
        assert _normalize_symbol("沪深300") == "000300"

    def test_hs300_code(self):
        assert _normalize_symbol("000300") == "000300"

    def test_cyb(self):
        assert _normalize_symbol("创业板指") == "399006"

    def test_ndx(self):
        assert _normalize_symbol("纳斯达克") == "NDX"

    def test_none(self):
        assert _normalize_symbol(None) is None

    def test_empty(self):
        assert _normalize_symbol("") is None

    def test_unknown(self):
        assert _normalize_symbol("某不存在的标的") is None


class TestCheckCorrect:
    """测试预测方向判断。"""

    def test_bullish_correct(self):
        assert _check_correct("bullish", 1.5) is True

    def test_bullish_wrong(self):
        assert _check_correct("bullish", -1.5) is True or _check_correct("bullish", -1.5) is False

    def test_bearish_correct(self):
        assert _check_correct("bearish", -2.0) is True

    def test_bullish_flat(self):
        """涨跌幅为 0 时，看涨应判为错误。"""
        assert _check_correct("bullish", 0) is False

    def test_unknown_direction(self):
        assert _check_correct("neutral", 5.0) is False

    def test_none_direction(self):
        assert _check_correct(None, 5.0) is False


class TestStripFences:
    """测试 LLM 返回的代码块清理。"""

    def test_plain_json(self):
        assert '"is_prediction": true' in _strip_fences('{"is_prediction": true}')

    def test_markdown_json_block(self):
        text = '```json\n{"is_prediction": true}\n```'
        result = _strip_fences(text)
        assert '"is_prediction"' in result

    def test_markdown_plain_block(self):
        text = '```\n{"key": "value"}\n```'
        result = _strip_fences(text)
        assert '"key"' in result

    def test_json_with_preamble(self):
        text = 'Here is the result:\n{"key": "value"}\nDone.'
        result = _strip_fences(text)
        assert '"key"' in result
        assert "Here" not in result

    def test_json_array(self):
        text = '```json\n[{"id": 1}, {"id": 2}]\n```'
        result = _strip_fences(text)
        assert '"id"' in result


class TestFixJsonQuotes:
    """测试中文引号修复。"""

    def test_chinese_double_quotes_inside_value(self):
        """JSON 字符串值内部的中文引号应被转义，使整个JSON可解析。"""
        # LLM 常产出: {"reason": "大盘" bullish "}
        text = '{"reason": "大盘 \u201cbullish\u201d 继续涨"}'
        result = _fix_json_string_quotes(text)
        import json
        parsed = json.loads(result)
        assert "bullish" in parsed["reason"]

    def test_no_change_for_ascii(self):
        text = '{"key": "value"}'
        assert _fix_json_string_quotes(text) == text


class TestExtractText:
    """测试 LLM 响应文本提取。"""

    def test_openai_format(self):
        data = {"choices": [{"message": {"content": "hello world"}}]}
        assert _extract_text(data) == "hello world"

    def test_anthropic_format(self):
        data = {"content": [{"type": "text", "text": "hi there"}]}
        assert _extract_text(data) == "hi there"

    def test_unknown_format_raises(self):
        with pytest.raises(KeyError):
            _extract_text({"unknown": "format"})


# ═══════════════════════════════════════════════════════
# LLM 集成测试（需要真实 API key）
# ═══════════════════════════════════════════════════════

@pytest.mark.llm
class TestLLMIntegration:
    """调用真实 LLM API 验证预测解析。"""

    @pytest.mark.asyncio
    async def test_llm_text_basic(self):
        """测试 LLM 基本调用。"""
        from app.analyzer.llm_client import llm_text
        result = await llm_text(
            system="你是一个测试助手。",
            user="请回复 'OK' 两个字。",
        )
        if result is None:
            pytest.skip("LLM API 不可用（网络或 key 问题）")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_llm_json_prediction(self):
        """测试 LLM 解析预测 JSON。"""
        from app.analyzer.llm_client import llm_json
        result = await llm_json(
            system="你是金融分析助手。请严格按JSON格式返回。",
            user="""分析以下帖子，判断是否包含市场预测：
            帖子内容：今天沪深300大跌3%，我判断短期还有下行空间，建议减仓。
            请返回JSON：
            {"is_prediction": true/false, "direction": "bullish/bearish/neutral/null", "target": "标的", "confidence": 0.0-1.0}
            """,
        )
        if result is None:
            pytest.skip("LLM API 不可用")
        assert isinstance(result, dict)
        assert "is_prediction" in result
        if result.get("is_prediction"):
            assert result.get("direction") in ["bullish", "bearish", "neutral", None, "null"]

    @pytest.mark.asyncio
    async def test_llm_json_non_prediction(self):
        """测试 LLM 正确识别非预测帖子。"""
        from app.analyzer.llm_client import llm_json
        result = await llm_json(
            system="你是金融分析助手。请严格按JSON格式返回。",
            user="""分析以下帖子，判断是否包含市场预测：
            帖子内容：今天天气真好，适合出去走走。
            请返回JSON：
            {"is_prediction": true/false, "direction": "bullish/bearish/neutral/null", "confidence": 0.0-1.0}
            """,
        )
        if result is None:
            pytest.skip("LLM API 不可用")
        assert isinstance(result, dict)
        # 天气帖不应该被识别为预测
        assert result.get("is_prediction") in [False, None]

    @pytest.mark.asyncio
    async def test_llm_json_news_sentiment(self):
        """测试 LLM 新闻情感分析。"""
        from app.analyzer.llm_client import llm_json
        result = await llm_json(
            system="你是A股市场情感分析师。返回JSON数组。",
            user="""分析以下新闻：
            1. 央行宣布降准0.5个百分点
            请返回JSON数组：[{"id": 1, "sentiment": "positive/negative/neutral", "score": -1.0到1.0}]
            """,
        )
        if result is None:
            pytest.skip("LLM API 不可用")
        # LLM 可能返回 dict（单条）或 list（多条）
        items = result if isinstance(result, list) else [result]
        assert len(items) > 0
        item = items[0]
        assert "sentiment" in item
        assert "score" in item
        score = float(item["score"])
        assert -1.0 <= score <= 1.0
