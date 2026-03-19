"""
运行此脚本获取 Telegram chat_id：
1. 在 Telegram 搜索 @BotFather → /newbot → 获取 bot token
2. 把 bot 加入各公司群，并发一条消息（任何内容）
3. python scripts/setup_telegram.py
会打印出所有群的 chat_id，填入 .env 即可
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")

resp = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates")
updates = resp.json().get("result", [])

seen = set()
for update in updates:
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    chat_title = chat.get("title") or chat.get("username") or "private"
    if chat_id and chat_id not in seen:
        seen.add(chat_id)
        print(f"{chat_title}: {chat_id}")
