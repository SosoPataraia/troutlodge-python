from django.core.management.base import BaseCommand
from core.models import User, Product, Availability, Order, CustomerEvent
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Populate test data for Step 5'

    def handle(self, *args, **kwargs):
        users = [
            {'username': 'sales1', 'email': 'sales1@test.com', 'role': 'sales', 'password': 'testpass123'},
            {'username': 'hatchery1', 'email': 'hatchery1@test.com', 'role': 'hatchery', 'password': 'testpass123'},
            {'username': 'customer1', 'email': 'customer1@test.com', 'role': 'customer', 'password': 'testpass123'},
            {'username': 'customer2', 'email': 'customer2@test.com', 'role': 'customer', 'password': 'testpass123'},
        ]

        for user_data in users:
            if not User.objects.filter(username=user_data['username']).exists():
                User.objects.create_user(**user_data)

        product, _ = Product.objects.get_or_create(
            type='steelhead', ploidy='diploid', diameter=4,
            defaults={'price': 0.1}
        )

        availability, _ = Availability.objects.get_or_create(
            product=product, week_number=30,
            defaults={
                'available_quantity': 50000,
                'expected_ship_date': '2025-07-30'
            }
        )

        customer1 = User.objects.get(username='customer1')
        customer2 = User.objects.get(username='customer2')

        order1, _ = Order.objects.get_or_create(
            customer=customer1, availability=availability,
            defaults={'quantity': 20000, 'status': 'pending'}
        )

        order2, _ = Order.objects.get_or_create(
            customer=customer2, availability=availability,
            defaults={'quantity': 20000, 'status': 'pending'}
        )

        # Simulate events
        if not CustomerEvent.objects.filter(user=customer1, event_type='LOGIN').exists():
            CustomerEvent.objects.create(user=customer1, event_type='LOGIN', metadata={'ip_address': '127.0.0.1'})
        if not CustomerEvent.objects.filter(user=customer1, event_type='ORDER_CREATED', order=order1).exists():
            CustomerEvent.objects.create(user=customer1, event_type='ORDER_CREATED', order=order1, metadata={'quantity': 20000})
        if not CustomerEvent.objects.filter(user=customer2, event_type='LOGIN').exists():
            CustomerEvent.objects.create(user=customer2, event_type='LOGIN', metadata={'ip_address': '127.0.0.2'})

        self.stdout.write(self.style.SUCCESS("Test data populated successfully."))
