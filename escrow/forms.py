from django import forms
from django.core.exceptions import ValidationError

from .models import EscrowContract, SettlementVault
from .utils import normalize_email

MIN_ESCROW_AMOUNT = 100
MAX_ESCROW_AMOUNT = 9999999999.99
MIN_INSPECTION_DAYS = 1
MAX_INSPECTION_DAYS = 30


class ContractCreationForm(forms.ModelForm):
    class Meta:
        model = EscrowContract
        fields = [
            'title', 'description', 'amount', 'fee_payer',
            'creator_email', 'creator_role', 'counterparty_email', 'inspection_days',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['amount'].min_value = MIN_ESCROW_AMOUNT
        self.fields['amount'].max_value = MAX_ESCROW_AMOUNT
        self.fields['inspection_days'].min_value = MIN_INSPECTION_DAYS
        self.fields['inspection_days'].max_value = MAX_INSPECTION_DAYS
        for name in ('creator_email', 'counterparty_email'):
            self.fields[name].widget.attrs.setdefault('autocapitalize', 'none')
            self.fields[name].widget.attrs.setdefault('autocomplete', 'email')
            self.fields[name].widget.attrs.setdefault('spellcheck', 'false')

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount < MIN_ESCROW_AMOUNT:
            raise ValidationError(
                f"The escrow amount must be at least {MIN_ESCROW_AMOUNT:,.2f}."
            )
        return amount

    def clean_inspection_days(self):
        days = self.cleaned_data['inspection_days']
        if days < MIN_INSPECTION_DAYS:
            raise ValidationError("The inspection window must be at least 1 day.")
        if days > MAX_INSPECTION_DAYS:
            raise ValidationError(f"The inspection window cannot exceed {MAX_INSPECTION_DAYS} days.")
        return days

    def clean(self):
        cleaned_data = super().clean()
        creator_email = normalize_email(cleaned_data.get('creator_email'))
        counterparty_email = normalize_email(cleaned_data.get('counterparty_email'))
        if creator_email:
            cleaned_data['creator_email'] = creator_email
        if counterparty_email:
            cleaned_data['counterparty_email'] = counterparty_email
        if creator_email and creator_email == counterparty_email:
            raise ValidationError(
                "The creator and counterparty cannot use the same email address."
            )
        return cleaned_data


class SettlementVaultForm(forms.ModelForm):
    class Meta:
        model = SettlementVault
        fields = ['bank_name', 'bank_code', 'account_number', 'account_name']
        widgets = {
            'account_number': forms.TextInput(attrs={
                'maxlength': 10,
                'pattern': r'\d{10}',
                'inputmode': 'numeric',
                'autocomplete': 'off',
            }),
        }

    def clean_account_number(self):
        account_number = (self.cleaned_data.get('account_number') or '').strip()
        if not account_number.isdigit() or len(account_number) != 10:
            raise ValidationError("Enter the 10-digit account number.")
        return account_number
