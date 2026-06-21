#!/usr/bin/env python3
"""前端数据导出脚本 — 从数据库导出真实数据到 frontend/public/data/*.json

用途:
    VPN 环境下内网穿透不可用，前端 (Vercel) 只能吃静态 JSON 快照。
    本脚本把数据库最新数据导出为前端期望的格式，然后 git push 触发 Vercel 重建。

数据流:
    PostgreSQL → 本脚本 → frontend/public/data/*.json → git push → Vercel 自动重建

运行方式:
    cd ~/clawd/fund-radar && python3 scripts/export_frontend.py
    cd ~/clawd/fund-radar && python3 scripts/export_frontend.py --no-push  # 只导出不push

可接入调度器: 信号生成后自动调用 (scheduler.py 中加一步)

数据可追溯: 本脚本可随时重新运行并复现相同输出 (基于当时数据库状态)。

Created: 2026-06-21
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 后端 .env
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
load_dotenv(BACKEND_DIR / ".env")

# 前端静态数据目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"
FRONTEND_DATA.mkdir(parents=True, exist_ok=True)


def _json_default(obj):
    """JSON 序列化: 处理 datetime/date/Decimal/asyncpg 类型。"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):  # date 等
        return obj.isoformat()
    if isinstance(obj, Decimal := __import__("decimal").Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def _write_json(filename: str, data):
    """写入 JSON 文件，ensure_ascii=False 保持中文可读。"""
    path = FRONTEND_DATA / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)
    count = len(data) if isinstance(data, list) else len(data.get("items", [data]))
    logger.info(f"  ✅ {filename}: {count} records ({path.stat().st_size // 1024}KB)")


async def export_signals(conn: asyncpg.Connection):
    """导出最近5条综合信号。"""
    rows = await conn.fetch("""
        SELECT signal_date, target_symbol, target_name, final_signal, confidence,
               blogger_consensus_score, news_sentiment_score, retail_sentiment_score,
               fund_flow_score, industry_momentum_score, reasoning,
               analyzed_news_count, participating_bloggers
        FROM daily_signals
        ORDER BY signal_date DESC
        LIMIT 5
    """)
    items = []
    for r in rows:
        d = dict(r)
        # target_name 兜底
        if not d.get("target_name"):
            d["target_name"] = "沪深300" if d.get("target_symbol") == "000300" else d.get("target_symbol", "")
        items.append(d)
    _write_json("signals.json", {"items": items})
    return len(items)


async def export_bloggers(conn: asyncpg.Connection):
    """导出博主列表 + 帖子数 + 准确率。"""
    rows = await conn.fetch("""
        SELECT b.username, b.platform, b.accuracy_score AS accuracy,
               COUNT(p.id) AS post_count,
               b.id
        FROM bloggers b
        LEFT JOIN predictions p ON p.blogger_id = b.id
        GROUP BY b.id, b.username, b.platform, b.accuracy_score
        ORDER BY post_count DESC, b.accuracy_score DESC
    """)
    items = []
    for r in rows:
        d = dict(r)
        username = d.get("username", "")
        platform = d.get("platform", "")
        # 生成搜索链接
        if "eastmoney" in platform:
            d["url"] = f"https://so.eastmoney.com/web/s?keyword={username}"
        elif "weibo" in platform:
            d["url"] = f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{username}"
        else:
            d["url"] = f"https://www.google.com/search?q={username}"
        # 前端期望的字段名
        d["postCount"] = d.pop("post_count")
        d["accuracy"] = float(d["accuracy"]) if d["accuracy"] else 0.5
        items.append(d)
    _write_json("bloggers.json", {"items": items})
    return len(items)


async def export_predictions(conn: asyncpg.Connection):
    """导出最近24条博主帖子 + LLM解析结果。"""
    rows = await conn.fetch("""
        SELECT p.post_content AS content, p.post_url AS url,
               p.predicted_direction AS direction, p.confidence,
               p.post_time AS "postTime",
               b.username AS blogger, b.platform
        FROM predictions p
        JOIN bloggers b ON p.blogger_id = b.id
        WHERE p.is_prediction = true
        ORDER BY p.post_time DESC
        LIMIT 24
    """)
    items = [dict(r) for r in rows]
    _write_json("predictions.json", items)
    return len(items)


async def export_news(conn: asyncpg.Connection):
    """导出最近50条新闻 + 情感分析。"""
    rows = await conn.fetch("""
        SELECT title, url, source,
               publish_time AS "publishTime",
               sentiment_score AS "sentimentScore",
               sentiment_label AS "sentimentLabel",
               summary
        FROM news
        ORDER BY publish_time DESC
        LIMIT 50
    """)
    items = []
    for r in rows:
        d = dict(r)
        # 兜底: summary 为空时用 title
        if not d.get("summary"):
            d["summary"] = d.get("title", "")
        items.append(d)
    _write_json("news.json", items)
    return len(items)


async def export_portfolio(conn: asyncpg.Connection):
    """导出用户持仓列表 → portfolio.json（前端持仓页面数据源）。"""
    rows = await conn.fetch("""
        SELECT id, fund_code, fund_name, fund_type,
               shares, cost_price, cost_total,
               current_price, current_value,
               profit_loss, profit_loss_pct,
               price_updated_at
        FROM portfolio
        ORDER BY current_value DESC NULLS LAST
    """)
    items = []
    for r in rows:
        d = dict(r)
        # datetime 序列化
        if d.get("price_updated_at"):
            d["price_updated_at"] = d["price_updated_at"].isoformat() if hasattr(d["price_updated_at"], "isoformat") else str(d["price_updated_at"])
        items.append(d)
    _write_json("portfolio.json", {"generated_at": datetime.now().isoformat(), "holdings": items})
    return len(items)


async def export_quant(conn: asyncpg.Connection):
    """导出最新量化快照。"""
    row = await conn.fetchrow("""
        SELECT id, snapshot_date, northbound_hgt, northbound_sgt, northbound_total,
               industry_avg_change_pct, industry_top_json, industry_bottom_json,
               fund_flow_000300, fund_flow_399006, fund_flow_000016,
               dragon_tiger_count, dragon_tiger_net_buy_wan, dragon_tiger_top_json,
               pe_000300, pb_000300, fund_flow_score, industry_momentum_score
        FROM quant_snapshots
        ORDER BY snapshot_date DESC
        LIMIT 1
    """)
    if row:
        data = dict(row)
        # 解析 JSON 字段（数据库里存的是 JSON 字符串）
        for k in ("industry_top_json", "industry_bottom_json", "dragon_tiger_top_json"):
            v = data.get(k)
            if isinstance(v, str):
                try:
                    data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
        _write_json("quant.json", data)
        return 1
    else:
        logger.warning("  ⚠️ quant_snapshots 表为空，跳过")
        _write_json("quant.json", {})
        return 0


async def export_portfolio_advice(conn: asyncpg.Connection):
    """导出持仓分析建议。"""
    rows = await conn.fetch("""
        SELECT pa.fund_code, pa.analyzed_at, pa.current_price,
               pa.profit_loss_pct, pa.action, pa.action_label, pa.reasoning,
               pf.fund_name
        FROM portfolio_analyses pa
        LEFT JOIN portfolio pf ON pa.fund_code = pf.fund_code
        WHERE pa.analyzed_at = (
            SELECT MAX(analyzed_at) FROM portfolio_analyses
        )
        ORDER BY pa.fund_code
    """)
    if not rows:
        logger.warning("  ⚠️ portfolio_analyses 表为空，跳过")
        _write_json("portfolio-advice.json", {"items": [], "advice": "", "alerts": []})
        return 0

    items = [dict(r) for r in rows]

    # 生成综合建议
    actions = [r["action"] for r in rows if r["action"]]
    if not actions:
        advice = "暂无操作建议"
    else:
        from collections import Counter
        c = Counter(actions)
        top_action = c.most_common(1)[0][0]
        action_map = {"hold": "持有观望", "buy": "建议加仓", "sell": "建议减仓", "reduce": "建议减仓"}
        advice = f"当前持仓整体建议：{action_map.get(top_action, top_action)}（{len(actions)}只基金分析）"

    # 赛道提醒：profit_loss_pct 最极端的
    alerts = []
    for r in rows:
        pnl = r.get("profit_loss_pct")
        if pnl is not None:
            if float(pnl) > 10:
                alerts.append({"fund_code": r["fund_code"], "fund_name": r.get("fund_name", ""),
                               "type": "profit", "message": f"涨幅{float(pnl):.1f}%，注意止盈"})
            elif float(pnl) < -10:
                alerts.append({"fund_code": r["fund_code"], "fund_name": r.get("fund_name", ""),
                               "type": "loss", "message": f"亏损{float(pnl):.1f}%，注意止损"})

    _write_json("portfolio-advice.json", {"items": items, "advice": advice, "alerts": alerts})
    return len(items)


def git_push():
    """git add + commit + push 前端数据文件。"""
    logger.info("Git push...")
    try:
        # 只提交 frontend/public/data/ 下的文件
        subprocess.run(["git", "add", "frontend/public/data/"], cwd=PROJECT_ROOT, check=True)

        # 检查有没有改动
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=PROJECT_ROOT,
            capture_output=True
        )
        if result.returncode == 0:
            logger.info("  ⏭️ 无数据变更，跳过 push")
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(
            ["git", "commit", "-m", f"chore: auto-export frontend data ({timestamp})"],
            cwd=PROJECT_ROOT, check=True, capture_output=True
        )
        # Vercel 每次只推1个commit的坑: 确保是单个 commit
        subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT, check=True, capture_output=True)
        logger.info("  ✅ Push 成功，Vercel 将自动重建")
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"  ❌ Git 操作失败: {err}")
        return False


async def main():
    no_push = "--no-push" in sys.argv

    logger.info("=" * 50)
    logger.info("FundRadar 前端数据导出")
    logger.info("=" * 50)

    # 连数据库
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not db_url:
        logger.error("DATABASE_URL 未配置，请检查 backend/.env")
        sys.exit(1)

    conn = await asyncpg.connect(db_url)
    logger.info(f"数据库连接成功: {conn.get_server_version()}")

    # 导出各模块
    # 注意: portfolio-advice.json 由 portfolio_advisor.py 独立生成（LLM分析，非DB导出）
    #       不要在这里覆盖它！前端期望 {generated_at, holdings[], sector_alerts[]} 格式
    logger.info("导出数据...")
    counts = {}
    counts["signals"] = await export_signals(conn)
    counts["bloggers"] = await export_bloggers(conn)
    counts["predictions"] = await export_predictions(conn)
    counts["news"] = await export_news(conn)
    counts["quant"] = await export_quant(conn)
    counts["portfolio"] = await export_portfolio(conn)

    await conn.close()

    logger.info(f"导出完成: {counts}")

    if no_push:
        logger.info("--no-push 模式，跳过 git push")
    else:
        git_push()

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
