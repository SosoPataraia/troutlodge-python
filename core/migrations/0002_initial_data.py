from django.db import migrations

def create_initial_products(apps, schema_editor):
    Product = apps.get_model('core', 'Product')
    products = [
        {'type': 'steelhead', 'ploidy': 'diploid', 'diameter': 4, 'price': 0.10},
        {'type': 'steelhead', 'ploidy': 'diploid', 'diameter': 5, 'price': 0.15},
        {'type': 'steelhead', 'ploidy': 'triploid', 'diameter': 4, 'price': 0.12},
        {'type': 'jumper', 'ploidy': 'diploid', 'diameter': 5, 'price': 0.18},
        {'type': 'kamloop', 'ploidy': 'triploid', 'diameter': 6, 'price': 0.20},
    ]
    for product in products:
        Product.objects.create(**product)

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_products),
    ]