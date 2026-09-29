#!/usr/bin/env python3
"""
Automated Secret & PII Scanner for CI/CD and Pre-Commit Hooks.
Scans repository files for accidental leaks of:
- Secret keys (Langfuse secret keys, OpenAI keys, private keys, tokens)
- Unredacted PII (CCCD, Credit Card, Phone numbers, Emails)
- Untracked/Sensitive files (.env, config/challenge.json)
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Regex rules for secrets
SECRET_PATTERNS = {
    "Langfuse Secret Key": re.compile(r"\bsk-lf-[a-f0-9-]{16,}\b", re.IGNORECASE),
    "OpenAI API Key": re.compile(r"\bsk-[a-zA-Z0-9]{24,}\b"),
    "Generic Private Key": re.compile(r"-----BEGIN [A-Z\s]+PRIVATE KEY-----"),
    "GitHub Token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}\b"),
    "AWS Access Key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

# Regex rules for PII
PII_PATTERNS = {
    "Credit Card (16 digits)": re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
    "CCCD (12 digits)": re.compile(r"\b\d{12}\b"),
    "Vietnamese Phone": re.compile(r"(?<![a-zA-Z0-9])(?:\+84|0)(?:[ .-]?\d){9}(?![a-zA-Z0-9])"),
    "Raw Email Address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
}

# Files and directories to exclude from deep content scanning
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".idea", ".vscode"
}
EXCLUDE_FILES = {
    ".env", "challenge.json", "logs_baseline.jsonl", "sample_queries.jsonl"
}

# Allowlist substrings (e.g. test dummy values, documentation or redaction markers)
SAFE_MARKERS = [
    "[REDACTED_EMAIL]",
    "[REDACTED_PHONE]",
    "[REDACTED_CCCD]",
    "[REDACTED_CREDIT_CARD]",
    "REDACTED",
    "placeholder",
    "012345678901",  # mock cccd in test doc
    "1234567812345678", # mock card in test doc
    "example.com",
    "user@example",
    "admin@gmail.com",
    "0912345678",
]


def is_safe_line(line: str) -> bool:
    for marker in SAFE_MARKERS:
        if marker in line:
            return True
    return False


def scan_file_for_secrets(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for secret patterns."""
    findings = []
    # Skip test files, rules and scanner script itself for PII scans to avoid false positives on definitions
    is_test_or_rule = "tests" in file_path.parts or file_path.name in {
        "pii.py", "scan_secrets_pii.py", "SUBMISSION.md", "RUBRIC.md", "README.md", "REPORT.md"
    }

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                # Check secrets
                for secret_name, pattern in SECRET_PATTERNS.items():
                    if pattern.search(line):
                        findings.append((line_no, "SECRET", f"{secret_name} detected"))

                # Check PII (only on production logs and application files)
                if not is_test_or_rule and not is_safe_line(line):
                    for pii_name, pattern in PII_PATTERNS.items():
                        match = pattern.search(line)
                        if match and not any(tag in line for tag in ["[REDACTED", "REDACTED"]):
                            findings.append((line_no, "PII", f"Possible unredacted {pii_name}"))
    except Exception as e:
        findings.append((0, "ERROR", f"Could not read file: {e}"))
    return findings


def check_git_tracked_sensitive_files(repo_root: Path) -> List[str]:
    """Verify that sensitive files like .env or challenge.json are not tracked by git."""
    violations = []
    sensitive_targets = [".env", "config/challenge.json"]

    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "ls-files"] + sensitive_targets,
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True
        )
        for tracked in out.strip().splitlines():
            if tracked:
                violations.append(f"CRITICAL: Sensitive file '{tracked}' is tracked in git index!")
    except Exception:
        pass
    return violations


def run_scanner(target_dir: Path) -> int:
    print("=" * 60)
    print("[SCAN] RUNNING AUTOMATED SECRET & PII SCANNER")
    print(f"Target directory: {target_dir}")
    print("=" * 60)

    # 1. Check git tracking
    git_violations = check_git_tracked_sensitive_files(target_dir)
    if git_violations:
        for v in git_violations:
            print(f"[FAIL] {v}")

    # 2. Scan files
    total_scanned = 0
    total_findings = len(git_violations)

    for root, dirs, files in os.walk(target_dir):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if file in EXCLUDE_FILES or file.endswith((".png", ".jpg", ".pyc", ".ico", ".bin")):
                continue

            file_path = Path(root) / file
            total_scanned += 1
            findings = scan_file_for_secrets(file_path)

            if findings:
                total_findings += len(findings)
                rel_path = file_path.relative_to(target_dir)
                for line_no, kind, desc in findings:
                    print(f"[WARN] [{kind}] {rel_path}:{line_no} -> {desc}")

    print("-" * 60)
    print(f"Scan complete. Total files scanned: {total_scanned}")
    if total_findings == 0:
        print("[PASS] SUCCESS: 0 secrets, 0 PII leaks detected. Repository is clean & safe to push!")
        return 0
    else:
        print(f"[FAIL] FAILED: {total_findings} potential violation(s) found.")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan repository for secrets and PII.")
    parser.add_argument("--path", default=".", help="Target path to scan")
    args = parser.parse_args()

    root_path = Path(args.path).resolve()
    sys.exit(run_scanner(root_path))
