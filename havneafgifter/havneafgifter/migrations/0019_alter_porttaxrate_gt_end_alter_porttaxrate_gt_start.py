# Generated by Django 5.0.4 on 2024-08-23 12:24

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('havneafgifter', '0018_alter_disembarkment_number_of_passengers_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='porttaxrate',
            name='gt_end',
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(2000000, message='Tallet er for højt')], verbose_name='Vessel gross tonnage (upper)'),
        ),
        migrations.AlterField(
            model_name='porttaxrate',
            name='gt_start',
            field=models.PositiveIntegerField(validators=[django.core.validators.MaxValueValidator(2000000, message='Tallet er for højt')], verbose_name='Vessel gross tonnage (lower)'),
        ),
    ]