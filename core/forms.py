from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Order, Availability, User

class OrderRequestForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['availability', 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['availability'].queryset = Availability.objects.filter(available_quantity__gt=0)

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ('username', 'email', 'company', 'phone', 'role', 'password1', 'password2')