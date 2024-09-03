from csp_helpers.mixins import CSPFormMixin
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthenticationForm
from django.contrib.auth.forms import BaseUserCreationForm, UsernameField
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms import (
    BaseInlineFormSet,
    BooleanField,
    CharField,
    ChoiceField,
    DateTimeField,
    DateTimeInput,
    EmailField,
    EmailInput,
    Field,
    Form,
    HiddenInput,
    IntegerField,
    ModelChoiceField,
    ModelForm,
    ModelMultipleChoiceField,
    MultipleChoiceField,
    PasswordInput,
    Textarea,
    TextInput,
    widgets,
)
from django.forms.models import inlineformset_factory
from django.forms.utils import ErrorList
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_select2.forms import Select2Widget
from dynamic_forms import DynamicField, DynamicFormMixin

from havneafgifter.form_mixins import BootstrapForm
from havneafgifter.models import (
    CruiseTaxForm,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    Municipality,
    Nationality,
    Port,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    Status,
    TaxRates,
    User,
    Vessel,
    imo_validator,
)


class AuthenticationForm(BootstrapForm, DjangoAuthenticationForm):
    username = UsernameField(
        widget=TextInput(
            attrs={
                "autofocus": True,
                "class": "form-control",
                "placeholder": _("Username or IMO number"),
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


class SignupVesselForm(CSPFormMixin, BaseUserCreationForm):
    # By inheriting from `BaseUserCreationForm`, this form takes care of
    # asking the user to repeat their desired password, checking that they are
    # identical.
    # It also takes care of hashing the password when creating the `User` object.

    class Meta:
        model = User
        fields = [
            "username",  # used for saving IMO number
            "first_name",
            "last_name",
            "email",
        ]

    username = CharField(
        min_length=0,
        max_length=7,
        validators=[
            RegexValidator(r"\d{7}"),
            imo_validator,
        ],
        label=_("IMO-number"),
    )

    first_name = CharField(
        required=True,
        max_length=150,
        label=_("First name"),
    )

    last_name = CharField(
        required=True,
        max_length=150,
        label=_("Last name"),
    )

    email = EmailField(
        max_length=254,
        widget=EmailInput(attrs={"autocomplete": "email"}),
        label=_("Email"),
    )

    # The following fields are present on the form, but are saved in the `Vessel` model
    # rather than `User`.

    type = ChoiceField(
        required=False,
        choices=ShipType.choices,
        label=_("Vessel type"),
    )

    name = CharField(
        required=False,
        max_length=255,
        label=_("Vessel name"),
    )

    owner = CharField(
        max_length=255,
        required=False,
        label=_("Vessel owner"),
    )

    master = CharField(
        max_length=255,
        required=False,
        label=_("Vessel captain"),
    )

    gross_tonnage = IntegerField(
        required=False,
        validators=[MinValueValidator(0)],
        label=_("Gross tonnage"),
    )

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Vessel.objects.update_or_create(
                user=user,
                imo=user.username,
                name=self.cleaned_data["name"],
                type=self.cleaned_data["type"],
                owner=self.cleaned_data["owner"],
                master=self.cleaned_data["master"],
                gross_tonnage=self.cleaned_data["gross_tonnage"],
            )
        return user


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
        ]
        localized_fields = [
            "datetime_of_arrival",
            "datetime_of_departure",
        ]

    _vessel_nationality_choices = BLANK_CHOICE_DASH + list(countries)

    _required_if_status_is_new = lambda form: form._status == Status.NEW  # noqa: E731

    _required_if_status_is_new_and_has_port_of_call = lambda form: (  # noqa: E731
        False if form.has_no_port_of_call else (form._status == Status.NEW)
    )

    port_of_call = DynamicField(
        ModelChoiceField,
        required=_required_if_status_is_new_and_has_port_of_call,
        queryset=Port.objects.all(),
        label=_("Port of call"),
    )

    nationality = DynamicField(
        ChoiceField,
        required=_required_if_status_is_new,
        choices=_vessel_nationality_choices,
        widget=Select2Widget(choices=_vessel_nationality_choices),
        label=_("Nationality"),
    )

    vessel_name = DynamicField(
        CharField,
        required=_required_if_status_is_new,
        max_length=255,
        initial=lambda form: getattr(form._vessel, "name", None),
        disabled=lambda form: form.user_is_ship,
        label=_("Vessel name"),
    )

    vessel_imo = DynamicField(
        CharField,
        required=_required_if_status_is_new,
        min_length=0,
        max_length=7,
        validators=[
            RegexValidator(r"\d{7}"),
            imo_validator,
        ],
        initial=lambda form: getattr(form._vessel, "imo", None),
        disabled=lambda form: form.user_is_ship,
        label=_("IMO-number"),
    )

    vessel_owner = DynamicField(
        CharField,
        required=_required_if_status_is_new,
        max_length=255,
        initial=lambda form: getattr(form._vessel, "owner", None),
        label=_("Vessel owner"),
    )

    vessel_master = DynamicField(
        CharField,
        required=_required_if_status_is_new,
        max_length=255,
        initial=lambda form: getattr(form._vessel, "master", None),
        label=_("Vessel captain"),
    )

    shipping_agent = DynamicField(
        ModelChoiceField,
        required=_required_if_status_is_new,
        queryset=ShippingAgent.objects.all(),
        initial=lambda form: (form._shipping_agent if form._shipping_agent else None),
        disabled=lambda form: form._shipping_agent is not None,
        label=_("Shipping agent"),
    )

    datetime_of_arrival = DynamicField(
        DateTimeField,
        required=_required_if_status_is_new_and_has_port_of_call,
        initial=lambda form: (
            form.instance.datetime_of_arrival.isoformat()
            if form.instance.datetime_of_arrival
            else None
        ),
        widget=HTML5DateWidget(),
        label=_("Arrival date/time"),
    )

    datetime_of_departure = DynamicField(
        DateTimeField,
        required=_required_if_status_is_new_and_has_port_of_call,
        initial=lambda form: (
            form.instance.datetime_of_departure.isoformat()
            if form.instance.datetime_of_departure
            else None
        ),
        widget=HTML5DateWidget(),
        label=_("Departure date/time"),
    )

    gross_tonnage = DynamicField(
        IntegerField,
        required=_required_if_status_is_new_and_has_port_of_call,
        validators=[MinValueValidator(0)],
        initial=lambda form: getattr(form._vessel, "gross_tonnage", None),
        disabled=lambda form: form.user_is_ship,
        label=_("Gross tonnage"),
    )

    vessel_type = DynamicField(
        ChoiceField,
        required=_required_if_status_is_new,
        choices=BLANK_CHOICE_DASH + ShipType.choices,
        initial=lambda form: getattr(form._vessel, "type", None),
        disabled=lambda form: form.user_is_ship,
        label=_("Vessel type"),
    )

    no_port_of_call = DynamicField(
        BooleanField,
        required=False,
        initial=lambda form: form.has_no_port_of_call,
        label=_("No port of call"),
    )

    status = ChoiceField(
        required=True,
        choices=Status.choices,
    )

    def __init__(self, user: User, status: Status | None = None, *args, **kwargs):
        self._user = user
        self._status = status or Status.DRAFT
        self._shipping_agent = (
            user.shipping_agent
            if user.shipping_agent is not None and user.has_group_name("Shipping")
            else None
        )
        self._vessel = (
            getattr(user, "vessel", None) if user.has_group_name("Ship") else None
        )
        super().__init__(*args, **kwargs)
        self.fields["no_port_of_call"].widget.attrs[
            "checked"
        ] = self.has_no_port_of_call

    @property
    def user_is_ship(self) -> bool:
        return "Ship" in self._user.group_names

    @property
    def has_no_port_of_call(self) -> bool:
        # 1. Check whether (unvalidated) form data sets `no_port_of_call`:
        form_has_no_port_of_call = self.data.get("no_port_of_call")
        if form_has_no_port_of_call == "on":
            return True
        # 2. Check whether model instance appears to have no port of call:
        self.instance: HarborDuesForm | CruiseTaxForm
        instance_has_no_port_of_call: bool = (
            (self.instance.pk is not None)
            and (self.instance.port_of_call is None)
            and (self.instance.vessel_type == ShipType.CRUISE)
        )
        return instance_has_no_port_of_call

    def clean(self):
        cleaned_data = super().clean()

        status = self._status or cleaned_data.get("status")
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
        vessel_type = cleaned_data.get("vessel_type")
        # "Port of call" cannot be set if "no port of call" is also set
        if (port_of_call is not None) and (no_port_of_call is True):
            raise ValidationError(
                _("Port of call cannot be filled if 'no port of call' is selected"),
                code="port_of_call_chosen_but_no_port_of_call_is_true",
            )
        # And the opposite: "port of call" must be set if "no port of call" is not set
        if (
            (port_of_call is None)
            and (no_port_of_call is False)
            and (vessel_type != ShipType.CRUISE)
        ):
            raise ValidationError(
                _("Port of call must be filled if 'no port of call' is not selected"),
                code="port_of_call_is_empty_and_no_port_of_call_is_false",
            )

        # Handle "no port of call" vs. "vessel type"
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

        # A number of fields are only allowed to be empty if:
        # - status is DRAFT
        # - or vessel type is CRUISE and "no port of call" is selected
        if self._status == Status.NEW and vessel_type != ShipType.CRUISE:
            fields = {
                "port_of_call",
                "datetime_of_arrival",
                "datetime_of_departure",
                "gross_tonnage",
            }
            for field in fields:
                if self.cleaned_data.get(field) is None:
                    label = self.fields[field].label
                    raise ValidationError(
                        _("%(field)s cannot be empty"),
                        params={"field": label},
                        code=f"{field}_cannot_be_empty",
                    )

        return cleaned_data

    def user_visible_non_field_errors(self) -> ErrorList:
        non_field_errors = self.errors.get(NON_FIELD_ERRORS)
        if non_field_errors:
            return ErrorList(
                [
                    error
                    for error in non_field_errors.__dict__["data"]
                    if error.code != "constraint_violated"
                ]
            )
        return ErrorList()  # empty error list


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
        required=True,
        min_value=0,
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


class ReasonForm(DynamicFormMixin, CSPFormMixin, ModelForm):
    class Meta:
        model = HarborDuesForm
        fields: list[Field] = []

    reason = CharField(
        required=True,
        widget=Textarea(),
        label=_("Reason"),
    )


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


class TaxRateForm(ModelForm, BootstrapForm):
    class Meta:
        model = TaxRates
        exclude = ["end_datetime"]

    start_datetime = DateTimeField(
        label=_("Gyldighed fra"),
        required=True,
        widget=DateTimeInput(
            attrs={
                # "id": "datetimepicker",
                "class": "form-control datetimepicker",
                "placeholder": _("Gyldighed fra"),
            }
        ),
    )

    def clean_start_datetime(self):
        start_datetime = self.cleaned_data.get("start_datetime")
        if start_datetime:
            now = timezone.now()
            one_week_from_now = now + timezone.timedelta(weeks=1)
            if start_datetime < one_week_from_now:
                raise ValidationError(
                    _("Start dato skal være mindst en uge i fremtiden"),
                    code="start_datetime_at_least_one_week_from_today",
                )
        return start_datetime


class PortTaxRateForm(ModelForm, BootstrapForm):
    class Meta:
        model = PortTaxRate
        exclude = ["tax_rates"]
        widgets = {
            "port": HiddenInput,
            "vessel_type": HiddenInput,
        }


class DisembarkmentTaxRateForm(ModelForm, BootstrapForm):
    class Meta:
        model = DisembarkmentTaxRate
        exclude = ["tax_rates"]
        widgets = {
            "municipality": HiddenInput,
            "disembarkment_site": HiddenInput,
        }


class TaxRateFormSet(BaseInlineFormSet):
    deletion_widget = HiddenInput

    # TODO: Prevent deletion of "old" or current TaxRate objects
    # TODO: start_datetime/pax_tax_rate combos need to be unique

    def __init__(self, *args, extradata=None, **kwargs):
        self.extradata = extradata
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        if self.extradata:
            form.extradata = self.extradata[i]
        return form


class BasePortTaxRateFormSet(TaxRateFormSet):
    def clean(self):
        # TODO: round_gross_ton_up_to must be between gt_start and gt_end of gt_start==0
        # TODO: There may be no gap between gt_end of one type/port
        #  occurrence and gt_start of the next
        # TODO: gt_start should be less than gt_end
        # TODO: Every type/port combo needs at least one gt_start==0
        # TODO: Every type/port combo needs at least one gt_end==None
        # TODO: type/port, gt_start, gt_end, round_gross_tonne_up_to combos need
        #  to be unique
        #

        # TODO: Every type/port combo needs one! gt_start==0 and one! gt_end==None.
        #  No duplicates if more than one combo occurrence.
        super().clean()

        combinations = {}

        for form in self.forms:

            if form.cleaned_data:
                delete = form.cleaned_data.get("DELETE")
                if delete:
                    continue

                port = form.cleaned_data.get("port")
                vessel_type = form.cleaned_data.get("vessel_type")
                gt_start = form.cleaned_data.get("gt_start")
                gt_end = form.cleaned_data.get("gt_end")

                key = (port, vessel_type)

                if key not in combinations:
                    combinations[key] = {
                        "count": 0,
                        "count_gt_start_zero": 0,
                        "count_gt_end_none": 0,
                    }

                combinations[key]["count"] += 1

                if gt_start == 0:
                    combinations[key]["count_gt_start_zero"] += 1

                if gt_end is None:
                    combinations[key]["count_gt_end_none"] += 1

        # validate occurrence combinations
        for key, value in combinations.items():
            port, vessel_type = key
            if value["count"] == 1:
                # only one occurrence of type/port comb
                # it must have both gt_star==0 and gt_end==None
                if value["count_gt_start_zero"] != 1 or value["count_gt_end_none"] != 1:
                    raise ValidationError(
                        _(
                            f"For the combination of port '{port}' and vessel type "
                            f"'{vessel_type}', the single entry must have both "
                            f"gt_start=0 and gt_end=None."
                        )
                    )
            else:
                # multiple type/port occurrences
                # it must have both gt_star==0 and gt_end==None
                errmsg = _(
                    f"There should be exactly one entry with gt_start=0 for port "
                    f"'{port}' and vessel type '{vessel_type}'."
                )
                if value["count_gt_start_zero"] != 1:
                    raise ValidationError(errmsg)
                if value["count_gt_end_none"] != 1:
                    raise ValidationError(errmsg)


class BaseDisembarkmentTaxRateFormSet(TaxRateFormSet):
    # TODO: There may be no duplicates of municipality/site combos
    pass


PortTaxRateFormSet = inlineformset_factory(
    parent_model=TaxRates,
    model=PortTaxRate,
    form=PortTaxRateForm,
    extra=0,
    can_delete=True,
    formset=BasePortTaxRateFormSet,
)

DisembarkmentTaxRateFormSet = inlineformset_factory(
    parent_model=TaxRates,
    model=DisembarkmentTaxRate,
    form=DisembarkmentTaxRateForm,
    # formset=TaxRateFormSet,
    extra=0,
    can_delete=True,
    formset=BaseDisembarkmentTaxRateFormSet,
)
