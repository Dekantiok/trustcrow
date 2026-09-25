from django.contrib import admin
from django.urls import path
from escrow import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('join/', views.join_escrow, name='join_escrow'),
    path('create/', views.create_contract, name='create_contract'),
    path('verify/<str:code>/', views.verify_otp_view, name='verify_otp'),
    path('escrow/<str:code>/', views.contract_detail, name='contract_detail'),
    path('escrow/<str:code>/join/', views.counterparty_verify_otp, name='counterparty_verify_otp'),
    path('escrow/<str:code>/pay/', views.initiate_payment, name='initiate_payment'),
    path('escrow/<str:code>/callback/', views.payment_callback, name='payment_callback'),
    path('webhooks/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('escrow/<str:code>/confirm/', views.buyer_confirm_delivery, name='buyer_confirm_delivery'),
    path('escrow/<str:code>/vault/', views.seller_add_vault, name='seller_add_vault'),
    path('escrow/<str:code>/payout/', views.trigger_payout, name='trigger_payout'),
]