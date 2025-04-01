# Generated by Django 5.1.3 on 2025-04-01 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('havneafgifter', '0028_alter_disembarkment_number_of_passengers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='harborduesform',
            name='vessel_imo',
            field=models.CharField(blank=True, max_length=7, null=True, verbose_name='IMO-no.'),
        ),
        migrations.AlterField(
            model_name='historicalcruisetaxform',
            name='vessel_imo',
            field=models.CharField(blank=True, max_length=7, null=True, verbose_name='IMO-no.'),
        ),
        migrations.AlterField(
            model_name='historicalharborduesform',
            name='vessel_imo',
            field=models.CharField(blank=True, max_length=7, null=True, verbose_name='IMO-no.'),
        ),
    ]
