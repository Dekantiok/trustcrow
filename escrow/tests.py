from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from decimal import Decimal
from .models import EscrowContract, AuthOTP, SettlementVault
from .services import calculate_service_fee
from .utils import generate_secure_code, generate_otp

class ServiceFeeTest(TestCase):
    def test_fee_tiers(self):
        self.assertEqual(calculate_service_fee(10000), Decimal('1500'))
        self.assertEqual(calculate_service_fee(50000), Decimal('1500'))
        self.assertEqual(calculate_service_fee(75000), Decimal('2000'))
        self.assertEqual(calculate_service_fee(100000), Decimal('2000'))
        self.assertEqual(calculate_service_fee(250000), Decimal('2500'))
        self.assertEqual(calculate_service_fee(750000), Decimal('5000'))
        self.assertEqual(calculate_service_fee(1500000), Decimal('10000'))

class UtilsTest(TestCase):
    def test_code_generation(self):
        code = generate_secure_code(9)
        self.assertEqual(len(code), 9)
        self.assertTrue(code.isalnum())

    def test_otp_generation(self):
        otp = generate_otp(6)
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

class ContractFlowTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch('escrow.views.send_otp_via_termii')
    def test_create_contract_and_verify(self, mock_termii):
        mock_termii.return_value = True
        payload = {
            'title': 'Test Item', 'description': 'Test desc', 'amount': '50000.00',
            'fee_payer': 'buyer', 'creator_email': 'buyer@test.com', 'creator_role': 'buyer',
            'counterparty_email': 'seller@test.com', 'inspection_days': 3
        }
        response = self.client.post(reverse('create_contract'), payload)
        self.assertEqual(response.status_code, 302)
        
        contract = EscrowContract.objects.get(creator_email='buyer@test.com')
        self.assertEqual(contract.status, 'pending_verification')
        self.assertEqual(contract.service_fee, Decimal('1500.00'))
        self.assertEqual(len(contract.code), 9)

        otp = AuthOTP.objects.get(email='buyer@test.com', intent='create')
        response = self.client.post(reverse('verify_otp', kwargs={'code': contract.code}), {'otp': otp.otp_code})
        self.assertEqual(response.status_code, 302)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'awaiting_counterparty')

    @patch('escrow.views.send_otp_via_termii')
    def test_join_escrow_and_verify(self, mock_termii):
        mock_termii.return_value = True
        contract = EscrowContract.objects.create(
            code='TESTCODE1', title='Test', description='Test', amount=Decimal('10000.00'),
            service_fee=Decimal('1500.00'), fee_payer='buyer', creator_email='buyer@test.com',
            creator_role='buyer', counterparty_email='seller@test.com', status='awaiting_counterparty'
        )
        response = self.client.post(reverse('join_escrow_page'), {'code': 'TESTCODE1', 'email': 'seller@test.com'})
        self.assertEqual(response.status_code, 302)

        otp = AuthOTP.objects.get(email='seller@test.com', intent='join')
        response = self.client.post(reverse('counterparty_verify_otp', kwargs={'code': contract.code}), {'otp': otp.otp_code})
        self.assertEqual(response.status_code, 302)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'awaiting_funding')

    def test_join_escrow_wrong_email(self):
        EscrowContract.objects.create(
            code='TESTCODE2', title='Test', description='Test', amount=Decimal('10000.00'),
            service_fee=Decimal('1500.00'), fee_payer='buyer', creator_email='buyer@test.com',
            creator_role='buyer', counterparty_email='seller@test.com', status='awaiting_counterparty'
        )
        response = self.client.post(reverse('join_escrow_page'), {'code': 'TESTCODE2', 'email': 'wrong@test.com'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'does not match the counterparty')

    def test_payment_restricted_to_buyer(self):
        contract = EscrowContract.objects.create(
            code='TESTCODE3', title='Test', description='Test', amount=Decimal('10000.00'),
            service_fee=Decimal('1500.00'), fee_payer='buyer', creator_email='buyer@test.com',
            creator_role='buyer', counterparty_email='seller@test.com', status='awaiting_funding',
            gateway_reference='REF123'
        )
        session = self.client.session
        session['active_email'] = 'seller@test.com'
        session.save()
        response = self.client.get(reverse('initiate_payment', kwargs={'code': contract.code}))
        self.assertEqual(response.status_code, 403)

class WebhookAndPayoutTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.contract = EscrowContract.objects.create(
            code='TESTCODE4', title='Test', description='Test', amount=Decimal('10000.00'),
            service_fee=Decimal('1500.00'), fee_payer='buyer', creator_email='buyer@test.com',
            creator_role='buyer', counterparty_email='seller@test.com', status='awaiting_funding',
            gateway_reference='WEBHOOK_REF'
        )

    @patch('escrow.views.get_payment_gateway')
    def test_paystack_webhook_success(self, mock_gateway):
        mock_instance = mock_gateway.return_value
        mock_instance.verify_incoming_webhook.return_value = {
            'event': 'charge.success', 'data': {'reference': 'WEBHOOK_REF'}
        }
        response = self.client.post(
            reverse('paystack_webhook'), data=b'{"event": "charge.success"}',
            content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE='dummy_sig'
        )
        self.assertEqual(response.status_code, 200)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, 'in_inspection')
        self.assertIsNotNone(self.contract.inspection_ends)

    def test_buyer_confirm_and_seller_payout(self):
        self.contract.status = 'in_inspection'
        self.contract.save()

        session = self.client.session
        session['active_email'] = 'buyer@test.com'
        session.save()
        self.client.post(reverse('buyer_confirm_delivery', kwargs={'code': self.contract.code}))
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, 'pending_payout')
        self.assertTrue(self.contract.buyer_confirmed)

        SettlementVault.objects.create(
            contract=self.contract, bank_name='Test Bank', bank_code='058',
            account_number='1234567890', account_name='Test Seller'
        )

        session['active_email'] = 'seller@test.com'
        session.save()

        with patch('escrow.views.get_payment_gateway') as mock_gateway:
            mock_instance = mock_gateway.return_value
            mock_instance.execute_seller_payout.return_value = {'status': True}
            self.client.post(reverse('trigger_payout', kwargs={'code': self.contract.code}))
            self.contract.refresh_from_db()
            self.assertEqual(self.contract.status, 'completed')