"""散户情绪爬虫 — akshare 数据源（微博NLP + 东财评论）。

数据源:
  1. 金十数据中心微博舆情报告 (stock_js_weibo_report)
     - 返回50只热门个股的多空 rate
  2. 东方财富个股综合评论 (stock_comment_em)
     - 返回5184只股票的综合得分/机构参与度/关注指数

标准化:
  - 微博 rate > 1.0 → bullish，映射到 [-1, 1]
  - 东财综合得分 → 归一化到 [0, 1] → 映射到 [-1, 1]
"""
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from app.crawler.base import BaseCrawler

logger = logging.getLogger(__name__)


def normalize_weibo_rate(rate: float) -> float:
    """金十微博 rate 标准化到 [-1, 1]。

    rate 含义: >1.0 偏多，<1.0 偏空，=1.0 中性。
    映射: rate=2.0 → 1.0, rate=1.0 → 0.0, rate=0.5 → -1.0
    公式: score = clamp((rate - 1.0) / 0.5, -1, 1)  -- rate 1.5 映射到 +1
    但实际 rate 波动小，用 log 变换更平滑:
    score = clamp((rate - 1.0) * 2, -1, 1)
    """
    score = (rate - 1.0) * 2
    return max(-1.0, min(1.0, score))


def normalize_em_score(score: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """东财综合得分标准化到 [-1, 1]。

    综合得分范围约 0-100，50 为中性。
    """
    normalized = (score - 50.0) / 50.0
    return max(-1.0, min(1.0, normalized))


def aggregate_sentiment(scores: list[float]) -> tuple[float, float, float]:
    """多源情绪聚合，返回 (score, bullish_ratio, bearish_ratio)。

    - score: 所有分数的均值
    - bullish_ratio: score > 0 的比例
    - bearish_ratio: score < 0 的比例
    """
    if not scores:
        return 0.0, 0.0, 0.0
    avg = sum(scores) / len(scores)
    bullish = sum(1 for s in scores if s > 0.05) / len(scores)
    bearish = sum(1 for s in scores if s < -0.05) / len(scores)
    return round(avg, 4), round(bullish, 4), round(bearish, 4)


class SentimentCrawler(BaseCrawler):
    """akshare 散户情绪爬虫。"""

    def __init__(self, **kwargs):
        super().__init__(rate_limit_delay=1.0, **kwargs)

    async def get_weibo_sentiment(self, time_period: str = "CNHOUR12") -> Optional[dict]:
        """金十数据中心微博舆情报告。

        Args:
            time_period: CNHOUR2/CNHOUR6/CNHOUR12/CNHOUR24/CNDAY7/CNDAY30

        Returns:
            {sentiment_score, bullish_ratio, bearish_ratio, raw_count, raw_data}
        """
        import akshare as ak
        try:
            df = ak.stock_js_weibo_report(time_period=time_period)
            if df is None or df.empty:
                logger.warning("微博舆情报告为空")
                return None

            # 列名可能是 'name', 'rate' 或中文
            rate_col = "rate" if "rate" in df.columns else df.columns[-1]
            name_col = "name" if "name" in df.columns else df.columns[0]

            rates = pd.to_numeric(df[rate_col], errors="coerce").dropna()
            if rates.empty:
                return None

            scores = [normalize_weibo_rate(r) for r in rates]
            score, bullish, bearish = aggregate_sentiment(scores)

            # 提取 top 个股
            top_stocks = []
            for _, row in df.head(10).iterrows():
                top_stocks.append({
                    "name": str(row.get(name_col, "")),
                    "rate": float(row.get(rate_col, 0)),
                })

            return {
                "sentiment_score": score,
                "bullish_ratio": bullish,
                "bearish_ratio": bearish,
                "raw_count": len(rates),
                "raw_data": {"top_stocks": top_stocks, "time_period": time_period},
            }
        except Exception as e:
            logger.error(f"微博舆情爬取失败: {e}")
            return None

    async def get_em_comment_sentiment(self, symbols: list[dict] | None = None) -> Optional[dict]:
        """东方财富个股综合评论情绪。

        Args:
            symbols: 指定标的列表 [{'symbol': '000300', 'code': '000300'}]
                     None 时取全市场聚合

        Returns:
            {sentiment_score, bullish_ratio, bearish_ratio, raw_count, raw_data}
        """
        import akshare as ak
        try:
            df = ak.stock_comment_em()
            if df is None or df.empty:
                logger.warning("东财评论数据为空")
                return None

            score_col = "综合得分" if "综合得分" in df.columns else None
            if score_col is None:
                # 尝试模糊匹配
                for col in df.columns:
                    if "得分" in col or "score" in col.lower():
                        score_col = col
                        break

            if score_col is None:
                logger.error(f"东财评论找不到得分列，现有列: {list(df.columns)}")
                return None

            scores_raw = pd.to_numeric(df[score_col], errors="coerce").dropna()
            if scores_raw.empty:
                return None

            # 如果指定了 symbols，只看这些标的
            if symbols:
                code_col = "代码" if "代码" in df.columns else df.columns[1]
                target_codes = {s["code"] for s in symbols}
                mask = df[code_col].astype(str).isin(target_codes)
                scores_raw = pd.to_numeric(df.loc[mask, score_col], errors="coerce").dropna()

            if scores_raw.empty:
                return None

            scores = [normalize_em_score(s) for s in scores_raw]
            score, bullish, bearish = aggregate_sentiment(scores)

            return {
                "sentiment_score": score,
                "bullish_ratio": bullish,
                "bearish_ratio": bearish,
                "raw_count": len(scores_raw),
                "raw_data": {
                    "avg_score": float(scores_raw.mean()),
                    "score_col": score_col,
                    "sample_size": len(scores_raw),
                },
            }
        except Exception as e:
            logger.error(f"东财评论爬取失败: {e}")
            return None

    async def get_combined_sentiment(
        self, weibo_weight: float = 0.5, em_weight: float = 0.5
    ) -> dict:
        """聚合微博 + 东财两源散户情绪。

        Returns:
            {
                sentiment_score: float,    # 加权 [-1, 1]
                bullish_ratio: float,
                bearish_ratio: float,
                sources: {...},           # 各源详情
            }
        """
        weibo = await self.get_weibo_sentiment()
        em = await self.get_em_comment_sentiment()

        results = {}
        total_weight = 0.0
        weighted_score = 0.0
        weighted_bullish = 0.0
        weighted_bearish = 0.0

        if weibo:
            results["weibo_nlp"] = weibo
            weighted_score += weibo["sentiment_score"] * weibo_weight
            weighted_bullish += weibo["bullish_ratio"] * weibo_weight
            weighted_bearish += weibo["bearish_ratio"] * weibo_weight
            total_weight += weibo_weight

        if em:
            results["eastmoney_comment"] = em
            weighted_score += em["sentiment_score"] * em_weight
            weighted_bullish += em["bullish_ratio"] * em_weight
            weighted_bearish += em["bearish_ratio"] * em_weight
            total_weight += em_weight

        if total_weight == 0:
            return {
                "sentiment_score": 0.0,
                "bullish_ratio": 0.0,
                "bearish_ratio": 0.0,
                "sources": {},
                "error": "所有散户情绪数据源都失败",
            }

        return {
            "sentiment_score": round(weighted_score / total_weight, 4),
            "bullish_ratio": round(weighted_bullish / total_weight, 4),
            "bearish_ratio": round(weighted_bearish / total_weight, 4),
            "sources": results,
        }
