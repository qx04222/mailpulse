"""
Tests for report generation:
- DOCX: engine/src/destinations/docx_report.py
- PDF:  engine/src/destinations/pdf_report.py
- Telegram brief: engine/src/processors/two_pass._format_telegram_brief
- JSON parsing: engine/src/processors/two_pass._parse_structured_json
"""
import json

import pytest

from engine.src.destinations.docx_report import generate_report_docx
from engine.src.destinations.pdf_report import generate_report_pdf
from engine.src.processors.two_pass import _format_telegram_brief, _parse_structured_json


class TestDocxReport:
    """Tests for generate_report_docx()"""

    def test_docx_returns_bytes(self, sample_structured_data):
        result = generate_report_docx(sample_structured_data, "Arcview", "03/12–03/15")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_docx_has_valid_header(self, sample_structured_data):
        result = generate_report_docx(sample_structured_data, "Arcview", "03/12–03/15")
        # DOCX files start with PK (ZIP format)
        assert result[:2] == b"PK"

    def test_docx_with_empty_data(self):
        empty_data = {
            "overview": {"total_emails": 0, "period": "03/12–03/15", "company": "Test"},
            "clients": [],
            "priority_actions": [],
            "followup_update": {"resolved": [], "overdue": [], "still_pending": []},
            "trash_spam_review": [],
        }
        result = generate_report_docx(empty_data, "Test", "03/12–03/15")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_docx_with_full_followup_data(self, sample_structured_data):
        # Ensure followup section renders without error
        result = generate_report_docx(sample_structured_data, "Arcview", "03/12–03/15")
        assert isinstance(result, bytes)

    def test_docx_with_trash_review(self, sample_structured_data):
        result = generate_report_docx(sample_structured_data, "Arcview", "03/12–03/15")
        assert isinstance(result, bytes)
        assert len(result) > 500  # Should have substantial content


class TestPdfReport:
    """Tests for generate_report_pdf()"""

    def test_pdf_returns_bytes(self):
        digest_text = (
            "*🔴 需立即处理*\n"
            "• 跟进王伟确认报价 → Nahrain\n\n"
            "*🟡 需要关注*\n"
            "• 回复李明新询价\n\n"
            "*📝 总结*\n"
            "本期共12封邮件，3个新询价。"
        )
        result = generate_report_pdf("Arcview", digest_text, "03/12–03/15")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_has_valid_header(self):
        result = generate_report_pdf("Test", "Simple digest text", "03/12–03/15")
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"

    def test_pdf_with_action_items(self, sample_raw_item):
        action_items = [
            {
                "score": 5,
                "reason": "紧急报价",
                "suggested_assignee_email": "nahrain@arcview.ca",
                "item": sample_raw_item,
            }
        ]
        result = generate_report_pdf(
            "Arcview", "Test digest", "03/12–03/15", action_items=action_items
        )
        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"

    def test_pdf_with_empty_digest(self):
        result = generate_report_pdf("Empty", "", "03/12–03/15")
        assert isinstance(result, bytes)

    def test_pdf_with_long_content(self):
        long_text = "*🔴 需立即处理*\n" + "\n".join(
            f"• 处理第{i}项紧急事项" for i in range(50)
        )
        result = generate_report_pdf("Arcview", long_text, "03/12–03/15")
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestFormatTelegramBrief:
    """Tests for _format_telegram_brief()"""

    def test_basic_format(self, sample_structured_data):
        result = _format_telegram_brief(sample_structured_data, "Arcview", "03/12–03/15")
        assert "Arcview" in result
        assert "03/12–03/15" in result
        assert "12" in result  # total emails

    def test_includes_high_priority_actions(self, sample_structured_data):
        result = _format_telegram_brief(sample_structured_data, "Arcview", "03/12–03/15")
        assert "需立即处理" in result
        assert "跟进王伟确认报价" in result
        assert "Nahrain" in result

    def test_includes_medium_actions(self, sample_structured_data):
        result = _format_telegram_brief(sample_structured_data, "Arcview", "03/12–03/15")
        assert "需要关注" in result
        assert "回复李明新询价" in result

    def test_includes_overdue_items(self, sample_structured_data):
        result = _format_telegram_brief(sample_structured_data, "Arcview", "03/12–03/15")
        assert "超期未处理" in result
        assert "Surrey 项目尾款" in result

    def test_empty_data(self):
        empty = {
            "overview": {"total_emails": 0},
            "priority_actions": [],
            "followup_update": {"overdue": []},
        }
        result = _format_telegram_brief(empty, "Test", "03/12–03/15")
        assert "Test" in result
        assert "0" in result

    def test_no_highlights(self):
        data = {
            "overview": {"total_emails": 5, "highlights": ""},
            "priority_actions": [],
            "followup_update": {},
        }
        result = _format_telegram_brief(data, "Test", "03/12–03/15")
        assert "Test" in result


class TestParseStructuredJson:
    """Tests for _parse_structured_json()"""

    def test_valid_json(self):
        text = '{"overview": {"total": 5}, "clients": []}'
        result = _parse_structured_json(text)
        assert result["overview"]["total"] == 5

    def test_json_in_code_block(self):
        text = '```json\n{"score": 4, "reason": "test"}\n```'
        result = _parse_structured_json(text)
        assert result["score"] == 4
        assert result["reason"] == "test"

    def test_json_in_code_block_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = _parse_structured_json(text)
        assert result["key"] == "value"

    def test_invalid_input_returns_empty_dict(self):
        assert _parse_structured_json("not json at all") == {}
        assert _parse_structured_json("") == {}
        assert _parse_structured_json("random text without braces") == {}

    def test_json_with_surrounding_text(self):
        text = 'Here is my analysis:\n{"result": true}\nEnd of response.'
        result = _parse_structured_json(text)
        assert result["result"] is True

    def test_nested_json(self):
        data = {
            "overview": {"total": 10, "nested": {"deep": True}},
            "clients": [{"name": "test"}],
        }
        text = json.dumps(data)
        result = _parse_structured_json(text)
        assert result["overview"]["nested"]["deep"] is True
