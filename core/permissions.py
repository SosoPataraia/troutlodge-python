# core/permissions.py
from rest_framework import permissions

from core.models import Order


class IsSales(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'sales'

class IsHatchery(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'hatchery'

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'customer'

class IsCustomerOrSales(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['customer', 'sales']

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'sales':
            return True
        if isinstance(obj, Order):
            return obj.customer == request.user
        return False