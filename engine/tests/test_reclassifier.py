"""
Tests for engine/src/processors/reclassifier.py
Covers: JSON extraction, confidence threshold, label application.
"""
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

import pytest

from engine.src.sources.gmail_source import RawItem, GmailSource


def _run(coro):
    return asyncio.run(coro)


def _make_anthropic_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


def _make_test_companies():
    """Return dicts matching the new DB-based config format."""
    return [
        {"id": "c1", "name": "Arcview", "gmail_label": "Arcview", "telegram_group_id": "-100111"},
        {"id": "c2", "name": "TorqueMax", "gmail_label": "TorqueMax", "telegram_group_id": "-100222"},
    ]


def _make_personal_item(msg_id: str = "msg_p1", subject: str = "未分类邮件"):
    return RawItem(
        id=msg_id,
        source_label="personal",
        subject=subject,
        body="这是一封来自客户的邮件，关于门窗项目。",
        sender="client@example.com",
        recipients=["xqi@arcview.ca"],
        received_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        metadata={"bucket": "inbox", "thread_id": "thread_p1"},
    )


class TestReclassifyJsonExtraction:
    """Test JSON extraction from Haiku classification responses."""

    @patch("engine.src.processors.reclassifier.client")
    def test_valid_json_response(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"company": "Arcview", "confidence": 0.9, "reason": "门窗相关"})
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 1
        assert result["skipped"] == 0
        assert result["details"][0]["assigned_to"] == "Arcview"

    @patch("engine.src.processors.reclassifier.client")
    def test_json_in_code_block(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            '```json\n{"company": "TorqueMax", "confidence": 0.85, "reason": "汽车零件"}\n```'
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 1
        assert result["details"][0]["assigned_to"] == "TorqueMax"

    @patch("engine.src.processors.reclassifier.client")
    def test_no_json_in_response_skips(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            "I'm not sure which company this belongs to."
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 0
        assert result["skipped"] == 1


class TestConfidenceThreshold:
    """Test that low confidence results are skipped."""

    @patch("engine.src.processors.reclassifier.client")
    def test_low_confidence_skipped(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        # Confidence 0.5 < threshold 0.7
        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"company": "Arcview", "confidence": 0.5, "reason": "不确定"})
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 0
        assert result["skipped"] == 1
        mock_gmail.apply_label.assert_not_called()

    @patch("engine.src.processors.reclassifier.client")
    def test_exactly_at_threshold_passes(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"company": "Arcview", "confidence": 0.7, "reason": "门窗项目"})
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 1
        mock_gmail.apply_label.assert_called_once()

    @patch("engine.src.processors.reclassifier.client")
    def test_company_none_skipped(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"company": "none", "confidence": 0.95, "reason": "个人邮件"})
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 0
        assert result["skipped"] == 1

    @patch("engine.src.processors.reclassifier.client")
    def test_unknown_company_skipped(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.return_value = _make_anthropic_response(
            json.dumps({"company": "UnknownCorp", "confidence": 0.95, "reason": "不在列表中"})
        )

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        # UnknownCorp not in label_map
        assert result["reclassified"] == 0
        assert result["skipped"] == 1


class TestReclassifyEdgeCases:
    """Edge cases in reclassification."""

    @patch("engine.src.processors.reclassifier.client")
    def test_no_personal_emails(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = []

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 0
        assert result["skipped"] == 0
        mock_client.messages.create.assert_not_called()

    @patch("engine.src.processors.reclassifier.client")
    def test_api_exception_skips_item(self, mock_client):
        mock_gmail = MagicMock(spec=GmailSource)
        mock_gmail.fetch_personal.return_value = [_make_personal_item()]
        mock_gmail.get_label_id.return_value = "Label_123"

        mock_client.messages.create.side_effect = Exception("Rate limited")

        from engine.src.processors.reclassifier import reclassify_unlabeled
        result = _run(reclassify_unlabeled(mock_gmail, _make_test_companies()))

        assert result["reclassified"] == 0
        assert result["skipped"] == 1
