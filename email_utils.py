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
