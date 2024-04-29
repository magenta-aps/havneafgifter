from django.test import TestCase

from havneafgifter.receipts import CruiseTaxFormReceipt, HarborDuesFormReceipt
from havneafgifter.tests.mixins import HarborDuesFormMixin


class _PDFTestCase(TestCase):
    def assert_content_is_pdf(self, content: bytes):
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)


class TestHarborDuesFormReceipt(HarborDuesFormMixin, _PDFTestCase):
    def test_renders_pdf(self):
        instance = HarborDuesFormReceipt(self.harbor_dues_form)
        self.assert_content_is_pdf(instance.pdf)


class TestCruiseTaxFormReceipt(HarborDuesFormMixin, _PDFTestCase):
    def test_renders_pdf(self):
        instance = CruiseTaxFormReceipt(self.cruise_tax_form)
        self.assert_content_is_pdf(instance.pdf)
