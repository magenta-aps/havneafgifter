# Generated by Django 5.0.4 on 2024-09-20 08:33

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [('havneafgifter', '0021_alter_disembarkment_number_of_passengers_and_more'), ('havneafgifter', '0022_alter_port_name')]

    dependencies = [
        ('havneafgifter', '0020_vessel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='disembarkment',
            name='number_of_passengers',
            field=models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(0, message='Tallet er for lille'), django.core.validators.MaxValueValidator(20000, message='Tallet er for stort')], verbose_name='Number of passengers disembarking'),
        ),
        migrations.AlterField(
            model_name='disembarkmentsite',
            name='name',
            field=models.CharField(max_length=200, validators=[django.core.validators.MaxLengthValidator(200, message='Navnet er for langt'), django.core.validators.MinLengthValidator(4, message='Navnet er for kort')], verbose_name='Disembarkment site'),
        ),
        migrations.AlterField(
            model_name='disembarkmenttaxrate',
            name='disembarkment_tax_rate',
            field=models.DecimalField(decimal_places=2, max_digits=4, validators=[django.core.validators.MinValueValidator(0, message='Beløbet er for lavt'), django.core.validators.MaxValueValidator(50, message='Beløbet er for højt')], verbose_name='Disembarkment tax rate'),
        ),
        migrations.AlterField(
            model_name='harborduesform',
            name='date',
            field=models.DateField(auto_now_add=True, verbose_name='Form submission date'),
        ),
        migrations.AlterField(
            model_name='historicalcruisetaxform',
            name='date',
            field=models.DateField(blank=True, editable=False, verbose_name='Form submission date'),
        ),
        migrations.AlterField(
            model_name='historicalharborduesform',
            name='date',
            field=models.DateField(blank=True, editable=False, verbose_name='Form submission date'),
        ),
        migrations.AlterField(
            model_name='portauthority',
            name='email',
            field=models.EmailField(max_length=254, validators=[django.core.validators.EmailValidator(message='Ugyldig email adresse')], verbose_name='Port authority contact email'),
        ),
        migrations.AlterField(
            model_name='portauthority',
            name='name',
            field=models.CharField(max_length=32, validators=[django.core.validators.MaxLengthValidator(32, message='Navnet er for langt'), django.core.validators.MinLengthValidator(4, message='Navnet er for kort')], verbose_name='Port authority company name'),
        ),
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
        migrations.AlterField(
            model_name='porttaxrate',
            name='port_tax_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=12, validators=[django.core.validators.MinValueValidator(0, message='Tallet er for lavt'), django.core.validators.MaxValueValidator(999999999999, message='Tallet er for højt')], verbose_name='Tax per gross ton'),
        ),
        migrations.AlterField(
            model_name='porttaxrate',
            name='round_gross_ton_up_to',
            field=models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0, message='Tallet er for lavt'), django.core.validators.MaxValueValidator(2000000, message='Tallet er for højt')], verbose_name='Rund op til (ton)'),
        ),
        migrations.AlterField(
            model_name='taxrates',
            name='pax_tax_rate',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, validators=[django.core.validators.MinValueValidator(0, message='Beløbet er for lavt'), django.core.validators.MaxValueValidator(999999, message='Beløbet er for højt')], verbose_name='Afgift pr. passager'),
        ),
        migrations.AlterField(
            model_name='port',
            name='name',
            field=models.CharField(max_length=16, validators=[django.core.validators.MaxLengthValidator(16, message='Navnet er for langt'), django.core.validators.MinLengthValidator(4, message='Navnet er for kort')], verbose_name='Port name'),
        ),
    ]
