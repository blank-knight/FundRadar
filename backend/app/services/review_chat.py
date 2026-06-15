"""复盘对话服务 — 调用 LLM 进行投资教练式对话。

功能：
- 拉取用户持仓快照作为上下文
- 维护对话历史（最近 N 轮），让 LLM 有记忆
- 投资教练人设：分析操作逻辑、指出优缺点、帮助新手成长
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_text
from app.models.models import Portfolio, TradeReviewMessage

logger = logging.getLogger(__name__)

# 对话历史窗口：最多保留最近 10 轮（20 条消息），防止 token 爆炸
MAX_HISTORY_MESSAGES = 20

SYSTEM_PROMPT = """你是一个耐心的投资教练，正在和用户进行一对一的投资复盘对话。

你的角色：
- 帮助用户分析操作逻辑，指出做对和可以改进的地方
- 用通俗语言解释投资概念，适合新手理解
- 不直接给出买卖建议，而是引导用户思考决策逻辑
- 关注用户的心理状态（追涨杀跌、恐惧贪婪等），温和指出
- 每次回复控制在 300 字以内，用 **粗体** 标记要点
- 如果用户提供了持仓信息，可以结合具体持仓进行分析

回复格式要求：
- 用中文，语气亲切但不啰嗦
- 可以用 emoji 适度点缀（✅ 🤔 📌 💡 等）
- 用 **粗体** 标记关键要点
- 如果用户问的问题超出投资范围，温和地引导回投资话题"""


async def _get_portfolio_summary(db: AsyncSession, user_id: int) -> str:
    """拉取用户持仓快照，作为 LLM 上下文。"""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id)
    )
    items = result.scalars().all()
    if not items:
        return "（用户暂无持仓记录）"

    lines = []
    total_cost = 0.0
    total_value = 0.0
    for item in items:
        value = item.current_value or item.cost_total
        pnl = item.profit_loss or 0.0
        pnl_pct = item.profit_loss_pct or 0.0
        total_cost += item.cost_total
        total_value += value
        pnl_str = f"盈亏 {pnl:+.0f}元（{pnl_pct:+.1f}%）" if item.current_price else "未更新行情"
        lines.append(
            f"- {item.fund_name}（{item.fund_code}）："
            f"持有 {item.shares}份，成本 {item.cost_price}，{pnl_str}"
        )

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    lines.append(f"\n汇总：总投入 {total_cost:.0f}元，总市值 {total_value:.0f}元，"
                 f"整体盈亏 {total_pnl:+.0f}元（{total_pnl_pct:+.1f}%）")

    return "\n".join(lines)


async def chat_with_review(
    db: AsyncSession,
    review_id: int,
    user_message: str,
    user_id: int,
) -> str:
    """
    核心对话函数：
    1. 拉取持仓上下文
    2. 拉取最近 N 条对话历史
    3. 构建多轮对话请求
    4. 调用 LLM 返回回复
    """
    # 持仓上下文
    portfolio_summary = await _get_portfolio_summary(db, user_id)

    # 对话历史
    result = await db.execute(
        select(TradeReviewMessage)
        .where(TradeReviewMessage.review_id == review_id)
        .order_by(TradeReviewMessage.id.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history_records = list(reversed(result.scalars().all()))

    # 构建对话上下文（历史 + 当前消息）
    # 由于 llm_text 只接受单轮 system+user，我们把历史拼进 system prompt
    history_text = ""
    if history_records:
        history_lines = []
        for msg in history_records:
            speaker = "用户" if msg.role == "user" else "教练"
            history_lines.append(f"{speaker}：{msg.content}")
        history_text = "\n\n【之前的对话记录】\n" + "\n".join(history_lines)

    system = f"""{SYSTEM_PROMPT}

【用户当前持仓】
{portfolio_summary}{history_text}"""

    user = f"用户：{user_message}\n\n教练："

    reply = await llm_text(system, user)
    if not reply:
        reply = (
            "抱歉，我暂时无法响应，请稍后再试。\n\n"
            "如果问题持续，可以检查网络连接或联系管理员。"
        )

    return reply
