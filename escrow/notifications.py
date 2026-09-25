from django.conf import settings
import requests

def send_otp_via_termii(email, otp_code):
    if settings.DEBUG:
        print(f"\n{'='*50}")
        print(f"DEVELOPMENT MODE: OTP FOR {email}")
        print(f"YOUR OTP IS: {otp_code}")
        print(f"{'='*50}\n")
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
        "message_text": f"Your Trustcrow verification code is <pin>. It is valid for 15 minutes.",
        "email_configuration_id": email_config_id
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        return response_data.get("code") == "ok"
    except Exception:
        return False