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
