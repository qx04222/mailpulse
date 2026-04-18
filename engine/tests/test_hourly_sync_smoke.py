"""
Smoke test for hourly_sync() entry point.

Guards against regressions where a single-company failure (or a systemic
outage like the 2026-04-16 Gmail OAuth token expiry) crashes the whole
hourly job instead of being logged and swallowed per-company.

All external boundaries (DB, Gmail, Claude, Lark, config loading) are
mocked — this test runs purely in-process.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_hourly_sync_handles_all_companies_failing():
    # When every run_company raises (like during the 2026-04-16 token outage),
    # hourly_sync() must not propagate — it should log and return.
    fake_companies = [
        {"id": "a", "name": "A"},
        {"id": "b", "name": "B"},
    ]

    failing_run_company = AsyncMock(
        side_effect=RuntimeError("simulated gmail auth failure")
    )

    with patch(
        "engine.src.bot.hourly_sync.run_company",
        failing_run_company,
    ), patch(
        "engine.src.bot.hourly_sync.load_companies",
        MagicMock(return_value=fake_companies),
    ), patch(
        "engine.src.utils.holidays.is_business_day",
        MagicMock(return_value=True),
    ), patch(
        "engine.src.bot.hourly_sync.reload_config",
        MagicMock(return_value=None),
    ), patch(
        "engine.src.bot.hourly_sync.notify_urgent_emails",
        AsyncMock(return_value=0),
    ):
        from engine.src.bot.hourly_sync import hourly_sync

        # Must not raise — per-company errors should be swallowed + logged.
        await hourly_sync()

    assert failing_run_company.await_count == 2, (
        f"expected run_company to be awaited once per company (2), "
        f"got {failing_run_company.await_count}"
    )
