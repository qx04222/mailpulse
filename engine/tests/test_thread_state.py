"""
Tests for thread status state machine logic.
Covers: inbound/outbound transitions, stale detection, count tracking.

Since the thread state machine may not be a standalone module yet, the logic
is implemented inline here as a specification for the expected behavior.
"""
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

import pytest


# ---------------------------------------------------------------------------
# Thread state machine (reference implementation)
# ---------------------------------------------------------------------------

STALE_THRESHOLD_DAYS = 14


@dataclass
class ThreadState:
    thread_id: str
    status: str = "active"  # active | waiting_reply | stale | closed
    email_count: int = 0
    inbound_count: int = 0
    outbound_count: int = 0
    last_activity: Optional[datetime] = None
    our_emails: list = field(default_factory=list)  # list of our email addresses

    def process_email(
        self,
        sender: str,
        recipients: list,
        received_at: datetime,
    ):
        """Process a new email in this thread."""
        self.email_count += 1
        self.last_activity = received_at

        sender_email = _extract_email(sender).lower()
        is_outbound = sender_email in [e.lower() for e in self.our_emails]

        if is_outbound:
            self.outbound_count += 1
            self.status = "waiting_reply"
        else:
            self.inbound_count += 1
            self.status = "active"

    def check_stale(self, now: Optional[datetime] = None):
        """Mark thread as stale if no activity for STALE_THRESHOLD_DAYS."""
        if now is None:
            now = datetime.now(timezone.utc)
        if self.last_activity and self.status in ("active", "waiting_reply"):
            delta = now - self.last_activity
            if delta.days >= STALE_THRESHOLD_DAYS:
                self.status = "stale"


def _extract_email(addr: str) -> str:
    """Extract email from 'Name <email>' format."""
    if "<" in addr and ">" in addr:
        return addr.split("<")[1].split(">")[0]
    return addr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

OUR_EMAILS = ["xqi@arcview.ca", "nahrain@arcview.ca"]


class TestInboundEmail:
    def test_inbound_sets_active(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        ts.process_email(
            sender="client@example.com",
            recipients=["xqi@arcview.ca"],
            received_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "active"
        assert ts.inbound_count == 1
        assert ts.outbound_count == 0
        assert ts.email_count == 1

    def test_inbound_after_waiting_resets_to_active(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS, status="waiting_reply")
        ts.process_email(
            sender="client@example.com",
            recipients=["xqi@arcview.ca"],
            received_at=datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "active"

    def test_inbound_with_display_name(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        ts.process_email(
            sender="Wang Wei <wangwei@client.com>",
            recipients=["xqi@arcview.ca"],
            received_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "active"
        assert ts.inbound_count == 1


class TestOutboundEmail:
    def test_outbound_sets_waiting_reply(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        ts.process_email(
            sender="xqi@arcview.ca",
            recipients=["client@example.com"],
            received_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "waiting_reply"
        assert ts.outbound_count == 1
        assert ts.inbound_count == 0

    def test_outbound_with_display_name(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        ts.process_email(
            sender="Xin Qi <xqi@arcview.ca>",
            recipients=["client@example.com"],
            received_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "waiting_reply"
        assert ts.outbound_count == 1

    def test_outbound_from_team_member(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        ts.process_email(
            sender="nahrain@arcview.ca",
            recipients=["client@example.com"],
            received_at=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        )
        assert ts.status == "waiting_reply"


class TestStaleDetection:
    def test_no_activity_14_days_becomes_stale(self):
        ts = ThreadState(
            thread_id="t1",
            our_emails=OUR_EMAILS,
            status="active",
            last_activity=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        )
        now = datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)  # 15 days later
        ts.check_stale(now)
        assert ts.status == "stale"

    def test_activity_within_14_days_not_stale(self):
        ts = ThreadState(
            thread_id="t1",
            our_emails=OUR_EMAILS,
            status="active",
            last_activity=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
        )
        now = datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)  # 6 days later
        ts.check_stale(now)
        assert ts.status == "active"

    def test_exactly_14_days_becomes_stale(self):
        ts = ThreadState(
            thread_id="t1",
            our_emails=OUR_EMAILS,
            status="waiting_reply",
            last_activity=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        )
        now = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)  # exactly 14 days
        ts.check_stale(now)
        assert ts.status == "stale"

    def test_closed_thread_stays_closed(self):
        ts = ThreadState(
            thread_id="t1",
            our_emails=OUR_EMAILS,
            status="closed",
            last_activity=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        now = datetime(2026, 3, 15, tzinfo=timezone.utc)
        ts.check_stale(now)
        assert ts.status == "closed"  # closed is not in (active, waiting_reply)

    def test_no_last_activity_not_stale(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS, status="active")
        ts.check_stale(datetime(2026, 3, 15, tzinfo=timezone.utc))
        assert ts.status == "active"


class TestCountTracking:
    def test_mixed_conversation_counts(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)

        # Inbound from client
        ts.process_email("client@example.com", ["xqi@arcview.ca"],
                         datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc))
        assert ts.email_count == 1
        assert ts.inbound_count == 1
        assert ts.outbound_count == 0

        # Outbound reply
        ts.process_email("xqi@arcview.ca", ["client@example.com"],
                         datetime(2026, 3, 15, 11, 0, tzinfo=timezone.utc))
        assert ts.email_count == 2
        assert ts.inbound_count == 1
        assert ts.outbound_count == 1

        # Client replies again
        ts.process_email("client@example.com", ["xqi@arcview.ca"],
                         datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc))
        assert ts.email_count == 3
        assert ts.inbound_count == 2
        assert ts.outbound_count == 1

    def test_last_activity_updated(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)
        t1 = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)

        ts.process_email("client@example.com", ["xqi@arcview.ca"], t1)
        assert ts.last_activity == t1

        ts.process_email("xqi@arcview.ca", ["client@example.com"], t2)
        assert ts.last_activity == t2

    def test_status_transitions_full_cycle(self):
        ts = ThreadState(thread_id="t1", our_emails=OUR_EMAILS)

        # 1. Client sends email → active
        ts.process_email("client@example.com", ["xqi@arcview.ca"],
                         datetime(2026, 3, 1, tzinfo=timezone.utc))
        assert ts.status == "active"

        # 2. We reply → waiting_reply
        ts.process_email("xqi@arcview.ca", ["client@example.com"],
                         datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc))
        assert ts.status == "waiting_reply"

        # 3. No response for 14+ days → stale
        ts.check_stale(datetime(2026, 3, 16, tzinfo=timezone.utc))
        assert ts.status == "stale"
