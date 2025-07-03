# core/models.py
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.db.models import F
from django_fsm import FSMField, transition
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = [
        ('sales', 'Sales Team'),
        ('hatchery', 'Hatchery Management'),
        ('customer', 'Customer'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    company = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    reliability_score = models.FloatField(default=0.8)

    def __str__(self):
        return self.username

class Product(models.Model):
    PLOIDY_CHOICES = [
        ('diploid', 'Diploid'),
        ('triploid', 'Triploid'),
    ]
    TYPE_CHOICES = [
        ('steelhead', 'Steelhead'),
        ('jumper', 'Jumper'),
        ('kamloop', 'Kamloop'),
    ]
    DIAMETER_CHOICES = [
        (4, '4mm'),
        (5, '5mm'),
        (6, '6mm'),
    ]
    ploidy = models.CharField(max_length=10, choices=PLOIDY_CHOICES)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    diameter = models.IntegerField(choices=DIAMETER_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    MIN_ORDER_QUANTITY = 20000

    def __str__(self):
        return f"{self.type} {self.ploidy} {self.diameter}mm"

class Availability(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    year = models.IntegerField(default=2025)
    week_number = models.IntegerField()
    available_quantity = models.IntegerField()
    expected_ship_date = models.DateField()

    def __str__(self):
        return f"{self.product} - {self.year} Week {self.week_number}"

    class Meta:
        unique_together = ('product', 'year', 'week_number')  # Ensure unique availability per product, year, week


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved for Down Payment'),
        ('down_paid', 'Down Payment Received'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('shipped', 'Shipped'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'customer'}
    )
    availability = models.ForeignKey(Availability, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = FSMField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        protected=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    invoice = models.FileField(upload_to='invoices/', null=True, blank=True)
    downpayment_invoice = models.FileField(upload_to='downpayment_invoices/', null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    downpayment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fullpayment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    downpayment_deadline = models.DateTimeField(null=True, blank=True)
    fullpayment_deadline = models.DateTimeField(null=True, blank=True)
    downpayment_proof = models.FileField(upload_to='payment_proofs/', null=True, blank=True)
    fullpayment_proof = models.FileField(upload_to='payment_proofs/', null=True, blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    downpayment_transaction_id = models.CharField(max_length=50, blank=True, null=True)
    fullpayment_transaction_id = models.CharField(max_length=50, blank=True, null=True)

    def calculate_total(self):
        return self.quantity * self.availability.product.price + self.transport_cost

    def calculate_downpayment(self):
        return self.calculate_total() * Decimal('0.15')

    def __str__(self):
        return f"Order {self.id} by {self.customer}"

    @transition(field=status, source='pending', target='approved')
    def approve(self):
        self.downpayment_amount = self.calculate_downpayment()
        self.downpayment_deadline = timezone.now() + timezone.timedelta(days=3)

    @transition(field=status, source='approved', target='down_paid')
    def confirm_downpayment(self):
        self.fullpayment_deadline = timezone.now() + timezone.timedelta(days=14)

    @transition(field=status, source='down_paid', target='confirmed')
    def confirm_full_payment(self):
        self.confirmed_at = timezone.now()

    @transition(field=status, source='confirmed', target='shipped')
    def ship(self):
        with transaction.atomic():
            # Lock the availability record for update
            availability = Availability.objects.select_for_update().get(pk=self.availability.pk)

            # Validate stock
            if availability.available_quantity < self.quantity:
                raise ValueError("Insufficient available quantity")

            # Update inventory
            availability.available_quantity -= self.quantity
            availability.save(update_fields=['available_quantity'])

            # Update order status
            self.save(update_fields=['status'])

            # Log event
            CustomerEvent.objects.create(
                user=self.customer,
                event_type='ORDER_SHIPPED',
                order=self
            )

    @transition(field=status, source=['pending', 'approved', 'down_paid'], target='cancelled')
    def cancel(self):
        pass

class CustomerEvent(models.Model):
    EVENT_TYPES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('ORDER_CREATED', 'Order Created'),
        ('DOWN_PAYMENT_UPLOADED', 'Down Payment Uploaded'),
        ('FULL_PAYMENT_UPLOADED', 'Full Payment Uploaded'),
        ('ORDER_APPROVED', 'Order Approved'),
        ('DOWN_PAYMENT_VERIFIED', 'Down Payment Verified'),
        ('FULL_PAYMENT_VERIFIED', 'Full Payment Verified'),
        ('ORDER_SHIPPED', 'Order Shipped'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'customer'}
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)  # Increased max_length to 30
    timestamp = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey(
        'Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.event_type} at {self.timestamp}"