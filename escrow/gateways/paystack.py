import requests
import hashlib
import hmac
import json
from django.conf import settings
from .base import PaymentGatewayBase

class PaystackGateway(PaymentGatewayBase):
    def __init__(self):
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_dummy')
        self.base_url = "https://api.paystack.co"

    def initialize_vault_payment(self, escrow_record, return_url):
        if escrow_record.fee_payer == 'buyer':
            total_amount = escrow_record.amount + escrow_record.service_fee
        else:
            total_amount = escrow_record.amount

        amount_in_kobo = int(total_amount * 100)
        payer_email = escrow_record.creator_email if escrow_record.creator_role == 'buyer' else escrow_record.counterparty_email

        payload = {
            "email": payer_email,
            "amount": amount_in_kobo,
            "reference": escrow_record.gateway_reference,
            "callback_url": return_url
        }
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(f"{self.base_url}/transaction/initialize", json=payload, headers=headers)
            data = response.json()
            return {"status": data.get("status"), "auth_url": data.get("data", {}).get("authorization_url")}
        except Exception as e:
            return {"status": False, "error": str(e)}

    def verify_incoming_webhook(self, request_headers, request_body):
        signature = request_headers.get('x-paystack-signature')
        if not signature:
            return False
            
        hash = hmac.new(
            self.secret_key.encode('utf-8'),
            request_body,
            digestmod=hashlib.sha512
        ).hexdigest()
        
        if hash != signature:
            return False
            
        return json.loads(request_body.decode('utf-8'))

    def execute_seller_payout(self, settlement_vault_record, total_disbursement):
        amount_in_kobo = int(total_disbursement * 100)
        payload = {
            "source": "balance",
            "amount": amount_in_kobo,
            "currency": "NGN",
            "recipient": settlement_vault_record.account_number 
        }
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(f"{self.base_url}/transfer", json=payload, headers=headers)
            return response.json()
        except Exception as e:
            return {"status": False, "error": str(e)}