# troutlodge/urls.py
from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),  # Root URL
    path('', include('core.urls')),  # Include core app URLs
    path('login/', include('django.contrib.auth.urls')),  # Django auth URLs
]