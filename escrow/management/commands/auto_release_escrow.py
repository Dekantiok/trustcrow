from django.core.management.base import BaseCommand
from django.utils.timezone import now
from escrow.models import EscrowContract

class Command(BaseCommand):
    def handle(self, *args, **options):
        expired_contracts = EscrowContract.objects.filter(
            status='in_inspection',
            inspection_ends__lt=now()
        )
        count = expired_contracts.update(status='pending_payout')
        self.stdout.write(self.style.SUCCESS(f'Successfully released {count} contracts.'))