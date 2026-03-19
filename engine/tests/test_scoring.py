"""
Tests for Haiku scoring in engine/src/processors/two_pass.py
Covers: score_email(), _dedup_by_thread(), JSON extraction edge cases.
"""
import json
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from engine.src.sources.gmail_source import RawItem


def _run(coro):
    """Helper to run an async function in tests."""
    return asyncio.run(coro)


def _make_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create() response."""
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


class TestScoreEmail:
    """Tests for score_email()"""

    @patch("engine.src.processors.two_pass.client")
    def test_score_email_valid_json(self, mock_client, sample_raw_item):
        valid_response = json.dumps({
            "score": 5,
            "reason": "紧急报价需确认",
            "one_line": "温哥华报价确认",
            "action_needed": True,
            "suggested_assignee_email": "nahrain@arcview.ca",
            "client_name": "王伟",
            "project_address": "Vancouver",
            "product_type": "门窗",
        })
        mock_client.messages.create.return_value = _make_anthropic_response(valid_response)

        from engine.src.processors.two_pass import score_email
        result = _run(score_email(sample_raw_item))

        assert result["score"] == 5
        assert result["action_needed"] is True
        assert result["client_name"] == "王伟"
        assert result["item"] is sample_raw_item

    @patch("engine.src.processors.two_pass.client")
    def test_score_email_json_in_code_block(self, mock_client, sample_raw_item):
        response_text = '```json\n{"score": 4, "reason": "需要跟进", "one_line": "跟进报价", "action_needed": false, "suggested_assignee_email": null, "client_name": "李明", "project_address": null, "product_type": null}\n```'
        mock_client.messages.create.return_value = _make_anthropic_response(response_text)

        from engine.src.processors.two_pass import score_email
        result = _run(score_email(sample_raw_item))

        assert result["score"] == 4
        assert result["client_name"] == "李明"
        assert result["action_needed"] is False

    @patch("engine.src.processors.two_pass.client")
    def test_score_email_malformed_response_fallback(self, mock_client, sample_raw_item):
        mock_client.messages.create.return_value = _make_anthropic_response(
            "I cannot parse this email properly, sorry."
        )

        from engine.src.processors.two_pass import score_email
        result = _run(score_email(sample_raw_item))

        # Should fallback gracefully
        assert result["score"] == 3
        assert result["reason"] == "解析失败"
        assert result["action_needed"] is False
        assert result["item"] is sample_raw_item

    @patch("engine.src.processors.two_pass.client")
    def test_score_email_json_with_surrounding_text(self, mock_client, sample_raw_item):
        response_text = '以下是分析结果：\n{"score": 2, "reason": "广告邮件", "one_line": "供应商促销", "action_needed": false, "suggested_assignee_email": null, "client_name": "", "project_address": null, "product_type": null}\n请注意以上分析。'
        mock_client.messages.create.return_value = _make_anthropic_response(response_text)

        from engine.src.processors.two_pass import score_email
        result = _run(score_email(sample_raw_item))

        assert result["score"] == 2
        assert result["one_line"] == "供应商促销"

    @patch("engine.src.processors.two_pass.client")
    def test_score_email_exception_in_api(self, mock_client, sample_raw_item):
        mock_client.messages.create.side_effect = Exception("API timeout")

        from engine.src.processors.two_pass import score_email
        with pytest.raises(Exception, match="API timeout"):
            _run(score_email(sample_raw_item))


class TestScoredToJson:
    """Tests for _scored_to_json helper."""

    def test_scored_to_json_output(self, sample_scored_item):
        from engine.src.processors.two_pass import _scored_to_json
        result = _scored_to_json([sample_scored_item])
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["score"] == 4
        assert parsed[0]["sender"] == sample_scored_item["item"].sender
        assert parsed[0]["subject"] == sample_scored_item["item"].subject

    def test_scored_to_json_empty(self):
        from engine.src.processors.two_pass import _scored_to_json
        result = _scored_to_json([])
        assert json.loads(result) == []
