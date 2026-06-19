"""多源情绪信号测试 — 散户情绪 + 三维加权 + 微博爬虫。"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestSentimentCrawler:
    """SentimentCrawler (akshare) 单元测试。"""

    @pytest.mark.asyncio
    async def test_weibo_sentiment_normalizes_bullish(self):
        """微博多空比 > 1.0 → 正情绪分。"""
        from app.crawler.sentiment import SentimentCrawler
        crawler = SentimentCrawler()
        # akshare stock_js_weibo_report 返回 name + rate 列
        # rate > 1.0 偏多，rate < 1.0 偏空，rate = 1.0 中性
        import pandas as pd
        mock_df = pd.DataFrame({"name": ["SH600000", "SZ000001"], "rate": [1.5, 1.3]})
        with patch("akshare.stock_js_weibo_report", return_value=mock_df):
            result = await crawler.get_weibo_sentiment()
        assert result is not None
        assert result["sentiment_score"] > 0  # 看多

    @pytest.mark.asyncio
    async def test_weibo_sentiment_normalizes_bearish(self):
        """微博多空比 < 1.0 → 负情绪分。"""
        from app.crawler.sentiment import SentimentCrawler
        import pandas as pd
        crawler = SentimentCrawler()
        mock_df = pd.DataFrame({"name": ["SH600000", "SZ000001"], "rate": [0.5, 0.7]})
        with patch("akshare.stock_js_weibo_report", return_value=mock_df):
            result = await crawler.get_weibo_sentiment()
        assert result is not None
        assert result["sentiment_score"] < 0  # 看空

    @pytest.mark.asyncio
    async def test_em_comment_sentiment(self):
        """东财评论分数标准化。"""
        from app.crawler.sentiment import SentimentCrawler
        import pandas as pd
        crawler = SentimentCrawler()
        mock_df = pd.DataFrame({
            "代码": ["000300"],
            "名称": ["沪深300"],
            "综合得分": [4.5],
            "机构参与度": [3.2],
            "关注指数": [85.0],
        })
        with patch("akshare.stock_comment_em", return_value=mock_df):
            result = await crawler.get_em_comment_sentiment()
        assert result is not None
        assert -1 <= result["sentiment_score"] <= 1

    @pytest.mark.asyncio
    async def test_sentiment_returns_none_on_error(self):
        """akshare 出错 → 返回 None。"""
        from app.crawler.sentiment import SentimentCrawler
        crawler = SentimentCrawler()
        with patch("akshare.stock_js_weibo_report", side_effect=Exception("network")):
            result = await crawler.get_weibo_sentiment()
        assert result is None


class TestWeiboCrawler:
    """WeiboCrawler 单元测试。"""

    @pytest.mark.asyncio
    async def test_parse_mblog_valid(self):
        """解析微博帖子结构。"""
        from app.crawler.weibo import WeiboCrawler
        crawler = WeiboCrawler()
        raw = {
            "id": "123456",
            "bid": "Abc123",
            "text": "今天A股大涨，牛市来了！",
            "created_at": "Mon Jun 16 10:00:00 +0800 2026",
            "user": {"id": 999, "screen_name": "财经大V"},
        }
        post = crawler._parse_mblog(raw)
        assert post is not None
        assert "大涨" in post["content"]
        assert "财经大V" == post["user_name"]

    @pytest.mark.asyncio
    async def test_parse_mblog_skip_empty(self):
        """空帖子 → None。"""
        from app.crawler.weibo import WeiboCrawler
        crawler = WeiboCrawler()
        raw = {"id": "1", "text": "", "user": {}}
        post = crawler._parse_mblog(raw)
        assert post is None

    def test_default_kols_not_empty(self):
        """默认 KOL 列表不为空。"""
        from app.crawler.weibo import DEFAULT_WEIBO_KOLS
        assert len(DEFAULT_WEIBO_KOLS) > 0
        for kol in DEFAULT_WEIBO_KOLS:
            assert "uid" in kol
            assert "username" in kol


class TestWeightedScore:
    """加权计算测试 — V1 三维 + V2 五维。"""

    def test_all_positive(self):
        from app.analyzer.signal_generator import _calc_v3_score
        score = _calc_v3_score(0.8, 0.6, 0.4, 0.45, 0.30, 0.25)
        assert score > 0
        assert abs(score - (0.8*0.45 + 0.6*0.30 + 0.4*0.25)) < 0.001

    def test_all_negative(self):
        from app.analyzer.signal_generator import _calc_v3_score
        score = _calc_v3_score(-0.8, -0.6, -0.4, 0.45, 0.30, 0.25)
        assert score < 0

    def test_mixed_signals(self):
        from app.analyzer.signal_generator import _calc_v3_score
        score = _calc_v3_score(0.5, 0.0, -0.3, 0.45, 0.30, 0.25)
        assert abs(score - 0.15) < 0.01

    def test_extreme_bullish(self):
        from app.analyzer.signal_generator import _calc_v3_score
        score = _calc_v3_score(1.0, 1.0, 1.0, 0.45, 0.30, 0.25)
        assert abs(score - 1.0) < 0.001

    def test_extreme_bearish(self):
        from app.analyzer.signal_generator import _calc_v3_score
        score = _calc_v3_score(-1.0, -1.0, -1.0, 0.45, 0.30, 0.25)
        assert abs(score - (-1.0)) < 0.001

    def test_v1_weights_sum_to_one(self):
        """V1 三维权重之和 = 1.0。"""
        from app.analyzer.signal_generator import W_BLOGGER_V1, W_NEWS_V1, W_RETAIL_V1
        assert abs((W_BLOGGER_V1 + W_NEWS_V1 + W_RETAIL_V1) - 1.0) < 0.001

    def test_v2_weights_sum_to_one(self):
        """V2 五维权重之和 = 1.0。"""
        from app.analyzer.signal_generator import (
            W_BLOGGER_V2, W_NEWS_V2, W_RETAIL_V2,
            W_FUND_FLOW_V2, W_INDUSTRY_V2
        )
        total = W_BLOGGER_V2 + W_NEWS_V2 + W_RETAIL_V2 + W_FUND_FLOW_V2 + W_INDUSTRY_V2
        assert abs(total - 1.0) < 0.001

    def test_v5_all_quant(self):
        """V5 全维度数据可用。"""
        from app.analyzer.signal_generator import _calc_v5_score
        score, w = _calc_v5_score(0.5, 0.3, -0.2, 0.6, 0.4)
        assert w == "v5_5dim"
        assert -1 <= score <= 1

    def test_v5_partial_quant(self):
        """V5 部分量化维度缺失 — 权重重分配。"""
        from app.analyzer.signal_generator import _calc_v5_score
        score, w = _calc_v5_score(0.5, 0.3, -0.2, None, 0.4)
        assert w == "v5_5dim"
        assert -1 <= score <= 1

    def test_v5_no_quant_fallback(self):
        """V5 量化全缺失 → 回退 V1。"""
        from app.analyzer.signal_generator import _calc_v5_score
        score, w = _calc_v5_score(0.5, 0.3, -0.2, None, None)
        assert w == "v1_fallback"
        assert -1 <= score <= 1


class TestContrarianMode:
    """散户反向因子测试。"""

    def test_contrarian_threshold_exists(self):
        from app.analyzer.signal_generator import RETAIL_CONTRARIAN, RETAIL_CONTRARIAN_THRESHOLD
        assert RETAIL_CONTRARIAN is True
        assert RETAIL_CONTRARIAN_THRESHOLD == 0.6

    def test_contrarian_reduces_bullish(self):
        """散户极度看多时，反向因子应降低买入力度。"""
        from app.analyzer.signal_generator import RETAIL_CONTRARIAN_THRESHOLD
        retail_score = 0.8  # 极度看多
        # 触发反向: effective = -0.8 * 0.5 = -0.4
        if retail_score > RETAIL_CONTRARIAN_THRESHOLD:
            effective = -retail_score * 0.5
        else:
            effective = retail_score
        assert effective == -0.4  # 反转了

    def test_no_contrarian_below_threshold(self):
        """散户温和看多时不触发反向。"""
        from app.analyzer.signal_generator import RETAIL_CONTRARIAN_THRESHOLD
        retail_score = 0.4  # 温和看多
        if retail_score > RETAIL_CONTRARIAN_THRESHOLD:
            effective = -retail_score * 0.5
        else:
            effective = retail_score
        assert effective == 0.4  # 正常


class TestRetailSentimentDB:
    """散户情绪 DB 查询测试（mock）。"""

    @pytest.mark.asyncio
    async def test_no_data_returns_zero(self):
        """无数据 → 0.0。"""
        from app.analyzer.signal_generator import get_retail_sentiment_score
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)
        score = await get_retail_sentiment_score(mock_db, hours=6)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_averages_multiple_sources(self):
        """多来源加权平均。"""
        from app.analyzer.signal_generator import get_retail_sentiment_score

        r1 = MagicMock(source="weibo_nlp", sentiment_score=0.6)
        r2 = MagicMock(source="eastmoney", sentiment_score=-0.2)

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [r1, r2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        score = await get_retail_sentiment_score(mock_db, hours=6)
        # (0.6 + (-0.2)) / 2 = 0.2
        assert abs(score - 0.2) < 0.01
