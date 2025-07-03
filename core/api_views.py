# core/api_views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from .models import User, Product, Availability, Order, CustomerEvent
from .serializers import UserSerializer, ProductSerializer, AvailabilitySerializer, OrderSerializer, CustomerEventSerializer
from .permissions import IsSales, IsHatchery, IsCustomer, IsCustomerOrSales
from .payment import PaymentAdapter
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.core.files import File

class UserListView(generics.ListAPIView):
    queryset = User.objects.filter(role='customer')
    serializer_class = UserSerializer
    permission_classes = [IsSales]

class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsSales | IsHatchery | IsCustomer]

class AvailabilityListCreateView(generics.ListCreateAPIView):
    queryset = Availability.objects.all()
    serializer_class = AvailabilitySerializer
    permission_classes = []

    def get_queryset(self):
        year = self.request.query_params.get('year', 2025)
        return Availability.objects.filter(year=year).order_by('week_number')

    def perform_create(self, serializer):
        if self.request.user.role != 'hatchery':
            return Response({"detail": "Only hatchery managers can create availability."}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

class OrderListCreateView(generics.ListCreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsCustomerOrSales]

    def get_queryset(self):
        if self.request.user.role == 'customer':
            return Order.objects.filter(customer=self.request.user)
        return Order.objects.all()

    def perform_create(self, serializer):
        if self.request.user.role != 'customer':
            return Response({"detail": "Only customers can create orders."}, status=status.HTTP_403_FORBIDDEN)
        serializer.save(customer=self.request.user, status='pending')
        order = serializer.instance
        CustomerEvent.objects.create(
            user=self.request.user,
            event_type='ORDER_CREATED',
            order=order,
            metadata={'quantity': order.quantity}
        )

class OrderApproveView(APIView):
    permission_classes = [IsSales]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, status='pending')
        payment_adapter = PaymentAdapter()
        payment_result = payment_adapter.request_downpayment(order)
        if payment_result['success']:
            order.approve()
            order.downpayment_transaction_id = payment_result['transaction_id']
            order.save()
            downpayment_invoice = generate_downpayment_invoice(order)
            order.downpayment_invoice.save(f"downpayment_invoice_{order.id}.pdf", downpayment_invoice)
            order.save()
            send_downpayment_request_email(order)
            CustomerEvent.objects.create(
                user=order.customer,
                event_type='ORDER_APPROVED',
                order=order,
                metadata={'transaction_id': order.downpayment_transaction_id}
            )
            return Response({"detail": "Order approved."}, status=status.HTTP_200_OK)
        return Response({"detail": "Payment initiation failed."}, status=status.HTTP_400_BAD_REQUEST)

class OrderVerifyDownPaymentView(APIView):
    permission_classes = [IsSales]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, status='approved')
        payment_adapter = PaymentAdapter()
        if payment_adapter.verify_payment(order.downpayment_transaction_id):
            order.confirm_downpayment()
            order.save()
            payment_result = payment_adapter.request_full_payment(order)
            if payment_result['success']:
                order.fullpayment_transaction_id = payment_result['transaction_id']
                order.fullpayment_amount = order.calculate_total() - order.downpayment_amount
                order.save()
                full_invoice = generate_invoice(order)
                order.invoice.save(f"invoice_{order.id}.pdf", full_invoice)
                order.save()
                send_fullpayment_request_email(order)
                CustomerEvent.objects.create(
                    user=order.customer,
                    event_type='DOWN_PAYMENT_VERIFIED',
                    order=order,
                    metadata={'transaction_id': order.downpayment_transaction_id}
                )
                return Response({"detail": "Down payment verified."}, status=status.HTTP_200_OK)
            return Response({"detail": "Full payment initiation failed."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Down payment verification failed."}, status=status.HTTP_400_BAD_REQUEST)

class OrderVerifyFullPaymentView(APIView):
    permission_classes = [IsSales]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, status='down_paid')
        payment_adapter = PaymentAdapter()
        if payment_adapter.verify_payment(order.fullpayment_transaction_id):
            order.confirm_full_payment()
            order.save()
            send_order_confirmation_email(order)
            CustomerEvent.objects.create(
                user=order.customer,
                event_type='FULL_PAYMENT_VERIFIED',
                order=order,
                metadata={'transaction_id': order.fullpayment_transaction_id}
            )
            return Response({"detail": "Full payment verified."}, status=status.HTTP_200_OK)
        return Response({"detail": "Full payment verification failed."}, status=status.HTTP_400_BAD_REQUEST)

class OrderShipView(APIView):
    permission_classes = [IsSales]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, status='confirmed')
        order.ship()
        order.save()
        send_shipment_confirmation_email(order)
        CustomerEvent.objects.create(
            user=order.customer,
            event_type='ORDER_SHIPPED',
            order=order,
            metadata={}
        )
        return Response({"detail": "Order shipped."}, status=status.HTTP_200_OK)

class CustomerEventListView(generics.ListAPIView):
    queryset = CustomerEvent.objects.all()
    serializer_class = CustomerEventSerializer
    permission_classes = [IsSales]

    def get_queryset(self):
        return CustomerEvent.objects.filter(user__role='customer')

# Reused utility functions from views.py
def generate_downpayment_invoice(order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Troutlodge Down Payment Invoice", styles['Title']))
    invoice_data = [
        ['Invoice Date:', timezone.now().strftime("%Y-%m-%d")],
        ['Invoice Number:', f"DP-{order.id}"],
        ['Order Number:', str(order.id)],
        ['Due Date:', order.downpayment_deadline.strftime("%Y-%m-%d")],
        ['Transaction ID:', order.downpayment_transaction_id or 'Pending'],
    ]
    customer_info = [
        ['Customer:', order.customer.username],
        ['Company:', order.customer.company or 'N/A'],
        ['VAT Number:', order.customer.vat_number or 'N/A'],
        ['Address:', order.customer.address or 'N/A'],
    ]
    product = order.availability.product
    order_details = [
        ['Product Type:', product.type],
        ['Ploidy:', product.ploidy],
        ['Diameter:', f"{product.diameter}mm"],
        ['Week Number:', str(order.availability.week_number)],
        ['Ship Date:', order.availability.expected_ship_date.strftime("%Y-%m-%d")],
        ['Quantity:', f"{order.quantity:,}"],
        ['Unit Price:', f"${product.price:.2f}"],
        ['Subtotal:', f"${order.quantity * product.price:.2f}"],
        ['Transport Cost:', f"${order.transport_cost:.2f}"],
        ['Total Amount:', f"${order.calculate_total():.2f}"],
        ['Down Payment (15%):', f"${order.downpayment_amount:.2f}"],
        ['Remaining Balance:', f"${order.calculate_total() - order.downpayment_amount:.2f}"],
    ]
    invoice_table = Table(invoice_data, colWidths=[100, 300])
    customer_table = Table(customer_info, colWidths=[100, 300])
    order_table = Table(order_details, colWidths=[150, 250])
    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, -3), (-1, -1), colors.lightblue),
    ]))
    elements.append(Paragraph("Invoice Details", styles['Heading3']))
    elements.append(invoice_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Customer Information", styles['Heading3']))
    elements.append(customer_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Order Details", styles['Heading3']))
    elements.append(order_table)
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Payment Instructions", styles['Normal']))
    elements.append(Paragraph("Bank: Troutlodge Financial", styles['Normal']))
    elements.append(Paragraph("Account: 1234-5678-9012", styles['Normal']))
    elements.append(Paragraph("SWIFT/BIC: TROUTLODGE", styles['Normal']))
    elements.append(Paragraph("Reference: DP-" + str(order.id), styles['Normal']))
    doc.build(elements)
    buffer.seek(0)
    return File(buffer, name=f"downpayment_invoice_{order.id}.pdf")

def generate_invoice(order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Troutlodge Full Payment Invoice", styles['Title']))
    invoice_data = [
        ['Invoice Date:', timezone.now().strftime("%Y-%m-%d")],
        ['Invoice Number:', f"INV-{order.id}"],
        ['Order Number:', str(order.id)],
        ['Due Date:', order.fullpayment_deadline.strftime("%Y-%m-%d") if order.fullpayment_deadline else 'N/A'],
        ['Transaction ID:', order.fullpayment_transaction_id or 'Pending'],
    ]
    customer_info = [
        ['Customer:', order.customer.username],
        ['Company:', order.customer.company or 'N/A'],
        ['VAT Number:', order.customer.vat_number or 'N/A'],
        ['Address:', order.customer.address or 'N/A'],
    ]
    product = order.availability.product
    order_details = [
        ['Product Type:', product.type],
        ['Ploidy:', product.ploidy],
        ['Diameter:', f"{product.diameter}mm"],
        ['Week Number:', str(order.availability.week_number)],
        ['Ship Date:', order.availability.expected_ship_date.strftime("%Y-%m-%d")],
        ['Quantity:', f"{order.quantity:,}"],
        ['Unit Price:', f"${product.price:.2f}"],
        ['Subtotal:', f"${order.quantity * product.price:.2f}"],
        ['Transport Cost:', f"${order.transport_cost:.2f}"],
        ['Total Amount:', f"${order.calculate_total():.2f}"],
        ['Down Payment Paid:', f"${order.downpayment_amount:.2f}"],
        ['Remaining Balance:', f"${order.calculate_total() - order.downpayment_amount:.2f}"],
    ]
    invoice_table = Table(invoice_data, colWidths=[120, 300])
    customer_table = Table(customer_info, colWidths=[120, 300])
    order_table = Table(order_details, colWidths=[180, 250])
    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, -2), (-1, -1), colors.lightgreen),
    ]))
    elements.append(Paragraph("Invoice Details", styles['Heading3']))
    elements.append(invoice_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Customer Information", styles['Heading3']))
    elements.append(customer_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Order Details", styles['Heading3']))
    elements.append(order_table)
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Payment Confirmation", styles['Heading3']))
    elements.append(Paragraph("This invoice confirms full payment for your order. Shipment will be arranged as per the expected ship date.", styles['Normal']))
    elements.append(Paragraph("Thank you for your business!", styles['Normal']))
    doc.build(elements)
    buffer.seek(0)
    return File(buffer, name=f"invoice_{order.id}.pdf")

def send_order_confirmation_email(order):
    subject = f"Order #{order.id} Confirmed"
    message = f"Dear {order.customer.username},\n\nYour order #{order.id} has been confirmed. Thank you for your purchase!\n\nTransaction ID: {order.fullpayment_transaction_id}"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.customer.email],
        fail_silently=False,
    )

def send_downpayment_request_email(order):
    subject = f"Troutlodge Down Payment Request for Order #{order.id}"
    message = f"Dear {order.customer.username},\n\n"
    message += f"Your order #{order.id} has been approved. Please make a down payment of ${order.downpayment_amount:.2f} within 3 days to secure your order.\n\n"
    message += f"Transaction ID: {order.downpayment_transaction_id}\n\n"
    message += "You can download the down payment invoice via the API.\n\n"
    message += "Thank you,\nTroutlodge Sales Team"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.customer.email],
        fail_silently=False,
    )

def send_fullpayment_request_email(order):
    subject = f"Troutlodge Full Payment Request for Order #{order.id}"
    message = f"Dear {order.customer.username},\n\n"
    message += f"Thank you for your down payment. Your order #{order.id} is now ready for full payment of ${order.calculate_total() - order.downpayment_amount:.2f}.\n\n"
    message += f"Transaction ID: {order.fullpayment_transaction_id}\n\n"
    message += "Please complete the payment within 14 days to avoid cancellation.\n\n"
    message += "You can download the full invoice via the API.\n\n"
    message += "Thank you,\nTroutlodge Sales Team"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.customer.email],
        fail_silently=False,
    )

def send_shipment_confirmation_email(order):
    subject = f"Troutlodge Shipment Confirmation for Order #{order.id}"
    message = f"Dear {order.customer.username},\n\n"
    message += f"Your order #{order.id} has been shipped and is expected to arrive on {order.availability.expected_ship_date.strftime('%Y-%m-%d')}.\n\n"
    message += "Thank you for your business!\nTroutlodge Team"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.customer.email],
        fail_silently=False,
    )