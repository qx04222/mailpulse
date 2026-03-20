"""
Main digest flow — orchestrates the entire email processing pipeline.
Processes each company: fetch emails, detect direction, extract clients,
upsert threads, score with AI, generate reports, push Telegram.
"""
import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .config import (
    settings,
    load_companies,
    load_people,
    get_team_emails,
    get_person_by_email,
    reload_config,
)
from .sources.gmail_source import GmailSource, RawItem
from .processors.two_pass import (
    generate_company_digest,
    generate_personal_digest,
    score_email,
    _dedup_by_thread,
    _date_range,
)
from .processors.followup import check_and_update_followups, format_followup_section
from .processors.reclassifier import reclassify_unlabeled
from .processors.client_extractor import process_email_for_client, is_new_client
from .processors.sla_checker import check_sla_breaches

from .storage.emails import (
    upsert_email,
    update_email_scores,
    _parse_sender_email,
    _detect_direction,
    _detect_direction_by_domain,
    _get_all_company_domains,
    _detect_is_reply,
    count_thread_emails,
)
from .storage.employee_discovery import discover_employees_from_email
from .storage.threads import (
    upsert_thread,
    get_threads_by_company,
    get_thread_by_gmail_id,
    mark_stale_threads,
)
from .storage.clients import get_client_by_email
from .storage.action_items import (
    upsert_action_item,
    get_pending_items,
    mark_resolved_by_thread,
)
from .storage.digest_runs import create_run, complete_run, fail_run
from .storage.events import create_event
from .storage.audit import log_action

from .destinations.telegram import send_message
from .destinations.docx_report import generate_report_docx
from .destinations.pdf_report import generate_report_pdf
from .destinations.supabase_upload import upload_report

gmail = GmailSource()


def _extract_recipients(item: RawItem) -> tuple:
    """Split item.recipients into to and cc lists (best effort)."""
    # RawItem.recipients merges To + CC; we keep them all as 'to' for now.
    # The raw email parser puts them together — a more precise split
    # would require re-parsing headers, but this is good enough.
    return item.recipients[:10], []


async def run_company(company: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full digest pipeline for a single company.

    1.  Create digest_run record
    2.  Fetch emails from Gmail
    3.  For each email: detect direction, extract client, upsert thread, upsert email
    4.  AI scoring (Haiku) for new emails
    5.  Update email records with scores
    6.  AI structured analysis (Sonnet)
    7.  Cache analysis in ai_company_analyses
    8.  Generate DOCX + PDF reports
    9.  Upload to Supabase Storage
    10. Check followup status
    11. Generate events (new_client, overdue, sla_breach)
    12. Push Telegram (brief + report link)
    13. Push personal summaries
    14. Complete digest_run record
    """
    company_id = company["id"]
    company_name = company["name"]
    gmail_label = company["gmail_label"]
    telegram_group_id = company.get("telegram_group_id", "")
    members = company.get("members", [])
    team_emails = get_team_emails()
    company_domains = _get_all_company_domains()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {company_name}...")

    # 1. Create digest run
    run_id = create_run(company_id, lookback_days=settings.digest_lookback_days)
    stats: Dict[str, Any] = {
        "total_emails": 0,
        "new_emails": 0,
        "high_priority": 0,
        "action_items_created": 0,
        "telegram_delivered": False,
        "report_docx_url": "",
        "report_pdf_url": "",
    }

    try:
        # 2. Fetch emails from Gmail
        items = gmail.fetch(
            label=gmail_label,
            lookback_days=settings.digest_lookback_days,
            include_trash=True,
            include_spam=True,
        )
        print(f"  -> {len(items)} emails fetched")
        stats["total_emails"] = len(items)

        # 3. For each email: direction, client, thread, email record
        email_records = []
        new_client_events = []

        for item in items:
            try:
                # 跳过已处理的邮件（避免重复调 AI）
                from .storage.emails import get_email_by_gmail_id
                existing_email = get_email_by_gmail_id(item.id)
                if existing_email:
                    # 包装成和新邮件一样的格式，保持下游代码兼容
                    email_records.append({
                        "item": item,
                        "email_row": existing_email,
                        "assigned_to_id": existing_email.get("assigned_to_id"),
                        "skipped": True,
                    })
                    continue

                sender_email = _parse_sender_email(item.sender)
                # 用域名判断方向（优先）+ 旧逻辑兜底
                direction = _detect_direction_by_domain(sender_email, company_domains)
                gmail_thread_id = item.metadata.get("thread_id", item.id)

                # Check if first in thread
                existing_count = count_thread_emails(gmail_thread_id)
                is_reply = _detect_is_reply(item.subject, existing_count == 0)

                # 3a. Extract client info
                recipients_to, recipients_cc = _extract_recipients(item)
                client = process_email_for_client(
                    sender=item.sender,
                    recipients_to=recipients_to,
                    recipients_cc=recipients_cc,
                    direction=direction,
                    company_id=company_id,
                    team_emails=team_emails,
                )
                client_id = client["id"] if client else None

                # Track new clients for event generation
                if client and is_new_client(client):
                    new_client_events.append(client)

                # 自动发现员工 + 分配负责人（基于域名匹配）
                assigned_to_id = discover_employees_from_email(
                    sender_email=sender_email,
                    sender_raw=item.sender,
                    recipients=recipients_to + recipients_cc,
                    company_id=company_id,
                    company_domains=company_domains,
                )

                # 3b. Upsert thread
                thread = upsert_thread(
                    gmail_thread_id=gmail_thread_id,
                    company_id=company_id,
                    subject=item.subject,
                    direction=direction,
                    received_at=item.received_at,
                    client_id=client_id,
                    assigned_to_id=assigned_to_id,
                )
                thread_id = thread.get("id")

                # 3c. Upsert email record
                email_row = upsert_email(
                    gmail_message_id=item.id,
                    gmail_thread_id=gmail_thread_id,
                    thread_id=thread_id,
                    company_id=company_id,
                    subject=item.subject,
                    sender=item.sender,
                    recipients_to=recipients_to,
                    recipients_cc=recipients_cc,
                    received_at=item.received_at,
                    body_preview=item.body[:500],
                    body_full=item.body[:3000],
                    direction=direction,
                    is_reply=is_reply,
                    bucket=item.metadata.get("bucket", "inbox"),
                    client_id=client_id,
                    assigned_to_id=assigned_to_id,
                    run_id=run_id,
                )
                email_records.append({
                    "email_row": email_row,
                    "item": item,
                    "direction": direction,
                    "thread_id": thread_id,
                    "client_id": client_id,
                    "assigned_to_id": assigned_to_id,
                })

            except Exception as e:
                print(f"  -> Email processing error ({item.subject[:40]}): {e}")

        stats["new_emails"] = len(email_records)

        # 4. AI scoring (Haiku) — only score NEW emails (skip already scored)
        deduped = _dedup_by_thread(items)
        new_items_to_score = []
        already_scored = []
        for item in deduped:
            existing = get_email_by_gmail_id(item.id)
            if existing and existing.get("score") is not None:
                # 已有分数，构造 scored 格式复用
                already_scored.append({
                    "score": existing["score"],
                    "reason": existing.get("score_reason", ""),
                    "one_line": existing.get("one_line", ""),
                    "action_needed": existing.get("action_needed", False),
                    "suggested_assignee_email": None,
                    "client_name": existing.get("client_name"),
                    "project_address": existing.get("project_address"),
                    "product_type": existing.get("product_type"),
                    "item": item,
                })
            else:
                new_items_to_score.append(item)

        if new_items_to_score:
            scored = await asyncio.gather(
                *[score_email(item) for item in new_items_to_score],
                return_exceptions=True,
            )
            new_scored = [s for s in scored if isinstance(s, dict)]
        else:
            new_scored = []

        all_scored = already_scored + new_scored
        print(f"  -> {len(new_scored)} new emails scored, {len(already_scored)} cached")

        # 5. Update email records with scores
        scored_by_msg_id = {s["item"].id: s for s in all_scored}
        for rec in email_records:
            item = rec["item"]
            s = scored_by_msg_id.get(item.id)
            if not s:
                continue
            email_row = rec["email_row"]
            email_id = email_row.get("id")
            if not email_id:
                continue

            # Find assigned person from AI suggestion
            ai_assigned_to_id = rec.get("assigned_to_id")
            suggested_email = (s.get("suggested_assignee_email") or "").lower()
            if suggested_email:
                person = get_person_by_email(suggested_email)
                if person:
                    ai_assigned_to_id = person["id"]

            try:
                update_email_scores(
                    email_id=email_id,
                    score=s.get("score", 3),
                    score_reason=s.get("reason", ""),
                    one_line=s.get("one_line", ""),
                    action_needed=s.get("action_needed", False),
                    client_name=s.get("client_name"),
                    client_org=s.get("client_org"),
                    project_address=s.get("project_address"),
                    product_type=s.get("product_type"),
                    assigned_to_id=ai_assigned_to_id,
                )
            except Exception as e:
                print(f"  -> Score update error: {e}")

        # Count high priority
        high_priority = [s for s in all_scored if s.get("score", 0) >= 4]
        stats["high_priority"] = len(high_priority)

        # 6. Check followup status (compare pending action_items with new threads)
        pending_items = get_pending_items(company_id)
        current_thread_ids = set()
        for rec in email_records:
            tid = rec.get("thread_id")
            if tid:
                current_thread_ids.add(tid)

        resolved_count = 0
        overdue_items = []
        still_pending = []
        for ai in pending_items:
            tid = ai.get("thread_id")
            if tid and tid in current_thread_ids:
                mark_resolved_by_thread(tid, note="auto: new activity in thread")
                resolved_count += 1
            elif ai["status"] == "overdue":
                overdue_items.append(ai)
            else:
                still_pending.append(ai)

        followup_section = _format_followup_for_sonnet(
            resolved_count, overdue_items, still_pending
        )

        # 6b. Save action items from high-scoring emails
        action_items_to_save = [
            s for s in all_scored
            if s.get("score", 0) >= 4 and s.get("action_needed", False)
        ]
        for s in action_items_to_save:
            item = s["item"]
            gmail_thread_id = item.metadata.get("thread_id", item.id)
            thread = get_thread_by_gmail_id(gmail_thread_id)
            thread_id = thread["id"] if thread else None

            # Find email_id and client_id
            email_id = None
            client_id = None
            assigned_to_id_for_ai = None
            for rec in email_records:
                if rec["item"].id == item.id:
                    email_id = rec["email_row"].get("id")
                    client_id = rec.get("client_id")
                    assigned_to_id_for_ai = rec.get("assigned_to_id")
                    break

            # Determine assignee from AI suggestion
            suggested_email = (s.get("suggested_assignee_email") or "").lower()
            if suggested_email:
                person = get_person_by_email(suggested_email)
                if person:
                    assigned_to_id_for_ai = person["id"]

            # Map numeric score to priority string
            score_val = s.get("score", 3)
            priority = "high" if score_val >= 5 else ("medium" if score_val >= 4 else "low")

            try:
                upsert_action_item(
                    company_id=company_id,
                    thread_id=thread_id,
                    email_id=email_id,
                    client_id=client_id,
                    title=item.subject,
                    priority=priority,
                    assigned_to_id=assigned_to_id_for_ai,
                    run_id=run_id,
                    description=s.get("reason", ""),
                )
                stats["action_items_created"] += 1
            except Exception as e:
                print(f"  -> Action item save error: {e}")

        # 7. AI structured analysis (Sonnet) — build a compat company object
        company_compat = _build_company_compat(company)
        structured_data, telegram_brief, _, _ = await generate_company_digest(
            company_name=company_name,
            items=items,
            followup_section=followup_section,
            lookback_days=settings.digest_lookback_days,
            company=company_compat,
        )

        # 7b. Cache analysis in ai_company_analyses
        try:
            from .storage.db import db as _db
            _db.table("ai_company_analyses").upsert({
                "company_id": company_id,
                "run_id": run_id,
                "analysis_json": structured_data,
                "highlights": structured_data.get("overview", {}).get("highlights", ""),
                "period": _date_range(settings.digest_lookback_days),
                "telegram_brief": telegram_brief,
                "model_used": "claude-sonnet-4-5",
            }, on_conflict="company_id,run_id").execute()
        except Exception as e:
            print(f"  -> Analysis cache error: {e}")

        # 8. Generate DOCX report
        date_range = _date_range(settings.digest_lookback_days)
        docx_url = ""
        pdf_url = ""

        try:
            docx_bytes = generate_report_docx(structured_data, company_name, date_range)
            docx_url = upload_report(
                company_name=company_name,
                file_bytes=docx_bytes,
                run_date=datetime.now().strftime("%Y-%m-%d"),
                file_ext="docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            stats["report_docx_url"] = docx_url
            print(f"  -> DOCX report uploaded")
        except Exception as e:
            print(f"  -> DOCX report error: {e}")

        # 9. Generate PDF report (backup)
        try:
            pdf_bytes = generate_report_pdf(
                company_name=company_name,
                digest_text=telegram_brief,
                date_range=date_range,
                action_items=action_items_to_save,
            )
            pdf_url = upload_report(
                company_name=company_name,
                file_bytes=pdf_bytes,
                run_date=datetime.now().strftime("%Y-%m-%d"),
                file_ext="pdf",
                content_type="application/pdf",
            )
            stats["report_pdf_url"] = pdf_url
            print(f"  -> PDF report uploaded")
        except Exception as e:
            print(f"  -> PDF report error: {e}")

        # 10. Mark stale threads
        stale_count = mark_stale_threads(company_id)
        if stale_count:
            print(f"  -> {stale_count} threads marked stale")

        # 11. Generate events
        # 11a. new_client events
        seen_client_ids = set()
        for client in new_client_events:
            cid = client.get("id")
            if cid and cid not in seen_client_ids:
                seen_client_ids.add(cid)
                try:
                    create_event(
                        company_id=company_id,
                        event_type="new_client",
                        severity="info",
                        title=f"New client: {client.get('name') or client.get('email')}",
                        description=f"First contact from {client.get('email')}",
                        client_id=cid,
                    )
                except Exception as e:
                    print(f"  -> New client event error: {e}")

        # 11b. overdue_warning events (action items seen_count > 2)
        for ai in overdue_items:
            try:
                create_event(
                    company_id=company_id,
                    event_type="overdue_warning",
                    severity="warning",
                    title=f"Overdue: {ai.get('title', '')}",
                    description=f"Action item seen {ai.get('seen_count', 0)} times without resolution",
                    thread_id=ai.get("thread_id"),
                    action_item_id=ai.get("id"),
                    person_id=ai.get("assigned_to_id"),
                )
            except Exception as e:
                print(f"  -> Overdue event error: {e}")

        # 11c. SLA breach events
        try:
            active_threads = get_threads_by_company(
                company_id, status=None
            )
            checkable = [
                t for t in active_threads
                if t.get("status") in ("active", "waiting_reply")
            ]
            breaches = check_sla_breaches(company_id, checkable)
            if breaches:
                print(f"  -> {len(breaches)} SLA breach events generated")
        except Exception as e:
            print(f"  -> SLA check error: {e}")

        # 11d. Digest completed event
        try:
            create_event(
                company_id=company_id,
                event_type="digest_completed",
                severity="info",
                title=f"Digest completed for {company_name}",
                description=(
                    f"Processed {stats['total_emails']} emails, "
                    f"{stats['high_priority']} high priority, "
                    f"{stats['action_items_created']} action items"
                ),
                metadata=stats,
            )
        except Exception:
            pass

        # 12. Push Telegram group summary
        if telegram_group_id:
            msg = telegram_brief
            if docx_url:
                msg += f"\n\U0001F4CE [完整报告下载]({docx_url})"
            success = send_message(telegram_group_id, msg)
            stats["telegram_delivered"] = success
            print(f"  -> Company group: {'sent' if success else 'failed'}")

        # 13. Push personal summaries
        for member in members:
            try:
                telegram_user_id = member.get("telegram_user_id")
                if not telegram_user_id:
                    continue

                member_compat = _build_person_compat(member)
                personal_summary = await generate_personal_digest(
                    person=member_compat,
                    company_name=company_name,
                    scored_items=list(all_scored),
                    pending_overdue=overdue_items + still_pending,
                    lookback_days=settings.digest_lookback_days,
                )
                if personal_summary:
                    ok = send_message(telegram_user_id, personal_summary)
                    print(f"  -> Personal ({member['name']}): {'sent' if ok else 'failed'}")
            except Exception as e:
                print(f"  -> Personal digest error ({member.get('name', '?')}): {e}")

        # 14. Complete digest run
        complete_run(run_id, stats)

        # Audit log
        log_action(
            action="digest_run",
            entity_type="company",
            entity_id=company_id,
            entity_name=company_name,
            description=f"Digest run completed: {stats['total_emails']} emails processed",
        )

        return {
            "company": company_name,
            "company_id": company_id,
            "emails": len(items),
            "high_priority": stats["high_priority"],
            "action_items": stats["action_items_created"],
            "docx_url": docx_url,
        }

    except Exception as e:
        print(f"  -> FATAL ERROR for {company_name}: {e}")
        try:
            fail_run(run_id, str(e))
        except Exception:
            pass
        raise


def _format_followup_for_sonnet(
    resolved_count: int,
    overdue: List[Dict[str, Any]],
    still_pending: List[Dict[str, Any]],
) -> str:
    """Format followup status for the Sonnet analysis prompt."""
    lines = []

    if resolved_count:
        lines.append(f"【本期已解决】{resolved_count} items resolved via new thread activity")

    if overdue:
        lines.append("【超期未处理】")
        for item in overdue:
            days = item.get("seen_count", 1) * 3
            lines.append(
                f"  [{days} days+] {item.get('title', '')} — "
                f"assigned: {item.get('assigned_to_id', 'unassigned')}"
            )

    if still_pending:
        lines.append("【上期待处理（持续跟进）】")
        for item in still_pending:
            lines.append(f"  {item.get('title', '')} — assigned: {item.get('assigned_to_id', 'unassigned')}")

    return "\n".join(lines) if lines else "（无历史待跟进项目）"


def _build_company_compat(company: Dict[str, Any]) -> Any:
    """
    Build a compatibility object that two_pass.py can use.
    two_pass expects company.members with .name, .email, .role attributes.
    """
    class _PersonCompat:
        def __init__(self, d: Dict[str, Any]):
            self.name = d.get("name", "")
            self.email = d.get("email", "")
            self.role = d.get("role", "member")
            self.telegram_user_id = d.get("telegram_user_id", "")
            self.companies: List[str] = []

    class _CompanyCompat:
        def __init__(self, d: Dict[str, Any]):
            self.name = d.get("name", "")
            self.gmail_label = d.get("gmail_label", "")
            self.telegram_group_id = d.get("telegram_group_id", "")
            self.members = [_PersonCompat(m) for m in d.get("members", [])]

    return _CompanyCompat(company)


def _build_person_compat(person: Dict[str, Any]) -> Any:
    """Build a compatibility object that two_pass.py can use for personal digest."""
    class _PersonCompat:
        def __init__(self, d: Dict[str, Any]):
            self.name = d.get("name", "")
            self.email = d.get("email", "")
            self.role = d.get("role", "member")
            self.telegram_user_id = d.get("telegram_user_id", "")
            self.companies: List[str] = []

    return _PersonCompat(person)


async def run_company_report_only(company: Dict[str, Any]) -> tuple:
    """Generate report only (for Bot /report command). Returns (docx_bytes, docx_url)."""
    company_name = company["name"]
    gmail_label = company["gmail_label"]

    items = gmail.fetch(
        label=gmail_label,
        lookback_days=settings.digest_lookback_days,
        include_trash=True,
        include_spam=True,
    )

    company_compat = _build_company_compat(company)
    structured_data, telegram_brief, _, _ = await generate_company_digest(
        company_name=company_name,
        items=items,
        followup_section="（无历史待跟进项目）",
        lookback_days=settings.digest_lookback_days,
        company=company_compat,
    )

    date_range = _date_range(settings.digest_lookback_days)
    docx_bytes = generate_report_docx(structured_data, company_name, date_range)

    docx_url = ""
    try:
        docx_url = upload_report(
            company_name=company_name,
            file_bytes=docx_bytes,
            run_date=datetime.now().strftime("%Y-%m-%d"),
            file_ext="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception:
        pass

    return docx_bytes, docx_url


async def run_all():
    """Main entry point: process all active companies."""
    print(f"\n{'='*50}")
    print(f"Email Digest Run — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"{'='*50}")

    # Load config from database
    print("\n[Config] Loading companies and people from database...")
    reload_config()
    companies = load_companies()
    people = load_people()
    print(f"[Config] {len(companies)} companies, {len(people)} people loaded")

    # Step 0: Reclassify unlabeled emails
    print("\n[Reclassifier] Scanning unlabeled emails...")
    try:
        # Build compat objects for reclassifier
        company_compats = [_build_company_compat(c) for c in companies]
        reclass = await reclassify_unlabeled(
            gmail, company_compats, lookback_days=settings.digest_lookback_days
        )
        print(f"[Reclassifier] Done: {reclass['reclassified']} reclassified, {reclass['skipped']} skipped")
    except Exception as e:
        print(f"[Reclassifier] Error: {e}")

    # Step 1: Process all companies concurrently
    results = await asyncio.gather(
        *[run_company(company) for company in companies],
        return_exceptions=True,
    )

    for r in results:
        if isinstance(r, Exception):
            print(f"ERROR: {r}")
        else:
            print(f"Done: {r['company']} ({r['emails']} emails, {r['high_priority']} high, {r['action_items']} actions)")

    print(f"\nRun complete.")


if __name__ == "__main__":
    asyncio.run(run_all())
