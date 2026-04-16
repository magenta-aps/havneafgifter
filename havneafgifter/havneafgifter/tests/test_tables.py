import zoneinfo
from datetime import datetime

from django.conf import settings
from django.test import SimpleTestCase

from havneafgifter.models import HarborDuesForm, Status
from havneafgifter.tables import HarborDuesFormTable


class TestHarborDuesFormTable(SimpleTestCase):

    timezone = zoneinfo.ZoneInfo(settings.TIME_ZONE)

    def setUp(self):
        super().setUp()
        self.form = HarborDuesForm(
            status=Status.DRAFT,
            datetime_of_arrival=datetime(2026, 4, 1, 0, 0, 0, tzinfo=self.timezone),
            datetime_of_departure=datetime(2026, 4, 5, 0, 0, 0, tzinfo=self.timezone),
        )
        self.instance = HarborDuesFormTable([self.form])

    def test_render_status(self):
        rendered = self.instance.render_status(self.form)
        self.assertEqual(
            rendered,
            f"""<span class="badge rounded-pill badge-draft">{
                self.form.get_status_display()
            }</span>""",  # type: ignore[attr]
        )

    def test_render_datetime_of_arrival(self):
        rendered = self.instance.render_datetime_of_arrival(
            self.form.datetime_of_arrival
        )
        self.assertEqual(rendered, "2026-04-01 00:00")

    def test_render_datetime_of_departure(self):
        rendered = self.instance.render_datetime_of_departure(
            self.form.datetime_of_departure
        )
        self.assertEqual(rendered, "2026-04-05 00:00")
