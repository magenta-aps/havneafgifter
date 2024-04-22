import os

from django.core.management import call_command
from django.db import migrations


def load_initial_data(apps, schema_editor):
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "initial_disembarkment_sites.json",
    )
    call_command("loaddata", path, verbosity=2)


class Migration(migrations.Migration):
    dependencies = [
        ('havneafgifter', '0004_alter_disembarkmentsite_name'),
    ]

    operations = [
        migrations.RunPython(load_initial_data)
    ]
