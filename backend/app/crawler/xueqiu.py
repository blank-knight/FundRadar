"""Xueqiu (雪球) crawler — scrapes financial blogger posts.

WAF bypass: Uses Playwright headless browser to pass Aliyun WAF JS challenge,
extracts cookies, then injects into httpx for normal API calls.
Falls back to manual XUEQIU_COOKIE env var if Playwright unavailable.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.crawler.base import BaseCrawler

logger = logging.getLogger(__name__)

# Xueqiu API endpoints (semi-public, no auth required for public profiles)
XUEQIU_USER_TIMELINE = "https://xueqiu.com/v4/statuses/user_timeline.json"
XUEQIU_USER_INFO = "https://xueqiu.com/users/show.json"
XUEQIU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://xueqiu.com/",
    "Origin": "https://xueqiu.cn",
}

# Known finance KOL user IDs on Xueqiu (platform_user_id)
DEFAULT_BLOGGERS = [
    {"platform_user_id": "1247347556", "username": "但斌"},
    {"platform_user_id": "5819606767", "username": "张坤"},
    {"platform_user_id": "2145717565", "username": "雪球基金"},
    {"platform_user_id": "1876614331", "username": "ETF拯救世界"},
    {"platform_user_id": "3491303582", "username": "持有封基"},
]


async def get_xueqiu_cookies_via_playwright(url: str = "https://xueqiu.com/") -> dict:
    """Use Playwright to bypass Aliyun WAF and extract cookies.

    Returns dict of cookies suitable for httpx.
    Raises ImportError if playwright not installed, RuntimeError on failure.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url, wait_until="networkidle", timeout=30000)

        # Wait for WAF JS challenge to resolve
        # The page will reload after WAF passes
        await page.wait_for_timeout(3000)

        cookies = await context.cookies()
        await browser.close()

    cookie_dict = {}
    for c in cookies:
        cookie_dict[c["name"]] = c["value"]

    if "xq_a_token" not in cookie_dict:
        raise RuntimeError(f"Playwright WAF bypass failed: no xq_a_token in cookies. Got: {list(cookie_dict.keys())}")

    logger.info(f"Playwright WAF bypass success, got {len(cookie_dict)} cookies (xq_a_token present)")
    return cookie_dict


def build_cookie_string(cookies: dict) -> str:
    """Convert cookie dict to header string."""
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


class XueqiuCrawler(BaseCrawler):
    """Crawl Xueqiu blogger posts for prediction extraction.

    Cookie acquisition order:
    1. Manual cookie passed via constructor
    2. Playwright WAF bypass (preferred for automated runs)
    3. Fallback: visit homepage for basic session cookie (may not pass WAF)
    """

    def __init__(self, cookie: str = "", use_playwright: bool = True, **kwargs):
        super().__init__(rate_limit_delay=2.0, **kwargs)
        self.cookie = cookie
        self.use_playwright = use_playwright

    async def __aenter__(self):
        await super().__aenter__()
        self._client.headers.update(XUEQIU_HEADERS)

        if self.cookie:
            # 1. Manual cookie (highest priority)
            self._client.headers.update({"Cookie": self.cookie})
        elif self.use_playwright:
            # 2. Try Playwright WAF bypass
            try:
                cookies = await get_xueqiu_cookies_via_playwright()
                cookie_str = build_cookie_string(cookies)
                self._client.headers.update({"Cookie": cookie_str})
                logger.info("Xueqiu using Playwright-extracted cookies")
            except ImportError:
                logger.warning("Playwright not installed, trying homepage cookie fallback")
                try:
                    await self._client.get("https://xueqiu.com/", follow_redirects=True)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Playwright WAF bypass failed: {e}, falling back to homepage cookie")
                try:
                    await self._client.get("https://xueqiu.com/", follow_redirects=True)
                except Exception:
                    pass
        else:
            # 3. Simple homepage visit
            try:
                await self._client.get("https://xueqiu.com/", follow_redirects=True)
            except Exception:
                pass
        return self

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """Fetch blogger profile info."""
        try:
            resp = await self.get(XUEQIU_USER_INFO, params={"id": user_id})
            data = resp.json()
            return {
                "platform_user_id": str(data.get("id", user_id)),
                "username": data.get("screen_name", ""),
                "avatar_url": data.get("profile_image_url", ""),
                "follower_count": data.get("followers_count", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get user info for {user_id}: {e}")
            return None

    async def get_user_posts(
        self, user_id: str, page: int = 1, count: int = 20
    ) -> list[dict]:
        """Fetch recent posts from a blogger."""
        try:
            resp = await self.get(
                XUEQIU_USER_TIMELINE,
                params={"user_id": user_id, "page": page, "count": count},
            )
            data = resp.json()
            statuses = data.get("statuses", [])
            posts = []
            for s in statuses:
                created_ms = s.get("created_at", 0)
                post_time = datetime.fromtimestamp(
                    created_ms / 1000, tz=timezone.utc
                ).replace(tzinfo=None)
                posts.append({
                    "platform_user_id": str(user_id),
                    "post_url": f"https://xueqiu.com/{user_id}/{s.get('id', '')}",
                    "post_content": _strip_html(s.get("text", "")),
                    "post_time": post_time,
                    "raw_data": {
                        "id": s.get("id"),
                        "retweet_count": s.get("retweet_count", 0),
                        "reply_count": s.get("reply_count", 0),
                        "like_count": s.get("like_count", 0),
                    },
                })
            return posts
        except Exception as e:
            logger.error(f"Failed to get posts for user {user_id}: {e}")
            return []

    async def search_users(self, query: str) -> list[dict]:
        """搜索雪球用户，返回候选博主列表。"""
        try:
            resp = await self.get(
                "https://xueqiu.com/query/v1/search/user.json",
                params={"q": query, "count": 10, "page": 1},
            )
            data = resp.json()
            users = data.get("list", data.get("users", []))
            results = []
            for u in users:
                results.append({
                    "platform": "xueqiu",
                    "platform_user_id": str(u.get("id", "")),
                    "username": u.get("screen_name", ""),
                    "avatar_url": u.get("profile_image_url", ""),
                    "follower_count": u.get("followers_count", 0),
                    "description": u.get("description", ""),
                    "profile_url": f"https://xueqiu.com/u/{u.get('id', '')}",
                })
            return results
        except Exception as e:
            logger.error(f"Xueqiu user search failed: {e}")
            return []


def _strip_html(text: str) -> str:
    """Remove basic HTML tags from Xueqiu post content."""
    import re
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
