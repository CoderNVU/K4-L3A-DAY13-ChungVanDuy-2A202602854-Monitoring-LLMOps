"""
Unit tests for Automated Secret & PII Scanner (Bonus Track 1).
"""

from pathlib import Path
from scripts.scan_secrets_pii import scan_file_for_secrets, check_git_tracked_sensitive_files


def test_scanner_detects_secret_key(tmp_path: Path):
    test_file = tmp_path / "leak.py"
    dummy_key = "sk-lf-" + "0123456789abcdef" * 2
    test_file.write_text(f"API_SECRET = '{dummy_key}'\n", encoding="utf-8")
    
    findings = scan_file_for_secrets(test_file)
    assert len(findings) == 1
    assert findings[0][1] == "SECRET"
    assert "Langfuse Secret Key" in findings[0][2]


def test_scanner_allows_redacted_pii(tmp_path: Path):
    clean_file = tmp_path / "clean_log.json"
    clean_file.write_text('{"user_email": "[REDACTED_EMAIL]", "phone": "[REDACTED_PHONE]"}\n', encoding="utf-8")
    
    findings = scan_file_for_secrets(clean_file)
    assert len(findings) == 0


def test_scanner_flags_unredacted_card(tmp_path: Path):
    bad_file = tmp_path / "leaked_card.json"
    bad_file.write_text('{"payment": "Customer paid with 9876-5432-1098-7654 today"}\n', encoding="utf-8")
    
    findings = scan_file_for_secrets(bad_file)
    assert len(findings) >= 1
    assert any("Credit Card" in f[2] for f in findings)


def test_git_sensitive_files_check():
    # .env and config/challenge.json must NOT be tracked
    repo_root = Path(__file__).resolve().parent.parent
    violations = check_git_tracked_sensitive_files(repo_root)
    assert len(violations) == 0, f"Sensitive files tracked in git: {violations}"
