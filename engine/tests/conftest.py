"""
Shared fixtures for MailPulse engine tests.
All external services (Gmail, Anthropic, Supabase) are mocked.
"""
import sys
import os
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Prevent real Settings / Supabase from being instantiated at import time.
# We patch environment variables BEFORE any engine module is imported.
# ---------------------------------------------------------------------------
_ENV_DEFAULTS = {
    "ANTHROPIC_API_KEY": "sk-test-fake",
    "GMAIL_CLIENT_ID": "fake-client-id",
    "GMAIL_CLIENT_SECRET": "fake-client-secret",
    "GMAIL_REFRESH_TOKEN": "fake-refresh-token",
    "TELEGRAM_BOT_TOKEN": "fake-bot-token",
    "SUPABASE_URL": "https://fake.supabase.co",
    "SUPABASE_SERVICE_KEY": "fake-service-key",
}

for key, val in _ENV_DEFAULTS.items():
    os.environ.setdefault(key, val)

# Mock supabase.create_client globally so storage modules don't connect.
# Force-replace even if the real supabase is installed.
_mock_supabase_module = MagicMock()
_mock_supabase_client = MagicMock()
_mock_supabase_module.create_client = MagicMock(return_value=_mock_supabase_client)
sys.modules["supabase"] = _mock_supabase_module

# Now safe to import engine code
from engine.src.sources.gmail_source import RawItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_raw_item():
    """A realistic RawItem representing a Chinese business email."""
    return RawItem(
        id="msg_abc123",
        source_label="Arcview",
        subject="Re: 关于温哥华项目的报价单",
        body=(
            "张经理您好，\n\n"
            "附件是我们最新的报价单，请查收。\n"
            "如有问题请随时联系。\n\n"
            "Best regards,\n"
            "王伟\n"
            "Arcview Windows & Doors"
        ),
        sender="Wang Wei <wangwei@example.com>",
        recipients=["xqi@arcview.ca", "nahrain@arcview.ca"],
        received_at=datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc),
        metadata={
            "bucket": "inbox",
            "thread_id": "thread_xyz789",
        },
    )


@pytest.fixture
def sample_raw_item_2():
    """A second RawItem in the same thread (for dedup testing)."""
    return RawItem(
        id="msg_def456",
        source_label="Arcview",
        subject="Re: 关于温哥华项目的报价单",
        body="收到，谢谢！",
        sender="Zhang Manager <zhang@client.com>",
        recipients=["wangwei@example.com", "xqi@arcview.ca"],
        received_at=datetime(2026, 3, 15, 14, 0, 0, tzinfo=timezone.utc),
        metadata={
            "bucket": "inbox",
            "thread_id": "thread_xyz789",
        },
    )


@pytest.fixture
def sample_raw_item_different_thread():
    """A RawItem in a different thread."""
    return RawItem(
        id="msg_ghi789",
        source_label="Arcview",
        subject="新询价：Burnaby 铝合金门窗",
        body="你好，我想了解一下你们的铝合金门窗价格。地址在 Burnaby。",
        sender="Li Ming <liming@newclient.com>",
        recipients=["xqi@arcview.ca"],
        received_at=datetime(2026, 3, 16, 9, 0, 0, tzinfo=timezone.utc),
        metadata={
            "bucket": "inbox",
            "thread_id": "thread_new001",
        },
    )


@pytest.fixture
def sample_scored_item(sample_raw_item):
    """A scored item dict as returned by score_email."""
    return {
        "score": 4,
        "reason": "客户发来报价单，需要及时查看",
        "one_line": "温哥华项目报价单",
        "action_needed": True,
        "suggested_assignee_email": "nahrain@arcview.ca",
        "client_name": "王伟",
        "project_address": "温哥华",
        "product_type": "门窗",
        "item": sample_raw_item,
    }


@pytest.fixture
def sample_structured_data():
    """Structured analysis JSON as returned by Sonnet (Manus-style report)."""
    return {
        "overview": {
            "total_emails": 12,
            "period": "03/12–03/15",
            "company": "Arcview",
            "highlights": "本期共收到12封邮件，3个新询价，2个待跟进报价。",
            "per_person_stats": [
                {"name": "Xin", "client_count": 5, "quoted": 2, "pending": 3, "resolved": 1},
                {"name": "Nahrain", "client_count": 7, "quoted": 4, "pending": 2, "resolved": 1},
            ],
        },
        "clients": [
            {
                "client_name": "王伟",
                "contact_email": "wangwei@example.com",
                "project_address": "Vancouver, BC",
                "product_type": "铝合金门窗",
                "assigned_to": "Nahrain",
                "status": "quoting",
                "status_label": "报价中",
                "priority": 4,
                "email_count": 3,
                "latest_date": "2026-03-15",
                "summary": "客户询问温哥华项目铝合金门窗报价，已发初步报价，等待客户确认。",
                "action_needed": "跟进客户确认报价",
                "action_deadline": "2026-03-18",
                "key_details": ["报价金额 $45,000", "包含安装费"],
            },
        ],
        "priority_actions": [
            {
                "priority": "high",
                "action": "跟进王伟确认报价",
                "assigned_to": "Nahrain",
                "client": "王伟",
                "deadline": "2026-03-18",
            },
            {
                "priority": "medium",
                "action": "回复李明新询价",
                "assigned_to": "Xin",
                "client": "李明",
                "deadline": None,
            },
        ],
        "followup_update": {
            "resolved": [{"subject": "Burnaby 项目报价", "resolved_by": "客户已确认"}],
            "overdue": [{"subject": "Surrey 项目尾款", "days": 10, "assigned_to": "Nahrain"}],
            "still_pending": [{"subject": "Richmond 新项目", "assigned_to": "Xin"}],
        },
        "trash_spam_review": [
            {
                "sender": "promo@supplier.com",
                "subject": "铝材促销",
                "bucket": "trash",
                "worth_checking": True,
                "reason": "供应商促销可能有用",
            },
        ],
    }


@pytest.fixture
def mock_supabase():
    """A mock Supabase client with chainable query builder."""
    client = MagicMock()

    # Make table().select().eq()...execute() chainable
    table_mock = MagicMock()
    table_mock.select.return_value = table_mock
    table_mock.eq.return_value = table_mock
    table_mock.in_.return_value = table_mock
    table_mock.order.return_value = table_mock
    table_mock.insert.return_value = table_mock
    table_mock.update.return_value = table_mock
    table_mock.execute.return_value = MagicMock(data=[])

    client.table.return_value = table_mock
    return client
