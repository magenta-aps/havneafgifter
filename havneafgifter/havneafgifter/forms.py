from csp_helpers.mixins import CSPFormMixin
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthenticationForm
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import RegexValidator
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateTimeField,
    DateTimeInput,
    Form,
    HiddenInput,
    IntegerField,
    ModelForm,
    ModelMultipleChoiceField,
    MultipleChoiceField,
    PasswordInput,
    TextInput,
    widgets,
)
from django.forms.utils import ErrorList
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_select2.forms import Select2Widget
from dynamic_forms import DynamicField, DynamicFormMixin

from havneafgifter.form_mixins import BootstrapForm
from havneafgifter.models import (
    DisembarkmentSite,
    HarborDuesForm,
    Municipality,
    Nationality,
    Port,
    ShipType,
    Status,
    imo_validator,
)


class AuthenticationForm(BootstrapForm, DjangoAuthenticationForm):
    username = UsernameField(
        widget=TextInput(
            attrs={
                "autofocus": True,
                "class": "form-control",
                "placeholder": _("Username"),
            }
        )
    )
    password = CharField(
        label=_("Password"),
        strip=False,
        widget=PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": "form-control",
                "placeholder": _("Password"),
            }
        ),
    )


class HTML5DateWidget(widgets.Input):
    input_type = "datetime-local"
    template_name = "django/forms/widgets/datetime.html"


class HarborDuesFormForm(DynamicFormMixin, CSPFormMixin, ModelForm):
    class Meta:
        model = HarborDuesForm
        fields = [
            "port_of_call",
            "nationality",
            "vessel_name",
            "vessel_imo",
            "vessel_owner",
            "vessel_master",
            "shipping_agent",
            "datetime_of_arrival",
            "datetime_of_departure",
            "gross_tonnage",
            "vessel_type",
            "status",
        ]
        localized_fields = [
            "datetime_of_arrival",
            "datetime_of_departure",
        ]
        widgets = {
            "datetime_of_arrival": HTML5DateWidget(),
            "datetime_of_departure": HTML5DateWidget(),
        }

    _vessel_nationality_choices = [("", "---")] + list(countries)

    nationality = ChoiceField(
        required=False,
        choices=_vessel_nationality_choices,
        widget=Select2Widget(choices=_vessel_nationality_choices),
    )

    vessel_imo = DynamicField(
        CharField,
        min_length=0,
        max_length=7,
        validators=[
            RegexValidator(r"\d{7}"),
            imo_validator,
        ],
        label=_("IMO-number"),
        disabled=lambda form: form.user_is_ship,
        required=False,
    )

    no_port_of_call = BooleanField(
        required=False,
        initial=False,
        label=_("No port of call"),
    )

    status = ChoiceField(
        required=False,
        choices=[
            (Status.NEW, _("No")),
            (Status.DRAFT, _("Yes")),
        ],
        label=_("Draft"),
    )

    def __init__(self, user_is_ship=False, *args, **kwargs):
        self.user_is_ship = user_is_ship
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        if status == Status.DRAFT:
            return cleaned_data

        # Handle "datetime" fields
        datetime_of_arrival = cleaned_data.get("datetime_of_arrival")
        datetime_of_departure = cleaned_data.get("datetime_of_departure")
        # If both dates are given, arrival must be before departure
        if (
            (datetime_of_arrival is not None)
            and (datetime_of_departure is not None)
            and (datetime_of_arrival > datetime_of_departure)
        ):
            raise ValidationError(
                _("Date of departure cannot be before date of arrival"),
                code="datetime_of_departure_before_datetime_of_arrival",
            )

        # Handle "port of call" fields
        port_of_call = cleaned_data.get("port_of_call")
        no_port_of_call = cleaned_data.get("no_port_of_call")
        # "Port of call" cannot be set if "no port of call" is also set
        if (port_of_call is not None) and (no_port_of_call is True):
            raise ValidationError(
                _("Port of call cannot be filled if 'no port of call' is selected"),
                code="port_of_call_chosen_but_no_port_of_call_is_true",
            )
        # And the opposite: "port of call" must be set if "no port of call" is not set
        if (port_of_call is None) and (no_port_of_call is False):
            raise ValidationError(
                _("Port of call must be filled if 'no port of call' is not selected"),
                code="port_of_call_is_empty_and_no_port_of_call_is_false",
            )

        # Handle "no port of call" vs. "vessel type"
        vessel_type = cleaned_data.get("vessel_type")
        # Only cruise ships can select "no port of call"
        if (vessel_type != ShipType.CRUISE) and (no_port_of_call is True):
            raise ValidationError(
                _(
                    "You can only choose 'no port of call' when the vessel is a "
                    "cruise ship"
                ),
                code="no_port_of_call_cannot_be_true_for_non_cruise_ships",
            )

        # Handle "port of call" vs. "arrival" and "departure" fields
        # If given a port of call, both arrival and departure dates must be given
        # as well.
        if (port_of_call is not None) and (
            datetime_of_arrival is None or datetime_of_departure is None
        ):
            raise ValidationError(
                _(
                    "If reporting port tax, please specify both arrival and departure "
                    "date",
                ),
                code="port_of_call_requires_arrival_and_departure_dates",
            )

    def user_visible_non_field_errors(self) -> ErrorList | None:
        non_field_errors = self.errors.get(NON_FIELD_ERRORS)
        if non_field_errors:
            return ErrorList(
                [
                    error
                    for error in non_field_errors.__dict__["data"]
                    if error.code != "constraint_violated"
                ]
            )
        return None


class PassengersTotalForm(CSPFormMixin, Form):
    total_number_of_passengers = IntegerField(
        label=_("Total number of passengers"),
        widget=widgets.NumberInput(attrs={"placeholder": "0"}),
    )

    def validate_total(self, sum_passengers_by_country):
        # Trigger form validation, so `self.cleaned_data` is populated
        self.is_valid()
        # Compare total number of passengers to the sum of passengers by country
        total_number_of_passengers = self.cleaned_data["total_number_of_passengers"]
        if total_number_of_passengers != sum_passengers_by_country:
            self.add_error(
                "total_number_of_passengers",
                _(
                    "The total number of passengers does not match the sum of "
                    "passengers by each nationality"
                ),
            )


class PassengersByCountryForm(DynamicFormMixin, CSPFormMixin, Form):
    nationality = ChoiceField(
        choices=Nationality,
        disabled=True,
    )
    number_of_passengers = DynamicField(
        IntegerField,
        label=lambda form: form.initial["nationality"].label,
    )
    pk = IntegerField(
        required=False,
        widget=HiddenInput(),
    )


class DisembarkmentForm(DynamicFormMixin, CSPFormMixin, Form):
    disembarkment_site = DynamicField(
        ChoiceField,
        choices=lambda form: [
            (form.initial_disembarkment_site.pk, str(form.initial_disembarkment_site))
        ],
        disabled=True,
    )
    number_of_passengers = DynamicField(
        IntegerField,
        label=lambda form: form.initial_disembarkment_site_name,
    )
    pk = IntegerField(
        required=False,
        widget=HiddenInput(),
    )

    def clean_disembarkment_site(self):
        disembarkment_site = self.cleaned_data.get("disembarkment_site")
        if isinstance(disembarkment_site, DisembarkmentSite):
            return disembarkment_site
        return DisembarkmentSite.objects.get(pk=disembarkment_site)

    @cached_property
    def initial_disembarkment_site(self):
        disembarkment_site = self.initial.get("disembarkment_site")
        if isinstance(disembarkment_site, int):
            disembarkment_site = DisembarkmentSite.objects.get(pk=disembarkment_site)
        return disembarkment_site

    @cached_property
    def initial_disembarkment_site_name(self):
        disembarkment_site = self.initial_disembarkment_site
        if disembarkment_site.is_outside_populated_areas:
            field = disembarkment_site._meta.get_field("is_outside_populated_areas")
            return field.verbose_name
        else:
            return disembarkment_site.name

    def get_municipality_display(self):
        return self.initial_disembarkment_site.get_municipality_display()


class StatisticsForm(BootstrapForm):
    municipality = MultipleChoiceField(
        label=_("Kommune"),
        choices=Municipality.choices,
        required=False,
    )
    arrival_gt = DateTimeField(
        label=_("Ankomst efter"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Ankomst efter")}
        ),
    )
    arrival_lt = DateTimeField(
        label=_("Ankomst før"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Ankomst før")}
        ),
    )
    departure_gt = DateTimeField(
        label=_("Afrejse efter"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Afrejse efter")}
        ),
    )
    departure_lt = DateTimeField(
        label=_("Afrejse før"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Afrejse før")}
        ),
    )
    vessel_type = MultipleChoiceField(
        label=_("Skibstype"),
        choices=ShipType.choices,
        required=False,
    )
    site = ModelMultipleChoiceField(
        label=_("Landgangssted"),
        queryset=DisembarkmentSite.objects.all(),
        required=False,
    )
    port_of_call = ModelMultipleChoiceField(
        label=_("Havn"), queryset=Port.objects.all(), required=False
    )
