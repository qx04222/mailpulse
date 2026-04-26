"""
One-command Gmail token refresh.
- Runs OAuth flow → new refresh token
- Pushes GMAIL_REFRESH_TOKEN + GMAIL_TOKEN_ISSUED_AT to Railway via `railway` CLI
- Updates local .env to keep dev in sync
- Sends Lark confirmation DM to admin

Prereq (one-time):
  brew install railway
  railway login
  cd /Users/xin/Desktop/mailpulse/engine && railway link  # pick the engine project

Usage:
  ./scripts/refresh_gmail_token.sh
  # or directly:
  python scripts/refresh_gmail_token.py
"""
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

ENV_PATH = Path(__file__).parent.parent / ".env"


def run_oauth_flow() -> str:
    """Open browser, return new refresh token."""
    load_dotenv()
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("❌ GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET missing in .env")

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
    if not creds.refresh_token:
        sys.exit("❌ No refresh_token in response — Google may have returned only an access token")
    return creds.refresh_token


def push_to_railway(token: str, issued_at: str) -> None:
    """Set both vars via railway CLI. Triggers automatic redeploy."""
    print("\n→ Pushing to Railway...")
    for key, value in [("GMAIL_REFRESH_TOKEN", token), ("GMAIL_TOKEN_ISSUED_AT", issued_at)]:
        result = subprocess.run(
            ["railway", "variables", "--set", f"{key}={value}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(f"❌ railway variables --set failed for {key}")
        print(f"  ✓ {key} set on Railway")


def update_local_env(token: str, issued_at: str) -> None:
    """Rewrite the two keys in local .env (in place)."""
    if not ENV_PATH.exists():
        print(f"⚠️  {ENV_PATH} not found, skipping local update")
        return
    text = ENV_PATH.read_text()
    text = _upsert_env_var(text, "GMAIL_REFRESH_TOKEN", token)
    text = _upsert_env_var(text, "GMAIL_TOKEN_ISSUED_AT", issued_at)
    ENV_PATH.write_text(text)
    print(f"  ✓ Local {ENV_PATH.name} updated")


def _upsert_env_var(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{key}={value}", text)
    if not text.endswith("\n"):
        text += "\n"
    return text + f"{key}={value}\n"


def send_lark_confirmation(issued_at: str) -> None:
    """Best-effort confirmation DM. Reuses existing Lark helper."""
    print("\n→ Sending Lark confirmation...")
    try:
        # Lazy import — avoid pulling settings if user just wants OAuth
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.bot.token_health_check import _find_admin_lark_id
        from src.destinations.lark import send_user_message

        admin_id = _find_admin_lark_id()
        if not admin_id:
            print("  ⚠️  No admin Lark ID found, skipping")
            return
        msg = (
            "✅ Gmail Token 已刷新\n\n"
            f"新 token 已推送到 Railway，签发日期 {issued_at}。\n"
            "Railway 将自动重新部署，下一个整点 hourly_sync 即可恢复。"
        )
        if send_user_message(admin_id, msg):
            print(f"  ✓ Confirmation sent to admin")
        else:
            print(f"  ⚠️  send_user_message returned falsy")
    except Exception as e:
        print(f"  ⚠️  Lark confirmation failed (non-fatal): {e}")


def main() -> None:
    print("🔐 Refreshing Gmail OAuth token...\n")
    token = run_oauth_flow()
    issued_at = date.today().isoformat()
    print(f"\n✅ Got new refresh token (issued {issued_at})")

    push_to_railway(token, issued_at)
    update_local_env(token, issued_at)
    send_lark_confirmation(issued_at)

    print("\n🎉 Done. Railway will redeploy automatically (1-2 min).")


if __name__ == "__main__":
    main()
