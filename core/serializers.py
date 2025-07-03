# core/serializers.py
from rest_framework import serializers
from .models import User, Product, Availability, Order, CustomerEvent

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'company', 'reliability_score']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'type', 'ploidy', 'diameter', 'price']

class AvailabilitySerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Availability
        fields = ['id', 'product', 'product_id', 'year', 'week_number', 'available_quantity', 'expected_ship_date']

class OrderSerializer(serializers.ModelSerializer):
    customer = UserSerializer(read_only=True)
    availability = AvailabilitySerializer(read_only=True)
    availability_id = serializers.PrimaryKeyRelatedField(
        queryset=Availability.objects.all(), source='availability', write_only=True
    )

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'availability', 'availability_id', 'quantity', 'status',
            'created_at', 'confirmed_at', 'downpayment_amount', 'fullpayment_amount',
            'downpayment_deadline', 'fullpayment_deadline', 'downpayment_transaction_id',
            'fullpayment_transaction_id', 'commission_rate', 'transport_cost'
        ]

class CustomerEventSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    order = OrderSerializer(read_only=True)

    class Meta:
        model = CustomerEvent
        fields = ['id', 'user', 'event_type', 'timestamp', 'order', 'metadata']