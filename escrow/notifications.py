import requests
from django.conf import settings

def send_otp_via_termii(email, otp_code):
    api_key = getattr(settings, 'TERMII_API_KEY', 'dummy_key')
    email_config_id = getattr(settings, 'TERMII_EMAIL_CONFIG_ID', 'default_config')
    
    url = "https://api.ng.termii.com/api/email/otp/send"
    payload = {
        "api_key": api_key,
        "email_address": email,
        "code": otp_code,
        "email_configuration_id": email_config_id
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False