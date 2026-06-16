"""端到端集成测试：爬虫 → 分析 → 信号生成 → 格式化推送。

这是 FundRadar 核心闭环的完整验证。
不依赖数据库，用内存对象串联全流程。

运行方式:
  PYTHONPATH=. python -m pytest tests/test_e2e.py -v -m "network or llm"
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.crawler.xueqiu import XueqiuCrawler
from app.crawler.news import NewsCrawler
from app.crawler.fund_nav import FundNavCrawler
from app.analyzer.llm_client import llm_json
from app.analyzer.signal_generator import _score_to_signal, _calc_confidence
from app.services.signal_pusher import format_signal_message


@pytest.mark.network
@pytest.mark.llm
class TestE2EPipeline:
    """完整流水线：真实爬虫数据 → LLM分析 → 信号 → 格式化。"""

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        """
        完整链路：
        1. 爬新闻 → LLM情感分析 → 情感分数
        2. 爬基金净值 → 提供数据背景
        3. 综合分数 → 信号映射 → 置信度计算
        4. 格式化为 Telegram 消息
        5. 验证消息完整性
        """
        # ─── Step 1: 爬新闻 ───
        async with NewsCrawler() as news_crawler:
            news_list = await news_crawler.get_all_news(count_each=5)

        assert isinstance(news_list, list)
        # 确保至少拿到一些新闻
        if not news_list:
            pytest.skip("今日无新闻数据（可能非交易日）")

        print(f"\n📊 E2E: 抓取到 {len(news_list)} 条新闻")

        # ─── Step 2: LLM 情感分析 ───
        # 取前 3 条做分析（避免超时）
        sample = news_list[:3]
        news_text = "\n".join(
            f"{i+1}. {n.get('title', '')[:60]}"
            for i, n in enumerate(sample)
        )

        sentiment_result = await llm_json(
            system="你是A股市场情感分析师。分析新闻对市场的影响，返回JSON。",
            user=f"""分析以下新闻的整体市场情感：
{news_text}

请返回JSON（单个对象）：
{{"overall_sentiment": "positive/negative/neutral", "score": -1.0到1.0的浮点数, "summary": "一句话总结"}}
""",
        )

        if sentiment_result is None:
            pytest.skip("LLM API 不可用")

        assert "overall_sentiment" in sentiment_result or "sentiment" in sentiment_result
        news_score = float(sentiment_result.get("score", 0))
        assert -1.0 <= news_score <= 1.0

        print(f"📊 E2E: 新闻情感分数 = {news_score:.2f} ({sentiment_result.get('overall_sentiment', sentiment_result.get('sentiment', 'unknown'))})")
        print(f"📊 E2E: LLM总结 = {sentiment_result.get('summary', 'N/A')}")

        # ─── Step 3: 爬基金净值 ───
        async with FundNavCrawler() as nav_crawler:
            nav_data = await nav_crawler.get_fund_realtime_nav("510330")

        if nav_data:
            print(f"📊 E2E: 沪深300ETF实时估值 = {nav_data.get('nav', 'N/A')}")
        else:
            print("📊 E2E: 基金净值暂无（可能非交易时段）")

        # ─── Step 4: 综合信号生成 ───
        # 模拟博主共识分数（实际应由 blogger_scorer 计算）
        blogger_score = news_score * 0.6  # 简化：新闻和博主方向基本一致
        combined_score = blogger_score * 0.6 + news_score * 0.4

        signal_key, signal_label = _score_to_signal(combined_score)
        confidence = _calc_confidence(
            bloggers=3,  # 假设3位博主
            news=len(news_list),
            score=combined_score,
        )

        print(f"📊 E2E: 综合分数 = {combined_score:.2f}")
        print(f"📊 E2E: 信号 = {signal_key} ({signal_label})")
        print(f"📊 E2E: 置信度 = {confidence:.1f}%")

        # ─── Step 5: 格式化消息 ───
        mock_signal = MagicMock(
            signal_date=datetime.now(timezone.utc),
            target_name="沪深300指数",
            target_symbol="000300.SH",
            final_signal=signal_key,
            confidence=confidence,
            blogger_consensus_score=blogger_score,
            news_sentiment_score=news_score,
            participating_bloggers=3,
            analyzed_news_count=len(news_list),
            reasoning=sentiment_result.get("summary", "综合分析"),
        )

        premium_msg = format_signal_message(mock_signal, is_premium=True)
        free_msg = format_signal_message(mock_signal, is_premium=False)

        # ─── Step 6: 验证消息完整性 ───
        assert "FundRadar" in premium_msg
        assert signal_label in premium_msg
        assert "沪深300" in premium_msg
        assert "不构成投资建议" in premium_msg

        assert "FundRadar" in free_msg
        assert signal_label in free_msg
        # 免费版不含置信度详情
        assert str(confidence) not in free_msg

        print(f"\n{'='*60}")
        print(f"✅ E2E 全链路通过！")
        print(f"{'='*60}")
        print(f"\n📨 付费版消息预览:\n{premium_msg[:500]}")
        print(f"\n📨 免费版消息预览:\n{free_msg[:300]}")

    @pytest.mark.asyncio
    async def test_xueqiu_blogger_analysis(self):
        """E2E: 雪球帖子 → LLM 分析是否包含预测。"""
        # 爬雪球帖子
        async with XueqiuCrawler() as crawler:
            posts = await crawler.get_user_posts("1247347556", page=1, count=5)

        if not posts:
            pytest.skip("雪球无帖子数据")

        print(f"\n📊 E2E Blogger: 抓取到 {len(posts)} 条帖子")

        # LLM 分析第一条
        post = posts[0]
        result = await llm_json(
            system="你是金融分析助手。判断帖子是否包含市场预测。返回JSON。",
            user=f"""分析以下帖子：
{post['post_content'][:500]}

返回JSON：
{{"is_prediction": true/false, "direction": "bullish/bearish/neutral/null"}}
""",
        )

        if result is None:
            pytest.skip("LLM API 不可用")

        print(f"📊 E2E Blogger: 预测={result.get('is_prediction')}, 方向={result.get('direction')}")
        assert "is_prediction" in result
