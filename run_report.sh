#!/usr/bin/env bash
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "=========================================================="
echo "24x7 ON Court Kerala — Monthly Performance Report System"
echo "=========================================================="

if [ "$1" == "--generate-only" ]; then
    echo "[*] Mode: Report Generation Only (Using existing DATA/)"
    python3 SRC/generate_checklist_htmls.py --all
else
    echo "[*] Mode: Full Pipeline (1. Live Data Extraction -> 2. Report Generation)"
    echo "[*] Step 1/2: Extracting fresh checklist datasets from Metabase..."
    python3 SRC/extract_monthly_checklist_data.py
    echo "[*] Step 2/2: Generating interactive HTML views & executive report..."
    python3 SRC/generate_checklist_htmls.py --all
fi

echo ""
echo "=========================================================="
echo "Report generation complete!"
echo "Master HTML Report: OUTPUT/monthly_case_performance_report.html"
echo "Markdown Briefing:  OUTPUT/monthly_case_performance_note.md"
echo "Interactive Views:  OUTPUT/CHECKLIST_VIEWS/ (20 Views)"
echo "=========================================================="
