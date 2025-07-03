# core/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, api_views

urlpatterns = [
    # Authentication URLs
    path('login/',
         auth_views.LoginView.as_view(
             template_name='registration/login.html',
             redirect_authenticated_user=True
         ),
         name='login'),
    path('logout/',
         auth_views.LogoutView.as_view(
             next_page='login',
             template_name='registration/logged_out.html'
         ),
         name='logout'),

    # Web views
    path('', views.dashboard, name='dashboard'),
    path('availability/', views.availability_view, name='availability_view'),

    # Role-specific dashboards
    path('sales/', views.sales_dashboard, name='sales_dashboard'),
    path('hatchery/', views.hatchery_dashboard, name='hatchery_dashboard'),
    path('customer/', views.customer_dashboard, name='customer_dashboard'),

    # Order workflow URLs
    path('approve_order/<int:order_id>/', views.approve_order, name='approve_order'),
    path('verify_down_payment/<int:order_id>/', views.verify_down_payment, name='verify_down_payment'),
    path('verify_full_payment/<int:order_id>/', views.verify_full_payment, name='verify_full_payment'),
    path('ship_order/<int:order_id>/', views.ship_order, name='ship_order'),

    # Customer actions
    path('upload_down_payment/<int:order_id>/', views.upload_down_payment, name='upload_down_payment'),
    path('upload_full_payment/<int:order_id>/', views.upload_full_payment, name='upload_full_payment'),
    path('request_order/', views.request_order, name='request_order'),
    path('view_invoice/<int:order_id>/', views.view_invoice, name='view_invoice'),

    # Registration
    path('register/', views.register, name='register'),

    # Hatchery management
    path('update_availability/', views.update_availability, name='update_availability'),

    # API endpoints
    path('api/users/', api_views.UserListView.as_view(), name='api_user_list'),
    path('api/products/', api_views.ProductListCreateView.as_view(), name='api_product_list_create'),
    path('api/availabilities/', api_views.AvailabilityListCreateView.as_view(), name='api_availability_list_create'),
    path('api/orders/', api_views.OrderListCreateView.as_view(), name='api_order_list_create'),
    path('api/orders/<int:order_id>/approve/', api_views.OrderApproveView.as_view(), name='api_order_approve'),
    path('api/orders/<int:order_id>/verify-down-payment/',
         api_views.OrderVerifyDownPaymentView.as_view(),
         name='api_order_verify_down_payment'),
    path('api/orders/<int:order_id>/verify-full-payment/',
         api_views.OrderVerifyFullPaymentView.as_view(),
         name='api_order_verify_full_payment'),
    path('api/orders/<int:order_id>/ship/', api_views.OrderShipView.as_view(), name='api_order_ship'),
    path('api/customer-events/', api_views.CustomerEventListView.as_view(), name='api_customer_event_list'),
]