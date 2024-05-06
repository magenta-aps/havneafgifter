from django.contrib.auth.forms import AuthenticationForm as DjangoAuthenticationForm
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import (
    CharField,
    ChoiceField,
    Form,
    IntegerField,
    ModelForm,
    PasswordInput,
    TextInput,
    widgets,
)
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_select2.forms import Select2Widget
from dynamic_forms import DynamicField, DynamicFormMixin

from havneafgifter.form_mixins import BootstrapForm
from havneafgifter.models import (
    DisembarkmentSite,
    HarborDuesForm,
    Nationality,
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


class HarborDuesFormForm(DynamicFormMixin, ModelForm):
    def __init__(self, user_is_ship=False, *args, **kwargs):
        self.user_is_ship = user_is_ship
        super().__init__(*args, **kwargs)

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
        ]
        localized_fields = [
            "datetime_of_arrival",
            "datetime_of_departure",
        ]
        widgets = {
            "nationality": Select2Widget(choices=countries),
            "datetime_of_arrival": HTML5DateWidget(),
            "datetime_of_departure": HTML5DateWidget(),
        }

    vessel_imo = DynamicField(
        CharField,
        max_length=7,
        min_length=7,
        validators=[
            RegexValidator(r"\d{7}"),
            imo_validator,
        ],
        label=_("IMO-number"),
        disabled=lambda form: form.user_is_ship,
        required=lambda form: not form.user_is_ship,
    )

    def clean(self):
        cleaned_data = super().clean()
        datetime_of_arrival = cleaned_data.get("datetime_of_arrival")
        datetime_of_departure = cleaned_data.get("datetime_of_departure")
        if datetime_of_arrival > datetime_of_departure:
            raise ValidationError(
                _("Date of departure cannot be before date of arrival"),
                code="datetime_of_departure_before_datetime_of_arrival",
            )


class PassengersTotalForm(Form):
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


class PassengersByCountryForm(DynamicFormMixin, Form):
    nationality = ChoiceField(
        choices=Nationality,
        disabled=True,
    )
    number_of_passengers = DynamicField(
        IntegerField,
        label=lambda form: form.initial["nationality"].label,
    )


class DisembarkmentForm(DynamicFormMixin, Form):
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
