# core/management/commands/create_test_users.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates test users for all roles, skipping existing users'

    def handle(self, *args, **options):
        users = [
            {'username': 'sales1', 'email': 'sales1@test.com', 'role': 'sales', 'password': 'testpass123'},
            {'username': 'hatchery1', 'email': 'hatchery1@test.com', 'role': 'hatchery', 'password': 'testpass123'},
            {'username': 'customer1', 'email': 'customer1@test.com', 'role': 'customer', 'password': 'testpass123'},
            {'username': 'customer2', 'email': 'customer2@test.com', 'role': 'customer', 'password': 'testpass123'},
        ]

        for user_data in users:
            if not User.objects.filter(username=user_data['username']).exists():
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    role=user_data['role'],
                    password=user_data['password']
                )
                self.stdout.write(self.style.SUCCESS(f'Created user: {user.username}'))
            else:
                self.stdout.write(self.style.WARNING(f'User {user_data["username"]} already exists, skipping.'))