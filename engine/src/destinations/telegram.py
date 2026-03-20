import httpx
from io import BytesIO
from ..config import settings


def send_message(chat_id: str, text: str) -> bool:
    """
    发消息到 Telegram 群组或个人。
    纯文本发送，避免 Markdown 格式问题。
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


def send_document(chat_id: str, file_bytes: bytes, filename: str, caption: str = "") -> bool:
    """
    发送文件到 Telegram 群组或个人。
    用于直接发送 DOCX/PDF 报告作为附件。
    """
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument"
    try:
        files = {"document": (filename, BytesIO(file_bytes))}
        data = {"chat_id": chat_id}
        if caption:
            # caption 限制 1024 字符
            data["caption"] = caption[:1024]
        resp = httpx.post(url, data=data, files=files, timeout=60)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] Error sending document to {chat_id}: {e}")
        return False
