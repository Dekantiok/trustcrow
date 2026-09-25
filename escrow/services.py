from decimal import Decimal

def calculate_service_fee(amount):
    """
    Calculates the flat-tier service fee based on the transaction amount.
    """
    amount = Decimal(amount)
    
    if amount <= Decimal('50000'):
        return Decimal('1500')
    elif amount <= Decimal('100000'):
        return Decimal('2000')
    elif amount <= Decimal('500000'):
        return Decimal('2500')
    elif amount <= Decimal('1000000'):
        return Decimal('5000')
    else:
        return Decimal('10000')