from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Order, Availability, User
from decimal import Decimal

class AvailabilityForm(forms.ModelForm):
    year = forms.IntegerField(min_value=2020, max_value=2030, initial=2025)
    week_number = forms.IntegerField(min_value=1, max_value=52)
    expected_ship_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Availability
        fields = ['product', 'year', 'week_number', 'available_quantity', 'expected_ship_date']

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get('year')
        week_number = cleaned_data.get('week_number')
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('available_quantity')

        # Validate quantity
        if quantity < 0:
            raise ValidationError("Available quantity cannot be negative.")

        # Validate week number
        if week_number < 1 or week_number > 52:
            raise ValidationError("Week number must be between 1 and 52.")

        # Check for existing availability
        if self.instance.pk is None:  # New instance
            if Availability.objects.filter(product=product, year=year, week_number=week_number).exists():
                raise ValidationError("Availability for this product, year, and week already exists.")

        return cleaned_data

class OrderRequestForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['availability', 'quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={'min': 20000, 'step': 10000})  # Minimum 20k, increments of 10k
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['availability'].queryset = Availability.objects.filter(available_quantity__gt=0)

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        availability = self.cleaned_data.get('availability')

        # Validate minimum order quantity (20,000)
        if quantity < 20000:
            raise ValidationError("Minimum order quantity is 20,000 eggs.")

        # Validate quantity is multiple of 10,000
        if quantity % 10000 != 0:
            raise ValidationError("Quantity must be in multiples of 10,000 eggs.")

        # Validate against available quantity
        if availability and quantity > availability.available_quantity:
            raise ValidationError(
                f"Requested quantity exceeds available amount. Only {availability.available_quantity} available."
            )

        return quantity


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)
    vat_number = forms.CharField(max_length=50, required=False, label="VAT Number")
    address = forms.CharField(widget=forms.Textarea, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ('username', 'email', 'company', 'phone', 'vat_number', 'address', 'role', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        # Set default role to customer if not specified
        if not user.role:
            user.role = 'customer'
        if commit:
            user.save()
        return user


# New payment-related forms
class DownPaymentForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['downpayment_proof']
        widgets = {
            'downpayment_proof': forms.ClearableFileInput(attrs={
                'accept': 'application/pdf,image/*',
                'class': 'form-control'
            })
        }

    def clean_downpayment_proof(self):
        proof = self.cleaned_data.get('downpayment_proof')
        if proof and proof.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError("File too large (max 5MB)")
        return proof


class FullPaymentForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['fullpayment_proof']
        widgets = {
            'fullpayment_proof': forms.ClearableFileInput(attrs={
                'accept': 'application/pdf,image/*',
                'class': 'form-control'
            })
        }

    def clean_fullpayment_proof(self):
        proof = self.cleaned_data.get('fullpayment_proof')
        if proof and proof.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError("File too large (max 5MB)")
        return proof


class OrderApprovalForm(forms.ModelForm):
    commission_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        initial=5.0,
        label="Commission Rate (%)"
    )
    transport_cost = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=True,
        initial=100.00,
        label="Transport Cost ($)"
    )
    downpayment_deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        initial=timezone.now() + timezone.timedelta(days=3)
    )

    class Meta:
        model = Order
        fields = ['commission_rate', 'transport_cost', 'downpayment_deadline', 'notes']

    def clean_commission_rate(self):
        rate = self.cleaned_data.get('commission_rate', 0)
        if rate > 20:  # Max commission 20%
            raise ValidationError("Commission rate cannot exceed 20%")
        return rate

    def clean_transport_cost(self):
        cost = self.cleaned_data.get('transport_cost')
        if cost < 0:
            raise ValidationError("Transport cost cannot be negative")
        return cost