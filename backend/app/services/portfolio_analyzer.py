"""持仓分析服务 — 结合新闻情绪 + 博主共识 + 持仓盈亏，给出操作建议。

建议类型：
  hold        持有  — 当前无明显信号，继续持有
  buy_more    加仓  — 信号偏多且当前亏损/微盈，可考虑摊低成本
  take_profit 止盈  — 盈利较高且信号转弱，考虑落袋
  stop_loss   止损  — 亏损较深且信号偏空，控制风险
  watch       观望  — 信号混乱，先观望不操作
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json
from app.models.models import DailySignal, Portfolio

logger = logging.getLogger(__name__)

ACTION_LABELS = {
    "hold": "持有",
    "buy_more": "加仓",
    "take_profit": "止盈",
    "stop_loss": "止损",
    "watch": "观望",
}

SYSTEM_PROMPT = """你是一位专业的基金投资顾问，同时也是耐心的新手教师。
你的任务是根据用户的持仓情况和市场信号，给出清晰的操作建议，并用通俗易懂的语言解释原因。

【重要】只输出一个 JSON 对象，不要任何其他文字、标题、表格或 markdown：
{"action": "hold|buy_more|take_profit|stop_loss|watch", "reasoning": "200字以内的建议理由"}

注意：reasoning 字段里不要使用任何引号（包括中文引号""和英文引号"），用【】或『』代替强调。

新手小课堂要求（写在 reasoning 里）：
- 解释本次建议涉及的1-2个基金/投资概念
- 语言简单，避免专业术语堆砌
- 结尾可以给一句鼓励的话"""


async def _fetch_recent_signal(fund_code: str, db: AsyncSession) -> dict | None:
    """拉取最近3天内该标的的 DailySignal。"""
    cutoff = datetime.utcnow() - timedelta(days=3)
    result = await db.execute(
        select(DailySignal)
        .where(
            DailySignal.target_symbol == fund_code,
            DailySignal.signal_date >= cutoff,
        )
        .order_by(desc(DailySignal.signal_date))
        .limit(1)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        return None
    return {
        "signal_date": signal.signal_date.strftime("%Y-%m-%d"),
        "final_signal": signal.final_signal,
        "confidence": signal.confidence,
        "blogger_consensus_score": signal.blogger_consensus_score,
        "news_sentiment_score": signal.news_sentiment_score,
        "reasoning": signal.reasoning,
    }


def _rule_based_hint(pnl_pct: float, signal: dict | None) -> str:
    """在 LLM 调用失败时，用简单规则给出兜底建议。"""
    if signal is None:
        direction = "neutral"
        confidence = 0.5
    else:
        direction = signal["final_signal"]
        confidence = signal["confidence"]

    if pnl_pct <= -10 and direction in ("bearish", "neutral"):
        return "stop_loss"
    if pnl_pct >= 15 and direction in ("bearish", "neutral"):
        return "take_profit"
    if pnl_pct <= -5 and direction == "bullish" and confidence >= 0.6:
        return "buy_more"
    if direction == "bullish" and confidence >= 0.7:
        return "hold"
    return "watch"


async def analyze_portfolio_item(item: Portfolio, db: AsyncSession) -> dict:
    """核心分析函数，返回 {action, action_label, reasoning, raw}。"""
    pnl_pct = item.profit_loss_pct or 0.0
    current_price = item.current_price or item.cost_price

    # 拉取市场信号
    signal = await _fetch_recent_signal(item.fund_code, db)

    # 构建 LLM 用户消息
    signal_text = (
        f"最新市场信号（{signal['signal_date']}）：\n"
        f"  方向={signal['final_signal']}，置信度={signal['confidence']:.0%}\n"
        f"  博主共识={signal['blogger_consensus_score']:.2f}，新闻情绪={signal['news_sentiment_score']:.2f}\n"
        f"  信号摘要：{signal['reasoning'][:200]}"
        if signal else "暂无近期市场信号数据。"
    )

    user_msg = f"""用户持仓信息：
基金代码：{item.fund_code}
基金名称：{item.fund_name}
类型：{item.fund_type}
持有份额：{item.shares}
成本价：{item.cost_price}
当前净值：{current_price}
总成本：{item.cost_total}
当前市值：{item.current_value or '未知'}
盈亏金额：{item.profit_loss or '未知'}
盈亏比例：{pnl_pct:.2f}%

{signal_text}

请根据以上信息给出操作建议。"""

    raw = await llm_json(SYSTEM_PROMPT, user_msg, retries=2)

    if raw and isinstance(raw, dict) and "action" in raw:
        action = raw["action"]
        if action not in ACTION_LABELS:
            action = "watch"
        return {
            "action": action,
            "action_label": ACTION_LABELS[action],
            "reasoning": raw.get("reasoning", "LLM 未返回理由。"),
            "raw": raw,
        }

    # LLM 失败 → 规则兜底
    logger.warning(f"LLM analysis failed for {item.fund_code}, using rule-based fallback")
    action = _rule_based_hint(pnl_pct, signal)
    fallback_reasoning = (
        f"【系统自动判断】当前盈亏 {pnl_pct:.1f}%，"
        f"市场信号{'偏' + signal['final_signal'] if signal else '未知'}，"
        f"建议操作：{ACTION_LABELS[action]}。\n\n"
        "【新手小课堂】AI 分析暂时不可用，以上为规则判断，仅供参考。"
        "投资有风险，入市需谨慎，建议结合自身情况决策。"
    )
    return {
        "action": action,
        "action_label": ACTION_LABELS[action],
        "reasoning": fallback_reasoning,
        "raw": None,
    }

