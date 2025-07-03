from django.contrib import admin
from .models import User, Product, Availability, Order

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'status', 'created_at', 'quantity',
                    'downpayment_amount', 'fullpayment_amount')
    list_filter = ('status', 'availability__product')
    search_fields = ('customer__username',)
    readonly_fields = ('created_at', 'confirmed_at')

admin.site.register(User)
admin.site.register(Product)
admin.site.register(Availability)
admin.site.register(Order, OrderAdmin)