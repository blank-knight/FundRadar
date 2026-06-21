"""
持仓顾问 — 基于持仓匹配新闻/分析师评级，生成操作建议+赛道提醒

流程：
1. 拿用户持仓 → LLM映射到行业/主题
2. 批量给新闻打标签（行业、多空、影响度）— 10条/批
3. 按持仓行业匹配相关新闻 → 汇总 → 生成操作建议
4. 识别非持仓热门赛道 → 赛道提醒

输出: frontend/public/data/portfolio-advice.json
"""
import asyncio
import asyncpg
import json
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 添加 backend 到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from app.analyzer.llm_client import llm_json, llm_text

DB_URL = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')
OUTPUT = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public', 'data', 'portfolio-advice.json')
USER_ID = 1  # Steven Tao


async def get_portfolio(conn, user_id):
    """拿到用户持仓"""
    rows = await conn.fetch(
        "SELECT fund_code, fund_name, fund_type, shares, cost_price, "
        "current_value, profit_loss, profit_loss_pct FROM portfolio WHERE user_id=$1",
        user_id,
    )
    return [dict(r) for r in rows]


async def get_recent_news(conn, limit=30):
    """拿到最近新闻（只取有标题的）"""
    rows = await conn.fetch(
        "SELECT id, title, url, source, sentiment_label FROM news "
        "ORDER BY publish_time DESC LIMIT $1",
        limit,
    )
    return [dict(r) for r in rows]


async def get_recent_predictions(conn, limit=20):
    """拿到最近分析师评级"""
    rows = await conn.fetch(
        """SELECT p.post_content, p.predicted_direction, p.confidence,
           b.username, p.post_url
           FROM predictions p LEFT JOIN bloggers b ON p.blogger_id = b.id
           WHERE p.is_prediction = true
           ORDER BY p.post_time DESC LIMIT $1""",
        limit,
    )
    return [dict(r) for r in rows]


# ── Step 1: 持仓 → 行业映射 ──
async def map_portfolio_sectors(portfolio):
    """一次LLM调用，把每只持仓映射到行业/主题关键词"""
    items = [{"code": p["fund_code"], "name": p["fund_name"]} for p in portfolio]
    system = "你是基金投资分析专家。分析以下基金/股票的核心投资方向和关联行业。"
    user = f"""分析以下持仓，为每只返回它覆盖的核心行业/主题（1-3个关键词，用于匹配新闻）。
返回JSON数组，每个元素: code, name, sectors(数组), brief(一句话描述投资方向)

持仓列表:
{json.dumps(items, ensure_ascii=False)}

示例输出:
[{{"code":"512760","name":"半导体ETF","sectors":["半导体","芯片","国产替代"],"brief":"跟踪国证半导体芯片指数，核心是芯片设计+制造产业链"}}]"""

    result = await llm_json(system, user)
    if not isinstance(result, list):
        # 降级：用基金名简单猜
        return [{"code": p["fund_code"], "name": p["fund_name"],
                 "sectors": [p["fund_name"][:4]], "brief": p["fund_name"]} for p in portfolio]
    return result


# ── Step 2: 批量给新闻打标签 ──
async def tag_news_batch(news_batch):
    """10条新闻一批，LLM给每条打标签"""
    items = [{"id": n["id"], "title": n["title"][:80]} for n in news_batch]
    system = "你是财经新闻分析师。快速判断每条新闻影响的行业和方向。"
    user = f"""分析以下新闻，为每条返回JSON:
- id: 新闻ID
- sectors: 影响的行业/主题（1-3个关键词）
- direction: "bullish"(利好) / "bearish"(利空) / "neutral"(中性)
- impact: "high"(重大) / "medium"(中等) / "low"(轻微)
- reason: 10字以内的判断理由

返回JSON数组。

新闻列表:
{json.dumps(items, ensure_ascii=False)}"""

    result = await llm_json(system, user)
    return result if isinstance(result, list) else []


async def tag_all_news(news_list, batch_size=10):
    """分批给所有新闻打标签"""
    tagged = {}
    for i in range(0, len(news_list), batch_size):
        batch = news_list[i:i + batch_size]
        tags = await tag_news_batch(batch)
        for tag in tags:
            if isinstance(tag, dict) and "id" in tag:
                tagged[tag["id"]] = tag
        await asyncio.sleep(1)  # 防限流
    return tagged


# ── Step 3: 按持仓匹配 + 生成建议 ──
async def generate_holding_advice(portfolio, portfolio_sectors, news_list, tagged_news, predictions):
    """一次LLM调用，为每只持仓生成操作建议"""
    # 先做数据准备：每只持仓匹配到的新闻
    holdings_data = []
    for i, p in enumerate(portfolio):
        sectors = portfolio_sectors[i].get("sectors", []) if i < len(portfolio_sectors) else []
        # 找匹配的新闻
        matched_news = []
        for n in news_list:
            tag = tagged_news.get(n["id"], {})
            n_sectors = [s.lower() for s in tag.get("sectors", [])]
            # 如果新闻的行业和持仓的行业有交集
            if any(s.lower() in " ".join(n_sectors) or ns in " ".join([x.lower() for x in sectors])
                   for s in sectors for ns in n_sectors):
                matched_news.append({
                    "title": n["title"][:60],
                    "direction": tag.get("direction", "neutral"),
                    "impact": tag.get("impact", "low"),
                    "reason": tag.get("reason", ""),
                })

        bull = len([m for m in matched_news if m["direction"] == "bullish"])
        bear = len([m for m in matched_news if m["direction"] == "bearish"])

        holdings_data.append({
            "code": p["fund_code"],
            "name": p["fund_name"],
            "sectors": sectors,
            "profit_pct": round(float(p.get("profit_loss_pct") or 0), 2),
            "matched_news_count": len(matched_news),
            "bullish_count": bull,
            "bearish_count": bear,
            "top_news": matched_news[:5],  # 取最重要的5条
        })

    system = "你是基金投资顾问。基于持仓的相关新闻数据，给出简洁可操作的建议。"
    # 预构建分析师摘要，避免f-string中dict格式化冲突
    analyst_summary = json.dumps(
        [{"analyst": p["username"], "direction": p["predicted_direction"], "content": p["post_content"][:50]}
         for p in predictions[:5]],
        ensure_ascii=False,
    )
    user = f"""基于以下持仓数据和相关新闻，为每只持仓生成操作建议。

持仓数据（含匹配到的新闻统计）:
{json.dumps(holdings_data, ensure_ascii=False)}

分析师评级参考:
{analyst_summary}

为每只持仓返回JSON:
- code: 代码
- name: 名称
- action: "加仓" / "减仓" / "持有" / "观望"
- confidence: 建议置信度 0-100
- reason: 50字以内的核心理由
- key_news: 最值得关注的那条新闻标题

返回JSON数组。"""

    result = await llm_json(system, user)
    return result if isinstance(result, list) else []


# ── Step 4: 赛道提醒 ──
async def generate_sector_alerts(tagged_news, portfolio_sectors):
    """从所有新闻标签中找热门赛道，排除已持有的"""
    # 持仓已有的行业
    held_sectors = set()
    for ps in portfolio_sectors:
        for s in ps.get("sectors", []):
            held_sectors.add(s.lower())

    # 统计每个行业的新闻热度
    sector_stats = {}
    for tag in tagged_news.values():
        for s in tag.get("sectors", []):
            key = s.lower()
            if key in held_sectors:
                continue  # 跳过已持有
            if key not in sector_stats:
                sector_stats[key] = {"sector": s, "total": 0, "bullish": 0, "bearish": 0}
            sector_stats[key]["total"] += 1
            if tag.get("direction") == "bullish":
                sector_stats[key]["bullish"] += 1
            elif tag.get("direction") == "bearish":
                sector_stats[key]["bearish"] += 1

    # 热度排名前5
    hot = sorted(sector_stats.values(), key=lambda x: x["total"], reverse=True)[:5]

    if not hot:
        return []

    system = "你是行业研究员。分析当前哪些行业/主题正在升温，给出投资建议。"
    user = f"""以下是近期新闻中出现频率最高的非持仓行业/主题:

{json.dumps(hot, ensure_ascii=False)}

为每个行业返回JSON:
- sector: 行业名
- trend: "升温" / "降温" / "波动"
- action: "关注" / "可小仓位试水" / "建议回避"
- reason: 30字理由
- heat: 热度分 0-100

返回JSON数组，按热度从高到低排列。"""

    result = await llm_json(system, user)
    return result if isinstance(result, list) else []


async def main():
    conn = await asyncpg.connect(DB_URL)

    print("1/5 拉取持仓和数据...")
    portfolio = await get_portfolio(conn, USER_ID)
    news_list = await get_recent_news(conn, 30)
    predictions = await get_recent_predictions(conn, 10)

    if not portfolio:
        print("⚠️ 用户没有持仓，无法分析")
        await conn.close()
        return

    print(f"   持仓 {len(portfolio)} 只, 新闻 {len(news_list)} 条, 分析师评级 {len(predictions)} 条")

    print("2/5 持仓 → 行业映射...")
    portfolio_sectors = await map_portfolio_sectors(portfolio)
    for ps in portfolio_sectors:
        print(f"   {ps.get('name','?')}: {ps.get('sectors',[])}")

    print("3/5 批量给新闻打标签...")
    tagged_news = await tag_all_news(news_list)
    print(f"   已标记 {len(tagged_news)}/{len(news_list)} 条新闻")

    print("4/5 生成持仓操作建议...")
    advice = await generate_holding_advice(portfolio, portfolio_sectors, news_list, tagged_news, predictions)
    for a in advice:
        print(f"   {a.get('name','?')}: {a.get('action','?')} ({a.get('confidence',0)}%)")

    print("5/5 生成赛道提醒...")
    alerts = await generate_sector_alerts(tagged_news, portfolio_sectors)
    for a in alerts:
        print(f"   {a.get('sector','?')}: {a.get('trend','?')} → {a.get('action','?')}")

    # 写入JSON
    result = {
        "generated_at": datetime.now().isoformat(),
        "holdings": advice,
        "sector_alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 输出: {OUTPUT}")

    await conn.close()

    # git push 触发 Vercel 重建
    import subprocess
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        subprocess.run(["git", "add", "frontend/public/data/portfolio-advice.json"],
                       cwd=project_root, check=True, capture_output=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"],
                              cwd=project_root, capture_output=True)
        if diff.returncode != 0:
            subprocess.run(["git", "commit", "-m",
                            f"chore: portfolio advice update ({datetime.now().strftime('%Y-%m-%d %H:%M')})"],
                           cwd=project_root, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "main"],
                           cwd=project_root, check=True, capture_output=True)
            print("✅ Git pushed, Vercel will rebuild")
        else:
            print("⏭️ No changes to push")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git push failed: {e.stderr.decode() if e.stderr else e}")


if __name__ == "__main__":
    asyncio.run(main())
