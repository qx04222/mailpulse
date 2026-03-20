import httpx
from ..config import settings


def send_message(chat_id: str, text: str) -> bool:
    """
    发消息到 Telegram 群组或个人。
    chat_id: 群组为负数字符串（如 "-1001234567890"），个人为正数字符串。
    支持 Markdown 格式（*粗体* `代码` _斜体_）。
    消息超 4096 字符自动分段发送。
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    chunks = [text[i:i+4096] for i in range(0, len(text), 4096)]

    for chunk in chunks:
        try:
            # 先尝试 Markdown 格式
            resp = httpx.post(url, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            }, timeout=30)
            if resp.status_code == 400:
                # Markdown 解析失败，去掉格式重试
                resp = httpx.post(url, json={
                    "chat_id": chat_id,
                    "text": chunk,
                }, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Telegram] Error sending to {chat_id}: {e}")
            return False
    return True
