from django.test import SimpleTestCase

from havneafgifter.models import HarborDuesForm, Status
from havneafgifter.templatetags.bootstrap_status_badge import bootstrap_status_badge


class TestBootstrapStatusBadge(SimpleTestCase):
    def test_badget(self):
        form = HarborDuesForm(status=Status.DRAFT)
        context: dict = bootstrap_status_badge(form)
        self.assertIs(context["form"], form)
        self.assertEqual(context["bg"], "badge-draft")
