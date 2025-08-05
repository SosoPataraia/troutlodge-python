from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Order, Availability, User, Product
from decimal import Decimal

class AvailabilityForm(forms.ModelForm):
    strain = forms.ChoiceField(choices=Product.TYPE_CHOICES)
    ploidy = forms.ChoiceField(choices=Product.PLOIDY_CHOICES)
    diameter = forms.ChoiceField(choices=Product.DIAMETER_CHOICES)
    year = forms.IntegerField(min_value=2020, max_value=2030, initial=2025)
    week_number = forms.IntegerField(min_value=1, max_value=52)
    available_quantity = forms.IntegerField(min_value=0)

    class Meta:
        model = Availability
        fields = ['year', 'week_number', 'available_quantity']

    def clean(self):
        cleaned_data = super().clean()
        strain = cleaned_data.get('strain')
        ploidy = cleaned_data.get('ploidy')
        diameter = cleaned_data.get('diameter')
        year = cleaned_data.get('year')
        week_number = cleaned_data.get('week_number')
        quantity = cleaned_data.get('available_quantity')

        if strain and ploidy and diameter and year and week_number:
            product, created = Product.objects.get_or_create(
                type=strain,
                ploidy=ploidy,
                diameter=diameter,
                defaults={'price': 0}  # Adjust default price as needed
            )
            cleaned_data['product'] = product

            try:
                existing = Availability.objects.get(product=product, year=year, week_number=week_number)
                self.instance = existing  # Set instance to update existing record
            except Availability.DoesNotExist:
                pass  # New record will be created
        else:
            raise ValidationError("All product details, year, and week number are required.")

        if quantity < 0:
            raise ValidationError("Available quantity cannot be negative.")

        return cleaned_data

    def save(self, commit=True):
        availability = super().save(commit=False)
        availability.product = self.cleaned_data['product']
        if commit:
            availability.save()
        return availability

class OrderRequestForm(forms.ModelForm):
    strain = forms.ChoiceField(choices=Product.TYPE_CHOICES)
    ploidy = forms.ChoiceField(choices=Product.PLOIDY_CHOICES)
    year = forms.IntegerField(min_value=2020, max_value=2030, initial=2025)
    week_number = forms.IntegerField(min_value=1, max_value=52)
    quantity = forms.IntegerField(min_value=1)

    class Meta:
        model = Order
        fields = ['quantity']

    def clean(self):
        cleaned_data = super().clean()
        strain = cleaned_data.get('strain')
        ploidy = cleaned_data.get('ploidy')
        year = cleaned_data.get('year')
        week_number = cleaned_data.get('week_number')
        quantity = cleaned_data.get('quantity')

        if strain and ploidy and year and week_number:
            # Find a product with any diameter (since diameter is not selected)
            try:
                product = Product.objects.filter(type=strain, ploidy=ploidy).first()
                if not product:
                    raise ValidationError("No product matches the selected strain and ploidy.")
                availability = Availability.objects.get(
                    product=product, year=year, week_number=week_number
                )
                if availability.available_quantity < quantity:
                    raise ValidationError("Requested quantity exceeds available stock.")
                cleaned_data['availability'] = availability
            except Availability.DoesNotExist:
                raise ValidationError("No availability for the selected product, year, and week.")
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        order.availability = self.cleaned_data['availability']
        if commit:
            order.save()
        return order


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)
    vat_number = forms.CharField(max_length=50, required=False, label="VAT Number")
    address = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'company', 'phone', 'vat_number', 'address', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'customer'  # Force role to 'customer'
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