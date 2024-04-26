# SPDX-FileCopyrightText: 2023 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from havneafgifter.models import DisembarkmentSite, Port, PortAuthority, ShippingAgent


class Command(BaseCommand):
    help = "Creates groups"

    def handle(self, *args, **options):
        editors, _ = Group.objects.update_or_create(
            name="Editors",
        )
        for model, actions in (
            (DisembarkmentSite, ("view", "add", "change", "delete")),
            (ShippingAgent, ("view", "add", "change", "delete")),
            (Port, ("view", "add", "change", "delete")),
            (PortAuthority, ("view", "add", "change", "delete")),
            (User, ("view", "add", "change", "delete")),
        ):
            content_type = ContentType.objects.get_for_model(
                model, for_concrete_model=False
            )
            for action in actions:
                editors.permissions.add(
                    Permission.objects.get(
                        codename=f"{action}_{content_type.model}",
                        content_type=content_type,
                    )
                )
        print("Created group Editors")
