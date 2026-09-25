import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now
from .models import EscrowContract, AuthOTP
from .forms import ContractCreationForm
from .services import calculate_service_fee
from .utils import generate_secure_code, generate_otp
from .notifications import send_otp_via_termii

def home_view(request):
    return render(request, 'home.html')

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
            otp_record = AuthOTP.objects.get(email=contract.creator_email, otp_code=submitted_otp, intent='create', is_used=False)
            
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
            
    return render(request, 'escrow/verify_otp.html', {'contract': contract, 'error_message': error_message})