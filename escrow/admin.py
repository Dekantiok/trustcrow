from django.contrib import admin
from .models import EscrowContract, AuthOTP, SettlementVault

@admin.register(EscrowContract)
class EscrowContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'title', 'amount', 'status', 'creator_email')
    list_filter = ('status', 'creator_role', 'fee_payer')
    search_fields = ('code', 'creator_email', 'counterparty_email', 'title')
    readonly_fields = ('code', 'gateway_reference', 'service_fee', 'inspection_ends', 'buyer_confirmed', 'seller_confirmed')

@admin.register(AuthOTP)
class AuthOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'intent', 'otp_code', 'is_used', 'expires_at')
    list_filter = ('intent', 'is_used')
    search_fields = ('email', 'otp_code')

@admin.register(SettlementVault)
class SettlementVaultAdmin(admin.ModelAdmin):
    list_display = ('contract', 'bank_name', 'account_number', 'account_name')
    search_fields = ('contract__code', 'account_number', 'account_name')