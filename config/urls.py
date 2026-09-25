from django.contrib import admin
from django.urls import path
from escrow import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('create/', views.create_contract, name='create_contract'),
    path('verify/<str:code>/', views.verify_otp_view, name='verify_otp'),
]