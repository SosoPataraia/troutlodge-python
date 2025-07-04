# core/views.py
from datetime import datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, FileResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from collections import defaultdict
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .forms import OrderApprovalForm, DownPaymentForm, FullPaymentForm, OrderRequestForm, CustomUserCreationForm, \
    AvailabilityForm
from .models import User, Product, Availability, Order, CustomerEvent
from .payment import PaymentAdapter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from django.core.files import File
from django.urls import reverse

def sales_required(view_func):
    return user_passes_test(lambda u: u.role == 'sales')(view_func)

def hatchery_required(view_func):
    return user_passes_test(lambda u: u.role == 'hatchery')(view_func)

def customer_required(view_func):
    return user_passes_test(lambda u: u.role == 'customer')(view_func)

# Signal handlers for login/logout
@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if user.role == 'customer':
        CustomerEvent.objects.create(
            user=user,
            event_type='LOGIN',
            metadata={'ip_address': request.META.get('REMOTE_ADDR')}
        )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user.role == 'customer':
        CustomerEvent.objects.create(
            user=user,
            event_type='LOGOUT',
            metadata={'ip_address': request.META.get('REMOTE_ADDR')}
        )

@login_required
def dashboard(request):
    if request.user.role == 'sales':
        return sales_dashboard(request)
    elif request.user.role == 'hatchery':
        return hatchery_dashboard(request)
    elif request.user.role == 'customer':
        return customer_dashboard(request)
    return HttpResponseForbidden()

@sales_required
def sales_dashboard(request):
    pending_orders = Order.objects.filter(status='pending')
    confirmed_orders = Order.objects.filter(status='confirmed').order_by('-confirmed_at')[:10]
    shipped_orders = Order.objects.filter(status='shipped')[:5]
    return render(request, 'sales_dashboard.html', {
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
    })

@sales_required
def approve_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='pending')
    payment_adapter = PaymentAdapter()
    if request.method == 'POST':
        form = OrderApprovalForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save(commit=False)
            order.approve()
            payment_result = payment_adapter.request_downpayment(order)
            if payment_result['success']:
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
                return redirect('sales_dashboard')
            else:
                return render(request, 'error.html', {'message': 'Payment initiation failed'})
    else:
        form = OrderApprovalForm(instance=order)
    return render(request, 'approve_order.html', {
        'order': order,
        'form': form,
        'total': order.calculate_total(),
        'downpayment': order.calculate_downpayment()
    })

@sales_required
def verify_down_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='approved')
    payment_adapter = PaymentAdapter()
    if request.method == 'POST':
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
                return redirect('sales_dashboard')
            else:
                return render(request, 'error.html', {'message': 'Full payment initiation failed'})
        else:
            return render(request, 'error.html', {'message': 'Down payment verification failed'})
    return render(request, 'verify_payment.html', {
        'order': order,
        'payment_type': 'down payment'
    })

@sales_required
def verify_full_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='down_paid')
    payment_adapter = PaymentAdapter()
    if request.method == 'POST':
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
            return redirect('sales_dashboard')
        else:
            return render(request, 'error.html', {'message': 'Full payment verification failed'})
    return render(request, 'verify_payment.html', {
        'order': order,
        'payment_type': 'full payment'
    })

@sales_required
def ship_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, status='confirmed')
    if request.method == 'POST':
        order.ship()
        order.save()
        send_shipment_confirmation_email(order)
        CustomerEvent.objects.create(
            user=order.customer,
            event_type='ORDER_SHIPPED',
            order=order,
            metadata={}
        )
        return redirect('sales_dashboard')
    return render(request, 'ship_order.html', {'order': order})

@login_required
def availability_view(request):
    year = int(request.GET.get('year', 2025))
    availabilities = Availability.objects.filter(year=year).order_by('week_number')
    years = range(2020, 2031)  # List of years from 2020 to 2030

    weeks = range(1, 53)
    products = Product.objects.all().order_by('type', 'ploidy', 'diameter')
    pivot_data = defaultdict(lambda: defaultdict(int))
    for avail in availabilities:
        pivot_data[avail.week_number][avail.product.id] = avail.available_quantity

    table_data = []
    for week in weeks:
        row = [week]
        for product in products:
            quantity = pivot_data[week].get(product.id, 0)
            row.append(quantity)
        table_data.append(row)

    return render(request, 'availability_view.html', {
        'year': year,
        'years': years,
        'weeks': weeks,
        'products': products,
        'table_data': table_data,
    })


@login_required
@hatchery_required
def hatchery_dashboard(request):
    year = int(request.GET.get('year', 2025))
    availabilities = Availability.objects.filter(year=year).order_by('week_number')
    years = range(2020, 2031)  # List of years from 2020 to 2030
    form = AvailabilityForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        availability = form.save()
        return redirect('hatchery_dashboard')
    return render(request, 'hatchery_dashboard.html', {
        'availabilities': availabilities,
        'year': year,
        'years': years,
        'form': form,
    })

@hatchery_required
def update_availability(request):
    if request.method == 'POST':
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('hatchery_dashboard')
        else:
            products = Product.objects.all()
            year = request.POST.get('year', 2025)
            availabilities = Availability.objects.filter(year=year).order_by('week_number')
            availability_data = [
                {
                    'product': avail.product,
                    'week_number': avail.week_number,
                    'week_start_date': datetime.datetime.strptime(f"{avail.year}-{avail.week_number}-1", "%Y-%W-%w").date(),
                    'available_quantity': avail.available_quantity,
                } for avail in availabilities
            ]
            return render(request, 'hatchery_dashboard.html', {
                'products': products,
                'availabilities': availability_data,
                'form': form,
                'year': year,
            })
    return redirect('hatchery_dashboard')

@customer_required
def customer_dashboard(request):
    reservations = Order.objects.filter(customer=request.user, status__in=['approved', 'down_paid'])
    confirmed_orders = Order.objects.filter(customer=request.user, status='confirmed')
    shipped_orders = Order.objects.filter(customer=request.user, status='shipped')
    available_batches = Availability.objects.filter(available_quantity__gt=0)
    return render(request, 'customer_dashboard.html', {
        'available_batches': available_batches,
        'reservations': reservations,
        'confirmed_orders': confirmed_orders,
        'shipped_orders': shipped_orders,
    })

@customer_required
def upload_down_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user, status='approved')
    if request.method == 'POST':
        form = DownPaymentForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            order = form.save()
            notify_sales_payment_uploaded(order, 'down payment')
            CustomerEvent.objects.create(
                user=order.customer,
                event_type='DOWN_PAYMENT_UPLOADED',
                order=order,
                metadata={'transaction_id': order.downpayment_transaction_id}
            )
            return redirect('customer_dashboard')
    else:
        form = DownPaymentForm(instance=order)
    return render(request, 'upload_payment.html', {
        'form': form,
        'order': order,
        'payment_type': 'down payment'
    })

@customer_required
def upload_full_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user, status='down_paid')
    if request.method == 'POST':
        form = FullPaymentForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            order = form.save()
            notify_sales_payment_uploaded(order, 'full payment')
            CustomerEvent.objects.create(
                user=order.customer,
                event_type='FULL_PAYMENT_UPLOADED',
                order=order,
                metadata={'transaction_id': order.fullpayment_transaction_id}
            )
            return redirect('customer_dashboard')
    else:
        form = FullPaymentForm(instance=order)
    return render(request, 'upload_payment.html', {
        'form': form,
        'order': order,
        'payment_type': 'full payment'
    })

@login_required
def view_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.role == 'sales' or (request.user.role == 'customer' and request.user == order.customer)):
        return HttpResponseForbidden()
    return FileResponse(
        order.invoice,
        as_attachment=False,
        filename=f"invoice_{order.id}.pdf",
        content_type='application/pdf'
    )

def generate_provisional_downpayment_invoice(order):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Troutlodge Provisional Down Payment Invoice", styles['Title']))
    invoice_data = [
        ['Invoice Date:', timezone.now().strftime("%Y-%m-%d")],
        ['Invoice Number:', f"DP-{order.id}"],
        ['Order Number:', str(order.id)],
        ['Due Date:', (timezone.now() + timezone.timedelta(days=3)).strftime("%Y-%m-%d")],
    ]
    customer_info = [
        ['Customer:', order.customer.username],
        ['Company:', order.customer.company or 'N/A'],
        ['VAT Number:', order.customer.vat_number or 'N/A'],
        ['Address:', order.customer.address or 'N/A'],
    ]
    product = order.availability.product
    subtotal = order.quantity * product.price
    downpayment = subtotal * Decimal('0.15')
    order_details = [
        ['Product Type:', product.type],
        ['Ploidy:', product.ploidy],
        ['Diameter:', f"{product.diameter}mm"],
        ['Week Number:', str(order.availability.week_number)],
        ['Quantity:', f"{order.quantity:,}"],
        ['Unit Price:', f"${product.price:.2f}"],
        ['Subtotal:', f"${subtotal:.2f}"],
        ['Down Payment (15%):', f"${downpayment:.2f}"],
    ]
    elements.append(Paragraph("Note: Transport cost will be added upon approval.", styles['Normal']))
    invoice_table = Table(invoice_data, colWidths=[100, 300])
    customer_table = Table(customer_info, colWidths=[100, 300])
    order_table = Table(order_details, colWidths=[150, 250])
    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, -2), (-1, -1), colors.lightblue),
    ]))
    elements.append(Paragraph("Invoice Details", styles['Heading3']))
    elements.append(invoice_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Customer Information", styles['Heading3']))
    elements.append(customer_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Order Details", styles['Heading3']))
    elements.append(order_table)
    doc.build(elements)
    buffer.seek(0)
    return File(buffer, name=f"provisional_downpayment_invoice_{order.id}.pdf")

@login_required
def request_order(request):
    if request.method == 'POST':
        form = OrderRequestForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.customer = request.user
            order.status = 'pending'
            order.save()
            provisional_invoice = generate_provisional_downpayment_invoice(order)
            order.downpayment_invoice.save(f"provisional_downpayment_invoice_{order.id}.pdf", provisional_invoice)
            order.save()
            CustomerEvent.objects.create(
                user=order.customer,
                event_type='ORDER_CREATED',
                order=order,
                metadata={'quantity': order.quantity}
            )
            return redirect('view_downpayment_invoice', order_id=order.id)
    else:
        form = OrderRequestForm()
    return render(request, 'request_order.html', {'form': form})

@login_required
def view_downpayment_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'view_downpayment_invoice.html', {'order': order})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

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
    recipient_list = [order.customer.email]
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        fail_silently=False,
    )

def send_downpayment_request_email(order):
    subject = f"Troutlodge Down Payment Request for Order #{order.id}"
    message = f"Dear {order.customer.username},\n\n"
    message += f"Your order #{order.id} has been approved. Please make a down payment of ${order.downpayment_amount:.2f} within 3 days to secure your order.\n\n"
    message += f"Transaction ID: {order.downpayment_transaction_id}\n\n"
    message += "You can download the down payment invoice from your dashboard.\n\n"
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
    message += "You can download the full invoice from your dashboard.\n\n"
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

def notify_sales_payment_uploaded(order, payment_type):
    subject = f"Payment Proof Uploaded for Order #{order.id}"
    message = f"A {payment_type} proof has been uploaded for order #{order.id} by {order.customer.username}.\n\n"
    message += f"Transaction ID: {order.downpayment_transaction_id if payment_type == 'down payment' else order.fullpayment_transaction_id}\n\n"
    message += "Please verify the payment in the sales dashboard."
    sales_team = User.objects.filter(role='sales')
    recipients = [user.email for user in sales_team]
    if recipients:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )