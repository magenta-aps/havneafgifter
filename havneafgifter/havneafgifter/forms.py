from typing import Any, Dict, List, Tuple

from csp_helpers.mixins import CSPFormMixin
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthenticationForm
from django.contrib.auth.forms import BaseUserCreationForm, UsernameField
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms import (
    BaseInlineFormSet,
    CharField,
    ChoiceField,
    DateInput,
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
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_select2.forms import Select2MultipleWidget, Select2Widget
from dynamic_forms import DynamicField, DynamicFormMixin

from havneafgifter.form_mixins import BootstrapForm, BootstrapFormSet, MonthField
from havneafgifter.models import (
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    Municipality,
    Nationality,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    Status,
    TaxRates,
    User,
    UserType,
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


class HTML5MonthWidget(widgets.Input):
    input_type = "month"
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
        label=_("IMO-no."),
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
    nationality = ChoiceField(
        required=False,
        choices=countries,
        widget=Select2Widget(choices=countries),
        label=_("Nationality"),
    )

    nationality = ChoiceField(
        required=False,
        choices=countries,
        widget=Select2Widget(choices=countries),
        label=_("Nationality"),
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
                nationality=self.cleaned_data["nationality"],
            )
        return user


class UpdateVesselForm(CSPFormMixin, ModelForm):
    class Meta:
        model = Vessel
        exclude = ["user", "imo"]

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
    nationality = ChoiceField(
        required=False,
        choices=countries,
        widget=Select2Widget(choices=countries),
        label=_("Nationality"),
    )

    nationality = ChoiceField(
        required=False,
        choices=countries,
        widget=Select2Widget(choices=countries),
        label=_("Nationality"),
    )


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
            "gross_tonnage",
            "datetime_of_arrival",
            "datetime_of_departure",
            "vessel_type",
        ]
        localized_fields = [
            "datetime_of_arrival",
            "datetime_of_departure",
        ]

    _vessel_nationality_choices = BLANK_CHOICE_DASH + list(countries)

    _required_if_status_is_new = lambda form: form._status == Status.NEW  # noqa: E731

    _required_if_status_is_new_and_has_port_of_call = lambda form: (  # noqa: E731
        form._status == Status.NEW and form.has_port_of_call
    )

    port_of_call = DynamicField(
        ChoiceField,
        required=_required_if_status_is_new_and_has_port_of_call,
        choices=lambda form: (
            BLANK_CHOICE_DASH
            + [(port.pk, port.name) for port in Port.objects.all()]
            + [(-1, _("No port of call"))]
        ),
        label=_("Port of call"),
    )
    nationality = DynamicField(
        ChoiceField,
        required=_required_if_status_is_new,
        choices=_vessel_nationality_choices,
        widget=Select2Widget(choices=_vessel_nationality_choices),
        initial=lambda form: getattr(form._vessel, "nationality", None),
        disabled=lambda form: form.user_is_ship,
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
        label=_("IMO-no."),
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
        required=False,
        queryset=ShippingAgent.objects.all(),
        initial=lambda form: (form._shipping_agent if form._shipping_agent else None),
        disabled=lambda form: form._shipping_agent is not None,
        label=_("Shipping agent"),
    )

    gross_tonnage = DynamicField(
        IntegerField,
        required=_required_if_status_is_new_and_has_port_of_call,
        validators=[MinValueValidator(0)],
        initial=lambda form: getattr(form._vessel, "gross_tonnage", None),
        disabled=lambda form: form.user_is_ship,
        label=_("Gross tonnage"),
    )

    datetime_of_arrival = DynamicField(
        DateTimeField,
        required=_required_if_status_is_new,
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

    vessel_type = DynamicField(
        ChoiceField,
        required=_required_if_status_is_new,
        choices=BLANK_CHOICE_DASH + ShipType.choices,
        initial=lambda form: getattr(form._vessel, "type", None),
        disabled=lambda form: form.user_is_ship,
        label=_("Vessel type"),
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

    @property
    def user_is_ship(self) -> bool:
        return self._user.is_authenticated and self._user.user_type == UserType.SHIP

    @property
    def has_port_of_call(self):
        port_of_call = self.data.get("base-port_of_call")
        return port_of_call != "-1"

    def clean(self):
        cleaned_data = super().clean()

        self._status = cleaned_data.get("status")
        status = self._status

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
        vessel_type = cleaned_data.get("vessel_type")

        # Handle "port of call" vs. "arrival" and "departure" fields
        # If given a port of call, both arrival and departure dates must be given
        # as well.
        if (port_of_call and port_of_call.name != "Blank") and (
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

    def clean_port_of_call(self):
        port_of_call = self.cleaned_data.get("port_of_call")
        if isinstance(port_of_call, Port):
            return port_of_call

        if port_of_call:
            port_of_call = int(port_of_call)
        else:
            return None

        if port_of_call > 0:
            return Port.objects.get(pk=port_of_call)
        elif port_of_call == -1:
            return Port(name="Blank")


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
        choices=BLANK_CHOICE_DASH + [(n, n.label) for n in Nationality],
        required=True,
    )
    number_of_passengers = DynamicField(
        IntegerField,
        required=True,
        min_value=0,
    )
    pk = IntegerField(
        required=False,
        widget=HiddenInput(),
    )


class DisembarkmentForm(DynamicFormMixin, CSPFormMixin, Form):
    disembarkment_site = DynamicField(
        ModelChoiceField,
        queryset=DisembarkmentSite.objects.all(),
        required=True,
    )
    number_of_passengers = DynamicField(
        IntegerField,
        required=lambda form: True if form.initial.get("pk") else False,
    )
    pk = IntegerField(
        required=False,
        widget=HiddenInput(),
    )


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
        choices=sorted(Municipality.choices, key=lambda x: str(x[1])),
        widget=Select2MultipleWidget(choices=Municipality.choices),
        required=False,
    )
    port_authority = ModelMultipleChoiceField(
        label=_("Havnemyndighed"),
        queryset=PortAuthority.objects.order_by("name"),
        widget=Select2MultipleWidget(choices=lambda _: PortAuthority.objects.all()),
        required=False,
    )
    arrival_gt = DateTimeField(
        label=_("Ankomst efter"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Ankomst tidligst")}
        ),
    )
    arrival_lt = DateTimeField(
        label=_("Ankomst før"),
        required=False,
        widget=DateTimeInput(
            attrs={"class": "datetimepicker", "placeholder": _("Ankomst senest")}
        ),
    )
    vessel_type = MultipleChoiceField(
        label=_("Skibstype"),
        choices=sorted(ShipType.choices, key=lambda x: str(x[1])),
        widget=Select2MultipleWidget(choices=ShipType.choices),
        required=False,
    )
    site = ModelMultipleChoiceField(
        label=_("Landgangssted"),
        queryset=DisembarkmentSite.objects.order_by("municipality", "name"),
        widget=Select2MultipleWidget(choices=lambda _: DisembarkmentSite.objects.all()),
        required=False,
    )
    port_of_call = ModelMultipleChoiceField(
        label=_("Havn"),
        queryset=Port.objects.order_by("portauthority", "name"),
        widget=Select2MultipleWidget(choices=lambda _: Port.objects.all()),
        required=False,
    )
    status = MultipleChoiceField(
        label=_("Status"),
        choices=sorted(Status.choices, key=lambda x: str(x[1])),
        widget=Select2MultipleWidget(choices=Status.choices),
        required=False,
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
                "class": "form-control datetimepicker",
                "placeholder": _("Gyldighed fra"),
            }
        ),
    )

    def clean(self):
        cleaned_data = self.cleaned_data
        start_datetime = cleaned_data.get("start_datetime")

        if start_datetime:
            edit_limit_datetime = timezone.now() + timezone.timedelta(weeks=1)

            if start_datetime < edit_limit_datetime:
                raise ValidationError(
                    _(
                        "Der må ikke oprettes eller redigeres i afgifter, "
                        "der bliver gyldige om mindre end 1 uge fra nu."
                    )
                )


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

    def __init__(self, *args, extradata=None, **kwargs):
        self.extradata = extradata
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        if self.extradata:
            form.extradata = self.extradata[i] if i < len(self.extradata) else None
        return form


class BasePortTaxRateFormSet(BootstrapFormSet, TaxRateFormSet):
    """
    Review note:
    The part of these validation methods, that generated the proper error messages,
    by sending a new ValidationError to the form.add_error() contain duplicate code.

    There were attempts at mitigating the duplicate code - but this came with a severe
    readability impact.

    It has since been decided to keep the duplicate code, to retain some readability.
    """

    @staticmethod
    def group_port_tax_rate_forms(
        forms_to_group: List[Any],
    ) -> Dict[Tuple[Any, Any], List[Any]]:
        grouped_forms: Dict[Tuple[Any, Any], List[Any]] = {}  # Type annotation added

        # find forms where port and vessel_type are the same
        for form in forms_to_group:
            port = form.cleaned_data.get("port")
            vessel_type = form.cleaned_data.get("vessel_type")
            key = (vessel_type, port)

            # add it to the dict, if it doesn't exist yet
            if key not in grouped_forms:
                grouped_forms[key] = []

            # add the form to the list, for the matching key
            grouped_forms[key].append(form)

        # remove the occurrences that only happened once (one-liner port tax rates)
        grouped_forms = {key: forms for key, forms in grouped_forms.items()}

        return grouped_forms

    def check_for_tonnage_presences(self):
        """
        Checks that the unique forms each have gt_start==0 and gt_end==None.
        This means we need to identify forms that have a combination of port and
        vessel_type that only occurrs once in self.forms.
        """

        def params_for_form(form):
            vtype = form.cleaned_data["vessel_type"]
            port = form.cleaned_data["port"]
            return {
                "msg_gtstart": (gt_start if gt_start is not None else "tom"),
                "msg_gtend": gt_end if gt_end is not None else "tom",
                "msg_vtype": (
                    ShipType(vtype).label if vtype is not None else "Enhver skibstype"
                ),
                "msg_port": (port.name if port is not None else "enhver havn"),
            }

        # "isolate" the forms with a reoccurring combination of port and vessel_type
        grouped_forms = BasePortTaxRateFormSet.group_port_tax_rate_forms(self.forms)
        combo_missing_message = (
            "%(msg_vtype)s, %(msg_port)s: For denne kombination af skibstype og havn "
            'skal én "Fra (ton)" [%(msg_gtstart)s] være 0 og én "Til (ton)" '
            "[%(msg_gtend)s] stå tomt."
        )

        # check for the expected gt_start and gt_end values
        for identifier, forms in grouped_forms.items():
            has_gt_start_0 = False
            has_gt_end_none = False
            for form in forms:
                gt_start = form.cleaned_data["gt_start"]
                gt_end = form.cleaned_data["gt_end"]
                if gt_start == 0:
                    if has_gt_start_0:
                        form.add_error(
                            "",
                            ValidationError(
                                message=combo_missing_message,
                                params=params_for_form(form),
                            ),
                        )

                    has_gt_start_0 = True
                if gt_end is None:
                    if has_gt_end_none:
                        form.add_error(
                            "",
                            ValidationError(
                                message=combo_missing_message,
                                params=params_for_form(form),
                            ),
                        )

                    has_gt_end_none = True
            if not has_gt_start_0:
                for form in forms:
                    form.add_error(
                        "",
                        ValidationError(
                            message=combo_missing_message, params=params_for_form(form)
                        ),
                    )

            if not has_gt_end_none:
                for form in forms:
                    form.add_error(
                        "",
                        ValidationError(
                            message=combo_missing_message, params=params_for_form(form)
                        ),
                    )

    def clean_round_gross_ton_up_to(self):
        """
        This checks for bad `PortTaxRate.round_gross_ton_up_to` values.

        For each form in the forms in the formset in `self` the following happens:
        1: `gt_start`, `gt_end` and `round_gross_ton_up_to` are read from the form.
        2: It's checked that `gt_start` is 0 and `gt_end` is not None (infinity).
            If that is not the case, that means:
                A: We're not dealing with a port tax rate, that's only in one
                `PortTaxRate` object.
                and/or
                B: We're not dealing with a `PortTaxRate` object, where rounding from 0
                is desired.
            Which means the `round_gross_ton_up_to` value doesn't need checking here.
        3: If the afforementioned _is_ the case, we need to verify that the value of
        `round_gross_ton_up_to` is between the values of `gt_start` and `gt_end`.
        4: Is the condition mentioned in step 3 not met, the following happens:
            1: Port name and vessel type are read from the form and saved to variables.
            2: User-friendly display strings are created/evaluated and saved as
            variables prefixed "msg_".
                The prefix is to indicate that they are to be used in f-strings
                to generate the correct error message.
            3: In an f-string the afforementioned display strings are composed into a
            user friendly and informative error message.
            4: A `ValidationError`is created with no field,  the afforementioned
            f-string as the error message and the display strings, port name and vessel
            type as parameters.
            5: The `ValidationError` constructor will then assemble the final error
            message and continue from there.

        This is intentionally written rather verbosely,
        to avoid long lines that would need breaking.
        During development the long, yet broken, lines have proven to make the
        error message composition cognitively taxing to an unnecessarily degree.
        """
        for form in self.forms:
            gt_start = form.cleaned_data["gt_start"]
            gt_end = form.cleaned_data["gt_end"]
            gt_round = form.cleaned_data.get("round_gross_ton_up_to")

            if (
                gt_start == 0
                and gt_end is not None
                and not (gt_start <= gt_round <= gt_end)
            ):
                # Gather error message component values
                vtype = form.cleaned_data["vessel_type"]
                port = form.cleaned_data["port"]

                # Compose error message
                errmsg = (
                    "%(msg_vtype)s , %(msg_port)s: "
                    '"Rund op til (ton)" [%(msg_gtround)s] '
                    'skal være mellem "Fra (ton)" [%(msg_gtstart)s] '
                    'og "Til (ton)" [%(msg_gtend)s]'
                )

                # Create validation error
                error = ValidationError(
                    errmsg,
                    params={
                        "msg_vtype": (
                            ShipType(vtype).label
                            if vtype is not None
                            else "Enhver skibstype"
                        ),
                        "msg_port": port and port.name or "enhver havn",
                        "msg_gtstart": gt_start if gt_start is not None else "tom",
                        "msg_gtend": gt_end if gt_end is not None else "tom",
                        "msg_gtround": gt_round if gt_round is not None else "tom",
                    },
                )

                # Add validation error to form
                form.add_error(None, error)

    def check_for_tonnage_gap_or_overlap(self):
        """
        Checks that for gaps in tonnages for multiple PortTaxRate forms in the formset.
        In other words: if more than one PortTaxRate form with a given combination
        of port and vessel type exists in the formset, we need to make sure that
        one gt_end equals another gt_start.
        """
        grouped_forms = BasePortTaxRateFormSet.group_port_tax_rate_forms(self.forms)

        for identifier, forms in grouped_forms.items():
            if len(forms) > 1:
                # "isolate" gt_start and gt_end
                intervals = []
                for form in forms:
                    gt_start = form.cleaned_data["gt_start"]
                    gt_end = form.cleaned_data["gt_end"]
                    intervals.append((gt_start, gt_end))

                # sort the intervals by gt_start
                intervals.sort(key=lambda x: x[0])

                # variables to hold/indicate gaps, overlaps and stuff
                has_gap = False
                has_overlap = False
                last_end = None

                # Check if all forms have gt_start == 0 and gt_end == None
                all_zero_none = all(
                    start == 0 and end is None for start, end in intervals
                )

                for start, end in intervals:
                    if last_end is None:
                        # get first interval of tonnages
                        last_end = end if end is not None else float("inf")
                    else:
                        # check for a gap
                        if start > last_end:
                            has_gap = True
                            break
                        # check for overlap (specifically less than)
                        if start < last_end and not all_zero_none:
                            has_overlap = True
                            break
                        # update, rinse, repeat
                        if end is not None:
                            last_end = max(last_end, end)

                # add errors
                if has_gap:
                    for form in forms:
                        vtype = form.cleaned_data["vessel_type"]
                        port = form.cleaned_data["port"]

                        error = ValidationError(
                            'Der er "hul" i brutto ton værdierne '
                            'for "%(msg_vtype)s/%(msg_port)s"',
                            params={
                                "msg_vtype": (
                                    ShipType(vtype).label
                                    if vtype is not None
                                    else "Enhver skibstype"
                                ),
                                "msg_port": (
                                    port.name if port is not None else "enhver havn"
                                ),
                            },
                        )
                        form.add_error("", error)
                elif has_overlap:
                    for form in forms:
                        vtype = form.cleaned_data["vessel_type"]
                        port = form.cleaned_data["port"]

                        error = ValidationError(
                            "Der er overlap i brutto ton værdierne "
                            'for "%(msg_vtype)s/%(msg_port)s"',
                            params={
                                "msg_vtype": (
                                    ShipType(vtype).label
                                    if vtype is not None
                                    else "Enhver skibstype"
                                ),
                                "msg_port": (
                                    port.name if port is not None else "enhver havn"
                                ),
                            },
                        )
                        form.add_error("", error)

    def check_for_duplicates(self):
        combinations = set()

        for form in self.forms:
            if form.cleaned_data:
                gt_start = form.cleaned_data["gt_start"]
                gt_end = form.cleaned_data["gt_end"]
                vtype = form.cleaned_data["vessel_type"]

                gt_round = form.cleaned_data["round_gross_ton_up_to"]
                port = form.cleaned_data["port"]

                # "normalise" gt_start and gt_end for comparison,
                # by letting -1 represent None
                normalized_gt_start = gt_start if gt_start is not None else -1
                normalized_gt_end = gt_end if gt_end is not None else -1

                combination = (
                    vtype,
                    port,
                    normalized_gt_start,
                    normalized_gt_end,
                    gt_round,
                )

                if combination in combinations:
                    # compose error message
                    errmsg = (
                        "En sats med denne kombination af "
                        '"Fra (ton)" [%(msg_gtstart)s], '
                        '"Til (ton)" [%(msg_gtend)s], '
                        'og "Rund op til (ton)" '
                        "[%(msg_gtround)s] for "
                        "%(msg_vtype)s, %(msg_port)s "
                        "eksisterer allerede."
                    )

                    # create validation error
                    error = ValidationError(
                        errmsg,
                        params={
                            "msg_gtstart": gt_start if gt_start is not None else "tomt",
                            "msg_gtend": gt_end if gt_end is not None else "tomt",
                            "msg_gtround": gt_round if gt_round is not None else "tom",
                            "msg_vtype": (
                                ShipType(vtype).label
                                if vtype is not None
                                else "Enhver skibstype"
                            ),
                            "msg_port": (
                                port.name if port is not None else "enhver havn"
                            ),
                        },
                    )

                    # add validation error to form
                    form.add_error(None, error)
                else:
                    combinations.add(combination)

    def clean(self):
        super().clean()
        self.clean_round_gross_ton_up_to()
        self.check_for_tonnage_gap_or_overlap()
        self.check_for_tonnage_presences()
        self.check_for_duplicates()


class BaseDisembarkmentTaxRateFormSet(BootstrapFormSet, TaxRateFormSet):
    """
    Checks for "duplicate" combinations for disembarkment_site and municipality.
    Adds an error to the form, if a given combination is already in the list.
    """

    def clean(self):
        super().clean()
        pairs = set()

        for form in self.forms:
            if form.cleaned_data:
                disemb_site = form.cleaned_data.get("disembarkment_site")
                municipality = form.cleaned_data.get("municipality")
                pair = (disemb_site, municipality)
                errmsg = (
                    f'"{municipality}, '
                    f'{disemb_site if disemb_site else "ethvert ilandsætningssted"}"'
                    f" er allerede i listen."
                )
                if pair in pairs:
                    form.add_error(None, errmsg)
                else:
                    pairs.add(pair)


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
    extra=0,
    can_delete=True,
    formset=BaseDisembarkmentTaxRateFormSet,
)


class PassengerStatisticsForm(BootstrapForm):
    nationality = MultipleChoiceField(
        label=_("Nationalitet"),
        choices=Nationality.choices,
        required=False,
    )
    first_month = MonthField(
        label=_("Fra"),
        required=False,
        widget=DateInput(
            attrs={
                "class": "datetimepicker",
                "placeholder": _("Fra"),
            }
        ),
    )
    last_month = MonthField(
        label=_("Til og med"),
        required=False,
        widget=DateInput(
            attrs={
                "class": "datetimepicker",
                "placeholder": _("Til og med"),
            }
        ),
    )
