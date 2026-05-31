"""Telegram Bot 命令处理器 — 绑定账号、查询信号、帮助。"""
import logging
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, DailySignal
from app.services.telegram_bot import bot
from app.services.signal_pusher import format_signal_message

logger = logging.getLogger(__name__)

HELP_TEXT = """
<b>🤖 FundRadar 使用指南</b>

<b>账号绑定</b>
1. 登录网页版，进入「设置」→「Telegram 绑定」
2. 获取绑定码（6位数字）
3. 发送 /bind 绑定码 完成绑定

<b>可用命令</b>
/signal    — 查看今日投资信号
/portfolio — 查看我的持仓和盈亏
/review    — 查看最新信号复盘报告
/status    — 查看账号和订阅状态
/unbind    — 解除 Telegram 绑定
/help      — 显示此帮助

<b>自动推送</b>
绑定后每天收盘后自动推送信号（约16:30）
系统检测到预测连续出错时自动推送复盘报告

<i>⚠️ 信号仅供参考，不构成投资建议</i>
""".strip()


async def handle_update(update: dict, db: AsyncSession) -> None:
    """处理单条 Telegram update。"""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message["chat"]["id"])
    text = message.get("text", "").strip()

    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=1)
    command = parts[0].lower().split("@")[0]  # 去掉 @botname 后缀
    args = parts[1].strip() if len(parts) > 1 else ""

    if command == "/start" or command == "/help":
        await bot.send_message(chat_id, HELP_TEXT)

    elif command == "/bind":
        await handle_bind(chat_id, args, db)

    elif command == "/unbind":
        await handle_unbind(chat_id, db)

    elif command == "/signal":
        await handle_signal(chat_id, db)

    elif command == "/portfolio":
        await handle_portfolio(chat_id, db)

    elif command == "/review":
        await handle_review(chat_id, db)

    elif command == "/status":
        await handle_status(chat_id, db)


async def handle_bind(chat_id: str, code: str, db: AsyncSession) -> None:
    """绑定 Telegram 账号。"""
    if not code or not code.isdigit() or len(code) != 6:
        await bot.send_message(
            chat_id,
            "❌ 请提供正确的6位绑定码\n示例：<code>/bind 123456</code>\n\n"
            "绑定码请在网页版「设置」→「Telegram 绑定」中获取。"
        )
        return

    # 查找匹配的用户
    result = await db.execute(
        select(User).where(User.telegram_bind_code == code)
    )
    user = result.scalar_one_or_none()

    if not user:
        await bot.send_message(chat_id, "❌ 绑定码无效或已过期，请重新在网页版获取。")
        return

    if user.telegram_chat_id and user.telegram_chat_id != chat_id:
        await bot.send_message(chat_id, "❌ 该账号已绑定其他 Telegram，请先解绑。")
        return

    # 绑定
    user.telegram_chat_id = chat_id
    user.telegram_bind_code = None  # 用完即废
    await db.commit()

    plan_label = {"free": "免费版", "monthly": "月度会员", "yearly": "年度会员", "lifetime": "永久会员"}.get(user.plan, user.plan)
    await bot.send_message(
        chat_id,
        f"✅ <b>绑定成功！</b>\n\n"
        f"账号：{user.email}\n"
        f"套餐：{plan_label}\n\n"
        f"每天收盘后将自动推送投资信号。\n"
        f"发送 /signal 可立即查看今日信号。"
    )


async def handle_unbind(chat_id: str, db: AsyncSession) -> None:
    """解除绑定。"""
    result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await bot.send_message(chat_id, "❌ 当前 Telegram 未绑定任何账号。")
        return

    user.telegram_chat_id = None
    await db.commit()
    await bot.send_message(chat_id, "✅ 已解除绑定，将不再收到推送消息。")


async def handle_signal(chat_id: str, db: AsyncSession) -> None:
    """发送今日信号。"""
    # 判断用户是否绑定及套餐
    result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = result.scalar_one_or_none()
    is_premium = False
    if user:
        now = datetime.utcnow()
        is_premium = (
            user.plan != "free"
            and (user.plan == "lifetime" or (user.plan_expires_at and user.plan_expires_at > now))
        )

    # 找今日信号
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(DailySignal).where(DailySignal.signal_date == today)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        await bot.send_message(
            chat_id,
            "⏳ 今日信号还未生成，通常在收盘后（16:30左右）发布。\n请稍后再试。"
        )
        return

    msg = format_signal_message(signal, is_premium=is_premium)
    await bot.send_message(chat_id, msg)


async def handle_status(chat_id: str, db: AsyncSession) -> None:
    """查询账号状态。"""
    result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        await bot.send_message(
            chat_id,
            "❌ 当前 Telegram 未绑定账号。\n发送 /help 查看绑定方法。"
        )
        return

    plan_label = {"free": "免费版", "monthly": "月度会员", "yearly": "年度会员", "lifetime": "永久会员"}.get(user.plan, user.plan)
    expires = ""
    if user.plan not in ("free", "lifetime") and user.plan_expires_at:
        expires = f"\n到期时间：{user.plan_expires_at.strftime('%Y-%m-%d')}"

    await bot.send_message(
        chat_id,
        f"<b>📋 账号状态</b>\n\n"
        f"邮箱：{user.email}\n"
        f"套餐：{plan_label}{expires}\n"
        f"注册时间：{user.created_at.strftime('%Y-%m-%d')}"
    )


def generate_bind_code() -> str:
    """生成6位数字绑定码。"""
    return str(secrets.randbelow(900000) + 100000)


async def handle_portfolio(chat_id: str, db: AsyncSession) -> None:
    """发送用户持仓汇总。"""
    from app.models.models import Portfolio

    result = await db.execute(
        select(User).where(User.telegram_chat_id == chat_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        await bot.send_message(chat_id, "❌ 请先绑定账号，发送 /help 查看方法。")
        return

    items_result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user.id)
    )
    items = items_result.scalars().all()

    if not items:
        await bot.send_message(
            chat_id,
            "📭 你还没有添加持仓。\n\n"
            "可以通过网页版「持仓管理」添加你持有的基金。"
        )
        return

    total_cost = sum(i.cost_total for i in items)
    total_value = sum(i.current_value or i.cost_total for i in items)
    total_pnl = total_value - total_cost
    total_pnl_pct = total_pnl / total_cost * 100 if total_cost > 0 else 0

    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    lines = [
        f"<b>💼 我的持仓</b>",
        f"━━━━━━━━━━━━━━━━",
        f"总成本：¥{total_cost:,.2f}",
        f"当前市值：¥{total_value:,.2f}",
        f"{pnl_emoji} 总盈亏：¥{total_pnl:+,.2f}（{total_pnl_pct:+.2f}%）",
        f"━━━━━━━━━━━━━━━━",
    ]
    for item in items:
        if item.profit_loss_pct is not None:
            pnl_str = f"{item.profit_loss_pct:+.2f}%"
            emoji = "🟢" if item.profit_loss_pct >= 0 else "🔴"
        else:
            pnl_str = "净值待更新"
            emoji = "⚪"
        lines.append(
            f"{emoji} <b>{item.fund_name}</b>（{item.fund_code}）\n"
            f"   份额：{item.shares:,.2f}  成本：{item.cost_price:.4f}\n"
            f"   盈亏：{pnl_str}"
        )

    lines.append(f"━━━━━━━━━━━━━━━━")
    lines.append(f"<i>净值每日17:00更新</i>")
    await bot.send_message(chat_id, "\n".join(lines))


async def handle_review(chat_id: str, db: AsyncSession) -> None:
    """发送最新一条复盘报告。"""
    from app.models.models import SignalReview
    from sqlalchemy import desc

    result = await db.execute(
        select(SignalReview).order_by(desc(SignalReview.reviewed_at)).limit(1)
    )
    review = result.scalar_one_or_none()

    if not review:
        await bot.send_message(
            chat_id,
            "📭 暂无复盘报告。\n\n"
            "系统会在检测到预测连续出错时自动生成复盘，"
            "目前信号表现正常。"
        )
        return

    part1 = (
        f"<b>🔍 最新信号复盘报告</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📌 标的：{review.target_symbol}\n"
        f"⚠️ 触发原因：{review.trigger_reason}\n"
        f"📊 准确率：{review.accuracy_rate:.0%}"
        f"（{review.correct_signals}/{review.total_signals}）\n"
        f"🗓 复盘区间：{review.review_start.strftime('%m-%d')} ~ "
        f"{review.review_end.strftime('%m-%d')}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<b>🔎 问题诊断</b>\n{review.problem_diagnosis}\n\n"
        f"<b>🛠 改进建议</b>\n{review.suggested_adjustments}"
    )
    part2 = (
        f"<b>📚 新手学习要点</b>\n{review.learning_points}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<i>复盘时间：{review.reviewed_at.strftime('%Y-%m-%d %H:%M')}</i>"
    )
    await bot.send_message(chat_id, part1)
    await bot.send_message(chat_id, part2)
