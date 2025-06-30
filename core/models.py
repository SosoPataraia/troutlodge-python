from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('sales', 'Sales Team'),
        ('hatchery', 'Hatchery Management'),
        ('customer', 'Customer'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    company = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

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

    def __str__(self):
        return f"{self.type} {self.ploidy} {self.diameter}mm"

class Availability(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    week_number = models.IntegerField()
    available_quantity = models.IntegerField()
    expected_ship_date = models.DateField()

    def __str__(self):
        return f"{self.product} - Week {self.week_number}"

class Order(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'customer'})
    availability = models.ForeignKey(Availability, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('confirmed', 'Confirmed')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    invoice = models.FileField(upload_to='invoices/', null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Order {self.id} by {self.customer}"