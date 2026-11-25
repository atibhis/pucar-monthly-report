#!/usr/bin/env python3
"""
Email the Court Dashboard through Gmail SMTP: the email-summary HTML as the body and the full
dashboard attached. Credentials come from METABASE/.env (GMAIL_USER, GMAIL_APP_PASSWORD).

  python3 SRC/send_court_dashboard_email.py --dashboard OUTPUT/Court-Dashboard_<ts>.html \
      --body OUTPUT/Court-Dashboard_email_<ts>.html [--to "a@x.com, b@y.com"]

--to defaults to GMAIL_USER (send to yourself).
"""
import argparse
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(os.path.join(os.path.dirname(ROOT), ".env"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--to", help="comma-separated recipients (default: GMAIL_USER)")
    args = ap.parse_args()

    user, pw = os.environ.get("GMAIL_USER", "").strip(), os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not user or not pw:
        raise SystemExit("GMAIL_USER / GMAIL_APP_PASSWORD missing from METABASE/.env")
    to = [a.strip() for a in (args.to or user).split(",") if a.strip()]

    with open(os.path.join(ROOT, "DATA", "court_dashboard_data.json")) as f:
        meta = json.load(f)["meta"]
    body = open(args.body, encoding="utf-8").read()
    month = f"{meta['month_name']} {meta['reporting_month'][:4]}"

    msg = EmailMessage()
    msg["Subject"] = f"Court Dashboard — {month} (generated {meta['generated_at']})"
    msg["From"], msg["To"] = user, ", ".join(to)
    text = re.sub(r"\n\s*\n+", "\n\n", re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<head>.*?</head>", "", body)))
    msg.set_content(f"Court Dashboard — {month}\n\n" + re.sub(r"[ \t]+", " ", text).strip()
                    + "\n\nThe full dashboard is attached: open it in a browser.")
    msg.add_alternative(body, subtype="html")
    with open(args.dashboard, "rb") as f:
        msg.add_attachment(f.read(), maintype="text", subtype="html", filename=os.path.basename(args.dashboard))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"[✓] Email sent to {len(to)} recipient(s): {os.path.basename(args.dashboard)} attached "
          f"({os.path.getsize(args.dashboard) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
