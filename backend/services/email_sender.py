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
            "<p>Hi " + html_text.escape(first) + ",</p>"
            "<p>Your code to reset your password is:</p>"
            "<p style=\"font-size:32px;font-weight:bold;letter-spacing:6px\">" + code + "</p>"
            "<p>It works for " + str(RESET_MINUTES) + " minutes.</p>"
            "<p style=\"color:#5b6b63\">If you did not ask for this, you can ignore this email. "
            "Your password stays the same.</p>"
            "<p>Real Estate AVM</p></div>")
    return subject, text, html


def send_reset_code(email, name, code):
    url, secret = os.getenv("MAIL_SCRIPT_URL"), os.getenv("MAIL_SCRIPT_SECRET")
    if not url or not secret:
        log.warning("Email is not set up (MAIL_SCRIPT_URL, MAIL_SCRIPT_SECRET). Reset code for %s: %s", email, code)
        return
    subject, text, html = reset_email(name, code)
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
        log.error("Could not send the reset email to %s: %s", email, error)
