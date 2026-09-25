import secrets
import string

def generate_secure_code(length=20):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_otp(length=6):
    return ''.join(secrets.choice(string.digits) for _ in range(length))