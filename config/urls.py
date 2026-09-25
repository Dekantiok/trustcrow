from django.contrib import admin
from django.urls import path
from escrow import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('join/', views.join_escrow_page, name='join_escrow_page'),
    path('create/', views.create_contract, name='create_contract'),
    path('verify/<str:code>/', views.verify_otp_view, name='verify_otp'),
    path('escrow/<str:code>/', views.contract_detail, name='contract_detail'),
    path('escrow/<str:code>/verify/', views.counterparty_verify_otp, name='counterparty_verify_otp'),
    path('escrow/<str:code>/verify-as/<str:role>/', views.verify_as_participant, name='verify_as_participant'),
    path('reauth/', views.reauth_verify_otp, name='reauth_verify_otp'),
    path('escrow/<str:code>/pay/', views.initiate_payment, name='initiate_payment'),
    path('escrow/<str:code>/callback/', views.payment_callback, name='payment_callback'),
    path('webhooks/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('escrow/<str:code>/dispatch/', views.seller_confirm_dispatch, name='seller_confirm_dispatch'),
    path('escrow/<str:code>/confirm/', views.buyer_confirm_delivery, name='buyer_confirm_delivery'),
    path('escrow/<str:code>/vault/', views.seller_add_vault, name='seller_add_vault'),
]