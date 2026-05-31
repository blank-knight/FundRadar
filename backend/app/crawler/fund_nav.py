"""Fund NAV and market index data crawler."""
import logging
from datetime import datetime
from typing import Optional

from app.crawler.base import BaseCrawler

logger = logging.getLogger(__name__)

# Tiantian Fund (天天基金) — public API, no auth
TIANTIAN_FUND_NAV = "https://fundgz.1234567.com.cn/js/{code}.js"
TIANTIAN_FUND_HISTORY = "https://api.fund.eastmoney.com/f10/lsjz"

# AKShare-compatible East Money index API
EASTMONEY_INDEX_API = "https://push2hist.eastmoney.com/api/qt/stock/kline/get"

# Tracked indices
TRACKED_INDICES = [
    {"symbol": "000300", "name": "沪深300", "em_code": "000300.SH"},
    {"symbol": "399006", "name": "创业板指", "em_code": "399006.SZ"},
    {"symbol": "000016", "name": "上证50",  "em_code": "000016.SH"},
    {"symbol": "NDX",    "name": "纳斯达克100", "em_code": "NDX"},
]


class FundNavCrawler(BaseCrawler):
    """Crawl fund NAV and index price data."""

    def __init__(self, **kwargs):
        super().__init__(rate_limit_delay=0.5, **kwargs)

    async def get_fund_realtime_nav(self, fund_code: str) -> Optional[dict]:
        """Get real-time estimated NAV from Tiantian Fund."""
        try:
            url = TIANTIAN_FUND_NAV.format(code=fund_code)
            resp = await self.get(url, headers={"Referer": "https://fund.eastmoney.com/"})
            # Response is JSONP: jsonpgz({...});
            import re, json
            match = re.search(r"jsonpgz\((\{.*?\})\)", resp.text)
            if not match:
                return None
            data = json.loads(match.group(1))
            return {
                "fund_code": fund_code,
                "name": data.get("name", ""),
                "nav": float(data.get("gsz", 0)),       # 估算净值
                "nav_date": data.get("gztime", ""),
                "change_pct": float(data.get("gszzl", 0)),  # 估算涨跌幅
            }
        except Exception as e:
            logger.error(f"Fund NAV fetch failed for {fund_code}: {e}")
            return None

    async def get_fund_history_nav(
        self, fund_code: str, page: int = 1, per_page: int = 20
    ) -> list[dict]:
        """Get historical NAV records from East Money."""
        try:
            resp = await self.get(
                TIANTIAN_FUND_HISTORY,
                params={
                    "fundCode": fund_code,
                    "pageIndex": page,
                    "pageSize": per_page,
                    "type": "lsjz",
                },
                headers={
                    "Referer": f"https://fund.eastmoney.com/{fund_code}.html",
                    "Accept": "*/*",
                },
            )
            data = resp.json()
            records = data.get("Data", {}).get("LSJZList", [])
            result = []
            for r in records:
                try:
                    result.append({
                        "fund_code": fund_code,
                        "trade_date": datetime.strptime(r["FSRQ"], "%Y-%m-%d"),
                        "nav": float(r.get("DWJZ", 0)),
                        "acc_nav": float(r.get("LJJZ", 0)),
                        "change_pct": float(r.get("JZZZL", 0) or 0),
                    })
                except (ValueError, KeyError):
                    continue
            return result
        except Exception as e:
            logger.error(f"Fund history NAV failed for {fund_code}: {e}")
            return []

    async def get_index_daily(self, em_code: str, days: int = 5) -> list[dict]:
        """Get recent daily OHLC for a market index via AKShare."""
        import akshare as ak
        import pandas as pd

        # 转换代码格式: 000300.SH -> sh000300, 399006.SZ -> sz399006
        code = em_code.replace(".SH", "").replace(".SZ", "")
        if em_code.endswith(".SH"):
            symbol = f"sh{code}"
        elif em_code.endswith(".SZ"):
            symbol = f"sz{code}"
        else:
            symbol = f"sh{code}"

        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            df = df.tail(days).reset_index(drop=True)
            result = []
            prev_close = None
            for _, row in df.iterrows():
                close = float(row["close"])
                change_pct = round((close - prev_close) / prev_close * 100, 4) if prev_close else 0.0
                result.append({
                    "trade_date": pd.Timestamp(row["date"]).to_pydatetime(),
                    "open_price": float(row["open"]),
                    "high_price": float(row["high"]),
                    "low_price": float(row["low"]),
                    "close_price": close,
                    "volume": float(row["volume"]),
                    "change_pct": change_pct,
                })
                prev_close = close
            return result
        except Exception as e:
            logger.error(f"Index daily data failed for {em_code}: {e}")
            return []


def _to_secid(em_code: str) -> str:
    """Convert East Money code to secid format (1.000300 or 0.399006)."""
    code = em_code.replace(".SH", "").replace(".SZ", "")
    if em_code.endswith(".SH"):
        return f"1.{code}"
    elif em_code.endswith(".SZ"):
        return f"0.{code}"
    # 默认按代码首位判断
    if code.startswith("0") or code.startswith("3"):
        return f"0.{code}"
    return f"1.{code}"
