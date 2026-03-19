import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, field

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import settings, load_companies


@dataclass
class RawItem:
    id: str
    source_label: str
    subject: str
    body: str
    sender: str
    recipients: list[str]              # To + CC 解析出的所有收件人邮箱
    received_at: datetime
    metadata: dict = field(default_factory=dict)


class GmailSource:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        creds.refresh(Request())
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch(
        self,
        label: str,
        lookback_days: int = 3,
        include_trash: bool = True,
        include_spam: bool = True,
        max_results: int = 100,
    ) -> list[RawItem]:
        service = self._get_service()
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        after_unix = int(cutoff.timestamp())
        items = []

        queries = [(f"label:{label} after:{after_unix}", "inbox", False)]
        if include_trash:
            queries.append((f"label:{label} in:trash after:{after_unix}", "trash", True))
        if include_spam:
            queries.append((f"label:{label} in:spam after:{after_unix}", "spam", True))

        for query, bucket, include_spam_trash in queries:
            result = service.users().messages().list(
                userId="me", q=query,
                maxResults=max_results,
                includeSpamTrash=include_spam_trash,
            ).execute()
            for msg_ref in result.get("messages", []):
                try:
                    msg = service.users().messages().get(
                        userId="me", id=msg_ref["id"], format="full",
                    ).execute()
                    item = self._parse(msg, label, bucket)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"[Gmail] Error {msg_ref['id']}: {e}")
        return items

    def fetch_personal(self, lookback_days: int = 3) -> list[RawItem]:
        service = self._get_service()
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        after_unix = int(cutoff.timestamp())
        companies = load_companies()
        exclude = " ".join(f"-label:{c['gmail_label']}" for c in companies)
        query = f"in:inbox {exclude} after:{after_unix}"
        result = service.users().messages().list(
            userId="me", q=query, maxResults=50
        ).execute()
        items = []
        for msg_ref in result.get("messages", []):
            try:
                msg = service.users().messages().get(
                    userId="me", id=msg_ref["id"], format="full"
                ).execute()
                item = self._parse(msg, "personal", "inbox")
                if item:
                    items.append(item)
            except Exception as e:
                print(f"[Gmail] Error {msg_ref['id']}: {e}")
        return items

    def _parse(self, msg: dict, label: str, bucket: str) -> Optional[RawItem]:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(无主题)")
        sender = headers.get("From", "unknown")
        date_str = headers.get("Date", "")

        # 解析收件人（To + CC）
        recipients = []
        for field_name in ["To", "Cc"]:
            val = headers.get(field_name, "")
            if val:
                emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', val)
                recipients.extend([e.lower() for e in emails])

        try:
            from email.utils import parsedate_to_datetime
            received_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
        except Exception:
            received_at = datetime.now(timezone.utc)

        body = self._extract_body(msg["payload"])
        return RawItem(
            id=msg["id"],
            source_label=label,
            subject=subject,
            body=body[:3000],
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            metadata={
                "bucket": bucket,
                "thread_id": msg.get("threadId"),
            },
        )

    def get_label_id(self, label_name: str) -> Optional[str]:
        """通过标签名查找 Gmail label ID，结果缓存"""
        if not hasattr(self, "_label_cache"):
            self._label_cache = {}
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        service = self._get_service()
        result = service.users().labels().list(userId="me").execute()
        for label in result.get("labels", []):
            self._label_cache[label["name"]] = label["id"]
        return self._label_cache.get(label_name)

    def apply_label(self, message_id: str, label_id: str):
        """给邮件添加标签"""
        service = self._get_service()
        service.users().messages().modify(
            userId="me", id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()

    def _extract_body(self, payload: dict) -> str:
        if "parts" in payload:
            for part in payload["parts"]:
                body = self._extract_body(part)
                if body:
                    return body
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        if payload.get("mimeType") == "text/html":
            data = payload.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                return re.sub(r"<[^>]+>", "", html)
        return ""
