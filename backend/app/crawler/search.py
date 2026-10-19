"""互联网搜索舆情爬虫 — 通过搜索引擎 API 抓取全网观点，供 LLM 分析多空情绪。

数据源: Serper.dev (Google Search API)
  - 免费额度: 2,500 次/月
  - 每次请求返回 10-20 条结果 (title + snippet + url)
  - 适合抓取研报摘要、论坛讨论、媒体观点

与现有 news 维度的区别:
  - news: 爬东财单源，实时但窄
  - search: 搜全网多源，覆盖面广但延迟几小时
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SERPER_API_URL = "https://google.serper.dev/search"

# ── 关键词模板 ──
# 按场景自动生成搜索关键词
KEYWORD_TEMPLATES = {
    # 板块级 — 热门赛道
    "半导体": ["半导体板块 后市分析", "半导体 买入 卖出 2025", "芯片板块 机构观点"],
    "新能源": ["新能源板块 后市分析", "光伏 锂电 2025 走势", "新能源 机构调研"],
    "医药": ["医药板块 后市分析", "创新药 医保 谈判 2025", "生物医药 机构观点"],
    "消费": ["消费板块 后市分析", "白酒 食品 2025 走势", "消费复苏 机构观点"],
    # 指数级
    "沪深300": ["沪深300 走势 判断 2025", "A股 后市 机构观点", "沪深300 买入 卖出"],
    "创业板": ["创业板 走势 判断 2025", "创业板 机构观点"],
    "纳指": ["纳斯达克 走势 分析 2025", "美股 后市 机构观点"],
    # 事件驱动
    "降准": ["降准 A股 影响", "央行 降准 基金 受益"],
    "美联储": ["美联储加息 A股 影响 2025", "美联储 货币政策 最新"],
}

# 默认搜索关键词组（沪深300为主标的）
DEFAULT_QUERIES = [
    "沪深300 后市 机构分析 2025",
    "A股 半导体 新能源 后市判断",
    "基金 买入 卖出 时机 2025",
    "北向资金 行业板块 观点",
]


class SearchCrawler:
    """通过 Serper.dev API 搜索全网金融观点。"""

    def __init__(self, num_results: int = 10):
        self.num_results = num_results
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def search(self, query: str, gl: str = "cn", hl: str = "zh-cn") -> list[dict]:
        """执行单次 Google 搜索，返回结果列表。

        Args:
            query: 搜索关键词
            gl: 地区 (cn=中国, us=美国)
            hl: 语言

        Returns:
            [{"title": ..., "snippet": ..., "url": ..., "source": ...}, ...]
        """
        api_key = getattr(settings, "SERPER_API_KEY", "") or ""
        if not api_key:
            logger.warning("SERPER_API_KEY not configured, skipping search crawl")
            return []

        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        payload = {
            "q": query,
            "num": self.num_results,
            "gl": gl,
            "hl": hl,
        }

        for attempt in range(3):
            try:
                resp = await self._client.post(SERPER_API_URL, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

                results = []
                # organic results
                for item in data.get("organic", []):
                    results.append({
                        "title": item.get("title", "").strip(),
                        "snippet": item.get("snippet", "").strip(),
                        "url": item.get("link", ""),
                        "source": "google_search",
                        "position": item.get("position", 0),
                    })

                # news results (if any)
                for item in data.get("news", []):
                    results.append({
                        "title": item.get("title", "").strip(),
                        "snippet": item.get("snippet", "").strip() or item.get("date", ""),
                        "url": item.get("link", ""),
                        "source": "google_news",
                        "position": 0,
                    })

                return results

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(10 * (attempt + 1))
                elif attempt == 2:
                    raise
                logger.warning(f"Serper HTTP {e.response.status_code} for '{query}', attempt {attempt+1}")
            except httpx.RequestError as e:
                if attempt == 2:
                    raise
                logger.warning(f"Serper request error for '{query}': {e}, attempt {attempt+1}")

        logger.error(f"Serper search failed after 3 attempts for '{query}'")
        return []

    async def search_multiple(self, queries: list[str]) -> list[dict]:
        """执行多个查询，合并去重后返回。

        Returns:
            [{"title", "snippet", "url", "source", "query"}, ...]
        """
        all_results = []
        seen_urls = set()

        for query in queries:
            results = await self.search(query)
            for r in results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    r["query"] = query
                    all_results.append(r)
                    seen_urls.add(url)
            # 间隔避免 rate limit
            await asyncio.sleep(1.0)

        logger.info(f"Search crawl: {len(queries)} queries → {len(all_results)} unique results")
        return all_results

    async def get_market_sentiment_search(self) -> list[dict]:
        """搜索当前市场情绪相关的内容（默认关键词组）。"""
        return await self.search_multiple(DEFAULT_QUERIES)

    async def get_sector_search(self, sector_name: str) -> list[dict]:
        """搜索特定板块的分析内容。"""
        queries = KEYWORD_TEMPLATES.get(sector_name, [f"{sector_name} 后市分析 2025"])
        return await self.search_multiple(queries)
