from django.db import models

class EscrowContract(models.Model):
    STATUS_CHOICES = [
        ('pending_verification', 'Pending Verification'),
        ('awaiting_counterparty', 'Awaiting Counterparty'),
        ('awaiting_funding', 'Awaiting Funding'),
        ('in_inspection', 'In Inspection'),
        ('pending_payout', 'Pending Payout'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    ]
    
    ROLE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ]

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2)
    fee_payer = models.CharField(max_length=10, choices=ROLE_CHOICES)
    creator_email = models.EmailField(db_index=True)
    creator_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    counterparty_email = models.EmailField(db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_verification')
    inspection_days = models.IntegerField(default=3)
    inspection_ends = models.DateTimeField(null=True, blank=True)
    buyer_confirmed = models.BooleanField(default=False)
    seller_confirmed = models.BooleanField(default=False)
    gateway_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.code})"

class AuthOTP(models.Model):
    INTENT_CHOICES = [
        ('create', 'Create'),
        ('join', 'Join'),
        ('reauth', 'Reauth'),
    ]

    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    intent = models.CharField(max_length=15, choices=INTENT_CHOICES)
    attempts_left = models.IntegerField(default=5)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"OTP for {self.email} ({self.intent})"

class SettlementVault(models.Model):
    contract = models.OneToOneField(EscrowContract, on_delete=models.CASCADE, related_name='settlement_vault')
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=10)
    account_number = models.CharField(max_length=10)
    account_name = models.CharField(max_length=150)

    def __str__(self):
        return f"Vault for {self.contract.code}"