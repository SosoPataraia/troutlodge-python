# core/urls.py
from django.urls import path
from . import views, api_views

urlpatterns = [
    # Web views
    path('', views.dashboard, name='dashboard'),
    path('availability/', views.availability_view, name='availability_view'),
    path('sales/', views.sales_dashboard, name='sales_dashboard'),
    path('approve_order/<int:order_id>/', views.approve_order, name='approve_order'),
    path('verify_down_payment/<int:order_id>/', views.verify_down_payment, name='verify_down_payment'),
    path('verify_full_payment/<int:order_id>/', views.verify_full_payment, name='verify_full_payment'),
    path('ship_order/<int:order_id>/', views.ship_order, name='ship_order'),
    path('hatchery/', views.hatchery_dashboard, name='hatchery_dashboard'),
    path('update_availability/', views.update_availability, name='update_availability'),
    path('customer/', views.customer_dashboard, name='customer_dashboard'),
    path('upload_down_payment/<int:order_id>/', views.upload_down_payment, name='upload_down_payment'),
    path('upload_full_payment/<int:order_id>/', views.upload_full_payment, name='upload_full_payment'),
    path('view_invoice/<int:order_id>/', views.view_invoice, name='view_invoice'),
    path('request_order/', views.request_order, name='request_order'),
    path('register/', views.register, name='register'),
    # API views
    path('api/users/', api_views.UserListView.as_view(), name='api_user_list'),
    path('api/products/', api_views.ProductListCreateView.as_view(), name='api_product_list_create'),
    path('api/availabilities/', api_views.AvailabilityListCreateView.as_view(), name='api_availability_list_create'),
    path('api/orders/', api_views.OrderListCreateView.as_view(), name='api_order_list_create'),
    path('api/orders/<int:order_id>/approve/', api_views.OrderApproveView.as_view(), name='api_order_approve'),
    path('api/orders/<int:order_id>/verify-down-payment/', api_views.OrderVerifyDownPaymentView.as_view(), name='api_order_verify_down_payment'),
    path('api/orders/<int:order_id>/verify-full-payment/', api_views.OrderVerifyFullPaymentView.as_view(), name='api_order_verify_full_payment'),
    path('api/orders/<int:order_id>/ship/', api_views.OrderShipView.as_view(), name='api_order_ship'),
    path('api/customer-events/', api_views.CustomerEventListView.as_view(), name='api_customer_event_list'),
]