from django.contrib import admin, messages
from django.db.models import Q
from django.utils import timezone

from .models import AuthOTP, EscrowContract, SettlementVault
from .services import settle_pending_payout


@admin.register(EscrowContract)
class EscrowContractAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'title', 'amount', 'status', 'creator_email',
        'counterparty_email', 'inspection_ends', 'created_at',
    )
    list_filter = ('status', 'creator_role', 'fee_payer')
    search_fields = ('code', 'creator_email', 'counterparty_email', 'title')
    readonly_fields = (
        'code', 'gateway_reference', 'service_fee', 'created_at',
        'inspection_ends', 'buyer_confirmed', 'seller_confirmed',
    )
    date_hierarchy = 'created_at'
    actions = (
        'resolve_dispute_to_payout',
        'resolve_dispute_cancelled',
        'cancel_contract',
        'extend_inspection_window',
    )

    def _cancel(self, request, queryset, verb):
        changed = 0
        for contract in queryset:
            if not contract.can_transition_to('cancelled'):
                self.message_user(
                    request,
                    f"{contract.code} cannot be cancelled from {contract.status}.",
                    level=messages.WARNING,
                )
                continue
            contract.transition_to('cancelled')
            changed += 1
        self.message_user(
            request, f"{verb} {changed} escrow(s).", level=messages.INFO
        )

    @admin.action(description="Resolve dispute: release funds to seller")
    def resolve_dispute_to_payout(self, request, queryset):
        for contract in queryset:
            if not contract.can_transition_to('pending_payout'):
                self.message_user(
                    request,
                    f"{contract.code} cannot be released from {contract.status}.",
                    level=messages.WARNING,
                )
                continue
            contract.transition_to('pending_payout')
            result = settle_pending_payout(contract)
            self.message_user(
                request,
                f"{contract.code}: "
                + ('paid' if result.success else f'NOT paid ({result.reason})'),
                level=messages.INFO if result.success else messages.ERROR,
            )

    @admin.action(description="Resolve dispute: cancel escrow")
    def resolve_dispute_cancelled(self, request, queryset):
        self._cancel(request, queryset, 'Resolved and cancelled')

    @admin.action(description="Cancel escrow")
    def cancel_contract(self, request, queryset):
        self._cancel(request, queryset, 'Cancelled')

    @admin.action(description="Extend inspection window by 3 days")
    def extend_inspection_window(self, request, queryset):
        for contract in queryset:
            if not contract.inspection_ends:
                self.message_user(
                    request,
                    f"{contract.code} has no inspection deadline to extend.",
                    level=messages.WARNING,
                )
                continue
            contract.inspection_ends += timezone.timedelta(days=3)
            contract.save(update_fields=['inspection_ends'])
        self.message_user(request, f"Extended {queryset.count()} escrow(s).",
                          level=messages.INFO)


@admin.register(AuthOTP)
class AuthOTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'intent', 'attempts_left', 'is_used', 'expires_at', 'created_at')
    list_filter = ('intent', 'is_used')
    search_fields = ('email', 'otp_code')
    readonly_fields = ('otp_code', 'created_at')
    actions = ('purge_stale',)

    @admin.action(description="Delete expired or already-used codes")
    def purge_stale(self, request, queryset):
        stale = queryset.filter(Q(is_used=True) | Q(expires_at__lt=timezone.now()))
        count, _ = stale.delete()
        self.message_user(request, f"Deleted {count} stale code(s).", level=messages.INFO)


@admin.register(SettlementVault)
class SettlementVaultAdmin(admin.ModelAdmin):
    list_display = ('contract', 'bank_name', 'masked_account', 'account_name')
    search_fields = ('contract__code', 'account_number', 'account_name')

    @admin.display(description='Account number')
    def masked_account(self, obj):
        return obj.masked_account_number


admin.site.site_header = 'Trustcrow Operations'
admin.site.site_title = 'Trustcrow'
admin.site.index_title = 'Escrow operations'
