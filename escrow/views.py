import datetime
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from .models import EscrowContract, AuthOTP
from .forms import ContractCreationForm
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

def home_view(request):
    return render(request, 'home.html')

def join_escrow(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if EscrowContract.objects.filter(code=code).exists():
            return redirect('contract_detail', code=code)
        else:
            return render(request, 'home.html', {'join_error': 'No escrow found with that code.'})
    return redirect('home')

def create_contract(request):
    if request.method == 'POST':
        form = ContractCreationForm(request.POST)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.code = generate_secure_code(20)
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

    context = {
        'contract': contract,
        'status_label': STATUS_LABELS.get(contract.status, contract.status),
        'badge_class': STATUS_BADGES.get(contract.status, 'bg-secondary'),
        'show_counterparty_form': contract.status == 'awaiting_counterparty',
        'show_payment_button': contract.status == 'awaiting_funding',
        'formatted_amount': f"\u20a6{contract.amount:,.2f}",
        'formatted_fee': f"\u20a6{contract.service_fee:,.2f}",
    }

    if request.method == 'POST' and contract.status == 'awaiting_counterparty':
        submitted_email = request.POST.get('email', '').strip().lower()
        if submitted_email == contract.counterparty_email.lower():
            otp_code = generate_otp()
            expires_at = now() + datetime.timedelta(minutes=15)
            AuthOTP.objects.create(
                email=submitted_email,
                otp_code=otp_code,
                intent='join',
                expires_at=expires_at
            )
            send_otp_via_termii(submitted_email, otp_code)
            return redirect('counterparty_verify_otp', code=contract.code)
        else:
            context['email_error'] = "Email does not match the counterparty on this contract."

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
    if contract.status != 'awaiting_funding':
        return redirect('contract_detail', code=contract.code)

    gateway = get_payment_gateway()
    return_url = request.build_absolute_uri(reverse('payment_callback', kwargs={'code': contract.code}))
    
    result = gateway.initialize_vault_payment(contract, return_url)
    
    if result.get('status') and result.get('auth_url'):
        return redirect(result['auth_url'])
    
    return render(request, 'escrow/payment_error.html', {'error': 'Failed to initialize payment.'})

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