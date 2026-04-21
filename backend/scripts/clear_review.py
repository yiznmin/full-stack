"""
Called by reviewer sub-agent after completing review.
Verdict determines whether the Edit/Write lock is cleared.

Usage:
  python scripts/clear_review.py pass "brief reason: no critical issues"
  python scripts/clear_review.py fail "auth missing on /admin/users, token not hashed"

Exit codes:
  0 = pass (lock cleared, Claude can continue)
  1 = fail (lock cleared so Claude can fix issues, quality_check.py will re-lock after next run)
"""
import sys
from datetime import datetime
from pathlib import Path

MARKER = Path(__file__).parent / ".needs_review"
REVIEWS_DIR = Path(__file__).parent.parent.parent / ".claude" / "reviews"


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("pass", "fail"):
        print("Usage: clear_review.py pass|fail [summary]")
        print("  pass = no critical issues, lock cleared")
        print("  fail = critical issues found, lock remains")
        sys.exit(1)

    verdict = sys.argv[1]
    summary = sys.argv[2] if len(sys.argv) > 2 else "(no summary provided)"
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")

    # Save review record regardless of verdict
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    record_path = REVIEWS_DIR / f"{timestamp}-{verdict}.md"
    record_path.write_text(
        f"# Review {timestamp}\n\n**Verdict**: {verdict.upper()}\n\n**Summary**: {summary}\n",
        encoding="utf-8",
    )

    if verdict == "pass":
        MARKER.unlink(missing_ok=True)
        print("Review PASSED — lock cleared. Edit/Write tools are now unblocked.")
        print(f"Record saved: {record_path.name}")
        sys.exit(0)
    else:
        MARKER.unlink(missing_ok=True)
        print("Review FAILED — lock cleared so you can fix issues.")
        print(f"Issues: {summary}")
        print("Fix the above issues, re-run quality_check.py, then /reviewer again.")
        print(f"Record saved: {record_path.name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
