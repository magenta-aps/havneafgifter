import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from havneafgifter.models import HarborDuesForm


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.load_shipping_agent_and_forms()

    def load_shipping_agent_and_forms(self):
        # Load dummy data - a shipping agent, 2 harbor dues forms, and 2 cruise
        # tax forms.
        path = self._get_fixture_path("shipping_agent_and_forms.json")
        call_command("loaddata", path, verbosity=1)
        for form in HarborDuesForm.objects.all():
            form.calculate_tax(save=True)

    def _get_fixture_path(self, fixture_name: str) -> str:
        path: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../fixtures",
            fixture_name,
        )
        return path
