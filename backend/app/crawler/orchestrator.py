"""Crawler orchestrator — runs all crawlers, writes CrawlLog, persists to DB."""
import logging
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crawler.xueqiu import XueqiuCrawler
from app.crawler.weibo import WeiboCrawler, DEFAULT_WEIBO_KOLS
from app.crawler.sentiment import SentimentCrawler
from app.crawler.news import NewsCrawler
from app.crawler.fund_nav import FundNavCrawler, TRACKED_INDICES
from app.models.models import (
    Blogger, Prediction, News, MarketData, CrawlLog,
    RetailSentiment, QuantSnapshot,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _write_crawl_log(
    db: AsyncSession,
    crawler_name: str,
    status: str,
    fetched: int,
    saved: int,
    skipped: int,
    duration: float,
    error: str | None = None,
    snapshot: dict | None = None,
) -> None:
    log = CrawlLog(
        crawler_name=crawler_name,
        run_at=datetime.utcnow(),
        status=status,
        items_fetched=fetched,
        items_saved=saved,
        items_skipped=skipped,
        duration_seconds=round(duration, 2),
        error_message=error,
        raw_snapshot=snapshot,
    )
    db.add(log)
    await db.commit()


async def run_xueqiu_crawl(db: AsyncSession) -> dict:
    """爬取博主帖子（多平台：微博为主 + 东财分析师）。

    雪球WAF已不可用，改为微博大V时间线 + 东财分析师评级。
    """
    t0 = time.time()
    saved_posts = 0
    skipped = 0
    fetched = 0
    snapshot = {"sources": {}}
    error_msg = None

    try:
        # === 数据源1: 微博大V帖子 ===
        db_weibo_result = await db.execute(
            select(Blogger).where(
                Blogger.platform == "weibo",
                Blogger.is_active == True,
            )
        )
        weibo_bloggers = db_weibo_result.scalars().all()

        if weibo_bloggers:
            async with WeiboCrawler() as crawler:
                weibo_fetched = 0
                weibo_saved = 0
                for blogger in weibo_bloggers:
                    uid = blogger.platform_user_id
                    posts = await crawler.get_user_timeline(uid, page=1)
                    weibo_fetched += len(posts)
                    b_saved = 0
                    for post in posts:
                        if not post.get("post_url") or not post.get("content"):
                            continue
                        exists = await db.execute(
                            select(Prediction).where(Prediction.post_url == post["post_url"])
                        )
                        if exists.scalar_one_or_none():
                            skipped += 1
                            continue
                        pred = Prediction(
                            blogger_id=blogger.id,
                            post_url=post["post_url"],
                            post_content=post["content"],
                            post_time=post["post_time"],
                            raw_data=post.get("raw_data"),
                        )
                        db.add(pred)
                        saved_posts += 1
                        b_saved += 1
                    snapshot["sources"][blogger.username] = {
                        "fetched": len(posts), "saved": b_saved,
                    }
                fetched += weibo_fetched
            await db.commit()

        # === 数据源2: 东财分析师评级 ===
        em_saved = await _crawl_em_analysts(db)
        saved_posts += em_saved
        snapshot["sources"]["eastmoney_analysts"] = {"saved": em_saved}

        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Blogger crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "bloggers_multi", status, fetched, saved_posts, skipped, duration, error_msg, snapshot)
    logger.info(f"Blogger crawl done: fetched={fetched} saved={saved_posts} skipped={skipped}")
    return {"saved_posts": saved_posts, "skipped": skipped, "fetched": fetched}


async def _crawl_em_analysts(db: AsyncSession) -> int:
    """爬取东财分析师最新评级，转为prediction存入。

    分析师评级映射: 买入→bullish, 增持→bullish, 中性→neutral, 减持/卖出→bearish
    """
    import akshare as ak

    saved = 0
    try:
        df = ak.stock_analyst_rank_em(year="2025")
        if df is None or df.empty:
            return 0

        # 筛选活跃分析师：成分股>5 + 近3个月正收益 + 年化TOP50
        import pandas as pd
        df["成分股个数"] = pd.to_numeric(df["成分股个数"], errors="coerce").fillna(0)
        df["3个月收益率"] = pd.to_numeric(df["3个月收益率"], errors="coerce").fillna(0)
        active = df[(df["成分股个数"] >= 5) & (df["3个月收益率"] > 0)].head(20)
        logger.info(f"EM analysts: {len(active)} active analysts (成分股>=5, 3月收益>0)")

        for _, row in active.iterrows():
            analyst_id = str(row.get("分析师ID", ""))
            analyst_name = str(row.get("分析师名称", ""))
            analyst_org = str(row.get("分析师单位", ""))
            stock_name = str(row.get("2025最新个股评级-股票名称", ""))
            stock_code = str(row.get("2025最新个股评级-股票代码", ""))

            if not analyst_id or not stock_name or stock_name == "nan":
                continue

            # 找DB里的分析师博主记录，没有就自动创建
            blogger_result = await db.execute(
                select(Blogger).where(
                    Blogger.platform == "eastmoney_analyst",
                    Blogger.platform_user_id == analyst_id,
                )
            )
            blogger = blogger_result.scalar_one_or_none()

            if not blogger:
                blogger = Blogger(
                    username=f"{analyst_name}-{analyst_org}",
                    platform="eastmoney_analyst",
                    platform_user_id=analyst_id,
                    follower_count=int(row.get("成分股个数", 0)),
                    accuracy_score=0.5,  # 初始值，后续根据预测验证更新
                    is_active=True,
                )
                db.add(blogger)
                await db.flush()
                logger.info(f"Created new analyst blogger: {analyst_name}({analyst_org})")

            # 构造post_url作为去重key
            post_url = f"em_analyst://{analyst_id}/{stock_code}"

            exists = await db.execute(
                select(Prediction).where(Prediction.post_url == post_url)
            )
            if exists.scalar_one_or_none():
                continue

            # 构造模拟帖子内容
            post_content = f"【{analyst_name}({analyst_org})】最新评级: {stock_name}({stock_code})"

            # 用分析师年度收益率推方向
            annual_return = row.get("2025年收益率")
            if annual_return is not None and str(annual_return) != "nan":
                try:
                    ret = float(annual_return)
                    if ret > 10:
                        direction = "bullish"
                    elif ret < -10:
                        direction = "bearish"
                    else:
                        direction = "neutral"
                    confidence = min(1.0, abs(ret) / 100)
                except (ValueError, TypeError):
                    direction = "neutral"
                    confidence = 0.3
            else:
                direction = "neutral"
                confidence = 0.3

            pred = Prediction(
                blogger_id=blogger.id,
                post_url=post_url,
                post_content=post_content,
                post_time=datetime.utcnow(),
                predicted_direction=direction,
                predicted_target=stock_code if stock_code != "nan" else None,
                confidence=confidence,
                is_prediction=True,  # 分析师评级直接是预测
                raw_data={
                    "analyst_name": analyst_name,
                    "analyst_org": analyst_org,
                    "stock_name": stock_name,
                    "stock_code": stock_code,
                    "annual_return": str(row.get("2025年收益率", "")),
                    "rank": str(row.get("序号", "")),
                },
            )
            db.add(pred)
            saved += 1

        await db.commit()
        logger.info(f"EM analysts crawl: saved {saved} ratings")
    except Exception as e:
        logger.error(f"EM analysts crawl error: {e}")

    return saved


async def run_news_crawl(db: AsyncSession) -> dict:
    """Crawl financial news and save new articles."""
    t0 = time.time()
    saved = 0
    skipped = 0
    fetched = 0
    snapshot: dict = {}
    error_msg = None

    try:
        async with NewsCrawler() as crawler:
            articles = await crawler.get_all_news(count_each=30)
            fetched = len(articles)
            snapshot = {"sources": {}}
            for article in articles:
                src = article.get("source", "unknown")
                snapshot["sources"][src] = snapshot["sources"].get(src, 0) + 1
                if not article.get("url") or not article.get("publish_time"):
                    skipped += 1
                    continue
                exists = await db.execute(
                    select(News).where(News.url == article["url"])
                )
                if exists.scalar_one_or_none():
                    skipped += 1
                    continue
                news = News(
                    source=article["source"],
                    title=article["title"],
                    url=article["url"],
                    publish_time=article["publish_time"],
                    summary=article.get("summary"),
                )
                db.add(news)
                saved += 1
            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"News crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "news", status, fetched, saved, skipped, duration, error_msg, snapshot)
    logger.info(f"News crawl done: fetched={fetched} saved={saved} skipped={skipped}")
    return {"saved_articles": saved, "skipped": skipped, "fetched": fetched}


async def run_market_data_crawl(db: AsyncSession) -> dict:
    """Crawl index daily data and save to market_data."""
    t0 = time.time()
    saved = 0
    skipped = 0
    fetched = 0
    snapshot: dict = {"indices": []}
    error_msg = None

    try:
        async with FundNavCrawler() as crawler:
            for idx in TRACKED_INDICES:
                if idx["symbol"] == "NDX":
                    continue
                records = await crawler.get_index_daily(idx["em_code"], days=5)
                fetched += len(records)
                idx_saved = 0
                for rec in records:
                    exists = await db.execute(
                        select(MarketData).where(
                            MarketData.symbol == idx["symbol"],
                            MarketData.trade_date == rec["trade_date"],
                        )
                    )
                    if exists.scalar_one_or_none():
                        skipped += 1
                        continue
                    md = MarketData(
                        symbol=idx["symbol"],
                        name=idx["name"],
                        trade_date=rec["trade_date"],
                        open_price=rec["open_price"],
                        high_price=rec["high_price"],
                        low_price=rec["low_price"],
                        close_price=rec["close_price"],
                        change_pct=rec["change_pct"],
                        volume=rec.get("volume"),
                    )
                    db.add(md)
                    saved += 1
                    idx_saved += 1
                snapshot["indices"].append({"symbol": idx["symbol"], "fetched": len(records), "saved": idx_saved})
            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Market data crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "market_data", status, fetched, saved, skipped, duration, error_msg, snapshot)
    logger.info(f"Market data crawl done: fetched={fetched} saved={saved} skipped={skipped}")
    return {"saved_records": saved, "skipped": skipped, "fetched": fetched}


async def run_weibo_crawl(db: AsyncSession) -> dict:
    """爬取微博大V帖子并存入 predictions 表。"""
    t0 = time.time()
    saved_posts = 0
    skipped = 0
    fetched = 0
    snapshot = {"kols": []}
    error_msg = None

    try:
        # 从数据库读已关注的微博博主，没有则用默认
        db_bloggers_result = await db.execute(
            select(Blogger).where(
                Blogger.platform == "weibo",
                Blogger.is_active == True,
            )
        )
        db_bloggers = db_bloggers_result.scalars().all()

        # 如果DB没有微博博主，用默认KOL列表
        kols = []
        if db_bloggers:
            for b in db_bloggers:
                kols.append({"uid": b.platform_user_id, "username": b.username})
        else:
            kols = DEFAULT_WEIBO_KOLS

        async with WeiboCrawler() as crawler:
            for kol in kols:
                uid = kol["uid"]
                posts = await crawler.get_user_timeline(uid, page=1)
                fetched += len(posts)
                kol_saved = 0

                for post in posts:
                    if not post.get("post_url") or not post.get("content"):
                        skipped += 1
                        continue

                    # 检查是否已存在（微博和雪球共用 predictions 表）
                    exists = await db.execute(
                        select(Prediction).where(Prediction.post_url == post["post_url"])
                    )
                    if exists.scalar_one_or_none():
                        skipped += 1
                        continue

                    # 找到或创建微博博主记录
                    blogger = None
                    if db_bloggers:
                        for b in db_bloggers:
                            if b.platform_user_id == uid:
                                blogger = b
                                break

                    if not blogger:
                        blogger = Blogger(
                            platform="weibo",
                            platform_user_id=uid,
                            username=kol.get("username", ""),
                        )
                        db.add(blogger)
                        await db.flush()

                    pred = Prediction(
                        blogger_id=blogger.id,
                        post_url=post["post_url"],
                        post_content=post["content"],
                        post_time=post["post_time"],
                        raw_data=post.get("raw_data"),
                    )
                    db.add(pred)
                    saved_posts += 1
                    kol_saved += 1

                snapshot["kols"].append({
                    "username": kol.get("username", uid),
                    "uid": uid,
                    "fetched": len(posts),
                    "saved": kol_saved,
                })

            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Weibo crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "weibo", status, fetched, saved_posts, skipped, duration, error_msg, snapshot)
    logger.info(f"Weibo crawl done: fetched={fetched} saved={saved_posts} skipped={skipped}")
    return {"saved_posts": saved_posts, "skipped": skipped, "fetched": fetched}


async def run_sentiment_crawl(db: AsyncSession) -> dict:
    """爬取散户情绪数据（akshare 微博NLP + 东财评论），存入 retail_sentiments 表。"""
    t0 = time.time()
    saved = 0
    fetched = 0
    snapshot: dict = {"sources": {}}
    error_msg = None

    try:
        async with SentimentCrawler() as crawler:
            now = datetime.utcnow()

            # 1. 微博舆情
            weibo = await crawler.get_weibo_sentiment(time_period="CNHOUR12")
            if weibo:
                fetched += 1
                rs = RetailSentiment(
                    source="weibo_nlp",
                    symbol="MARKET",
                    sentiment_score=weibo["sentiment_score"],
                    bullish_ratio=weibo["bullish_ratio"],
                    bearish_ratio=weibo["bearish_ratio"],
                    raw_data=weibo["raw_data"],
                    captured_at=now,
                )
                db.add(rs)
                saved += 1
                snapshot["sources"]["weibo_nlp"] = {
                    "score": weibo["sentiment_score"],
                    "bullish": weibo["bullish_ratio"],
                }

            # 2. 东财评论
            em = await crawler.get_em_comment_sentiment()
            if em:
                fetched += 1
                rs = RetailSentiment(
                    source="eastmoney_comment",
                    symbol="MARKET",
                    sentiment_score=em["sentiment_score"],
                    bullish_ratio=em["bullish_ratio"],
                    bearish_ratio=em["bearish_ratio"],
                    raw_data=em["raw_data"],
                    captured_at=now,
                )
                db.add(rs)
                saved += 1
                snapshot["sources"]["eastmoney_comment"] = {
                    "score": em["sentiment_score"],
                    "bullish": em["bullish_ratio"],
                }

            await db.commit()
        status = "success" if saved > 0 else "partial"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Sentiment crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "sentiment", status, fetched, saved, 0, duration, error_msg, snapshot)
    logger.info(f"Sentiment crawl done: fetched={fetched} saved={saved}")
    return {"saved": saved, "fetched": fetched, "sources": snapshot.get("sources", {})}


async def run_signal_feedback(db: AsyncSession) -> dict:
    """
    每日反馈调节任务：
    1. 验证昨天的信号
    2. 检查是否需要触发复盘
    返回执行摘要。
    """
    from app.services.signal_feedback import verify_daily_signal, check_and_trigger_review
    from app.crawler.fund_nav import TRACKED_INDICES

    today = datetime.utcnow()
    results = {}

    for idx in TRACKED_INDICES:
        symbol = idx["symbol"]
        if symbol == "NDX":
            continue  # 暂不验证海外指数

        verification = await verify_daily_signal(db, today, symbol)
        review = await check_and_trigger_review(db, symbol)

        results[symbol] = {
            "verified": verification is not None,
            "correct": verification.is_correct if verification else None,
            "review_triggered": review is not None,
            "review_id": review.id if review else None,
        }
        if verification:
            logger.info(
                f"[feedback] {symbol}: predicted={verification.predicted_signal} "
                f"actual={verification.actual_change_pct:+.2f}% correct={verification.is_correct}"
            )
        if review:
            logger.warning(f"[feedback] {symbol}: review triggered, id={review.id}")

    return results


# ════════════════════════════════════════════════════════════════════
# V2: 量化数据采集 (a-stock-data)
# ════════════════════════════════════════════════════════════════════

def _compute_fund_flow_score(northbound_total: float | None, main_net_5d: float | None) -> float | None:
    """计算资金面综合得分 (-1~1)。

    北向资金 + 主力资金流加权:
      - 北向：当日净流入(亿)，归一化到 [-1, 1]，±50亿为满分
      - 主力资金流：近5日主力净流入累计(亿)，归一化到 [-1, 1]，±20亿为满分
    权重: 北向 60% + 主力 40%
    """
    score_nb = None
    score_mf = None

    if northbound_total is not None:
        score_nb = max(-1.0, min(1.0, northbound_total / 50.0))

    if main_net_5d is not None:
        score_mf = max(-1.0, min(1.0, main_net_5d / 20.0))

    if score_nb is not None and score_mf is not None:
        return round(0.6 * score_nb + 0.4 * score_mf, 4)
    elif score_nb is not None:
        return round(score_nb, 4)
    elif score_mf is not None:
        return round(score_mf, 4)
    return None


def _compute_industry_momentum(industry_data: dict) -> float | None:
    """计算行业动能得分 (-1~1)。

    全行业平均涨跌幅 + 上涨行业占比加权:
      - avg_change_pct: ±2% 为满分
      - up_ratio: 0.5 为中性，偏移量 × 2
    权重: avg_change 50% + up_ratio 50%
    """
    if not industry_data or not industry_data.get("total"):
        return None

    avg_pct = industry_data.get("avg_change_pct", 0)
    total = industry_data["total"]

    # 上涨行业占比
    up_count = sum(1 for r in industry_data.get("top", []) if r.get("change_pct", 0) > 0)
    # top + bottom 可能有重叠，用 total 更准
    # 但如果只有 top 列表，用 top 里的涨跌统计
    if industry_data.get("top"):
        up_in_list = sum(1 for r in industry_data["top"] if r.get("change_pct", 0) > 0)
        up_ratio = up_in_list / len(industry_data["top"]) if industry_data["top"] else 0.5
    else:
        up_ratio = 0.5

    score_avg = max(-1.0, min(1.0, avg_pct / 2.0))
    score_up = max(-1.0, min(1.0, (up_ratio - 0.5) * 2))

    return round(0.5 * score_avg + 0.5 * score_up, 4)


async def run_quant_crawl(db: AsyncSession) -> dict:
    """采集量化数据快照（北向资金 / 行业轮动 / 指数资金流 / 龙虎榜）。

    数据来源: a-stock-data → app/crawler/astock.py
    存入: quant_snapshots 表
    """
    from app.crawler.astock import fetch_quant_snapshot, tencent_quote
    import httpx

    t0 = time.time()
    fetched = 0
    error_msg = None
    snapshot: dict = {}

    try:
        # 采集核心量化数据
        tracked_em = [idx["em_code"] for idx in TRACKED_INDICES if idx["symbol"] != "NDX"]
        data = await fetch_quant_snapshot(tracked_em)
        fetched = sum(1 for v in data.values() if v)

        # 采集 PE/PB 估值
        pe_300 = None
        pb_300 = None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                from app.crawler.astock import DEFAULT_HEADERS
                quotes = await tencent_quote(client, ["000300"])
                if "000300" in quotes:
                    pe_300 = quotes["000300"].get("pe_ttm")
                    pb_300 = quotes["000300"].get("pb")
                    fetched += 1
        except Exception as e:
            logger.warning(f"tencent_quote failed: {e}")

        # ── 提取字段 ──
        nb = data.get("northbound", {})
        nb_hgt = nb.get("latest_hgt")
        nb_sgt = nb.get("latest_sgt")
        nb_total = (nb_hgt or 0) + (nb_sgt or 0) if (nb_hgt is not None or nb_sgt is not None) else None

        industry = data.get("industry", {})
        avg_change = industry.get("avg_change_pct")

        # 指数资金流 — 取最近5日主力净流入累计
        ff_data = data.get("fund_flows", {})
        ff_300 = _sum_main_net(ff_data.get("000300.SH", []), days=5)
        ff_006 = _sum_main_net(ff_data.get("399006.SZ", []), days=5)
        ff_016 = _sum_main_net(ff_data.get("000016.SH", []), days=5)

        # 龙虎榜
        dt = data.get("dragon_tiger", {})

        # ── 计算衍生指标 ──
        fund_flow_score = _compute_fund_flow_score(nb_total, ff_300)
        industry_score = _compute_industry_momentum(industry)

        # ── 存入 DB ──
        now = datetime.utcnow()
        # 查重 — 同一天只存一条
        existing = await db.execute(
            select(QuantSnapshot).where(QuantSnapshot.snapshot_date >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        )
        if existing.scalar_one_or_none():
            logger.info("[quant] 今日已采集，跳过")
            duration = time.time() - t0
            await _write_crawl_log(db, "quant", "skipped", fetched, 0, 0, duration)
            return {"saved": 0, "skipped": True}

        qs = QuantSnapshot(
            snapshot_date=now,
            northbound_hgt=nb_hgt,
            northbound_sgt=nb_sgt,
            northbound_total=nb_total,
            industry_avg_change_pct=avg_change,
            industry_top_json=industry.get("top", [])[:5],
            industry_bottom_json=industry.get("bottom", [])[-5:],
            fund_flow_000300=ff_300,
            fund_flow_399006=ff_006,
            fund_flow_000016=ff_016,
            fund_flow_detail=ff_data,
            dragon_tiger_count=dt.get("total_records"),
            dragon_tiger_net_buy_wan=dt.get("total_net_buy_wan"),
            dragon_tiger_top_json=dt.get("stocks", [])[:10],
            pe_000300=pe_300,
            pb_000300=pb_300,
            fund_flow_score=fund_flow_score,
            industry_momentum_score=industry_score,
            raw_data=data,
        )
        db.add(qs)
        await db.commit()

        snapshot = {
            "northbound_total": nb_total,
            "industry_avg": avg_change,
            "fund_flow_300_5d_yi": ff_300,
            "fund_flow_score": fund_flow_score,
            "industry_score": industry_score,
            "pe_300": pe_300,
        }
        status = "success"

    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Quant crawl error: {e}", exc_info=True)

    duration = time.time() - t0
    await _write_crawl_log(db, "quant", status, fetched, 1 if status == "success" else 0, 0, duration, error_msg, snapshot)
    logger.info(f"Quant crawl done: status={status} duration={duration:.1f}s score_ff={snapshot.get('fund_flow_score')}")
    return {"saved": 1 if status == "success" else 0, "status": status, **snapshot}


def _sum_main_net(flow_rows: list[dict], days: int = 5) -> float | None:
    """从资金流日数据中取最近 N 日主力净流入累计（元 → 亿元）。"""
    if not flow_rows:
        return None
    recent = flow_rows[-days:]
    total = sum(r.get("main_net", 0) for r in recent)
    return round(total / 1e8, 2)  # 元 → 亿元
