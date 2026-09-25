from django import forms
from .models import EscrowContract

class ContractCreationForm(forms.ModelForm):
    class Meta:
        model = EscrowContract
        fields = ['title', 'description', 'amount', 'fee_payer', 'creator_email', 'creator_role', 'counterparty_email', 'inspection_days']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }