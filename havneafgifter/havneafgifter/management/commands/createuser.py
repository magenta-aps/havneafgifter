from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from havneafgifter.models import PortAuthority, ShippingAgent, User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument("password", type=str)
        parser.add_argument("-s", "--is_staff", action="store_true")
        parser.add_argument("-g", "--groups", type=str, nargs="+")
        parser.add_argument("--port-authority", type=str, nargs="+")
        parser.add_argument("--shipping-agent", type=str, nargs="+")

    def handle(self, *args, **options):
        user, _ = User.objects.update_or_create(
            username=options["username"],
            defaults={
                "is_staff": options["is_staff"],
                "is_superuser": False,
            },
        )
        password = options["password"]
        if password and not user.check_password(password):
            user.set_password(password)
            user.save()
        groups = options.get("groups")
        if groups:
            for group_name in groups:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                except Group.DoesNotExist:
                    print(f"Group {group_name} does not exist")

        port_authority = options.get("port-authority")
        if port_authority:
            try:
                port_authority_name = " ".join(port_authority)
                port_authority_object = PortAuthority.objects.get(
                    name=port_authority_name
                )
                user.port_authority = port_authority_object
                user.save(update_fields=["port_authority"])
            except PortAuthority.DoesNotExist:
                print(f"Port Authority {port_authority_name} does not exist")

        shipping_agent = options.get("shipping-agent")
        if shipping_agent:
            try:
                shipping_agent_name = " ".join(shipping_agent)
                shipping_agent_object = ShippingAgent.objects.get(
                    name=shipping_agent_name
                )
                user.shipping_agent = shipping_agent_object
                user.save(update_fields=["shipping_agent"])
            except ShippingAgent.DoesNotExist:
                print(f"Shipping Agent {shipping_agent_name} does not exist")
