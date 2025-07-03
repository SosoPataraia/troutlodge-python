from django.core.management.base import BaseCommand
from core.models import Order, CustomerEvent
from core.payment import PaymentAdapter
from django.utils import timezone

class Command(BaseCommand):
    help = 'Simulate a timely downpayment and event creation'

    def handle(self, *args, **kwargs):
        order = Order.objects.filter(id=1).first()
        if not order:
            self.stdout.write(self.style.ERROR("Order with ID 1 not found."))
            return

        payment_adapter = PaymentAdapter()
        result = payment_adapter.request_downpayment(order)
        order.downpayment_transaction_id = result['transaction_id']
        order.approve()
        order.save()

        CustomerEvent.objects.get_or_create(
            user=order.customer,
            event_type='ORDER_APPROVED',
            order=order,
            defaults={'metadata': {'transaction_id': result['transaction_id']}}
        )

        CustomerEvent.objects.get_or_create(
            user=order.customer,
            event_type='DOWN_PAYMENT_UPLOADED',
            order=order,
            defaults={
                'metadata': {'transaction_id': result['transaction_id']},
                'timestamp': timezone.now()
            }
        )

        self.stdout.write(self.style.SUCCESS("Simulated payment and created events."))
