# email_utils.py — Send via SendGrid Web API (no SMTP), fail-safe
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = (
    os.getenv("SENDGRID_API_KEY") or os.getenv("SMTP_PASS")  # reuse your existing key
)
EMAIL_FROM = os.getenv("EMAIL_FROM") or "no-reply@example.com"

def send_password_reset_email(to_email: str, reset_url: str):
    if not SENDGRID_API_KEY:
        logger.info("[DEV] Password reset link for %s: %s", to_email, reset_url)
        return

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": "Reset your password — Son of Mervan",
        "content": [{
            "type": "text/plain",
            "value": (
                "You requested a password reset for your Son of Mervan account.\n\n"
                f"Click the link below to set a new password:\n{reset_url}\n\n"
                "This link expires in 60 minutes. If you did not request this, you can safely ignore this email."
            ),
        }],
    }

    try:
        logger.debug("[SG] POST /v3/mail/send (password reset) from=%s to=%s", EMAIL_FROM, to_email)
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("[SG] accepted (%d) to=%s", r.status_code, to_email)
        else:
            logger.error("[SG] ERROR %d: %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("[SG] EXCEPTION sending password reset to %s: %s", to_email, e)


def send_account_deletion_email(to_email: str):
    if not SENDGRID_API_KEY:
        logger.info("[DEV] Account deletion confirmation sent to %s", to_email)
        return

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": "Account deletion scheduled — Son of Mervan",
        "content": [{
            "type": "text/plain",
            "value": (
                "Your Son of Mervan account has been scheduled for deletion.\n\n"
                "Your account and all associated data will be permanently removed after 30 days.\n\n"
                "If you did not request this, please contact support immediately."
            ),
        }],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("[SG] deletion confirmation accepted (%d) to=%s", r.status_code, to_email)
        else:
            logger.error("[SG] ERROR %d: %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("[SG] EXCEPTION sending deletion email to %s: %s", to_email, e)


def send_budget_alert_email(
    to_email: str,
    category: str,
    pct: float,
    actual: float,
    planned: float,
    month: str,
):
    """Send a budget alert email when a category threshold is breached."""
    if not SENDGRID_API_KEY:
        logger.info(
            "[DEV] Budget alert: %s reached %.1f%% (£%.2f / £%.2f) in %s",
            category, pct, actual, planned, month,
        )
        return

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": f"Budget Alert: {category} spending at {pct:.0f}% — Son of Mervan",
        "content": [{
            "type": "text/plain",
            "value": (
                f"Hi,\n\n"
                f"This is a heads-up that your {category} spending for {month} has reached "
                f"{pct:.1f}% of your planned budget.\n\n"
                f"  Actual spent:  £{actual:.2f}\n"
                f"  Planned budget: £{planned:.2f}\n\n"
                f"Log in to Son of Mervan to review your spending and adjust your plan if needed.\n\n"
                f"You can manage your alert thresholds in the Alerts section of the app."
            ),
        }],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("[SG] budget alert accepted (%d) to=%s", r.status_code, to_email)
        else:
            logger.error("[SG] budget alert ERROR %d: %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("[SG] EXCEPTION sending budget alert to %s: %s", to_email, e)


def send_monthly_digest_email(
    to_email: str,
    month: str,
    income: float,
    total_spent: float,
    savings_rate: float,
    top_categories: list[tuple[str, float]],
    over_budget: list[str],
    currency: str = "GBP",
):
    """
    Send the monthly budget digest email.

    Args:
        to_email: recipient address
        month: "YYYY-MM" label (e.g. "2026-03")
        income: planned/actual salary for the month
        total_spent: total actual spending
        savings_rate: percentage of income saved (0–100)
        top_categories: [(category_name, amount), …] sorted descending, max 3
        over_budget: list of category names where actual > planned
        currency: ISO 4217 code for the currency symbol label
    """
    if not SENDGRID_API_KEY:
        logger.info(
            "[DEV] Monthly digest for %s — month=%s income=%.2f spent=%.2f savings=%.1f%%",
            to_email, month, income, total_spent, savings_rate,
        )
        return

    # Build plain-text body
    top_lines = "\n".join(
        f"  {i+1}. {cat}: {currency} {amt:.2f}"
        for i, (cat, amt) in enumerate(top_categories[:3])
    )
    over_lines = (
        "  " + ", ".join(over_budget)
        if over_budget
        else "  None — great work!"
    )
    body = (
        f"Hi,\n\n"
        f"Here's your spending summary for {month}:\n\n"
        f"  Income:       {currency} {income:.2f}\n"
        f"  Total spent:  {currency} {total_spent:.2f}\n"
        f"  Savings rate: {savings_rate:.1f}%\n\n"
        f"Top 3 categories by spend:\n{top_lines}\n\n"
        f"Over-budget categories:\n{over_lines}\n\n"
        f"Log in to Son of Mervan to dive deeper into your finances.\n\n"
        f"To stop receiving these digests, go to Account Settings → Email Digest and turn it off."
    )

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": f"Your {month} budget digest — Son of Mervan",
        "content": [{"type": "text/plain", "value": body}],
    }

    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("[SG] digest accepted (%d) to=%s month=%s", r.status_code, to_email, month)
        else:
            logger.error("[SG] digest ERROR %d: %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("[SG] EXCEPTION sending digest to %s: %s", to_email, e)


def send_verification_email(to_email: str, verify_url: str):
    # If no key set, behave like dev: log link and return
    if not SENDGRID_API_KEY:
        logger.info("[DEV] Verification link for %s: %s", to_email, verify_url)
        return

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": EMAIL_FROM},
        "subject": "Verify your email — Son of Mervan",
        "content": [{
            "type": "text/plain",
            "value": (
                "Welcome to Son of Mervan!\n\n"
                f"Please verify your email by clicking the link below:\n{verify_url}\n\n"
                "This link expires in 60 minutes."
            ),
        }],
    }

    try:
        logger.debug("[SG] POST /v3/mail/send from=%s to=%s", EMAIL_FROM, to_email)
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code in (200, 202):
            logger.info("[SG] accepted (%d) to=%s", r.status_code, to_email)
        else:
            logger.error("[SG] ERROR %d: %s", r.status_code, r.text)
            # don't crash signup if email fails
    except Exception as e:
        logger.exception("[SG] EXCEPTION sending to %s: %s", to_email, e)
        # don't raise — keep signup successful
