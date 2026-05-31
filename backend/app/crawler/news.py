"""Financial news crawler — East Money (东方财富) + Sina Finance."""
import logging
from datetime import datetime
from typing import Optional
import re

from app.crawler.base import BaseCrawler

logger = logging.getLogger(__name__)

# East Money news API (public, no auth)
EASTMONEY_NEWS_API = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_10_1_.html"
EASTMONEY_STOCK_NEWS = "https://np-anotice-stock.eastmoney.com/api/security/ann"

# Sina Finance RSS (reliable, no auth)
SINA_FINANCE_RSS = "https://feed.mix.sina.com.cn/api/roll/get"


class NewsCrawler(BaseCrawler):
    """Crawl financial news from East Money and Sina Finance."""

    def __init__(self, **kwargs):
        super().__init__(rate_limit_delay=1.0, **kwargs)

    async def get_eastmoney_news(self, count: int = 30) -> list[dict]:
        """Fetch latest market news from East Money 快讯."""
        try:
            resp = await self.get(
                "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_10_1_.html",
                headers={"Referer": "https://www.eastmoney.com/"},
            )
            # East Money returns JSONP-like or JSON
            text = resp.text
            # Strip JSONP wrapper if present
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            import json
            data = json.loads(match.group())
            items = data.get("LivesList", [])[:count]
            news = []
            for item in items:
                news.append({
                    "source": "eastmoney",
                    "title": item.get("title", "").strip(),
                    "url": item.get("url") or f"https://finance.eastmoney.com/a/{item.get('id', '')}.html",
                    "publish_time": _parse_eastmoney_time(item.get("showtime", "")),
                    "summary": item.get("digest", "").strip() or None,
                })
            return [n for n in news if n["title"]]
        except Exception as e:
            logger.error(f"East Money news fetch failed: {e}")
            return []

    async def get_sina_finance_news(self, count: int = 30) -> list[dict]:
        """Fetch latest news from East Money fund news (替代原新浪接口)."""
        try:
            resp = await self.get(
                "https://fund.eastmoney.com/js/fundcode_search.js",
            )
            # 东方财富基金快讯，用另一个稳定接口
            resp2 = await self.get(
                "https://newsapi.eastmoney.com/kuaixun/v1/getlist_103_ajaxResult_10_1_.html",
                headers={"Referer": "https://fund.eastmoney.com/"},
            )
            import json, re
            text = resp2.text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            items = data.get("LivesList", [])[:count]
            news = []
            for item in items:
                news.append({
                    "source": "eastmoney_fund",
                    "title": item.get("title", "").strip(),
                    "url": item.get("url") or f"https://fund.eastmoney.com/a/{item.get('id', '')}.html",
                    "publish_time": _parse_eastmoney_time(item.get("showtime", "")),
                    "summary": item.get("digest", "").strip() or None,
                })
            return [n for n in news if n["title"]]
        except Exception as e:
            logger.error(f"East Money fund news fetch failed: {e}")
            return []

    async def get_tencent_finance_news(self, count: int = 30) -> list[dict]:
        """Fetch latest news from Tencent Finance (腾讯财经)."""
        try:
            resp = await self.get(
                "https://i.news.qq.com/trpc.qqnews_web.pc_base_srv.base_http_proxy/GetIndexPageContent",
                params={
                    "sub_srv_id": "24",
                    "srv_id": "pc",
                    "offset": 0,
                    "count": count,
                    "filterNeg": "1",
                    "callback": "",
                },
                headers={"Referer": "https://finance.qq.com/"},
            )
            import json, re
            text = resp.text.strip()
            # 去掉 JSONP 包裹
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return []
            data = json.loads(match.group())
            items = data.get("idlist", [{}])[0].get("newslist", [])
            news = []
            for item in items[:count]:
                title = item.get("title", "").strip()
                url = item.get("url", "") or item.get("shorturl", "")
                if not title or not url:
                    continue
                news.append({
                    "source": "tencent",
                    "title": title,
                    "url": url,
                    "publish_time": _parse_ts(item.get("timestamp", 0)),
                    "summary": item.get("abstract", "").strip() or None,
                })
            return news
        except Exception as e:
            logger.error(f"Tencent Finance news fetch failed: {e}")
            return []

    async def get_all_news(self, count_each: int = 20) -> list[dict]:
        """Fetch from all sources and deduplicate by URL."""
        em = await self.get_eastmoney_news(count_each)
        fund = await self.get_sina_finance_news(count_each)
        all_news = em + fund
        seen_urls: set[str] = set()
        deduped = []
        for n in all_news:
            if n["url"] and n["url"] not in seen_urls:
                seen_urls.add(n["url"])
                deduped.append(n)
        return deduped


def _parse_eastmoney_time(s: str) -> Optional[datetime]:
    """Parse East Money time string like '2024-01-15 09:30:00'."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return datetime.utcnow()


def _parse_sina_time(s: str) -> Optional[datetime]:
    """Parse Sina unix timestamp string."""
    try:
        return datetime.utcfromtimestamp(int(s))
    except (ValueError, TypeError):
        return datetime.utcnow()


def _parse_ts(ts) -> Optional[datetime]:
    """Parse unix timestamp (int or str) to datetime."""
    try:
        return datetime.utcfromtimestamp(int(ts))
    except (ValueError, TypeError):
        return datetime.utcnow()
