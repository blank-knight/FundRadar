"""微博大V爬虫 — m.weibo.cn 移动端 API。

鉴权方式: 先访问 m.weibo.cn 首页获取 cookie，之后用 cookie 调 API。
KOL 列表: 与雪球重叠的财经大V，微博粉丝量大，发帖频繁。
"""
import logging
import re
from datetime import datetime
from typing import Optional

import httpx

from app.crawler.base import BaseCrawler

logger = logging.getLogger(__name__)

WEIBO_BASE = "https://m.weibo.cn"
WEIBO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.weibo.cn/",
    "X-Requested-With": "XMLHttpRequest",
    "MWeibo-Pwa": "1",
}

# 财经大V (微博 uid)
DEFAULT_WEIBO_KOLS = [
    {"uid": "1671525290", "username": "但斌"},        # 东方港湾但斌
    {"uid": "1699432410", "username": "林园"},        # 林园投资
    {"uid": "1929304917", "username": "侯安扬"},      # 上善若水侯安扬
    {"uid": "1648009647", "username": "吴晓波"},      # 吴晓波频道
    {"uid": "1665334020", "username": "付鹏的财经观察"}, # 付鹏
]


def strip_html(text: str) -> str:
    """去除微博 HTML 标签和多余空白。"""
    text = re.sub(r"<a[^>]*>.*?</a>", "", text)  # 去链接
    text = re.sub(r"<span[^>]*>.*?</span>", "", text)  # 去 span
    text = re.sub(r"<[^>]+>", "", text)  # 去其他标签
    text = re.sub(r"\\\u002F", "/", text)  # 修复转义
    text = re.sub(r"\s+", " ", text).strip()
    return text


class WeiboCrawler(BaseCrawler):
    """微博大V帖子爬虫 (m.weibo.cn API)。"""

    def __init__(self, cookie: str = "", **kwargs):
        super().__init__(rate_limit_delay=3.0, **kwargs)
        self.cookie = cookie

    async def __aenter__(self):
        await super().__aenter__()
        self._client.headers.update(WEIBO_HEADERS)
        if self.cookie:
            self._client.headers.update({"Cookie": self.cookie})
        else:
            # 访问 m.weibo.cn 首页获取 session cookie
            try:
                await self._client.get(f"{WEIBO_BASE}/", follow_redirects=True)
            except Exception:
                pass
        return self

    async def search_posts(self, keyword: str, page: int = 1) -> list[dict]:
        """搜索微博帖子。

        Returns:
            [{user_name, user_id, content, post_url, post_time, raw_data}]
        """
        try:
            containerid = f"100103type=1&q={keyword}"
            resp = await self.get(
                f"{WEIBO_BASE}/api/container/getIndex",
                params={"containerid": containerid, "page": page},
            )
            data = resp.json()

            posts = []
            cards = data.get("data", {}).get("cards", [])
            for card in cards:
                # card_type 9 是微博正文
                if card.get("card_type") == 9:
                    post = self._parse_mblog(card.get("mblog", {}))
                    if post:
                        posts.append(post)
                # card_group 里的也提取
                elif "card_group" in card:
                    for cg in card.get("card_group", []):
                        if cg.get("card_type") == 9:
                            post = self._parse_mblog(cg.get("mblog", {}))
                            if post:
                                posts.append(post)

            return posts
        except Exception as e:
            logger.error(f"微博搜索 '{keyword}' 失败: {e}")
            return []

    async def get_user_timeline(self, uid: str, page: int = 1) -> list[dict]:
        """获取指定大V的微博时间线。

        Args:
            uid: 微博用户 ID
            page: 页码

        Returns:
            [{user_name, user_id, content, post_url, post_time, raw_data}]
        """
        try:
            containerid = f"107603{uid}"
            resp = await self.get(
                f"{WEIBO_BASE}/api/container/getIndex",
                params={"containerid": containerid, "page": page},
            )
            data = resp.json()

            posts = []
            cards = data.get("data", {}).get("cards", [])
            for card in cards:
                if card.get("card_type") == 9:
                    post = self._parse_mblog(card.get("mblog", {}))
                    if post:
                        posts.append(post)

            return posts
        except Exception as e:
            logger.error(f"获取微博用户 {uid} 时间线失败: {e}")
            return []

    def _parse_mblog(self, mblog: dict) -> Optional[dict]:
        """解析单条微博 mblog JSON。"""
        if not mblog or not mblog.get("text"):
            return None

        user = mblog.get("user", {})
        bid = mblog.get("bid", "")
        created_at_str = mblog.get("created_at", "")

        return {
            "user_name": user.get("screen_name", ""),
            "user_id": str(user.get("id", "")),
            "content": strip_html(mblog.get("text", "")),
            "post_url": f"{WEIBO_BASE}/detail/{bid}" if bid else "",
            "post_time": self._parse_time(created_at_str),
            "raw_data": {
                "id": mblog.get("id"),
                "bid": bid,
                "reposts_count": mblog.get("reposts_count", 0),
                "comments_count": mblog.get("comments_count", 0),
                "attitudes_count": mblog.get("attitudes_count", 0),
                "source": mblog.get("source", ""),
            },
        }

    def _parse_time(self, time_str: str) -> datetime:
        """解析微博时间格式。

        格式: 'Mon Jun 16 10:30:00 +0800 2025' 或 '今天 10:30' 或 '6分钟前'
        """
        if not time_str:
            return datetime.utcnow()

        # 尝试标准格式
        try:
            return datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            pass

        # '今天 HH:MM'
        if "今天" in time_str:
            today = datetime.utcnow()
            try:
                parts = time_str.replace("今天", "").strip().split(":")
                return today.replace(hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0)
            except (ValueError, IndexError):
                return today

        # 'X分钟前'
        m = re.match(r"(\d+)\s*分钟前", time_str)
        if m:
            minutes = int(m.group(1))
            return datetime.utcnow().replace(microsecond=0) - __import__("datetime").timedelta(minutes=minutes)

        # 'X小时前'
        m = re.match(r"(\d+)\s*小时前", time_str)
        if m:
            hours = int(m.group(1))
            return datetime.utcnow().replace(microsecond=0) - __import__("datetime").timedelta(hours=hours)

        return datetime.utcnow()
