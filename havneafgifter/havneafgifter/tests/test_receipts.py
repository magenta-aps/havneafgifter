from unittest.mock import Mock, PropertyMock, patch

from django.http import HttpRequest
from django.template import Context, RequestContext, Template
from django.test import SimpleTestCase, TestCase
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.models import ShipType
from havneafgifter.receipts import (
    _PDF_BASE_TEMPLATE,
    CruiseTaxFormReceipt,
    Engine,
    HarborDuesFormReceipt,
    Receipt,
)
from havneafgifter.tests.mixins import HarborDuesFormMixin


class _PDFMixin:
    def assert_content_is_pdf(self, content: bytes):
        self.assertIsInstance(content, bytes)
        self.assertGreater(len(content), 0)


class TestReceipt(ParametrizedTestCase, _PDFMixin, SimpleTestCase):
    @parametrize(
        "request,expected_context_type",
        [
            (None, Context),
            (HttpRequest(), RequestContext),
        ],
    )
    @patch.object(Engine, "get_template", return_value=Template(""))
    def test_init(self, mock_get_template, request, expected_context_type):
        mock_form: Mock = Mock()
        instance: Receipt = Receipt(mock_form, request=request)
        self.assertIsInstance(instance._engine, Engine)
        self.assertIsInstance(instance._template, Template)
        self.assertIsInstance(instance._context, expected_context_type)
        mock_get_template.assert_called_once_with(instance.template)
        self.assertEqual(instance._context["form"], mock_form)
        self.assertEqual(instance._context["base"], _PDF_BASE_TEMPLATE)

    @patch.object(Engine, "get_template")
    def test_html(self, mock_get_template):
        mock_form: Mock = Mock()
        mock_template: Mock = Mock()
        mock_get_template.return_value = mock_template
        instance: Receipt = Receipt(mock_form)
        result = instance.html
        mock_template.render.assert_called_once_with(
            Context(
                {
                    "form": mock_form,
                    "base": _PDF_BASE_TEMPLATE,
                    "can_create": False,
                    "can_edit": False,
                    "can_withdraw": False,
                    "can_approve": False,
                    "can_reject": False,
                    "landing_modal": False,
                }
            ),
        )
        self.assertIs(result, mock_template.render.return_value)

    @patch.object(Engine, "get_template")
    def test_pdf(self, mock_get_template):
        with patch(
            "havneafgifter.receipts.Receipt.html", new_callable=PropertyMock
        ) as mock_html:
            instance: Receipt = Receipt(Mock())
            mock_html.return_value = ""
            result = instance.pdf
            self.assert_content_is_pdf(result)

    @patch.object(Engine, "get_template")
    def test_get_context_data(self, mock_get_template):
        instance: Receipt = Receipt(Mock())
        self.assertDictEqual(
            instance.get_context_data(),
            {
                "can_create": False,
                "can_edit": False,
                "can_withdraw": False,
                "can_approve": False,
                "can_reject": False,
            },
        )


class TestHarborDuesFormReceipt(HarborDuesFormMixin, _PDFMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.instance: HarborDuesFormReceipt = HarborDuesFormReceipt(
            self.harbor_dues_form
        )

    def test_renders_pdf(self):
        self.assert_content_is_pdf(self.instance.pdf)

    def test_get_context_data(self):
        self.assertDictEqual(
            self.instance.get_context_data(),
            {
                "ShipType": ShipType,
                "PASSENGER_OR_FISHER": (ShipType.PASSENGER, ShipType.FISHER),
                "FREIGHTER_OR_OTHER": (ShipType.FREIGHTER, ShipType.OTHER),
                "can_create": False,
                "can_edit": True,
                "can_withdraw": True,
                "can_approve": True,
                "can_reject": True,
            },
        )


class TestCruiseTaxFormReceipt(HarborDuesFormMixin, _PDFMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.instance: CruiseTaxFormReceipt = CruiseTaxFormReceipt(self.cruise_tax_form)

    def test_renders_pdf(self):
        self.assert_content_is_pdf(self.instance.pdf)

    def test_get_context_data(self):
        result: dict = self.instance.get_context_data()
        self.assertListEqual(
            list(result.keys()),
            [
                "disembarkment_tax_items",
                "can_create",
                "can_edit",
                "can_withdraw",
                "can_approve",
                "can_reject",
            ],
        )
        self.assertListEqual(
            result["disembarkment_tax_items"],
            self.cruise_tax_form.calculate_disembarkment_tax()["details"],
        )


class TestCruiseTaxFormReceiptWithoutPortOfCall(
    HarborDuesFormMixin, _PDFMixin, TestCase
):
    def setUp(self):
        super().setUp()
        self.instance: CruiseTaxFormReceipt = CruiseTaxFormReceipt(
            self.cruise_tax_form_without_port_of_call
        )

    def test_renders_pdf(self):
        self.assert_content_is_pdf(self.instance.pdf)
