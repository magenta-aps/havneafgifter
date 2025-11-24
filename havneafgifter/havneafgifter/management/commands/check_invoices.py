# SPDX-FileCopyrightText: 2025 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
from collections import defaultdict
from datetime import date
from typing import List

from django.core.management.base import BaseCommand

from havneafgifter.models import HarborDuesForm, Status
from havneafgifter.prisme import Prisme, PrismeSELAccountResponse


class Command(BaseCommand):
    def handle(self, *args, **options):
        qs = HarborDuesForm.objects.filter(status=Status.INVOICED)
        if qs.exists():
            prisme = Prisme()
            by_cvr = defaultdict(list)
            for item in qs:
                by_cvr[item.cvr].append(item)  # TODO: skaf CVR
            for cvr, items in by_cvr.items():
                try:
                    by_invoice_number = {
                        f"{HarborDuesForm.invoice_prefix}{item.pk}": item
                    }
                    earliest_submit = min([item.date for item in items])
                    responses: List[PrismeSELAccountResponse] = prisme.get_account_data(
                        cvr, date_from=earliest_submit, date_to=date.today()
                    )
                    for response in responses:
                        # TODO: Tjek at dette holder med info fra Prisme
                        for transaction in response.transactions:
                            if transaction.extern_invoice_number in by_invoice_number:
                                harborduesform = by_invoice_number[
                                    transaction.extern_invoice_number
                                ]
                                if transaction.remaining_amount == 0:
                                    # Apparently, when running in a management command,
                                    # we automatically have permission to call `pay()`
                                    harborduesform.status.pay()
                except Exception as e:
                    print(f"Failed for {cvr}: {e}")
                    # Run next iteration
