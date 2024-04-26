# Generated by Django 5.0.4 on 2024-05-10 11:19

import django.contrib.auth.mixins
import django_tables2.views
import havneafgifter.views
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('havneafgifter', '0002_alter_portauthority_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='HarborDuesFormListView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'abstract': False,
            },
            bases=(django.contrib.auth.mixins.LoginRequiredMixin, models.Model, havneafgifter.views.HavneafgiftView, django_tables2.views.SingleTableView),
        ),
    ]
