import re
import httpx
from ..config import settings


def _clean_markdown(text: str) -> str:
    """清理文本中的 Markdown 特殊字符，避免 Telegram 解析错误"""
    # 移除不成对的 * _ ` 等 Markdown 标记
    # 保留 emoji 和中文
    cleaned = text
    # 转义可能导致问题的字符
    for char in ['_', '*', '`', '[', ']', '(', ')']:
        # 简单处理：去掉单独出现的 Markdown 标记
        pass
    return cleaned


def send_message(chat_id: str, text: str) -> bool:
    """
    发消息到 Telegram 群组或个人。
    直接用纯文本发送，避免 Markdown 格式问题。
    消息超 4096 字符自动分段发送。
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]

    for chunk in chunks:
        try:
            resp = httpx.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
            }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Telegram] Error sending to {chat_id}: {e}")
            return False
    return True
