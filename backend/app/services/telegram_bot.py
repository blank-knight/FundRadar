"""Telegram Bot 推送服务 — 发送每日信号、绑定用户、处理命令。"""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base = f"https://api.telegram.org/bot{self.token}"

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> bool:
        """发送消息，返回是否成功。"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": disable_web_page_preview,
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram send failed: {data.get('description')}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Telegram send error to {chat_id}: {e}")
            return False

    async def get_updates(self, offset: int = 0, timeout: int = 10) -> list[dict]:
        """拉取新消息（长轮询）。"""
        try:
            async with httpx.AsyncClient(timeout=timeout + 5) as client:
                resp = await client.get(
                    f"{self.base}/getUpdates",
                    params={"offset": offset, "timeout": timeout},
                )
                data = resp.json()
                return data.get("result", []) if data.get("ok") else []
        except Exception as e:
            logger.error(f"Telegram getUpdates error: {e}")
            return []

    async def set_webhook(self, webhook_url: str) -> bool:
        """设置 Webhook（生产环境用）。"""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base}/setWebhook",
                    json={"url": webhook_url},
                )
                return resp.json().get("ok", False)
        except Exception as e:
            logger.error(f"Set webhook error: {e}")
            return False


# 单例
bot = TelegramBot()
