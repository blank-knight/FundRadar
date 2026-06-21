"""持仓净值更新服务 — 每日收盘后拉取最新净值/价格，刷新盈亏。

支持三种 fund_type：
  fund  — 场外基金，用 akshare fund_open_fund_info_em 拉单位净值
  etf   — 场内 ETF，用天天基金实时估值接口（fundgz.1234567.com.cn）
  stock — A股/指数，用 akshare stock_zh_index_daily 或 stock_zh_a_hist
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Portfolio

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 各类型净值拉取
# ─────────────────────────────────────────────

async def fetch_fund_nav(fund_code: str) -> float | None:
    """场外基金：akshare fund_open_fund_info_em，返回最新单位净值。"""
    try:
        import akshare as ak
        # 新版 akshare 参数名是 symbol，旧版是 fund，兼容两者
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        except TypeError:
            df = ak.fund_open_fund_info_em(fund=fund_code, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        latest = df.iloc[-1]
        nav = float(latest.get("单位净值") or latest.iloc[1])
        return nav
    except Exception as e:
        logger.warning(f"fetch_fund_nav failed for {fund_code}: {e}")
        return None


async def fetch_etf_price(fund_code: str) -> float | None:
    """场内 ETF：天天基金实时估值接口，返回估算净值（盘中）或最新净值。"""
    try:
        import re, json
        import httpx
        url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(url, headers={"Referer": "https://fund.eastmoney.com/"})
            resp.raise_for_status()
        match = re.search(r"jsonpgz\((\{.*?\})\)", resp.text)
        if not match:
            return None
        data = json.loads(match.group(1))
        # gsz=估算净值（盘中），dwjz=上一日净值
        price = data.get("gsz") or data.get("dwjz")
        return float(price) if price else None
    except Exception as e:
        logger.warning(f"fetch_etf_price failed for {fund_code}: {e}")
        return None


async def fetch_stock_price(fund_code: str) -> float | None:
    """A股/指数：akshare stock_zh_index_daily（指数）或 stock_zh_a_hist（个股），返回最新收盘价。"""
    try:
        import akshare as ak

        # 判断是指数还是个股
        # 指数代码：000开头(上证)、399开头(深证)、NDX等
        is_index = (
            fund_code.startswith("000") or
            fund_code.startswith("399") or
            fund_code.startswith("NDX") or
            fund_code.upper() in ("SPX", "DJI", "VIX")
        )

        if is_index:
            # 转换为 akshare 格式
            if fund_code.startswith("000"):
                symbol = f"sh{fund_code}"
            elif fund_code.startswith("399"):
                symbol = f"sz{fund_code}"
            else:
                # 海外指数暂不支持
                logger.warning(f"Overseas index {fund_code} not supported yet")
                return None
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is None or df.empty:
                return None
            return float(df.iloc[-1]["close"])
        else:
            # 个股：stock_zh_a_hist，取最近1条
            df = ak.stock_zh_a_hist(
                symbol=fund_code,
                period="daily",
                adjust="qfq",
            )
            if df is None or df.empty:
                return None
            return float(df.iloc[-1]["收盘"])
    except Exception as e:
        logger.warning(f"fetch_stock_price failed for {fund_code}: {e}")
        return None


# ─────────────────────────────────────────────
# 统一入口
# ─────────────────────────────────────────────

FETCHERS = {
    "fund":  fetch_fund_nav,
    "etf":   fetch_etf_price,
    "stock": fetch_stock_price,
}


async def update_portfolio_nav(item: Portfolio) -> bool:
    """更新单条持仓的净值和盈亏，原地修改，不 commit。"""
    fetcher = FETCHERS.get(item.fund_type)
    if fetcher is None:
        logger.warning(f"Unknown fund_type '{item.fund_type}' for {item.fund_code}, skip")
        return False

    price = await fetcher(item.fund_code)
    if price is None:
        return False

    item.current_price = price
    item.current_value = round(item.shares * price, 4)
    item.profit_loss = round(item.current_value - item.cost_total, 4)
    item.profit_loss_pct = (
        round(item.profit_loss / item.cost_total * 100, 4)
        if item.cost_total > 0 else 0.0
    )
    item.price_updated_at = datetime.utcnow()
    return True


async def update_all_portfolio_nav(db: AsyncSession) -> dict:
    """
    遍历所有持仓，按 fund_type 分别拉取最新价格，刷新盈亏。
    支持 fund / etf / stock 三种类型。
    """
    result = await db.execute(select(Portfolio))
    items = result.scalars().all()

    if not items:
        return {"updated": 0, "failed": 0, "skipped": 0, "total": 0}

    updated = failed = skipped = 0

    for item in items:
        if item.fund_type not in FETCHERS:
            skipped += 1
            logger.info(f"Skipped unknown type '{item.fund_type}': {item.fund_code}")
            continue

        ok = await update_portfolio_nav(item)
        if ok:
            updated += 1
            logger.info(
                f"NAV updated [{item.fund_type}] {item.fund_code} "
                f"price={item.current_price} pnl={item.profit_loss_pct:+.2f}%"
            )
        else:
            failed += 1
            logger.warning(f"NAV update failed [{item.fund_type}]: {item.fund_code}")

    await db.commit()
    logger.info(
        f"NAV update done: updated={updated} failed={failed} "
        f"skipped={skipped} total={len(items)}"
    )

    # 同步更新 portfolio.json（前端数据源）
    try:
        await _sync_portfolio_json(items)
    except Exception as e:
        logger.error(f"Failed to sync portfolio.json: {e}")

    return {"updated": updated, "failed": failed, "skipped": skipped, "total": len(items)}


async def _sync_portfolio_json(items) -> None:
    """净值更新后，把最新数据写回 frontend/public/data/portfolio.json。

    portfolio.json 是前端唯一数据源，不能从 DB 全量覆盖（会复活前端删除的持仓），
    只更新已有持仓的净值/盈亏字段。
    """
    import json
    from pathlib import Path
    from datetime import datetime

    json_path = Path(__file__).resolve().parents[2].parent / "frontend" / "public" / "data" / "portfolio.json"

    # 读取现有 portfolio.json
    existing = {"generated_at": datetime.now().isoformat(), "holdings": []}
    if json_path.exists():
        with open(json_path) as f:
            existing = json.load(f)

    # 按 fund_code 建索引
    db_by_code = {}
    for item in items:
        if item.fund_code:
            db_by_code[item.fund_code] = {
                "current_price": item.current_price,
                "current_value": item.current_value,
                "profit_loss": item.profit_loss,
                "profit_loss_pct": item.profit_loss_pct,
                "price_updated_at": item.price_updated_at.isoformat() if item.price_updated_at else None,
            }

    # 更新 JSON 中已有持仓的净值（不增删持仓）
    for h in existing.get("holdings", []):
        code = h.get("fund_code") or h.get("code")
        if code in db_by_code:
            h.update(db_by_code[code])

    existing["generated_at"] = datetime.now().isoformat()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"portfolio.json synced with latest NAV ({len(existing.get('holdings', []))} holdings)")
