#!/usr/bin/env python3
"""
Send Trading Report via Email

Sends the final.md report as an HTML email using Gmail SMTP or
Google Workspace MCP integration.

Environment Variables:
- EMAIL_RECIPIENT: Email address to send the report to
- SMTP_SERVER: SMTP server (default: smtp.gmail.com)
- SMTP_PORT: SMTP port (default: 587)
- EMAIL_USERNAME: SMTP username (your Gmail)
- EMAIL_PASSWORD: App password (not your regular password)

For Gmail:
1. Enable 2FA on your Google account
2. Create an App Password: https://myaccount.google.com/apppasswords
3. Use that app password as EMAIL_PASSWORD

Usage:
    python send_report.py <run_dir>
    python send_report.py <run_dir> --preview  # Show email content without sending
"""

import json
import sys
import os
import smtplib
import markdown
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_optional(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return _load_json(path)
    except Exception:
        return None


def _generate_email_subject(run_dir: Path) -> str:
    """Generate email subject based on decision."""
    decision = _load_optional(run_dir / "decision.json")
    health = _load_optional(run_dir / "data_health.json")

    asof = (health or {}).get("last_trading_day", run_dir.name)

    if not decision:
        return f"Trading Signal - {asof} - NO DATA"

    action = decision.get("action", "UNKNOWN")
    if action == "NO_TRADE":
        reason = decision.get("reason", "")
        if "regime" in reason.lower():
            return f"Trading Signal - {asof} - NO TRADE (Market Regime)"
        elif "conviction" in reason.lower():
            return f"Trading Signal - {asof} - NO TRADE (Low Conviction)"
        else:
            return f"Trading Signal - {asof} - NO TRADE"
    else:
        symbol = decision.get("symbol", "?")
        grade = decision.get("grade", "?")
        conviction = decision.get("conviction", 0)
        return f"Trading Signal - {asof} - {action} {symbol} ({grade}, {conviction}/100)"


def _generate_email_html(run_dir: Path) -> str:
    """Convert final.md to HTML email."""
    report_path = run_dir / "final.md"

    if not report_path.exists():
        return "<p>Report not found</p>"

    with open(report_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert markdown to HTML
    try:
        html_body = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code"]
        )
    except Exception:
        # Fallback: wrap in pre tag
        html_body = f"<pre>{md_content}</pre>"

    # Wrap in email template
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1 {{
                color: #1a1a2e;
                border-bottom: 2px solid #4a4e69;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #22223b;
                margin-top: 30px;
            }}
            h3 {{
                color: #4a4e69;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
                font-weight: 600;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            code {{
                background-color: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            .buy {{
                color: #28a745;
                font-weight: bold;
            }}
            .sell {{
                color: #dc3545;
                font-weight: bold;
            }}
            hr {{
                border: none;
                border-top: 1px solid #ddd;
                margin: 30px 0;
            }}
            em {{
                color: #666;
            }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    return html


def send_email_smtp(
    recipient: str,
    subject: str,
    html_body: str,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    username: str = None,
    password: str = None
) -> bool:
    """Send email via SMTP."""
    if not username or not password:
        print("SMTP credentials not provided")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = recipient

    # Attach HTML version
    html_part = MIMEText(html_body, "html")
    msg.attach(html_part)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"SMTP send failed: {e}")
        return False


def send_report(run_dir: Path, preview: bool = False) -> bool:
    """
    Send the trading report via email.

    Args:
        run_dir: Path to the run directory
        preview: If True, print email content without sending

    Returns:
        True if sent successfully, False otherwise
    """
    print(f"Preparing email report for: {run_dir.name}")

    # Generate email content
    subject = _generate_email_subject(run_dir)
    html_body = _generate_email_html(run_dir)

    print(f"Subject: {subject}")

    if preview:
        print("\n" + "="*60)
        print("EMAIL PREVIEW")
        print("="*60)
        print(f"To: [EMAIL_RECIPIENT env var]")
        print(f"Subject: {subject}")
        print("="*60)

        # Print markdown version for readability
        report_path = run_dir / "final.md"
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                print(f.read())
        print("="*60)
        return True

    # Get email configuration from environment
    recipient = os.environ.get("EMAIL_RECIPIENT")
    if not recipient:
        print("EMAIL_RECIPIENT not set in environment")
        return False

    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("EMAIL_USERNAME")
    password = os.environ.get("EMAIL_PASSWORD")

    if not username or not password:
        print("EMAIL_USERNAME or EMAIL_PASSWORD not set")
        print("Set these environment variables or use --preview mode")
        return False

    # Send via SMTP
    print(f"Sending to: {recipient}")
    success = send_email_smtp(
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        username=username,
        password=password
    )

    if success:
        print("Email sent successfully!")
    else:
        print("Failed to send email")

    return success


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Send trading report via email')
    parser.add_argument('run_dir', type=str, help='Path to run directory')
    parser.add_argument('--preview', action='store_true', help='Preview email without sending')
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"Error: Run directory does not exist: {run_dir}")
        sys.exit(1)

    success = send_report(run_dir, preview=args.preview)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
