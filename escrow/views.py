import datetime
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.urls import reverse
from django.contrib import messages
from .models import EscrowContract, AuthOTP
from .forms import ContractCreationForm, SettlementVaultForm
from .services import calculate_service_fee
from .utils import generate_secure_code, generate_otp
from .notifications import send_otp_via_termii
from .gateways import get_payment_gateway

STATUS_LABELS = {
    'pending_verification': 'Pending Verification',
    'awaiting_counterparty': 'Awaiting Counterparty',
    'awaiting_funding': 'Awaiting Funding',
    'in_inspection': 'In Inspection',
    'pending_payout': 'Pending Payout',
    'completed': 'Completed',
    'disputed': 'Disputed',
    'cancelled': 'Cancelled',
}

STATUS_BADGES = {
    'pending_verification': 'bg-warning text-dark',
    'awaiting_counterparty': 'bg-info text-dark',
    'awaiting_funding': 'bg-primary',
    'in_inspection': 'bg-primary',
    'pending_payout': 'bg-success',
    'completed': 'bg-success',
    'disputed': 'bg-danger',
    'cancelled': 'bg-secondary',
}

def get_buyer_email(contract):
    if contract.creator_role == 'buyer':
        return contract.creator_email
    return contract.counterparty_email

def get_seller_email(contract):
    if contract.creator_role == 'seller':
        return contract.creator_email
    return contract.counterparty_email

def home_view(request):
    if 'active_email' in request.session:
        del request.session['active_email']
    return render(request, 'home.html')

def join_escrow_page(request):
    error_message = None
    
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        email = request.POST.get('email', '').strip().lower()
        
        try:
            contract = EscrowContract.objects.get(code=code)
            
            if contract.status != 'awaiting_counterparty':
                error_message = "This escrow is not currently accepting counterparty verification."
            elif email != contract.counterparty_email.lower():
                error_message = "The email does not match the counterparty linked to this escrow."
            else:
                otp_code = generate_otp()
                expires_at = now() + datetime.timedelta(minutes=15)
                AuthOTP.objects.create(
                    email=email,
                    otp_code=otp_code,
                    intent='join',
                    expires_at=expires_at
                )
                send_otp_via_termii(email, otp_code)
                return redirect('counterparty_verify_otp', code=contract.code)
        except EscrowContract.DoesNotExist:
            error_message = "No escrow found with that code."
    
    return render(request, 'escrow/join_escrow.html', {'error_message': error_message})

def create_contract(request):
    if request.method == 'POST':
        form = ContractCreationForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.code = generate_secure_code(9)
            contract.service_fee = calculate_service_fee(contract.amount)
            contract.status = 'pending_verification'
            contract.gateway_reference = f"{contract.code}_{int(now().timestamp())}"
            contract.save()

            otp_code = generate_otp()
            expires_at = now() + datetime.timedelta(minutes=15)
            AuthOTP.objects.create(
                email=contract.creator_email,
                otp_code=otp_code,
                intent='create',
                expires_at=expires_at
            )
            send_otp_via_termii(contract.creator_email, otp_code)
            return redirect('verify_otp', code=contract.code)
    else:
        form = ContractCreationForm()
    return render(request, 'escrow/create_contract.html', {'form': form})

def verify_otp_view(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    error_message = None

    if request.method == 'POST':
        submitted_otp = request.POST.get('otp')
        try:
            otp_record = AuthOTP.objects.get(
                email=contract.creator_email,
                otp_code=submitted_otp,
                intent='create',
                is_used=False
            )
            if otp_record.expires_at > now() and otp_record.attempts_left > 0:
                otp_record.is_used = True
                otp_record.save()
                contract.status = 'awaiting_counterparty'
                contract.save()
                request.session['active_email'] = contract.creator_email
                return redirect('contract_detail', code=contract.code)
            else:
                otp_record.attempts_left -= 1
                otp_record.save()
                error_message = "Invalid or expired OTP."
        except AuthOTP.DoesNotExist:
            error_message = "OTP not found. Please check your email."

    return render(request, 'escrow/verify_otp.html', {
        'contract': contract,
        'error_message': error_message,
    })

def contract_detail(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    current_user = request.session.get('active_email')
    buyer_email = get_buyer_email(contract)
    seller_email = get_seller_email(contract)

    is_buyer = (current_user == buyer_email)
    is_seller = (current_user == seller_email)

    vault = getattr(contract, 'settlement_vault', None)

    context = {
        'contract': contract,
        'status_label': STATUS_LABELS.get(contract.status, contract.status),
        'badge_class': STATUS_BADGES.get(contract.status, 'bg-secondary'),
        'show_payment_button': (contract.status == 'awaiting_funding' and is_buyer),
        'show_buyer_confirm': (contract.status == 'in_inspection' and is_buyer),
        'show_seller_vault_form': (contract.status in ['in_inspection', 'pending_payout'] and is_seller and not vault),
        'show_payout_button': (contract.status == 'pending_payout' and is_seller and vault),
        'formatted_amount': f"\u20a6{contract.amount:,.2f}",
        'formatted_fee': f"\u20a6{contract.service_fee:,.2f}",
        'current_user': current_user,
        'vault': vault,
    }

    return render(request, 'escrow/contract_detail.html', context)

def counterparty_verify_otp(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    error_message = None

    if request.method == 'POST':
        submitted_otp = request.POST.get('otp')
        try:
            otp_record = AuthOTP.objects.get(
                email=contract.counterparty_email,
                otp_code=submitted_otp,
                intent='join',
                is_used=False
            )
            if otp_record.expires_at > now() and otp_record.attempts_left > 0:
                otp_record.is_used = True
                otp_record.save()
                contract.status = 'awaiting_funding'
                contract.save()
                request.session['active_email'] = contract.counterparty_email
                return redirect('contract_detail', code=contract.code)
            else:
                otp_record.attempts_left -= 1
                otp_record.save()
                error_message = "Invalid or expired OTP."
        except AuthOTP.DoesNotExist:
            error_message = "OTP not found. Please check your email."

    return render(request, 'escrow/counterparty_verify_otp.html', {
        'contract': contract,
        'error_message': error_message,
    })

def initiate_payment(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    buyer_email = get_buyer_email(contract)
    if request.session.get('active_email') != buyer_email:
        return HttpResponseForbidden("Only the buyer can fund this escrow.")

    if contract.status != 'awaiting_funding':
        return redirect('contract_detail', code=contract.code)

    gateway = get_payment_gateway()
    return_url = request.build_absolute_uri(reverse('payment_callback', kwargs={'code': contract.code}))
    result = gateway.initialize_vault_payment(contract, return_url)
    
    if result.get('status') and result.get('auth_url'):
        return redirect(result['auth_url'])
    
    messages.error(request, "Payment initialization failed. Please try again.")
    return redirect('contract_detail', code=contract.code)

def payment_callback(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    return render(request, 'escrow/payment_callback.html', {'contract': contract})

@csrf_exempt
def paystack_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Method not allowed")

    gateway = get_payment_gateway()
    payload_data = gateway.verify_incoming_webhook(request.headers, request.body)
    
    if not payload_data:
        return HttpResponseBadRequest("Invalid signature")

    event = payload_data.get('event')
    data = payload_data.get('data', {})
    reference = data.get('reference')

    if event == 'charge.success' and reference:
        try:
            contract = EscrowContract.objects.get(gateway_reference=reference)
            if contract.status == 'awaiting_funding':
                contract.status = 'in_inspection'
                contract.inspection_ends = now() + datetime.timedelta(days=contract.inspection_days)
                contract.save()
        except EscrowContract.DoesNotExist:
            pass

    return HttpResponse("Webhook received", status=200)

def buyer_confirm_delivery(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    buyer_email = get_buyer_email(contract)
    
    if request.session.get('active_email') != buyer_email:
        return HttpResponseForbidden("Only the buyer can confirm delivery.")
        
    if contract.status != 'in_inspection':
        return redirect('contract_detail', code=contract.code)
        
    if request.method == 'POST':
        contract.status = 'pending_payout'
        contract.buyer_confirmed = True
        contract.save()
        return redirect('contract_detail', code=contract.code)
        
    return redirect('contract_detail', code=contract.code)

def seller_add_vault(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    seller_email = get_seller_email(contract)
    
    if request.session.get('active_email') != seller_email:
        return HttpResponseForbidden("Only the seller can add payout details.")
        
    if contract.status not in ['in_inspection', 'pending_payout']:
        return redirect('contract_detail', code=contract.code)
        
    if hasattr(contract, 'settlement_vault'):
        return redirect('contract_detail', code=contract.code)
        
    if request.method == 'POST':
        form = SettlementVaultForm(request.POST)
        if form.is_valid():
            vault = form.save(commit=False)
            vault.contract = contract
            vault.save()
            return redirect('contract_detail', code=contract.code)
    else:
        form = SettlementVaultForm()
        
    return render(request, 'escrow/add_vault.html', {'form': form, 'contract': contract})

def trigger_payout(request, code):
    contract = get_object_or_404(EscrowContract, code=code)
    seller_email = get_seller_email(contract)
    
    if request.session.get('active_email') != seller_email:
        return HttpResponseForbidden("Only the seller can trigger payout.")
        
    if contract.status != 'pending_payout':
        return redirect('contract_detail', code=contract.code)
        
    vault = getattr(contract, 'settlement_vault', None)
    if not vault:
        return redirect('seller_add_vault', code=contract.code)
        
    if contract.fee_payer == 'seller':
        total_disbursement = contract.amount - contract.service_fee
    else:
        total_disbursement = contract.amount
        
    gateway = get_payment_gateway()
    result = gateway.execute_seller_payout(vault, total_disbursement)
    
    if result.get('status') or result.get('message') == 'Success':
        contract.status = 'completed'
        contract.save()
        return redirect('contract_detail', code=contract.code)
        
    messages.error(request, "Payout failed. Please try again or contact support.")
    return redirect('contract_detail', code=contract.code)