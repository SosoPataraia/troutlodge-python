# core/management/commands/update_reliability_scores.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.ml_model import ReliabilityModel

class Command(BaseCommand):
    help = 'Update reliability scores for all customers using ML model'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        customers = User.objects.filter(role='customer')
        model = ReliabilityModel()

        # Train model on all customers
        if customers.exists():
            model.train(customers)
            self.stdout.write(self.style.SUCCESS('Model trained successfully.'))

        # Update scores
        for customer in customers:
            old_score = customer.reliability_score
            new_score = model.predict(customer)
            customer.reliability_score = new_score
            customer.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {customer.username}: {old_score:.2f} -> {new_score:.2f}'
                )
            )