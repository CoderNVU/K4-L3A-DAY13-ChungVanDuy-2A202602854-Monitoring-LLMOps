"""
Unit tests for Dedicated Audit Logger and Retention Policy (Bonus Track 2).
"""

from pathlib import Path
from app.audit_logger import log_audit_event, apply_retention_policy, read_audit_events
from scripts.query_audit import filter_events


def test_log_audit_event_schema(tmp_path: Path):
    audit_file = tmp_path / "test_audit.jsonl"
    record = log_audit_event(
        actor="student_test",
        action="PROMPT_ACCESS",
        resource="prompt:day13-chat:v1",
        status="SUCCESS",
        details={"version": 1, "label": "production"},
        client_ip="127.0.0.1",
        audit_file=audit_file,
    )

    assert record["actor"] == "student_test"
    assert record["action"] == "PROMPT_ACCESS"
    assert record["resource"] == "prompt:day13-chat:v1"
    assert record["status"] == "SUCCESS"
    assert record["audit_id"].startswith("aud-")
    assert "ts" in record

    # Verify written to disk
    events = read_audit_events(audit_file)
    assert len(events) == 1
    assert events[0]["audit_id"] == record["audit_id"]


def test_audit_retention_policy(tmp_path: Path):
    audit_file = tmp_path / "test_retention.jsonl"
    # Write 15 events
    for i in range(15):
        log_audit_event(
            actor="admin",
            action="INCIDENT_TOGGLE",
            resource=f"incident:test_{i}",
            status="SUCCESS",
            audit_file=audit_file,
        )

    assert len(read_audit_events(audit_file)) == 15

    # Retain only 5
    pruned = apply_retention_policy(max_records=5, audit_file=audit_file)
    assert pruned == 10

    retained = read_audit_events(audit_file)
    assert len(retained) == 5
    # Ensure newest records are kept
    assert retained[-1]["resource"] == "incident:test_14"


def test_query_filter():
    events = [
        {"action": "PROMPT_ACCESS", "actor": "user1", "status": "SUCCESS"},
        {"action": "INCIDENT_TOGGLE", "actor": "admin", "status": "SUCCESS"},
        {"action": "PROMPT_ACCESS", "actor": "user2", "status": "DENIED"},
    ]

    filtered_action = filter_events(events, action="PROMPT_ACCESS")
    assert len(filtered_action) == 2

    filtered_denied = filter_events(events, status="DENIED")
    assert len(filtered_denied) == 1
    assert filtered_denied[0]["actor"] == "user2"
