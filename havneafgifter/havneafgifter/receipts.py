import weasyprint
from django.template import Context, Engine, Template
from django.utils.safestring import SafeString
from django_weasyprint.utils import django_url_fetcher

from havneafgifter.models import CruiseTaxForm, HarborDuesForm, ShipType


class Receipt:
    """Receipt classes take a `HarborDuesForm` or `CruiseTaxForm` as input
    and render their data to HTML or PDF.
    """

    template = None
    """HTML template to use (for both HTML and PDF output.)"""

    def __init__(
        self,
        form: HarborDuesForm | CruiseTaxForm,
        base: str = "havneafgifter/pdf/base.html",
    ) -> None:
        super().__init__()
        self.form: HarborDuesForm | CruiseTaxForm = form
        self._engine: Engine = Engine.get_default()
        self._template: Template = self._engine.get_template(self.template)
        self._context: Context = Context({"form": form, **self.get_context_data()})
        # Dynamic base template
        self._context["base"] = base

    @property
    def html(self) -> SafeString:
        return self._template.render(self._context)

    @property
    def pdf(self) -> bytes:
        font_config = weasyprint.text.fonts.FontConfiguration()
        html = weasyprint.HTML(
            string=self.html,
            base_url="",
            url_fetcher=django_url_fetcher,
        )
        document = html.render(font_config=font_config)
        return document.write_pdf()

    def get_context_data(self) -> dict:
        return {}


class HarborDuesFormReceipt(Receipt):
    template = "havneafgifter/pdf/harbor_dues_form_receipt.html"

    def get_context_data(self) -> dict:
        return {
            "ShipType": ShipType,
            "PASSENGER_OR_FISHER": (ShipType.PASSENGER, ShipType.FISHER),
            "FREIGHTER_OR_OTHER": (ShipType.FREIGHTER, ShipType.OTHER),
        }


class CruiseTaxFormReceipt(Receipt):
    template = "havneafgifter/pdf/cruise_tax_form_receipt.html"

    def get_context_data(self) -> dict:
        disembarkment_tax: dict = self.form.calculate_disembarkment_tax(save=False)
        return {
            "disembarkment_tax_items": disembarkment_tax["details"],
        }
