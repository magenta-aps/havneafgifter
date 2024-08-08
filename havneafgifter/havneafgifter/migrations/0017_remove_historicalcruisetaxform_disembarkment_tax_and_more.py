# Generated by Django 5.0.4 on 2024-08-06 08:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('havneafgifter', '0016_historicalcruisetaxform_historicalharborduesform'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalcruisetaxform',
            name='disembarkment_tax',
        ),
        migrations.RemoveField(
            model_name='historicalcruisetaxform',
            name='harbour_tax',
        ),
        migrations.RemoveField(
            model_name='historicalcruisetaxform',
            name='pax_tax',
        ),
        migrations.RemoveField(
            model_name='historicalcruisetaxform',
            name='pdf',
        ),
        migrations.RemoveField(
            model_name='historicalharborduesform',
            name='harbour_tax',
        ),
        migrations.RemoveField(
            model_name='historicalharborduesform',
            name='pdf',
        ),
        migrations.AddField(
            model_name='historicalcruisetaxform',
            name='reason_text',
            field=models.TextField(null=True, verbose_name='Reason text'),
        ),
        migrations.AddField(
            model_name='historicalharborduesform',
            name='reason_text',
            field=models.TextField(null=True, verbose_name='Reason text'),
        ),
    ]