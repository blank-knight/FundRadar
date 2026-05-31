"""端到端测试 — 逐层验证核心链路。"""
import asyncio
import httpx
import sys

BASE = "http://localhost:8001/api"
RESULTS = []

def ok(name, detail=""):
    RESULTS.append(("✅", name, detail))
    print(f"  ✅ {name} {detail}")

def fail(name, detail=""):
    RESULTS.append(("❌", name, detail))
    print(f"  ❌ {name} {detail}")

def warn(name, detail=""):
    RESULTS.append(("⚠️", name, detail))
    print(f"  ⚠️  {name} {detail}")

# ─── 1. 用户注册/登录 ───────────────────────────────────────
async def test_auth(client):
    print("\n【1】用户注册/登录")
    # 注册
    r = await client.post(f"{BASE}/auth/register", json={
        "email": "test_e2e@example.com", "password": "Test1234!"
    })
    if r.status_code in (200, 201):
        ok("注册", f"status={r.status_code}")
    elif r.status_code == 400 and "already" in r.text.lower():
        warn("注册", "用户已存在，跳过")
    else:
        fail("注册", f"status={r.status_code} body={r.text[:100]}")

    # 登录
    r = await client.post(f"{BASE}/auth/login", json={
        "email": "test_e2e@example.com", "password": "Test1234!"
    })
    if r.status_code == 200 and "token" in r.json():
        token = r.json()["token"]
        ok("登录", f"拿到 token")
        return token
    else:
        fail("登录", f"status={r.status_code} body={r.text[:100]}")
        return None

# ─── 2. 博主管理 API ────────────────────────────────────────
async def test_bloggers(client, token):
    print("\n【2】博主管理 API")
    h = {"Authorization": f"Bearer {token}"}

    # 搜索（直接调爬虫，绕过 httpx client 冲突）
    from app.crawler.xueqiu import XueqiuCrawler as XC
    async with XC() as xc:
        results = await xc.search_users("但斌")
    if results:
        ok("搜索博主", f"返回 {len(results)} 个结果，第一个: {results[0].get('username','?')}")
        first = results[0]
    else:
        warn("搜索博主", "返回空列表")
        first = {"platform": "xueqiu", "platform_user_id": "1247347556",
                 "username": "但斌", "avatar_url": "", "follower_count": 0}

    # 添加博主
    r = await client.post(f"{BASE}/bloggers", json=first, headers=h)
    if r.status_code in (200, 201):
        blogger_id = r.json()["id"]
        ok("添加博主", f"id={blogger_id} name={r.json()['username']}")
    elif r.status_code == 409:
        warn("添加博主", "已存在，查列表拿 id")
        r2 = await client.get(f"{BASE}/bloggers", headers=h)
        blogger_id = r2.json()[0]["id"] if r2.json() else None
    else:
        fail("添加博主", f"status={r.status_code} body={r.text[:100]}")
        blogger_id = None

    # 列表
    r = await client.get(f"{BASE}/bloggers", headers=h)
    if r.status_code == 200:
        ok("博主列表", f"共 {len(r.json())} 个博主")
    else:
        fail("博主列表", f"status={r.status_code}")

    return blogger_id

# ─── 3. 爬虫 ───────────────────────────────────────────────
async def test_crawlers():
    print("\n【3】爬虫")
    from app.crawler.news import NewsCrawler
    from app.crawler.xueqiu import XueqiuCrawler, DEFAULT_BLOGGERS
    from app.crawler.fund_nav import FundNavCrawler, TRACKED_INDICES

    # 新闻
    async with NewsCrawler() as c:
        news = await c.get_all_news(10)
    if news:
        ok("新闻爬虫", f"{len(news)} 条，来源: {set(n['source'] for n in news)}")
    else:
        fail("新闻爬虫", "0 条")

    # 雪球
    async with XueqiuCrawler() as c:
        posts = await c.get_user_posts("1247347556", count=3)
    if posts:
        ok("雪球爬虫", f"但斌 {len(posts)} 条帖子")
    else:
        fail("雪球爬虫", "0 条")

    # 基金净值
    async with FundNavCrawler() as c:
        idx = await c.get_index_daily(TRACKED_INDICES[0]["symbol"])
    if idx:
        first = idx[0] if isinstance(idx, list) else idx
        ok("基金净值爬虫", f"指数: {first.get('symbol','')} close={first.get('close_price','?')}")
    else:
        fail("基金净值爬虫", "无数据")

# ─── 4. LLM 解析 ───────────────────────────────────────────
async def test_llm():
    print("\n【4】LLM 解析")
    from app.analyzer.llm_client import llm_text
    try:
        resp = await llm_text("你是测试助手", "回复 OK 即可，测试连通性")
        if resp:
            ok("LLM 连通", f"响应: {str(resp)[:60]}")
        else:
            fail("LLM 连通", "空响应")
    except Exception as e:
        fail("LLM 连通", str(e)[:100])

# ─── 5. 数据库写入链路 ──────────────────────────────────────
async def test_db_pipeline():
    print("\n【5】数据库写入链路")
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_news_crawl
    try:
        async with AsyncSessionLocal() as db:
            result = await run_news_crawl(db)
        if result.get("saved", 0) >= 0:
            ok("新闻入库", f"fetched={result.get('fetched',0)} saved={result.get('saved',0)} skipped={result.get('skipped',0)}")
        else:
            fail("新闻入库", str(result))
    except Exception as e:
        fail("新闻入库", str(e)[:120])

# ─── 6. 信号生成 ───────────────────────────────────────────
async def test_signal():
    print("\n【6】信号生成")
    from app.core.database import AsyncSessionLocal
    from app.analyzer.signal_generator import generate_daily_signal
    from datetime import date
    try:
        async with AsyncSessionLocal() as db:
            signal = await generate_daily_signal(db, target_symbol="000300")
        if signal:
            ok("信号生成", f"signal={signal.final_signal} confidence={signal.confidence:.2f}")
        else:
            warn("信号生成", "返回 None（可能数据不足）")
    except Exception as e:
        fail("信号生成", str(e)[:120])

# ─── 主流程 ────────────────────────────────────────────────
async def main():
    print("=" * 50)
    print("FundRadar 端到端测试")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=20) as client:
        token = await test_auth(client)
        if token:
            await test_bloggers(client, token)

    await test_crawlers()
    await test_llm()
    await test_db_pipeline()
    await test_signal()

    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    passed = sum(1 for r in RESULTS if r[0] == "✅")
    warned = sum(1 for r in RESULTS if r[0] == "⚠️")
    failed = sum(1 for r in RESULTS if r[0] == "❌")
    for r in RESULTS:
        print(f"  {r[0]} {r[1]}: {r[2]}")
    print(f"\n总计: ✅{passed} ⚠️{warned} ❌{failed}")

if __name__ == "__main__":
    asyncio.run(main())
