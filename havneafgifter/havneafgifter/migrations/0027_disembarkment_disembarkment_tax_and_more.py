# Generated by Django 5.1.3 on 2025-03-21 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('havneafgifter', '0026_alter_portauthority_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='disembarkment',
            name='disembarkment_tax',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True, verbose_name='Landsætningsafgift for pågældende anløb'),
        ),
        migrations.AddField(
            model_name='disembarkment',
            name='used_disembarkment_tax_rate',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True, verbose_name='Tax rate used for existing calculation'),
        ),
    ]
