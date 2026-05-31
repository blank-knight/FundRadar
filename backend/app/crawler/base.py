"""Base crawler with rate limiting, retry, and session management."""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class BaseCrawler:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def __init__(self, rate_limit_delay: float = 1.5, timeout: float = 20.0):
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers=self.DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET with exponential backoff retry (3 attempts)."""
        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(self.rate_limit_delay * (2 ** attempt))
                resp = await self._client.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(10 * (attempt + 1))
                elif attempt == 2:
                    raise
                logger.warning(f"HTTP {e.response.status_code} for {url}, attempt {attempt+1}")
            except httpx.RequestError as e:
                if attempt == 2:
                    raise
                logger.warning(f"Request error {url}: {e}, attempt {attempt+1}")
        raise RuntimeError(f"Failed after 3 attempts: {url}")
