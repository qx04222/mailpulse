"""
Tests for engine/src/sources/gmail_source.py
Covers: _parse(), _extract_body(), recipient extraction, date parsing, dedup.
"""
import base64
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from engine.src.sources.gmail_source import GmailSource, RawItem


def _make_gmail_message(
    msg_id: str = "msg_001",
    thread_id: str = "thread_001",
    subject: str = "测试邮件",
    from_addr: str = "sender@example.com",
    to_addr: str = "xqi@arcview.ca",
    cc_addr: str = "",
    date_str: str = "Mon, 15 Mar 2026 10:30:00 +0000",
    body_text: str = "这是邮件正文",
    body_html: str = "",
    multipart: bool = False,
) -> dict:
    """Build a realistic Gmail API message dict."""
    headers = [
        {"name": "Subject", "value": subject},
        {"name": "From", "value": from_addr},
        {"name": "To", "value": to_addr},
        {"name": "Date", "value": date_str},
    ]
    if cc_addr:
        headers.append({"name": "Cc", "value": cc_addr})

    text_data = base64.urlsafe_b64encode(body_text.encode()).decode().rstrip("=")

    if multipart or body_html:
        html_data = base64.urlsafe_b64encode(
            (body_html or f"<p>{body_text}</p>").encode()
        ).decode().rstrip("=")
        payload = {
            "mimeType": "multipart/alternative",
            "headers": headers,
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": text_data},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": html_data},
                },
            ],
        }
    else:
        payload = {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": text_data},
        }

    return {
        "id": msg_id,
        "threadId": thread_id,
        "payload": payload,
    }


class TestGmailParse:
    """Tests for GmailSource._parse()"""

    def setup_method(self):
        self.source = GmailSource()

    def test_parse_normal_email(self):
        msg = _make_gmail_message(
            subject="关于报价的确认",
            from_addr="Wang Wei <wangwei@client.com>",
            to_addr="xqi@arcview.ca",
            body_text="请确认附件中的报价单。",
        )
        item = self.source._parse(msg, "Arcview", "inbox")
        assert item is not None
        assert item.id == "msg_001"
        assert item.source_label == "Arcview"
        assert item.subject == "关于报价的确认"
        assert item.sender == "Wang Wei <wangwei@client.com>"
        assert "请确认附件中的报价单" in item.body
        assert item.metadata["bucket"] == "inbox"
        assert item.metadata["thread_id"] == "thread_001"

    def test_parse_recipients_to_and_cc(self):
        msg = _make_gmail_message(
            to_addr="Xin <xqi@arcview.ca>, Other <other@arcview.ca>",
            cc_addr="Nahrain <nahrain@arcview.ca>, manager@client.com",
        )
        item = self.source._parse(msg, "Arcview", "inbox")
        assert "xqi@arcview.ca" in item.recipients
        assert "other@arcview.ca" in item.recipients
        assert "nahrain@arcview.ca" in item.recipients
        assert "manager@client.com" in item.recipients
        assert len(item.recipients) == 4

    def test_parse_recipients_lowercased(self):
        msg = _make_gmail_message(to_addr="XQI@ArcView.CA")
        item = self.source._parse(msg, "Arcview", "inbox")
        assert "xqi@arcview.ca" in item.recipients

    def test_extract_body_plain_text(self):
        msg = _make_gmail_message(body_text="纯文本正文内容")
        item = self.source._parse(msg, "test", "inbox")
        assert "纯文本正文内容" in item.body

    def test_extract_body_html_strips_tags(self):
        msg = _make_gmail_message(
            body_text="",
            body_html="<p>Hello <b>World</b></p>",
            multipart=False,
        )
        # For HTML-only, build a message with only HTML part
        html_data = base64.urlsafe_b64encode(b"<p>Hello <b>World</b></p>").decode().rstrip("=")
        msg["payload"] = {
            "mimeType": "text/html",
            "headers": msg["payload"]["headers"],
            "body": {"data": html_data},
        }
        item = self.source._parse(msg, "test", "inbox")
        assert "Hello" in item.body
        assert "World" in item.body
        assert "<p>" not in item.body
        assert "<b>" not in item.body

    def test_extract_body_multipart_prefers_plain(self):
        msg = _make_gmail_message(
            body_text="纯文本版本",
            body_html="<p>HTML版本</p>",
            multipart=True,
        )
        item = self.source._parse(msg, "test", "inbox")
        # _extract_body recurses parts and returns first non-empty; text/plain comes first
        assert "纯文本版本" in item.body

    def test_date_parsing_rfc2822(self):
        msg = _make_gmail_message(date_str="Sat, 15 Mar 2026 18:30:00 +0800")
        item = self.source._parse(msg, "test", "inbox")
        assert item.received_at.year == 2026
        assert item.received_at.month == 3
        assert item.received_at.day == 15

    def test_date_parsing_fallback_on_invalid(self):
        msg = _make_gmail_message(date_str="not-a-date")
        item = self.source._parse(msg, "test", "inbox")
        # Should fall back to now() without raising
        assert item.received_at is not None
        assert item.received_at.tzinfo is not None

    def test_missing_subject_uses_default(self):
        msg = _make_gmail_message()
        # Remove Subject header
        msg["payload"]["headers"] = [
            h for h in msg["payload"]["headers"] if h["name"] != "Subject"
        ]
        item = self.source._parse(msg, "test", "inbox")
        assert item.subject == "(无主题)"

    def test_missing_from_uses_unknown(self):
        msg = _make_gmail_message()
        msg["payload"]["headers"] = [
            h for h in msg["payload"]["headers"] if h["name"] != "From"
        ]
        item = self.source._parse(msg, "test", "inbox")
        assert item.sender == "unknown"

    def test_body_truncated_to_3000(self):
        long_body = "A" * 5000
        msg = _make_gmail_message(body_text=long_body)
        item = self.source._parse(msg, "test", "inbox")
        assert len(item.body) <= 3000

    def test_empty_body(self):
        msg = _make_gmail_message()
        msg["payload"]["body"] = {"data": ""}
        item = self.source._parse(msg, "test", "inbox")
        assert item.body == ""


class TestDedupByThread:
    """Tests for _dedup_by_thread (imported via two_pass but logic is straightforward)."""

    def test_dedup_keeps_latest_per_thread(
        self, sample_raw_item, sample_raw_item_2, sample_raw_item_different_thread
    ):
        from engine.src.processors.two_pass import _dedup_by_thread

        items = [sample_raw_item, sample_raw_item_2, sample_raw_item_different_thread]
        result = _dedup_by_thread(items)

        thread_ids = [r.metadata["thread_id"] for r in result]
        assert len(result) == 2
        # Should keep the later item from the shared thread
        assert "thread_xyz789" in thread_ids
        assert "thread_new001" in thread_ids

        # The one kept for thread_xyz789 should be the later one (sample_raw_item_2)
        shared = [r for r in result if r.metadata["thread_id"] == "thread_xyz789"][0]
        assert shared.id == "msg_def456"

    def test_dedup_no_thread_id_uses_msg_id(self):
        from engine.src.processors.two_pass import _dedup_by_thread

        item = RawItem(
            id="no_thread_msg",
            source_label="test",
            subject="test",
            body="test",
            sender="a@b.com",
            recipients=[],
            received_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
            metadata={},  # no thread_id
        )
        result = _dedup_by_thread([item])
        assert len(result) == 1
        assert result[0].id == "no_thread_msg"

    def test_dedup_empty_list(self):
        from engine.src.processors.two_pass import _dedup_by_thread

        assert _dedup_by_thread([]) == []
