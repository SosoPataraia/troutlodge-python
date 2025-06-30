from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates test users for all roles'

    def handle(self, *args, **options):
        users = [
            {'username': 'sales1', 'email': 'sales@test.com', 'role': 'sales', 'password': 'testpass123'},
            {'username': 'hatchery1', 'email': 'hatchery@test.com', 'role': 'hatchery', 'password': 'testpass123'},
            {'username': 'customer1', 'email': 'customer@test.com', 'role': 'customer', 'password': 'testpass123'},
        ]

        for user_data in users:
            user = User.objects.create_user(
                username=user_data['username'],
                email=user_data['email'],
                role=user_data['role'],
                password=user_data['password']
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {user.username}'))