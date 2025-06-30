from django.contrib import admin
from .models import User, Product, Availability, Order

class ProductAdmin(admin.ModelAdmin):
    list_display = ('type', 'ploidy', 'diameter', 'price')
    list_filter = ('type', 'ploidy', 'diameter')
    search_fields = ('type',)

class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ('product', 'week_number', 'available_quantity', 'expected_ship_date')
    list_filter = ('week_number', 'product')
    search_fields = ('product__type',)

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'created_at', 'quantity')
    list_filter = ('status', 'availability__product')
    search_fields = ('customer__username',)

admin.site.register(User)
admin.site.register(Product, ProductAdmin)
admin.site.register(Availability, AvailabilityAdmin)
admin.site.register(Order, OrderAdmin)