"""
Sends the 'forgot password' code by email.

Render's free servers block normal email ports (SMTP), so we send through
Brevo's web API over HTTPS instead (free: 300 emails a day).

Set on the server:
  BREVO_API_KEY  the API key from Brevo (a secret)
  MAIL_FROM      the sender email, verified in Brevo

Without them (on your laptop) the code is printed in the server log, so you
can still test the whole flow.
"""

import logging
import os

import requests

from backend.services.auth import RESET_MINUTES

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
log = logging.getLogger("uvicorn.error")


def reset_email(name, code):
    """(subject, plain text, html) in short, simple words"""
    first = (name or "there").split()[0]
    subject = "Your Real Estate AVM code: " + code
    text = ("Hi " + first + ",\n\n"
            "Your code to reset your password is: " + code + "\n\n"
            "It works for " + str(RESET_MINUTES) + " minutes.\n"
            "If you did not ask for this, you can ignore this email. Your password stays the same.\n\n"
            "Real Estate AVM")
    html = ("<div style=\"font-family:Arial,sans-serif;font-size:16px;color:#1f2d27\">"
            "<p>Hi " + first + ",</p>"
            "<p>Your code to reset your password is:</p>"
            "<p style=\"font-size:32px;font-weight:bold;letter-spacing:6px\">" + code + "</p>"
            "<p>It works for " + str(RESET_MINUTES) + " minutes.</p>"
            "<p style=\"color:#5b6b63\">If you did not ask for this, you can ignore this email. "
            "Your password stays the same.</p>"
            "<p>Real Estate AVM</p></div>")
    return subject, text, html


def send_reset_code(email, name, code):
    key, sender = os.getenv("BREVO_API_KEY"), os.getenv("MAIL_FROM")
    if not key or not sender:
        log.warning("Email is not set up (BREVO_API_KEY, MAIL_FROM). Reset code for %s: %s", email, code)
        return
    subject, text, html = reset_email(name, code)
    try:
        response = requests.post(
            BREVO_URL,
            headers={"api-key": key, "accept": "application/json", "content-type": "application/json"},
            json={"sender": {"name": "Real Estate AVM", "email": sender},
                  "to": [{"email": email, "name": name}],
                  "subject": subject, "textContent": text, "htmlContent": html},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # logged for us; the user still sees the same message as always
        detail = getattr(getattr(error, "response", None), "text", "")
        log.error("Could not send the reset email to %s: %s %s", email, error, detail[:300])
