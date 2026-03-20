"""
Lark Base (多维表格 / Bitable) sync.
Push email/thread/client data to a Lark Base table for structured viewing.
Supports upsert: existing threads update in place, new threads create records.
"""
from typing import Optional, Dict, Any, List

from .lark import _api_call


# ══════════════════════════════════════════════════════════════
# Low-level CRUD
# ══════════════════════════════════════════════════════════════

def list_records(
    app_token: str,
    table_id: str,
    page_size: int = 500,
    filter_expr: str = "",
) -> List[Dict[str, Any]]:
    """List existing records in a Lark Base table."""
    try:
        params: Dict[str, Any] = {"page_size": page_size}
        if filter_expr:
            params["filter"] = filter_expr
        data = _api_call(
            "GET",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            params=params,
        )
        return data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"[Lark Base] Error listing records: {e}")
        return []


def create_record(
    app_token: str,
    table_id: str,
    fields: Dict[str, Any],
) -> Optional[str]:
    """Create a single record. Returns the record_id or None."""
    try:
        data = _api_call(
            "POST",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json_data={"fields": fields},
        )
        record = data.get("data", {}).get("record", {})
        return record.get("record_id")
    except Exception as e:
        print(f"[Lark Base] Error creating record: {e}")
        return None


def batch_create_records(
    app_token: str,
    table_id: str,
    records: List[Dict[str, Any]],
) -> int:
    """Batch create records (max 500 per batch). Returns count created."""
    if not records:
        return 0

    created = 0
    for i in range(0, len(records), 500):
        batch = records[i:i + 500]
        payload = {"records": [{"fields": r} for r in batch]}
        try:
            data = _api_call(
                "POST",
                f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                json_data=payload,
            )
            batch_records = data.get("data", {}).get("records", [])
            created += len(batch_records)
        except Exception as e:
            print(f"[Lark Base] Batch create error (batch {i // 500 + 1}): {e}")

    return created


def update_record(
    app_token: str,
    table_id: str,
    record_id: str,
    fields: Dict[str, Any],
) -> bool:
    """Update an existing record."""
    try:
        _api_call(
            "PUT",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            json_data={"fields": fields},
        )
        return True
    except Exception as e:
        print(f"[Lark Base] Error updating record {record_id}: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# Table management
# ══════════════════════════════════════════════════════════════

THREAD_TABLE_FIELDS = [
    {"field_name": "thread_id", "type": 1},        # text
    {"field_name": "客户", "type": 1},              # text
    {"field_name": "主题", "type": 1},              # text
    {"field_name": "状态", "type": 3,               # single select
     "property": {"options": [
         {"name": "紧急"},
         {"name": "需处理"},
         {"name": "关注"},
         {"name": "低优先"},
     ]}},
    {"field_name": "优先级", "type": 3,             # single select
     "property": {"options": [
         {"name": "高"},
         {"name": "中"},
         {"name": "低"},
     ]}},
    {"field_name": "负责人", "type": 1},            # text
    {"field_name": "摘要", "type": 1},              # text
    {"field_name": "邮件数", "type": 2},            # number
    {"field_name": "最后活动", "type": 5},          # date
    {"field_name": "方向", "type": 3,               # single select
     "property": {"options": [
         {"name": "客户来信"},
         {"name": "我方发出"},
     ]}},
]


def create_thread_table(app_token: str, table_name: str = "邮件线程") -> Optional[str]:
    """Create a pre-configured table for email threads. Returns table_id."""
    try:
        data = _api_call(
            "POST",
            f"/open-apis/bitable/v1/apps/{app_token}/tables",
            json_data={
                "table": {
                    "name": table_name,
                    "fields": THREAD_TABLE_FIELDS,
                },
            },
        )
        table_id = data.get("data", {}).get("table_id")
        print(f"[Lark Base] Created table '{table_name}' -> {table_id}")
        return table_id
    except Exception as e:
        print(f"[Lark Base] Error creating table: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# High-level sync with upsert
# ══════════════════════════════════════════════════════════════

def _build_thread_fields(t: Dict[str, Any], people_map: Dict[str, str]) -> Dict[str, Any]:
    """Convert a thread dict to Lark Base field values."""
    assignee_id = t.get("assigned_to_id")
    assignee_name = people_map.get(assignee_id, "") if assignee_id else ""
    score = t.get("max_score", 0)
    direction_raw = t.get("direction", "")
    direction = "客户来信" if direction_raw == "inbound" else ("我方发出" if direction_raw == "outbound" else "")

    last_activity = t.get("latest", {}).get("received_at", "")
    # Lark date field needs millisecond timestamp
    last_activity_ts = None
    if last_activity:
        try:
            from datetime import datetime
            if "T" in last_activity:
                dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(last_activity[:19], "%Y-%m-%d %H:%M:%S")
            last_activity_ts = int(dt.timestamp() * 1000)
        except Exception:
            pass

    fields: Dict[str, Any] = {
        "thread_id": t.get("thread_id", t.get("gmail_thread_id", "")),
        "客户": t.get("client_name", "") or t.get("subject", ""),
        "主题": t.get("subject", ""),
        "状态": _score_to_status_cn(score),
        "优先级": _score_to_priority_cn(score),
        "负责人": assignee_name,
        "摘要": (t.get("thread_summary", "") or "")[:500],
        "邮件数": t.get("email_count", 0),
    }
    if last_activity_ts:
        fields["最后活动"] = last_activity_ts
    if direction:
        fields["方向"] = direction

    return fields


def sync_threads_to_base(
    app_token: str,
    table_id: str,
    threads: List[Dict[str, Any]],
    people_map: Optional[Dict[str, str]] = None,
    company_id: str = "",
) -> int:
    """
    Sync thread data to Lark Base with upsert logic.
    Uses lark_base_sync table in Supabase to track which threads
    have been synced and their Lark record_ids.
    Returns number of records created/updated.
    """
    if not app_token or not table_id:
        print("[Lark Base] Sync skipped: no app_token or table_id configured")
        return 0

    people_map = people_map or {}

    # Load existing sync records from DB
    existing_map: Dict[str, str] = {}  # thread_id -> lark_record_id
    if company_id:
        try:
            from ..storage.db import db
            resp = db.table("lark_base_sync") \
                .select("thread_id,record_id") \
                .eq("company_id", company_id) \
                .execute()
            for row in (resp.data or []):
                if row.get("thread_id"):
                    existing_map[row["thread_id"]] = row["record_id"]
        except Exception as e:
            print(f"[Lark Base] Could not load sync state: {e}")

    created = 0
    updated = 0

    for t in threads:
        fields = _build_thread_fields(t, people_map)
        db_thread_id = t.get("db_thread_id", "")  # UUID from threads table

        if db_thread_id and db_thread_id in existing_map:
            # Update existing record
            record_id = existing_map[db_thread_id]
            if update_record(app_token, table_id, record_id, fields):
                updated += 1
                # Update sync timestamp
                if company_id:
                    try:
                        from ..storage.db import db
                        from datetime import datetime, timezone
                        db.table("lark_base_sync") \
                            .update({"updated_at": datetime.now(timezone.utc).isoformat()}) \
                            .eq("company_id", company_id) \
                            .eq("thread_id", db_thread_id) \
                            .execute()
                    except Exception:
                        pass
        else:
            # Create new record
            record_id = create_record(app_token, table_id, fields)
            if record_id:
                created += 1
                # Save sync mapping
                if company_id and db_thread_id:
                    try:
                        from ..storage.db import db
                        db.table("lark_base_sync").upsert({
                            "company_id": company_id,
                            "thread_id": db_thread_id,
                            "record_id": record_id,
                        }, on_conflict="company_id,thread_id").execute()
                    except Exception:
                        pass

    print(f"[Lark Base] Sync done: {created} created, {updated} updated")
    return created + updated


def _score_to_status_cn(score: int) -> str:
    if score >= 5:
        return "紧急"
    elif score >= 4:
        return "需处理"
    elif score >= 3:
        return "关注"
    else:
        return "低优先"


def _score_to_priority_cn(score: int) -> str:
    if score >= 4:
        return "高"
    elif score >= 3:
        return "中"
    else:
        return "低"
