# email_utils.py — Send via SendGrid Web API (no SMTP), fail-safe
import os, json, requests

SENDGRID_API_KEY = (
    os.getenv("SENDGRID_API_KEY") or os.getenv("SMTP_PASS")  # reuse your existing key
)
EMAIL_FROM = os.getenv("EMAIL_FROM") or "no-reply@example.com"

def send_verification_email(to_email: str, verify_url: str):
    # If no key set, behave like dev: print link and return
    if not SENDGRID_API_KEY:
        print(f"[DEV] Verification link for {to_email}: {verify_url}")
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
        print(f"[SG] POST /v3/mail/send from={EMAIL_FROM} to={to_email}")
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
            print(f"[SG] accepted ({r.status_code})")
        else:
            print(f"[SG] ERROR {r.status_code}: {r.text}")
            # don’t crash signup if email fails
    except Exception as e:
        print(f"[SG] EXCEPTION: {e}")
        # don’t raise — keep signup successful
