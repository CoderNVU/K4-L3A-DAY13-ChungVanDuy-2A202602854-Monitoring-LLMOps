#!/usr/bin/env python3
"""
CLI Tool for querying and analyzing Dedicated Audit Logs (Bonus Track 2).
Usage:
  python scripts/query_audit.py
  python scripts/query_audit.py --action INCIDENT_TOGGLE
  python scripts/query_audit.py --actor admin
  python scripts/query_audit.py --status SUCCESS
  python scripts/query_audit.py --summary
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add workspace to path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.audit_logger import read_audit_events, apply_retention_policy, AUDIT_LOG_FILE


def filter_events(
    events: List[Dict[str, Any]],
    action: str = None,
    actor: str = None,
    status: str = None,
) -> List[Dict[str, Any]]:
    filtered = []
    for ev in events:
        if action and ev.get("action") != action:
            continue
        if actor and ev.get("actor") != actor:
            continue
        if status and ev.get("status") != status:
            continue
        filtered.append(ev)
    return filtered


def print_summary(events: List[Dict[str, Any]]):
    print("=" * 60)
    print("📊 AUDIT LOG SUMMARY REPORT")
    print(f"Total Audit Records: {len(events)}")
    print("=" * 60)

    # Action counts
    action_counts = {}
    status_counts = {}
    actor_counts = {}

    for ev in events:
        act = ev.get("action", "UNKNOWN")
        st = ev.get("status", "UNKNOWN")
        ac = ev.get("actor", "UNKNOWN")
        action_counts[act] = action_counts.get(act, 0) + 1
        status_counts[st] = status_counts.get(st, 0) + 1
        actor_counts[ac] = actor_counts.get(ac, 0) + 1

    print("\n[Breakdown by Action]:")
    for act, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {act:<25} : {count} events")

    print("\n[Breakdown by Status]:")
    for st, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {st:<25} : {count} events")

    print("\n[Breakdown by Actor]:")
    for ac, count in sorted(actor_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {ac:<25} : {count} events")
    print("=" * 60)


def print_events(events: List[Dict[str, Any]], limit: int = 20):
    print("=" * 80)
    print(f"AUDIT LOG EVENTS (Showing {min(len(events), limit)} of {len(events)})")
    print("=" * 80)
    print(f"{'TIMESTAMP (UTC)':<24} | {'AUDIT_ID':<12} | {'ACTION':<18} | {'ACTOR':<12} | {'STATUS':<7} | RESOURCE")
    print("-" * 80)

    for ev in events[-limit:]:
        ts = ev.get("ts", "")[:19]
        aid = ev.get("audit_id", "")
        act = ev.get("action", "")[:18]
        actor = ev.get("actor", "")[:12]
        st = ev.get("status", "")[:7]
        res = ev.get("resource", "")
        print(f"{ts:<24} | {aid:<12} | {act:<18} | {actor:<12} | {st:<7} | {res}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Query dedicated audit logs.")
    parser.add_argument("--action", help="Filter by action name")
    parser.add_argument("--actor", help="Filter by actor")
    parser.add_argument("--status", help="Filter by status (SUCCESS, DENIED, FAILED)")
    parser.add_argument("--limit", type=int, default=20, help="Max records to display")
    parser.add_argument("--summary", action="store_true", help="Print summary breakdown")
    parser.add_argument("--prune", type=int, help="Enforce retention policy with max records")
    args = parser.parse_args()

    if args.prune:
        pruned = apply_retention_policy(max_records=args.prune)
        print(f"[RETENTION] Pruned {pruned} old audit record(s). Retained max {args.prune} records.")

    events = read_audit_events()
    filtered = filter_events(events, action=args.action, actor=args.actor, status=args.status)

    if args.summary:
        print_summary(filtered)
    else:
        print_events(filtered, limit=args.limit)


if __name__ == "__main__":
    main()
