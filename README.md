# Trout eggs Management System

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Django](https://img.shields.io/badge/django-5.0-green)

A web application for managing trout fish orders, inventory, and sales processes.

## Features
- Role-based access (Hatchery, Sales, Customer)
- Product availability tracking
- Order management system
- Automated invoice generation

## Setup
```bash
# Clone repository
git clone https://github.com/yourusername/troutlodge-python.git

# Install dependencies
pip install -r requirements.txt

# Migrate database
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver
```

## Test Users
| Role       | Username   | Password     |
|------------|------------|--------------|
| Sales      | sales1     | testpass123  |
| Hatchery   | hatchery1  | testpass123  |
| Customer   | customer1  | testpass123  |
