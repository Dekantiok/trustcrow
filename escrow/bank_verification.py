import requests
from django.conf import settings

MOCK_BANKS = {
    '044': 'Access Bank',
    '023': 'Citibank Nigeria',
    '063': 'Diamond Bank',
    '050': 'Ecobank Nigeria',
    '070': 'Fidelity Bank',
    '011': 'First Bank of Nigeria',
    '214': 'First City Monument Bank',
    '058': 'Guaranty Trust Bank',
    '030': 'Heritage Bank',
    '301': 'Jaiz Bank',
    '082': 'Keystone Bank',
    '014': 'Stanbic IBTC Bank',
    '232': 'Sterling Bank',
    '100': 'SunTrust Bank',
    '032': 'Union Bank of Nigeria',
    '033': 'United Bank for Africa',
    '215': 'Unity Bank',
    '035': 'Wema Bank',
    '057': 'Zenith Bank',
}

def verify_bank_account(account_number, bank_code):
    if settings.DEBUG:
        if account_number == '0123456789':
            return {'status': True, 'account_name': 'TEST ACCOUNT NAME'}
        return {'status': True, 'account_name': f'TEST USER {account_number[-4:]}'}
    
    paystack_secret = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_dummy')
    url = f"https://api.paystack.co/bank/resolve?account_number={account_number}&bank_code={bank_code}"
    headers = {"Authorization": f"Bearer {paystack_secret}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('status'):
            return {'status': True, 'account_name': data['data']['account_name']}
        return {'status': False, 'error': 'Account resolution failed'}
    except Exception as e:
        return {'status': False, 'error': str(e)}

def get_bank_name(bank_code):
    return MOCK_BANKS.get(bank_code, 'Unknown Bank')