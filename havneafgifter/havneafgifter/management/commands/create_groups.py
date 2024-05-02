# SPDX-FileCopyrightText: 2023 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
from typing import Iterable, Tuple, Type

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    PassengersByCountry,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    TaxRates,
    User,
)


class Command(BaseCommand):
    help = "Creates groups"

    def get_permissions(self, *modelactions: Tuple[Type, Iterable[str]]):
        for model, actions in modelactions:
            content_type = ContentType.objects.get_for_model(
                model, for_concrete_model=False
            )
            for action in actions:
                yield Permission.objects.get(
                    codename=f"{action}_{content_type.model}",
                    content_type=content_type,
                )

    def set_group_permissions(self, group: Group, *permissions: Permission):
        for permission in permissions:
            group.permissions.add(permission)

    def handle(self, *args, **options):
        self.setup_permissions()
        self.setup_port_authority()
        self.setup_shipping_agent()
        self.setup_tax_officer()

    def setup_permissions(self):
        harborduesform_contenttype = ContentType.objects.get_for_model(
            HarborDuesForm, for_concrete_model=False
        )
        cruisetaxform_contenttype = ContentType.objects.get_for_model(
            CruiseTaxForm, for_concrete_model=False
        )
        Permission.objects.create(
            content_type=harborduesform_contenttype,
            codename="approve_harborduesform",
            name="Can approve harborduesforms",
        )
        Permission.objects.create(
            content_type=harborduesform_contenttype,
            codename="reject_harborduesform",
            name="Can reject harborduesforms",
        )
        Permission.objects.create(
            content_type=harborduesform_contenttype,
            codename="invoice_harborduesform",
            name="Can invoice harborduesforms",
        )
        Permission.objects.create(
            content_type=cruisetaxform_contenttype,
            codename="approve_cruisetaxform",
            name="Can approve cruisetaxforms",
        )
        Permission.objects.create(
            content_type=cruisetaxform_contenttype,
            codename="reject_cruisetaxform",
            name="Can reject cruisetaxforms",
        )
        Permission.objects.create(
            content_type=cruisetaxform_contenttype,
            codename="invoice_cruisetaxform",
            name="Can invoice cruisetaxforms",
        )

    def setup_port_authority(self):
        havnemyndighed, _ = Group.objects.update_or_create(
            name="PortAuthority",
        )
        self.set_group_permissions(
            havnemyndighed,
            *self.get_permissions(
                # Port managers have access to the following actions
                # on all model instances of these classes
                (DisembarkmentSite, ("view",)),
                (DisembarkmentTaxRate, ("view",)),
                (
                    Port,
                    (
                        "view",
                        "add",
                    ),
                ),
                (PortAuthority, ("view",)),
                (PortTaxRate, ("view",)),
                (ShippingAgent, ("view",)),
                (TaxRates, ("view",)),
                (
                    User,
                    (
                        "view",
                        "add",
                    ),
                ),
            ),
        )

    def setup_shipping_agent(self):
        shipping, _ = Group.objects.update_or_create(name="Shipping")
        self.set_group_permissions(
            shipping,
            *self.get_permissions(
                # Shipping agents have access to the following actions
                # on all model instances of these classes
                (CruiseTaxForm, ("add",)),
                (Disembarkment, ("add",)),
                (DisembarkmentSite, ("view",)),
                (DisembarkmentTaxRate, ("view",)),
                (HarborDuesForm, ("add",)),
                (PassengersByCountry, ("add",)),
                (Port, ("view",)),
                (PortAuthority, ("view",)),
                (PortTaxRate, ("view",)),
                (ShippingAgent, ("view",)),
                (TaxRates, ("view",)),
                (User, ("view",)),
            ),
        )

    def setup_tax_officer(self):
        tax, _ = Group.objects.update_or_create(name="TaxAuthority")
        self.set_group_permissions(
            tax,
            *self.get_permissions(
                # Tax officers have access to the following actions
                # on all model instances of these classes
                (CruiseTaxForm, ("view",)),
                (Disembarkment, ("view",)),
                (DisembarkmentSite, ("view", "add", "change")),
                (DisembarkmentTaxRate, ("add", "view", "change")),
                (HarborDuesForm, ("view",)),
                (PassengersByCountry, ("view",)),
                (Port, ("view",)),
                (PortAuthority, ("view",)),
                (PortTaxRate, ("add", "view", "change")),
                (ShippingAgent, ("view",)),
                (TaxRates, ("add", "view", "change")),
                (User, ("view",)),
            ),
        )
