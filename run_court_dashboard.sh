#!/usr/bin/env bash
# Live Court Dashboard: query Metabase -> DATA/court_dashboard_data.json
#   -> OUTPUT/Court-Dashboard_<DDMMYY_HHMM>.html        (full interactive dashboard)
#   -> OUTPUT/Court-Dashboard_email_<DDMMYY_HHMM>.html  (email-body summary)
#   ./run_court_dashboard.sh                         # reporting month = last complete month
#   ./run_court_dashboard.sh --month 2026-10
#   ./run_court_dashboard.sh --offline               # re-render from the last pull, no queries
#   ./run_court_dashboard.sh --send                  # ...and email it to yourself (GMAIL_USER)
#   ./run_court_dashboard.sh --send-to "a@x, b@y"    # ...and email it to these recipients
#   DASHBOARD_URL=https://host/path.html ./run_court_dashboard.sh   # once hosted: email links to it
set -e
cd "$(dirname "$0")"
SEND=""; TO=""; ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --send) SEND=1 ;;
    --send-to) SEND=1; TO="$2"; shift ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done
python3 SRC/extract_court_dashboard.py ${ARGS[@]+"${ARGS[@]}"}
python3 SRC/render_court_dashboard.py
DASH=$(ls -t OUTPUT/Court-Dashboard_[0-9]*_[0-9]*.html | head -1)
BODY="OUTPUT/Court-Dashboard_email_${DASH##*Court-Dashboard_}"
python3 SRC/render_email_body.py --dashboard "$DASH" ${DASHBOARD_URL:+--link "$DASHBOARD_URL"}
if [ -n "$SEND" ]; then
  python3 SRC/send_court_dashboard_email.py --dashboard "$DASH" --body "$BODY" ${TO:+--to "$TO"}
fi
