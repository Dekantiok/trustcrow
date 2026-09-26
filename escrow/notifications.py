import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15


def send_otp_via_termii(email, otp_code):
    if settings.DEBUG:
        # Never emit a live credential to stdout; the dev banner is opt-in.
        if getattr(settings, 'LOG_OTP_TO_CONSOLE', False):
            logger.warning("DEVELOPMENT OTP for %s: %s", email, otp_code)
        return True

    api_key = getattr(settings, 'TERMII_API_KEY', 'dummy_key')
    email_config_id = getattr(settings, 'TERMII_EMAIL_CONFIG_ID', 'default_config')
    
    url = "https://api.ng.termii.com/api/email/otp/send"
    
    payload = {
        "api_key": api_key,
        "email_address": email,
        "pin_attempts": 3,
        "pin_time_to_live": 15,
        "pin_length": 6,
        "pin_type": "NUMERIC",
        "channel": "email",
        "pin_placeholder": "<pin>",
        "message_text": "Your Trustcrow verification code is <pin>. It is valid for 15 minutes.",
        "email_configuration_id": email_config_id
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=getattr(settings, 'GATEWAY_HTTP_TIMEOUT', DEFAULT_TIMEOUT),
        )
        response_data = response.json()
        if response_data.get("code") != "ok":
            logger.error("Termii rejected OTP for %s: %s", email, response_data.get("message"))
        return response_data.get("code") == "ok"
    except Exception:
        logger.exception("Termii OTP delivery failed for %s", email)
        return False