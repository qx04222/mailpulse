"""
Lark (飞书国际版) API client.
Handles: authentication, message sending, file upload, chat list.
Uses tenant_access_token for bot-level access.
"""
import time
from typing import Optional, Dict, Any, List

import httpx

from ..config import settings


# Token cache
_token_cache: Dict[str, Any] = {
    "token": "",
    "expires_at": 0,
}

BASE_URL = "https://open.larksuite.com"


def _get_base_url() -> str:
    """Return the configured Lark API base URL."""
    return getattr(settings, "lark_base_url", BASE_URL).rstrip("/")


def _get_tenant_access_token() -> str:
    """
    Obtain tenant_access_token via app_id + app_secret.
    Caches the token and refreshes 5 minutes before expiry.
    """
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 300:
        return _token_cache["token"]

    url = f"{_get_base_url()}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": settings.lark_app_id,
        "app_secret": settings.lark_app_secret,
    }

    resp = httpx.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 0:
        raise RuntimeError(f"[Lark] Token error: {data.get('msg', 'unknown')}")

    token = data["tenant_access_token"]
    expire = data.get("expire", 7200)  # default 2 hours

    _token_cache["token"] = token
    _token_cache["expires_at"] = now + expire

    print(f"[Lark] Token refreshed, expires in {expire}s")
    return token


def _headers() -> Dict[str, str]:
    """Build authorization headers."""
    return {
        "Authorization": f"Bearer {_get_tenant_access_token()}",
        "Content-Type": "application/json",
    }


def _api_call(
    method: str,
    path: str,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None,
    retries: int = 2,
) -> Dict[str, Any]:
    """
    Generic Lark API call with retry logic.
    Retries on 5xx or token expiry (code 99991663).
    """
    url = f"{_get_base_url()}{path}"

    for attempt in range(retries + 1):
        try:
            resp = httpx.request(
                method,
                url,
                headers=_headers(),
                json=json_data,
                params=params,
                timeout=30,
            )
            data = resp.json()

            # Token expired — clear cache and retry
            if data.get("code") == 99991663:
                _token_cache["token"] = ""
                _token_cache["expires_at"] = 0
                if attempt < retries:
                    continue
                raise RuntimeError(f"[Lark] Token expired after {retries} retries")

            if data.get("code") != 0:
                msg = data.get("msg", "unknown error")
                if attempt < retries and resp.status_code >= 500:
                    time.sleep(1)
                    continue
                raise RuntimeError(f"[Lark] API error ({path}): code={data.get('code')} msg={msg}")

            return data

        except httpx.HTTPStatusError as e:
            if attempt < retries and e.response.status_code >= 500:
                time.sleep(1)
                continue
            raise
        except httpx.RequestError as e:
            if attempt < retries:
                time.sleep(1)
                continue
            raise

    return {}


# ══════════════════════════════════════════════════════════════
# Message sending
# ══════════════════════════════════════════════════════════════

def send_user_message(user_id: str, text: str) -> bool:
    """Send a text message to a Lark user (DM). Accepts open_id."""
    try:
        import json as json_mod
        _api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=open_id",
            json_data={
                "receive_id": user_id,
                "msg_type": "text",
                "content": json_mod.dumps({"text": text}),
            },
        )
        return True
    except Exception as e:
        print(f"[Lark] Error sending DM to {user_id}: {e}")
        return False


def send_text_message(chat_id: str, text: str) -> bool:
    """
    Send a text message to a Lark group chat.
    Returns True on success.
    """
    try:
        import json as json_mod
        _api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=chat_id",
            json_data={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json_mod.dumps({"text": text}),
            },
        )
        return True
    except Exception as e:
        print(f"[Lark] Error sending text to {chat_id}: {e}")
        return False


def send_card_message(chat_id: str, card: Dict[str, Any]) -> Optional[str]:
    """
    Send an interactive card message to a Lark group chat.
    Returns the message_id on success, None on failure.
    """
    try:
        import json as json_mod
        data = _api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=chat_id",
            json_data={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json_mod.dumps(card),
            },
        )
        return data.get("data", {}).get("message_id")
    except Exception as e:
        print(f"[Lark] Error sending card to {chat_id}: {e}")
        return None


def send_user_card(user_id: str, card: Dict[str, Any]) -> Optional[str]:
    """
    Send an interactive card message to a Lark user (DM).
    Returns the message_id on success, None on failure.
    """
    try:
        import json as json_mod
        data = _api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=open_id",
            json_data={
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json_mod.dumps(card),
            },
        )
        return data.get("data", {}).get("message_id")
    except Exception as e:
        print(f"[Lark] Error sending card DM to {user_id}: {e}")
        return None


def upload_file(
    file_bytes: bytes,
    filename: str,
    file_type: str = "stream",
) -> Optional[str]:
    """
    Upload a file to Lark and return the file_key.
    file_type: "opus" | "mp4" | "pdf" | "doc" | "xls" | "ppt" | "stream"
    """
    try:
        url = f"{_get_base_url()}/open-apis/im/v1/files"
        token = _get_tenant_access_token()

        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": file_type, "file_name": filename},
            files={"file": (filename, file_bytes)},
            timeout=60,
        )
        data = resp.json()

        if data.get("code") != 0:
            print(f"[Lark] File upload error: {data.get('msg')}")
            return None

        file_key = data.get("data", {}).get("file_key")
        print(f"[Lark] File uploaded: {filename} -> {file_key}")
        return file_key
    except Exception as e:
        print(f"[Lark] File upload error: {e}")
        return None


def send_file_message(chat_id: str, file_key: str) -> bool:
    """Send a file message using an already-uploaded file_key."""
    try:
        import json as json_mod
        _api_call(
            "POST",
            "/open-apis/im/v1/messages?receive_id_type=chat_id",
            json_data={
                "receive_id": chat_id,
                "msg_type": "file",
                "content": json_mod.dumps({"file_key": file_key}),
            },
        )
        return True
    except Exception as e:
        print(f"[Lark] Error sending file to {chat_id}: {e}")
        return False


def send_document(chat_id: str, file_bytes: bytes, filename: str) -> bool:
    """
    Upload a file then send it as a message. Convenience wrapper.
    Auto-detects file_type from filename extension.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    type_map = {
        "pdf": "pdf",
        "doc": "doc",
        "docx": "doc",
        "xls": "xls",
        "xlsx": "xls",
        "ppt": "ppt",
        "pptx": "ppt",
        "mp4": "mp4",
        "opus": "opus",
    }
    file_type = type_map.get(ext, "stream")
    print(f"[Lark] Uploading {filename} ({len(file_bytes)} bytes, type={file_type})")

    file_key = upload_file(file_bytes, filename, file_type=file_type)
    if not file_key:
        print(f"[Lark] File upload failed for {filename}, cannot send document")
        return False
    return send_file_message(chat_id, file_key)


# ══════════════════════════════════════════════════════════════
# Chat list
# ══════════════════════════════════════════════════════════════

def get_chat_list() -> List[Dict[str, Any]]:
    """
    Get the list of group chats the bot is in.
    Returns list of {chat_id, name, description, ...}.
    """
    try:
        data = _api_call("GET", "/open-apis/im/v1/chats", params={"page_size": 100})
        return data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"[Lark] Error getting chat list: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# Connection test
# ══════════════════════════════════════════════════════════════

def test_connection() -> Dict[str, Any]:
    """
    Test the Lark API connection. Returns status info.
    """
    try:
        token = _get_tenant_access_token()
        chats = get_chat_list()
        return {
            "connected": True,
            "token_preview": token[:10] + "...",
            "chat_count": len(chats),
            "chats": [{"chat_id": c.get("chat_id"), "name": c.get("name")} for c in chats[:20]],
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }
