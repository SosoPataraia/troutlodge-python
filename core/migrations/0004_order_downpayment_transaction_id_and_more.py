# Generated by Django 5.2.3 on 2025-07-02 14:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_order_commission_rate_order_downpayment_amount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='downpayment_transaction_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='fullpayment_transaction_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
