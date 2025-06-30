from io import BytesIO
from django.core.files import File
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, FileResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from .models import User, Product, Availability, Order
from .forms import OrderRequestForm
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


# ======================
# Custom Decorators
# ======================
def sales_required(view_func):
    """Restrict access to sales team members only"""
    return user_passes_test(lambda u: u.role == 'sales')(view_func)


def hatchery_required(view_func):
    """Restrict access to hatchery management only"""
    return user_passes_test(lambda u: u.role == 'hatchery')(view_func)


def customer_required(view_func):
    """Restrict access to customers only"""
    return user_passes_test(lambda u: u.role == 'customer')(view_func)


# ======================
# Core Views
# ======================
def hatchery_dashboard(request):
    pass


@login_required
def dashboard(request):
    """Main dashboard routing view"""
    if request.user.role == 'sales':
        return sales_dashboard(request)
    elif request.user.role == 'hatchery':
        return hatchery_dashboard(request)
    elif request.user.role == 'customer':
        return customer_dashboard(request)
    return HttpResponseForbidden()


# ======================
# Sales Team Views
# ======================
@sales_required
def sales_dashboard(request):
    """Sales team dashboard showing pending and confirmed orders"""
    pending_orders = Order.objects.filter(status='pending')
    confirmed_orders = Order.objects.filter(status='confirmed').order_by('-confirmed_at')[:10]
    return render(request, 'sales_dashboard.html', {
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders
    })


@sales_required
def confirm_order(request, order_id):
    """Confirm a pending order and generate invoice"""
    order = get_object_or_404(Order, id=order_id, status='pending')

    if request.method == 'POST':
        # Generate and save invoice
        invoice_file = generate_invoice(order)
        order.invoice.save(f"invoice_{order.id}.pdf", invoice_file)

        # Update order status
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()

        # Send confirmation email
        send_order_confirmation_email(order)

        return redirect('dashboard')

    return render(request, 'confirm_order.html', {'order': order})


# ======================
# Hatchery Views
# ======================
@hatchery_required
def update_availability(request):
    """Update product availability information"""
    if request.method == 'POST':
        try:
            product_id = request.POST.get('product')
            week_number = request.POST.get('week_number')
            quantity = int(request.POST.get('quantity'))
            ship_date = request.POST.get('ship_date')

            product = get_object_or_404(Product, id=product_id)

            Availability.objects.update_or_create(
                product=product,
                week_number=week_number,
                defaults={
                    'available_quantity': quantity,
                    'expected_ship_date': ship_date
                }
            )
            return redirect('dashboard')

        except (ValueError, TypeError):
            return render(request, 'error.html', {'message': 'Invalid input data'})

    products = Product.objects.all()
    return render(request, 'hatchery_dashboard.html', {'products': products})


# ======================
# Customer Views
# ======================
@customer_required
def customer_dashboard(request):
    """Customer dashboard showing available products and orders"""
    available_batches = Availability.objects.filter(available_quantity__gt=0)
    customer_orders = Order.objects.filter(customer=request.user)
    return render(request, 'customer_dashboard.html', {
        'available_batches': available_batches,
        'orders': customer_orders
    })


@customer_required
def request_order(request):
    """Handle new order requests from customers"""
    if request.method == 'POST':
        form = OrderRequestForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.customer = request.user
            order.status = 'pending'
            order.save()
            return redirect('dashboard')
    else:
        form = OrderRequestForm()

    return render(request, 'request_order.html', {'form': form})


# ======================
# Shared Views
# ======================
@login_required
def view_invoice(request, order_id):
    """View/download invoice PDF"""
    order = get_object_or_404(Order, id=order_id)

    if not (request.user.role == 'sales' or
            (request.user.role == 'customer' and request.user == order.customer)):
        return HttpResponseForbidden()

    return FileResponse(
        order.invoice,
        as_attachment=False,
        filename=f"invoice_{order.id}.pdf",
        content_type='application/pdf'
    )


def register(request):
    """Handle new user registration"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'customer'  # Default role
            user.save()
            return redirect('login')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


# ======================
# Utility Functions
# ======================
def generate_invoice(order):
    """Generate PDF invoice using ReportLab"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Add invoice header
    elements.append(Paragraph("Troutlodge Invoice", styles['Title']))
    elements.append(Paragraph(f"Order #{order.id}", styles['Heading2']))

    # Customer information table
    customer_info = [
        ['Customer:', order.customer.username],
        ['Company:', order.customer.company or 'N/A'],
        ['Email:', order.customer.email],
        ['Phone:', order.customer.phone or 'N/A'],
    ]

    # Order details table
    product = order.availability.product
    order_details = [
        ['Product Type:', product.type],
        ['Ploidy:', product.ploidy],
        ['Diameter:', f"{product.diameter}mm"],
        ['Week Number:', str(order.availability.week_number)],
        ['Ship Date:', order.availability.expected_ship_date.strftime("%Y-%m-%d")],
        ['Quantity:', str(order.quantity)],
        ['Unit Price:', f"${product.price:.2f}"],
        ['Total:', f"${order.quantity * product.price:.2f}"],
    ]

    # Create and style tables
    customer_table = Table(customer_info, colWidths=[100, 300])
    order_table = Table(order_details, colWidths=[100, 300])

    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))

    # Add elements to PDF
    elements.append(Paragraph("Customer Information", styles['Heading3']))
    elements.append(customer_table)
    elements.append(Paragraph("Order Details", styles['Heading3']))
    elements.append(order_table)

    doc.build(elements)
    buffer.seek(0)
    return File(buffer, name=f"invoice_{order.id}.pdf")


def send_order_confirmation_email(order):
    """Send order confirmation email to customer"""
    subject = f"Troutlodge Order Confirmation #{order.id}"
    message = f"Your order #{order.id} has been confirmed.\n\n"
    message += f"Product: {order.availability.product}\n"
    message += f"Quantity: {order.quantity}\n"
    message += f"Expected Ship Date: {order.availability.expected_ship_date}\n\n"
    message += "You can view your invoice at: "
    message += f"{settings.BASE_URL}{reverse('view_invoice', args=[order.id])}"

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.customer.email],
        fail_silently=False,
    )