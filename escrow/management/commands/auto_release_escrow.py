from django.core.management.base import BaseCommand
from django.utils.timezone import now
from escrow.models import EscrowContract
from escrow.views import execute_auto_payout

class Command(BaseCommand):
    def handle(self, *args, **options):
        expired_contracts = EscrowContract.objects.filter(
            status='in_transit',
            inspection_ends__lt=now()
        )
        count = 0
        for contract in expired_contracts:
            contract.status = 'pending_payout'
            contract.save()
            execute_auto_payout(contract)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {count} expired contracts.'))