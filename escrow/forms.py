from django import forms
from django.core.exceptions import ValidationError
from .models import EscrowContract, SettlementVault

class ContractCreationForm(forms.ModelForm):
    class Meta:
        model = EscrowContract
        fields = ['title', 'description', 'amount', 'fee_payer', 'creator_email', 'creator_role', 'counterparty_email', 'inspection_days']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        creator_email = cleaned_data.get('creator_email')
        counterparty_email = cleaned_data.get('counterparty_email')

        if creator_email and counterparty_email and creator_email.lower() == counterparty_email.lower():
            raise ValidationError("The creator and counterparty cannot use the same email address.")
        
        return cleaned_data

class SettlementVaultForm(forms.ModelForm):
    class Meta:
        model = SettlementVault
        fields = ['bank_name', 'bank_code', 'account_number', 'account_name']
        widgets = {
            'account_number': forms.TextInput(attrs={'maxlength': 10, 'pattern': '\d{10}'}),
        }