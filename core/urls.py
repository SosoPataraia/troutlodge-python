from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.views.generic.base import RedirectView
from core import views  # Import views from core app

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url=reverse_lazy('login'))),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('request_order/', views.request_order, name='request_order'),
    path('update_availability/', views.update_availability, name='update_availability'),
    path('confirm_order/<int:order_id>/', views.confirm_order, name='confirm_order'),
    path('invoices/<int:order_id>/', views.view_invoice, name='view_invoice'),
    path('register/', views.register, name='register'),
]