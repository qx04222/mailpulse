"""
Daily Gmail OAuth token health check.
Runs at 06:00 ET. Sends Lark DM to admin when token is failing or
approaching expiration so re-auth happens before hourly_sync breaks.

Token age semantics (personal Gmail + unverified Production app):
  - 0-4 days: silent (healthy)
  - 5-6 days: preemptive warning ("renew today/tomorrow")
  - 7+ days OR refresh fails: urgent alert
"""
import logging
from datetime import date, datetime
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from ..config import settings, load_people

logger = logging.getLogger(__name__)

REFRESH_COMMAND = (
    "cd ~/Desktop/mailpulse/engine && ./scripts/refresh_gmail_token.sh"
)


def _find_admin_lark_id() -> Optional[str]:
    """Same lookup pattern as hourly_sync — person named 'Xin' with lark_user_id."""
    try:
        people = load_people()
    except Exception as e:
        logger.warning(f"[TokenHealth] Could not load people: {e}")
        return None
    for p in people:
        name = p.get("name") or ""
        if "Xin" in name and p.get("lark_user_id"):
            return p["lark_user_id"]
    return None


def _token_age_days() -> Optional[int]:
    """Days since GMAIL_TOKEN_ISSUED_AT. None if unset or unparseable."""
    raw = settings.gmail_token_issued_at
    if not raw:
        return None
    try:
        issued = date.fromisoformat(raw.strip())
    except ValueError:
        logger.warning(f"[TokenHealth] Bad GMAIL_TOKEN_ISSUED_AT value: {raw!r}")
        return None
    return (date.today() - issued).days


def _try_refresh() -> tuple[bool, Optional[str]]:
    """Attempt to refresh the access token. Returns (ok, error_message)."""
    try:
        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        creds.refresh(Request())
        return True, None
    except Exception as e:
        return False, str(e)


def _send_lark(text: str) -> None:
    admin_id = _find_admin_lark_id()
    if not admin_id:
        logger.warning("[TokenHealth] No admin Lark ID found, cannot notify")
        return
    try:
        from ..destinations.lark import send_user_message
        sent = send_user_message(admin_id, text)
        if sent:
            logger.info(f"[TokenHealth] Notified admin (lark_user_id={admin_id})")
        else:
            logger.warning("[TokenHealth] send_user_message returned falsy")
    except Exception as e:
        logger.error(f"[TokenHealth] Failed to send Lark DM: {e}")


async def check_gmail_token_health() -> None:
    """Daily token health check. Async to fit AsyncIOScheduler."""
    logger.info("[TokenHealth] Running daily Gmail token health check...")

    age = _token_age_days()
    ok, err = _try_refresh()

    age_str = f"{age} 天" if age is not None else "未知（GMAIL_TOKEN_ISSUED_AT 未设置）"
    logger.info(f"[TokenHealth] refresh_ok={ok}, age={age_str}")

    # Failure path — token already dead, urgent
    if not ok:
        msg = (
            "🚨 Gmail Token 已失效\n\n"
            f"Token 年龄: {age_str}\n"
            f"错误: {err}\n\n"
            "邮件同步已停止，请尽快重新授权：\n"
            f"```\n{REFRESH_COMMAND}\n```\n"
            "脚本会自动完成 OAuth → 推到 Railway → 重新部署。"
        )
        _send_lark(msg)
        return

    # Success path — check age for preemptive warning
    if age is None:
        # Token works but we don't know its age — set baseline reminder
        logger.info("[TokenHealth] Token healthy but issued_at unknown")
        return

    if age >= 7:
        # Past expected lifetime; alert urgently even though refresh worked
        msg = (
            "⚠️ Gmail Token 已超过 7 天\n\n"
            f"Token 年龄: {age} 天（仍可用，但随时可能失效）\n\n"
            "建议立刻刷新：\n"
            f"```\n{REFRESH_COMMAND}\n```"
        )
        _send_lark(msg)
        return

    if age >= 5:
        msg = (
            "🔔 Gmail Token 即将到期\n\n"
            f"Token 年龄: {age} 天（约 {7 - age} 天后失效）\n\n"
            "有空时跑一下：\n"
            f"```\n{REFRESH_COMMAND}\n```"
        )
        _send_lark(msg)
        return

    # age < 5: silent, all good
    logger.info(f"[TokenHealth] Healthy ({age} days old), no alert")
