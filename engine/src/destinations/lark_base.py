"""
Lark Base (多维表格 / Bitable) sync.
Push email/thread/client data to a Lark Base table for structured viewing.
Optional feature, controlled by config.
"""
from typing import Optional, Dict, Any, List

from .lark import _api_call


def list_records(
    app_token: str,
    table_id: str,
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    List existing records in a Lark Base table.
    """
    try:
        data = _api_call(
            "GET",
            f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            params={"page_size": page_size},
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
    """
    Create a single record in a Lark Base table.
    Returns the record_id or None.
    """
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
    """
    Batch create records in a Lark Base table.
    Each record is a dict of {fields: {...}}.
    Returns the count of successfully created records.
    """
    if not records:
        return 0

    # Lark limits batch to 500 records
    created = 0
    for i in range(0, len(records), 500):
        batch = records[i:i + 500]
        payload = {
            "records": [{"fields": r} for r in batch],
        }
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
    """
    Update an existing record in a Lark Base table.
    """
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


def sync_threads_to_base(
    app_token: str,
    table_id: str,
    threads: List[Dict[str, Any]],
    people_map: Optional[Dict[str, str]] = None,
) -> int:
    """
    Sync thread data to a Lark Base table.
    Maps thread fields to Lark Base columns:
        client_name, email, status, priority, assignee, summary, last_activity

    Returns number of records created.
    """
    if not app_token or not table_id:
        print("[Lark Base] Sync skipped: no app_token or table_id configured")
        return 0

    people_map = people_map or {}

    records = []
    for t in threads:
        assignee_id = t.get("assigned_to_id")
        assignee_name = people_map.get(assignee_id, "") if assignee_id else ""

        fields = {
            "client_name": t.get("client_name", "") or t.get("subject", ""),
            "subject": t.get("subject", ""),
            "status": _score_to_status(t.get("max_score", 0)),
            "priority": _score_to_priority(t.get("max_score", 0)),
            "assignee": assignee_name,
            "summary": (t.get("thread_summary", "") or "")[:500],
            "email_count": t.get("email_count", 0),
            "last_activity": t.get("latest", {}).get("received_at", ""),
        }
        records.append(fields)

    return batch_create_records(app_token, table_id, records)


def _score_to_status(score: int) -> str:
    """Map email score to a display status."""
    if score >= 5:
        return "Urgent"
    elif score >= 4:
        return "Action Required"
    elif score >= 3:
        return "Needs Attention"
    else:
        return "Low Priority"


def _score_to_priority(score: int) -> str:
    """Map email score to priority label."""
    if score >= 4:
        return "High"
    elif score >= 3:
        return "Medium"
    else:
        return "Low"
