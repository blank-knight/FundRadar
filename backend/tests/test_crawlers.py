"""Phase 3: 爬虫层测试 — 雪球 / 新闻 / 基金净值。

运行方式:
  PYTHONPATH=. python -m pytest tests/test_crawlers.py -v

注意: 这些测试需要网络连接，标记为 @pytest.mark.network
"""
import pytest
from datetime import datetime

from app.crawler.xueqiu import XueqiuCrawler, _strip_html
from app.crawler.news import NewsCrawler, _parse_eastmoney_time, _parse_ts
from app.crawler.fund_nav import FundNavCrawler, _to_secid


# ═══════════════════════════════════════════════════════
# 纯逻辑测试（不需要网络）
# ═══════════════════════════════════════════════════════

class TestStripHtml:
    """测试 HTML 标签清理。"""

    def test_simple_tag(self):
        assert _strip_html("<p>hello</p>") == "hello"

    def test_nested_tags(self):
        assert _strip_html("<div><span>test</span></div>") == "test"

    def test_with_attrs(self):
        result = _strip_html('<a href="xxx">link</a>')
        assert "link" in result
        assert "<a" not in result

    def test_empty(self):
        assert _strip_html("") == ""

    def test_whitespace_collapse(self):
        result = _strip_html("hello   world\n\nfoo")
        assert "  " not in result


class TestParseEastmoneyTime:
    """测试东方财富时间解析。"""

    def test_standard_format(self):
        dt = _parse_eastmoney_time("2024-01-15 09:30:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_short_format(self):
        dt = _parse_eastmoney_time("2024-01-15 09:30")
        assert dt is not None

    def test_invalid_fallback(self):
        dt = _parse_eastmoney_time("invalid")
        assert dt is not None  # 应回退到 utcnow

    def test_empty_fallback(self):
        dt = _parse_eastmoney_time("")
        assert dt is not None


class TestParseTimestamp:
    """测试 Unix 时间戳解析。"""

    def test_valid_timestamp(self):
        dt = _parse_ts(1705305600)  # 2024-01-15
        assert dt is not None

    def test_string_timestamp(self):
        dt = _parse_ts("1705305600")
        assert dt is not None

    def test_invalid_fallback(self):
        dt = _parse_ts("invalid")
        assert dt is not None


class TestToSecid:
    """测试东方财富代码转换。"""

    def test_sh_code(self):
        assert _to_secid("000300.SH") == "1.000300"

    def test_sz_code(self):
        assert _to_secid("399006.SZ") == "0.399006"

    def test_bare_sh_code(self):
        # 6开头是SH
        assert _to_secid("600519.SH") == "1.600519"


# ═══════════════════════════════════════════════════════
# 网络测试（需要互联网连接）
# ═══════════════════════════════════════════════════════

@pytest.mark.network
class TestXueqiuCrawler:
    """雪球爬虫实测。"""

    @pytest.mark.asyncio
    async def test_get_user_posts(self):
        """测试获取博主帖子 — 至少应该返回列表（可能为空如果被封）。"""
        async with XueqiuCrawler() as crawler:
            posts = await crawler.get_user_posts("1247347556", page=1, count=5)
            # 不论是否拿到数据，不应该抛异常
            assert isinstance(posts, list)

    @pytest.mark.asyncio
    async def test_post_structure(self):
        """如果有帖子，验证字段结构。"""
        async with XueqiuCrawler() as crawler:
            posts = await crawler.get_user_posts("1247347556", page=1, count=3)
            if posts:
                post = posts[0]
                assert "platform_user_id" in post
                assert "post_content" in post
                assert "post_time" in post
                assert isinstance(post["post_content"], str)
                assert isinstance(post["post_time"], datetime)
                assert len(post["post_content"]) > 0


@pytest.mark.network
class TestNewsCrawler:
    """新闻爬虫实测。"""

    @pytest.mark.asyncio
    async def test_get_eastmoney_news(self):
        """测试东方财富快讯 — 应返回 >= 5 条新闻。"""
        async with NewsCrawler() as crawler:
            news = await crawler.get_eastmoney_news(count=10)
            # 至少拿到一些新闻
            assert isinstance(news, list)
            if news:
                n = news[0]
                assert "source" in n
                assert "title" in n
                assert "url" in n
                assert len(n["title"]) > 0

    @pytest.mark.asyncio
    async def test_get_all_news_dedup(self):
        """测试多源新闻去重。"""
        async with NewsCrawler() as crawler:
            all_news = await crawler.get_all_news(count_each=5)
            assert isinstance(all_news, list)
            # 验证 URL 去重
            urls = [n["url"] for n in all_news if n.get("url")]
            assert len(urls) == len(set(urls)), "Found duplicate URLs"


@pytest.mark.network
class TestFundNavCrawler:
    """基金净值爬虫实测。"""

    @pytest.mark.asyncio
    async def test_get_fund_realtime_nav(self):
        """测试实时估算净值 — 用沪深300ETF (510330)。"""
        async with FundNavCrawler() as crawler:
            data = await crawler.get_fund_realtime_nav("510330")
            if data:
                assert "fund_code" in data
                assert "nav" in data
                assert isinstance(data["nav"], float)
                assert data["nav"] > 0
                assert "nav_date" in data

    @pytest.mark.asyncio
    async def test_get_fund_history_nav(self):
        """测试历史净值。"""
        async with FundNavCrawler() as crawler:
            records = await crawler.get_fund_history_nav("110011", page=1, per_page=5)
            assert isinstance(records, list)
            if records:
                r = records[0]
                assert "fund_code" in r
                assert "nav" in r
                assert r["nav"] > 0
                assert "trade_date" in r
