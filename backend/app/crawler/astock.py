"""A股量化数据采集器 — 基于 a-stock-data (v3.2.2) 直连HTTP API。

数据源优先级：
  1. 腾讯财经 (qt.gtimg.cn) — 不封IP，PE/PB/市值/换手率
  2. 同花顺 (data.hexin.cn) — 不封IP，北向资金
  3. 东财 push2/push2his — 资金流/行业排名 (内置 em_get 限流防封)
  4. 东财 datacenter — 融资融券/龙虎榜 (内置 em_get 限流防封)
  5. 东财 np-weblist — 全球资讯 (内置 em_get 限流防封)

来源: https://github.com/simonlin1212/a-stock-data (Apache-2.0)
"""
import asyncio
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ── 东财限流（串行 + 最小间隔 + 随机抖动）─────────────────────────
EM_MIN_INTERVAL = 1.0  # 秒，批量场景调大到 1.5~2
_em_last_call: float = 0.0


async def _em_throttle():
    """东财请求前的串行节流。"""
    global _em_last_call
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call)
    if wait > 0:
        await asyncio.sleep(wait + random.uniform(0.1, 0.5))
    _em_last_call = time.time()


async def em_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
) -> dict | None:
    """东财统一请求入口：自动节流 + 默认UA。

    返回 JSON dict，请求失败返回 None。
    """
    await _em_throttle()
    merged_headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    if headers:
        merged_headers.update(headers)
    try:
        resp = await client.get(url, params=params, headers=merged_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"em_get failed: {url} → {e}")
        return None


DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


async def em_datacenter(
    client: httpx.AsyncClient,
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict]:
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用。"""
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    d = await em_get(client, DATACENTER_URL, params=params)
    if d and d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


# ════════════════════════════════════════════════════════════════════
# 1. 腾讯财经 — 实时行情（PE/PB/市值/换手率），不封IP
# ════════════════════════════════════════════════════════════════════

async def tencent_quote(client: httpx.AsyncClient, codes: list[str]) -> dict[str, dict]:
    """批量拉取腾讯财经实时行情。

    Args:
        codes: 股票/指数代码列表, 如 ["000300", "399006"]
    Returns:
        {code: {name, price, change_pct, pe_ttm, pb, mcap_yi, ...}}
    """
    prefixed = []
    for c in codes:
        c = c.strip()
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    try:
        resp = await client.get(url, headers={"User-Agent": UA}, timeout=10)
        data = resp.content.decode("gbk")
    except Exception as e:
        logger.warning(f"tencent_quote failed: {e}")
        return {}

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        try:
            vals = line.split('"')[1].split("~")
        except IndexError:
            continue
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "amplitude_pct": float(vals[43]) if vals[43] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


# ════════════════════════════════════════════════════════════════════
# 2. 同花顺北向资金 — 沪深股通实时分钟流向（零鉴权）
# ════════════════════════════════════════════════════════════════════

HSGT_HEADERS = {
    "User-Agent": UA,
    "Host": "data.hexin.cn",
    "Referer": "https://data.hexin.cn/",
}


async def hsgt_realtime(client: httpx.AsyncClient) -> dict:
    """沪深股通当日实时分钟流向。

    Returns:
        {times: [...], hgt_yi: [...], sgt_yi: [...], latest_hgt: float, latest_sgt: float}
        latest 为最新累计净买入(亿元)，非交易时间可能为 None。
    """
    url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
    try:
        resp = await client.get(url, headers=HSGT_HEADERS, timeout=10)
        d = resp.json()
    except Exception as e:
        logger.warning(f"hsgt_realtime failed: {e}")
        return {"times": [], "hgt_yi": [], "sgt_yi": [], "latest_hgt": 0, "latest_sgt": 0}

    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])

    n = len(times)
    hgt_padded = (hgt + [None] * (n - len(hgt))) if n else []
    sgt_padded = (sgt + [None] * (n - len(sgt))) if n else []

    # 提取最新非空值
    latest_hgt = next((v for v in reversed(hgt_padded) if v is not None), 0)
    latest_sgt = next((v for v in reversed(sgt_padded) if v is not None), 0)

    return {
        "times": times,
        "hgt_yi": hgt_padded,
        "sgt_yi": sgt_padded,
        "latest_hgt": latest_hgt,
        "latest_sgt": latest_sgt,
    }


# ════════════════════════════════════════════════════════════════════
# 3. 东财 push2 — 指数资金流向（日级，主力/超大单净流入）
# ════════════════════════════════════════════════════════════════════

async def index_fund_flow(client: httpx.AsyncClient, em_code: str) -> list[dict]:
    """指数资金流（日级，最近120日）。

    Args:
        em_code: 东财格式代码，如 "000300.SH" → 需转成 secid "1.000300"
    Returns:
        [{date, main_net, small_net, mid_net, large_net, super_net}]  单位: 元
    """
    # 000300.SH → 1.000300, 399006.SZ → 0.399006
    if em_code.endswith(".SH"):
        secid = f"1.{em_code[:-3]}"
    elif em_code.endswith(".SZ"):
        secid = f"0.{em_code[:-3]}"
    else:
        secid = f"1.{em_code}"

    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        "lmt": "120",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }
    d = await em_get(client, url, params=params, headers=headers)
    if not d:
        return []

    klines = (d.get("data") or {}).get("klines", [])
    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append({
                "date": parts[0],
                "main_net": float(parts[1]) if parts[1] != "-" else 0,
                "small_net": float(parts[2]) if parts[2] != "-" else 0,
                "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                "large_net": float(parts[4]) if parts[4] != "-" else 0,
                "super_net": float(parts[5]) if parts[5] != "-" else 0,
            })
    return rows


async def stock_fund_flow_minute(client: httpx.AsyncClient, code: str) -> list[dict]:
    """个股/指数资金流向（分钟级，当日盘中）。

    Returns: [{time, main_net, small_net, mid_net, large_net, super_net}]  单位: 元
    """
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "secid": secid,
        "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Origin": "https://quote.eastmoney.com",
    }
    d = await em_get(client, url, params=params, headers=headers, timeout=10)
    if not d:
        return []

    rows = []
    for line in (d.get("data") or {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time": parts[0],
                "main_net": float(parts[1]),
                "small_net": float(parts[2]),
                "mid_net": float(parts[3]),
                "large_net": float(parts[4]),
                "super_net": float(parts[5]),
            })
    return rows


# ════════════════════════════════════════════════════════════════════
# 4. 东财行业板块排名
# ════════════════════════════════════════════════════════════════════

async def industry_comparison(
    client: httpx.AsyncClient, top_n: int = 20
) -> dict:
    """全行业涨跌幅排名（东财行业板块，~100个行业）。

    Returns: {top: [...], bottom: [...], total: int, avg_change_pct: float}
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    d = await em_get(client, url, params=params)
    if not d:
        return {"top": [], "bottom": [], "total": 0, "avg_change_pct": 0}

    items = (d.get("data") or {}).get("diff") or []
    if not items:
        return {"top": [], "bottom": [], "total": 0, "avg_change_pct": 0}

    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": float(item.get("f3", 0) or 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })

    avg = round(sum(r["change_pct"] for r in rows) / len(rows), 2) if rows else 0
    return {
        "top": rows[:top_n],
        "bottom": rows[-top_n:],
        "total": len(rows),
        "avg_change_pct": avg,
    }


# ════════════════════════════════════════════════════════════════════
# 5. 东财 datacenter — 全市场融资融券汇总
# ════════════════════════════════════════════════════════════════════

async def market_margin_trading(client: httpx.AsyncClient) -> list[dict]:
    """全市场融资融券汇总（最近交易日）。

    Returns: [{date, rzye(融资余额), rqye(融券余额), rzrqye(合计)}]
    """
    data = await em_datacenter(
        client,
        "RPTA_WEB_RZRQ_GGMX",
        filter_str="",  # 不过滤个股，取全市场
        page_size=30,
        sort_columns="DATE",
        sort_types="-1",
    )
    rows = []
    for row in data:
        rows.append({
            "date": str(row.get("DATE", ""))[:10],
            "rzye": row.get("RZYE", 0),       # 融资余额(元)
            "rzmre": row.get("RZMRE", 0),      # 融资买入额
            "rqye": row.get("RQYE", 0),        # 融券余额(元)
            "rzrqye": row.get("RZRQYE", 0),    # 融资融券余额合计
        })
    return rows


# ════════════════════════════════════════════════════════════════════
# 6. 东财全市场龙虎榜
# ════════════════════════════════════════════════════════════════════

async def daily_dragon_tiger(
    client: httpx.AsyncClient,
    trade_date: str | None = None,
    min_net_buy: float | None = None,
) -> dict:
    """全市场龙虎榜。

    Returns: {date, total_records, stocks: [...], total_net_buy_wan: float}
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    data = await em_datacenter(
        client,
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT",
        sort_types="-1",
    )
    if not data:
        return {"date": trade_date, "total_records": 0, "stocks": [],
                "total_net_buy_wan": 0}

    stocks = []
    total_net = 0
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net_buy is not None and net_buy < min_net_buy:
            continue
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
        total_net += net_buy

    return {
        "date": trade_date,
        "total_records": len(stocks),
        "stocks": stocks,
        "total_net_buy_wan": round(total_net, 1),
    }


# ════════════════════════════════════════════════════════════════════
# 7. 东财全球资讯 (7×24)
# ════════════════════════════════════════════════════════════════════

async def eastmoney_global_news(
    client: httpx.AsyncClient, page_size: int = 50
) -> list[dict]:
    """东方财富全球财经资讯（7×24滚动）。

    Returns: [{title, summary, time}]
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web",
        "biz": "web_724",
        "fastColumn": "102",
        "sortEnd": "",
        "pageSize": str(page_size),
        "req_trace": str(uuid.uuid4()),
    }
    headers = {"Referer": "https://kuaixun.eastmoney.com/"}
    d = await em_get(client, url, params=params, headers=headers, timeout=10)
    if not d:
        return []

    rows = []
    for item in (d.get("data") or {}).get("fastNewsList", []):
        rows.append({
            "title": item.get("title", ""),
            "summary": (item.get("summary", "") or "")[:200],
            "time": item.get("showTime", ""),
        })
    return rows


# ════════════════════════════════════════════════════════════════════
# 汇总入口：一次性采集全市场量化快照
# ════════════════════════════════════════════════════════════════════

async def fetch_quant_snapshot(tracked_em_codes: list[str] | None = None) -> dict:
    """一次性采集当日量化数据快照。

    Args:
        tracked_em_codes: 跟踪指数的东财代码，如 ["000300.SH", "399006.SZ"]
    Returns:
        {
            "northbound": {...},
            "industry": {...},
            "fund_flows": {"000300.SH": [...], ...},
            "dragon_tiger": {...},
            "timestamp": "2026-06-17T..."
        }
    """
    if tracked_em_codes is None:
        tracked_em_codes = ["000300.SH", "399006.SZ", "000016.SH"]

    result: dict = {"timestamp": datetime.utcnow().isoformat()}

    async with httpx.AsyncClient(
        headers=DEFAULT_HEADERS, timeout=20, follow_redirects=True
    ) as client:
        # 1. 北向资金
        try:
            result["northbound"] = await hsgt_realtime(client)
        except Exception as e:
            logger.warning(f"northbound failed: {e}")
            result["northbound"] = {}

        # 2. 行业排名
        try:
            result["industry"] = await industry_comparison(client, top_n=20)
        except Exception as e:
            logger.warning(f"industry failed: {e}")
            result["industry"] = {"top": [], "total": 0, "avg_change_pct": 0}

        # 3. 各跟踪指数资金流（日级，最近10日）
        result["fund_flows"] = {}
        for em_code in tracked_em_codes:
            try:
                flow = await index_fund_flow(client, em_code)
                result["fund_flows"][em_code] = flow[-10:] if flow else []
            except Exception as e:
                logger.warning(f"fund_flow {em_code} failed: {e}")
                result["fund_flows"][em_code] = []

        # 4. 龙虎榜
        try:
            result["dragon_tiger"] = await daily_dragon_tiger(client)
        except Exception as e:
            logger.warning(f"dragon_tiger failed: {e}")
            result["dragon_tiger"] = {"total_records": 0, "stocks": []}

    return result
