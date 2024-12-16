from django.test import SimpleTestCase

from havneafgifter.models import HarborDuesForm, Status
from havneafgifter.tables import HarborDuesFormTable


class TestHarborDuesFormTable(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.form = HarborDuesForm(status=Status.DRAFT)
        self.instance = HarborDuesFormTable([self.form])

    def test_render_status(self):
        rendered = self.instance.render_status(self.form)
        self.assertEqual(
            rendered,
            f"""<span class="badge rounded-pill badge-draft">{
                self.form.get_status_display()
            }</span>""",  # type: ignore[attr]
        )
