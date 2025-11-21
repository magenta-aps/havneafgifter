# SPDX-FileCopyrightText: 2023 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from django.core.management.base import BaseCommand

from havneafgifter.models import HarborDuesForm, Status


class Command(BaseCommand):
    def handle(self, *args, **options):
        qs = HarborDuesForm.objects.filter(status=Status.NEW)
        for report in qs:
            report.send_invoice()
