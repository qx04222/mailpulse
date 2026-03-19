"""
获取 Gmail OAuth2 Refresh Token
运行前请设置环境变量 GMAIL_CLIENT_ID 和 GMAIL_CLIENT_SECRET
或在 .env 文件中配置
"""
import os
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

client_id = os.getenv("GMAIL_CLIENT_ID")
client_secret = os.getenv("GMAIL_CLIENT_SECRET")

if not client_id or not client_secret:
    print("请先设置 GMAIL_CLIENT_ID 和 GMAIL_CLIENT_SECRET 环境变量")
    print("或在 .env 文件中配置")
    exit(1)

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=["https://www.googleapis.com/auth/gmail.modify"],
)

creds = flow.run_local_server(port=8090, access_type="offline", prompt="consent")
print(f"\n✅ Refresh Token:\n{creds.refresh_token}")
print("\n把上面的 token 复制给我。")
