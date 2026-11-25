"""
Sends the 'forgot password' code by email, free, from your own Gmail.

Render's free servers block normal email ports (SMTP), so the server calls a
small Google Apps Script web app over HTTPS, and the script sends the email
with your Gmail (about 100 emails a day, free). The script is in
docs/send_email_apps_script.js, with setup steps.

Set on the server:
  MAIL_SCRIPT_URL     the web app address Google gives you (ends in /exec)
  MAIL_SCRIPT_SECRET  a long random word, the same one saved in the script

Without them (on your laptop) the code is printed in the server log, so you
can still test the whole flow.
"""

import html as html_text
import logging
import os

import requests

from backend.services.auth import RESET_MINUTES

log = logging.getLogger("uvicorn.error")


PURPOSES = {
    # (what the code is for, what happens if you ignore the email)
    "reset": ("reset your password", "Your password stays the same."),
    "verify": ("confirm your email for Real Estate AVM", "No account will be made with your email."),
}


def reset_email(name, code, purpose="reset"):
    """(subject, plain text, html) in short, simple words"""
    first = (name or "there").split()[0]
    what, ignore = PURPOSES[purpose]
    subject = "Your Real Estate AVM code: " + code
    text = ("Hi " + first + ",\n\n"
            "Your code to " + what + " is: " + code + "\n\n"
            "It works for " + str(RESET_MINUTES) + " minutes.\n"
            "If you did not ask for this, you can ignore this email. " + ignore + "\n\n"
            "Real Estate AVM")
    html = ("<div style=\"font-family:Arial,sans-serif;font-size:16px;color:#1f2d27\">"
            "<p>Hi " + html_text.escape(first) + ",</p>"
            "<p>Your code to " + what + " is:</p>"
            "<p style=\"font-size:32px;font-weight:bold;letter-spacing:6px\">" + code + "</p>"
            "<p>It works for " + str(RESET_MINUTES) + " minutes.</p>"
            "<p style=\"color:#5b6b63\">If you did not ask for this, you can ignore this email. "
            + ignore + "</p>"
            "<p>Real Estate AVM</p></div>")
    return subject, text, html


def email_configured():
    """True when the Google Apps Script settings are there (online)"""
    return bool(os.getenv("MAIL_SCRIPT_URL") and os.getenv("MAIL_SCRIPT_SECRET"))


def send_reset_code(email, name, code):
    _send(email, name, code, "reset")


def send_verify_code(email, name, code):
    _send(email, name, code, "verify")


def _send(email, name, code, purpose):
    url, secret = os.getenv("MAIL_SCRIPT_URL"), os.getenv("MAIL_SCRIPT_SECRET")
    if not url or not secret:
        log.warning("Email is not set up (MAIL_SCRIPT_URL, MAIL_SCRIPT_SECRET). %s code for %s: %s",
                    purpose.title(), email, code)
        return
    subject, text, html = reset_email(name, code, purpose)
    try:
        # Google answers with a redirect to the script's reply; requests follows it
        response = requests.post(
            url,
            json={"secret": secret, "to": email, "subject": subject, "text": text, "html": html},
            timeout=20,
        )
        response.raise_for_status()
        if response.text.strip() != "ok":
            raise requests.RequestException("script said: " + response.text.strip()[:200])
    except requests.RequestException as error:
        # logged for us; the user still sees the same message as always
        log.error("Could not send the %s email to %s: %s", purpose, email, error)
