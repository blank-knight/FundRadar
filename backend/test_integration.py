"""端到端集成测试 — 真实 DB + 真实网络 + 真实 LLM"""
import asyncio
import sys
import os

# 加载 .env
from dotenv import load_dotenv
load_dotenv("/home/zwt/clawd/fund-radar/backend/.env")

sys.path.insert(0, "/home/zwt/clawd/fund-radar/backend")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_db():
    async with SessionLocal() as db:
        result = await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
        tables = [r[0] for r in result.fetchall()]
        print(f"✓ DB 连接成功，共 {len(tables)} 张表: {tables}")
    return True


async def test_news_crawl():
    from app.crawler.news import NewsCrawler
    async with NewsCrawler() as c:
        articles = await c.get_eastmoney_news(count=5)
        sina = await c.get_sina_finance_news(count=5)
    print(f"✓ 东方财富新闻: {len(articles)} 条")
    if articles:
        print(f"  样本: {articles[0]['title'][:40]}")
    print(f"✓ 新浪财经新闻: {len(sina)} 条")
    if sina:
        print(f"  样本: {sina[0]['title'][:40]}")
    return len(articles) + len(sina) > 0


async def test_market_data():
    from app.crawler.fund_nav import FundNavCrawler
    async with FundNavCrawler() as c:
        records = await c.get_index_daily("000300.SH", days=3)
        nav = await c.get_fund_realtime_nav("110020")
    print(f"✓ 沪深300行情: {len(records)} 条")
    if records:
        r = records[-1]
        print(f"  最新: {r['trade_date'].date()} 收盘={r['close_price']} 涨跌={r['change_pct']:+.2f}%")
    if nav:
        print(f"✓ 基金净值: {nav['name']} = {nav['nav']} ({nav['change_pct']:+.2f}%)")
    return len(records) > 0


async def test_save_to_db():
    from app.crawler.orchestrator import run_news_crawl, run_market_data_crawl
    from app.models.models import News, MarketData, CrawlLog
    async with SessionLocal() as db:
        news_result = await run_news_crawl(db)
        market_result = await run_market_data_crawl(db)

        news_count = await db.execute(select(News))
        market_count = await db.execute(select(MarketData))
        log_count = await db.execute(select(CrawlLog))

        print(f"✓ 新闻入库: fetched={news_result['fetched']} saved={news_result['saved_articles']}")
        print(f"✓ 行情入库: fetched={market_result['fetched']} saved={market_result['saved_records']}")
        print(f"✓ CrawlLog: {len(log_count.scalars().all())} 条日志")
    return True


async def test_llm():
    from app.analyzer.llm_client import llm_json
    result = await llm_json(
        system="你是一个测试助手，只返回JSON。",
        user='请返回 {"status": "ok", "message": "LLM连接正常"}',
    )
    if result and result.get("status") == "ok":
        print(f"✓ LLM 调用成功: {result}")
        return True
    print(f"✗ LLM 调用失败: {result}")
    return False


async def main():
    print("=" * 50)
    print("FundRadar 端到端集成测试")
    print("=" * 50)
    results = {}

    for name, coro in [
        ("DB连接+建表验证", test_db()),
        ("新闻爬虫", test_news_crawl()),
        ("行情爬虫", test_market_data()),
        ("数据入库", test_save_to_db()),
        ("LLM调用", test_llm()),
    ]:
        print(f"\n--- {name} ---")
        try:
            results[name] = await coro
        except Exception as e:
            print(f"✗ 异常: {e}")
            import traceback; traceback.print_exc()
            results[name] = False

    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for name, ok in results.items():
        print(f"  {'✓' if ok else '✗'} {name}")
    all_pass = all(results.values())
    print(f"\n{'全部通过 ✓' if all_pass else '有失败项，见上方详情'}")
    return all_pass


if __name__ == "__main__":
    asyncio.run(main())
