"""
Dedicated Audit Logging Module with Strict Schema & Retention Policy (Bonus Track 2).
Logs security-sensitive events:
- Prompt access and prompt version promotion/rollback
- Incident injection and mitigation toggles
- High-privilege actions and sensitive operations
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

AUDIT_LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"


def get_utc_timestamp() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def log_audit_event(
    actor: str,
    action: str,
    resource: str,
    status: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    client_ip: str = "127.0.0.1",
    audit_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Append a structured audit event to the dedicated audit log.
    Schema:
      - audit_id: str (aud-<8-hex>)
      - ts: str (ISO 8601 UTC)
      - actor: str (user_id_hash, "system", "admin")
      - action: str (e.g. PROMPT_ACCESS, INCIDENT_TOGGLE, SYSTEM_STARTUP)
      - resource: str (e.g. prompt:day13-chat, incident:rag_slow)
      - status: str (SUCCESS, DENIED, FAILED)
      - client_ip: str
      - details: dict
    """
    target_file = audit_file or AUDIT_LOG_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "audit_id": f"aud-{uuid.uuid4().hex[:8]}",
        "ts": get_utc_timestamp(),
        "actor": actor,
        "action": action,
        "resource": resource,
        "status": status,
        "client_ip": client_ip,
        "details": details or {},
    }

    line = json.dumps(record, ensure_ascii=False)
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    return record


def apply_retention_policy(
    max_records: int = 1000,
    audit_file: Optional[Path] = None,
) -> int:
    """
    Enforce retention policy: keeps the most recent `max_records`.
    Returns the number of pruned records.
    """
    target_file = audit_file or AUDIT_LOG_FILE
    if not target_file.exists():
        return 0

    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) <= max_records:
        return 0

    pruned_count = len(lines) - max_records
    retained_lines = lines[-max_records:]

    with open(target_file, "w", encoding="utf-8") as f:
        for line in retained_lines:
            f.write(line + "\n")

    return pruned_count


def read_audit_events(audit_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read all audit events from file."""
    target_file = audit_file or AUDIT_LOG_FILE
    if not target_file.exists():
        return []

    events = []
    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events
