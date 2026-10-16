#!/usr/bin/env python3
"""
Report Cadence Validator for Monthly Performance Report System.

Checks if a performance report was already generated within the last N days
(default: 7 days). If so, exits with code 1 to prevent redundant execution,
unless overridden by the --force / -f flag.
"""

import os
import sys
import re
import argparse
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "OUTPUT")


def parse_report_date(filename):
    """
    Attempts to parse date from report filename:
    - monthly_case_performance_report_DDMMYY.html (e.g. 161026 -> 2026-10-16)
    - monthly_case_performance_report_YYYYMMDD.html (e.g. 20261016 -> 2026-10-16)
    - monthly_case_performance_report_YYYY-MM-DD.html
    - monthly_case_performance_report_MMYY.html (legacy e.g. 0926 -> 2026-09-26)
    """
    m = re.search(r"monthly_case_performance_report_(\d{6})\.html$", filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d%m%y")
        except ValueError:
            pass

    m = re.search(r"monthly_case_performance_report_(\d{4}-\d{2}-\d{2})\.html$", filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    m = re.search(r"monthly_case_performance_report_(\d{8})\.html$", filename)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            pass

    m = re.search(r"monthly_case_performance_report_(\d{2})(\d{2})\.html$", filename)
    if m:
        # e.g. 0926 -> September 2026. Use 2026-09-26 as conservative date
        try:
            month = int(m.group(1))
            year = 2000 + int(m.group(2))
            return datetime(year, month, 26)
        except Exception:
            pass

    return None


def get_latest_report():
    if not os.path.exists(OUTPUT_DIR):
        return None

    reports = []
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("monthly_case_performance_report_") and f.endswith(".html"):
            full_path = os.path.join(OUTPUT_DIR, f)
            parsed_dt = parse_report_date(f)
            mtime_dt = datetime.fromtimestamp(os.path.getmtime(full_path))
            effective_dt = parsed_dt if parsed_dt else mtime_dt
            reports.append({
                "filename": f,
                "path": full_path,
                "parsed_dt": parsed_dt,
                "mtime_dt": mtime_dt,
                "effective_dt": effective_dt
            })

    if not reports:
        return None

    reports.sort(key=lambda r: r["effective_dt"], reverse=True)
    return reports[0]


def main():
    parser = argparse.ArgumentParser(description="Check report generation cadence")
    parser.add_argument("--days", type=int, default=7, help="Minimum days required between reports (default: 7)")
    parser.add_argument("--force", "-f", action="store_true", help="Force rerun regardless of cadence")
    parser.add_argument("--check-only", action="store_true", help="Only check and print status, do not exit with error")
    args, unknown = parser.parse_known_args()

    # If --force or -f is anywhere in sys.argv, honor it
    if "--force" in sys.argv or "-f" in sys.argv:
        args.force = True

    if args.force:
        print("[*] Cadence check: --force flag detected. Bypassing 7-day interval check.")
        return 0

    latest = get_latest_report()
    if not latest:
        print("[*] Cadence check: No previous reports found in OUTPUT/. Proceeding with generation.")
        return 0

    now = datetime.now()
    diff = now - latest["effective_dt"]
    days_since = diff.total_seconds() / 86400.0

    if days_since < args.days:
        next_run_dt = latest["effective_dt"] + timedelta(days=args.days)
        print("\n==========================================================")
        print("[!] 7-DAY CADENCE CHECK: Report generation throttled.")
        print("==========================================================")
        print(f"[*] Last report generated : OUTPUT/{latest['filename']}")
        print(f"[*] Report date           : {latest['effective_dt'].strftime('%Y-%m-%d')} ({days_since:.1f} days ago)")
        print(f"[*] Cadence policy        : Minimum {args.days} days required between full runs")
        print(f"[*] Next eligible run     : {next_run_dt.strftime('%Y-%m-%d')} (in {args.days - days_since:.1f} days)")
        print("[*] Status                : SKIPPING execution (within 7-day window).")
        print("[*]")
        print("[*] To override and generate a fresh report anyway, run:")
        print("    bash run_report.sh --force")
        print("==========================================================\n")
        if args.check_only:
            return 0
        return 1
    else:
        print(f"[*] Cadence check passed: Last report was {days_since:.1f} days ago (>= {args.days} days). Proceeding with generation.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
