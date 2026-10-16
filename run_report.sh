#!/usr/bin/env bash
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "=========================================================="
echo "24x7 ON Court Kerala — Monthly Performance Report System"
echo "=========================================================="

# 1. Check 7-Day Generation Cadence
# If a report was generated within the last 7 days, skip unless --force / -f is passed
if ! python3 SRC/check_report_cadence.py "$@"; then
    exit 0
fi

# 2. Derive DDMMYY date tag for today (e.g. 161026 for 16 Oct 2026)
DATE_TAG=$(date +"%d%m%y")
export REPORT_DATE_TAG="$DATE_TAG"

# Check execution mode
GENERATE_ONLY=0
for arg in "$@"; do
    if [ "$arg" == "--generate-only" ]; then
        GENERATE_ONLY=1
        break
    fi
done

if [ "$GENERATE_ONLY" -eq 1 ]; then
    echo "[*] Mode: Report Generation Only (Using existing DATA/)"
    python3 SRC/generate_checklist_htmls.py --all
else
    echo "[*] Mode: Full Pipeline (1. Live Data Extraction -> 2. Report Generation)"
    echo "[*] Step 1/2: Extracting fresh checklist datasets from Metabase..."
    python3 SRC/extract_monthly_checklist_data.py "$@"
    echo "[*] Step 2/2: Generating interactive HTML views & executive report..."
    python3 SRC/generate_checklist_htmls.py --all
fi

echo ""
echo "=========================================================="
echo "Report generation complete!"
echo "Master HTML Report: OUTPUT/monthly_case_performance_report_${DATE_TAG}.html"
if [ -f "OUTPUT/monthly_case_performance_note_${DATE_TAG}.md" ]; then
    echo "Markdown Briefing:  OUTPUT/monthly_case_performance_note_${DATE_TAG}.md"
fi
echo "Interactive Views:  OUTPUT/CHECKLIST_VIEWS/ (20 Views)"
echo "=========================================================="
