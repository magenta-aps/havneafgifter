from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.core.mail import EmailMessage
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import F, Q, QuerySet
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.defaultfilters import date
from django.templatetags.l10n import localize
from django.utils import translation
from django.utils.functional import cached_property
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django_countries import countries
from django_fsm import FSMField, transition
from simple_history.models import HistoricalRecords
from simple_history.signals import pre_create_historical_record
from simple_history.utils import update_change_reason

from havneafgifter.data import DateTimeRange

logger = logging.getLogger(__name__)

pdf_storage = FileSystemStorage(location=settings.STORAGE_PDF)


@dataclass
class MailRecipient:
    name: str
    email: str
    object: models.Model | None


class MailRecipientList:
    def __init__(self, form: HarborDuesForm | CruiseTaxForm):
        self.form = form
        self.recipients = []

        if (
            form.port_of_call
            and form.port_of_call.portauthority
            and form.port_of_call.portauthority.email
        ):
            self.recipients.append(
                MailRecipient(
                    name=form.port_of_call.portauthority.name,
                    email=form.port_of_call.portauthority.email,
                    object=form.port_of_call.portauthority,
                )
            )
        else:
            if (
                isinstance(form, CruiseTaxForm)
                and not form.has_port_of_call
                and settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL
            ):
                self.recipients.append(
                    MailRecipient(
                        name=gettext("Authority for vessels without port of call"),
                        email=settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL,
                        object=None,
                    )
                )
            else:
                logger.info(
                    "%r is not linked to a port authority, excluding from "
                    "mail recipients",
                    self,
                )

        if form.shipping_agent and form.shipping_agent.email:
            self.recipients.append(
                MailRecipient(
                    name=form.shipping_agent.name,
                    email=form.shipping_agent.email,
                    object=form.shipping_agent,
                )
            )
        else:
            logger.info(
                "%r is not linked to a shipping agent, excluding from mail recipients",
                self,
            )

        if settings.EMAIL_ADDRESS_SKATTESTYRELSEN:
            self.recipients.append(
                MailRecipient(
                    name=gettext("Tax Authority"),
                    email=settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
                    object=None,
                )
            )
        else:
            logger.info(
                "Skattestyrelsen email not configured, excluding from mail recipients",
            )

    @property
    def recipient_emails(self) -> list[str]:
        return [recipient.email for recipient in self.recipients]


class User(AbstractUser):
    cpr = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        validators=[
            MinLengthValidator(10),
            MaxLengthValidator(10),
            RegexValidator(r"\d{10}"),
        ],
    )
    cvr = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        validators=[
            MinLengthValidator(8),
            MaxLengthValidator(8),
            RegexValidator(r"\d{8}"),
        ],
    )
    organization = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    port_authority = models.ForeignKey(
        "PortAuthority",
        null=True,
        blank=True,
        related_name="users",
        on_delete=models.SET_NULL,
    )
    port = models.ForeignKey(
        "Port",
        null=True,
        blank=True,
        related_name="users",
        on_delete=models.SET_NULL,
    )
    shipping_agent = models.ForeignKey(
        "ShippingAgent",
        null=True,
        blank=True,
        related_name="users",
        on_delete=models.SET_NULL,
    )

    def clean(self):
        if self.port is not None:
            if self.port_authority is None:
                raise ValidationError(
                    _("You must specify a port authority if a port is specified")
                )
            else:
                port_belongs_to_port_authority = self.port_authority.port_set.filter(
                    pk=self.port.pk
                ).exists()
                if not port_belongs_to_port_authority:
                    raise ValidationError(
                        _(
                            "The port specified must belong to the selected "
                            "port authority"
                        )
                    )

    @property
    def group_names(self):
        return [group.name for group in self.groups.all()]

    def has_group_name(self, name):
        return self.groups.filter(name=name).exists()

    @property
    def user_type(self):
        if self.is_staff:
            return UserType.ADMIN

        if self.is_superuser:
            return UserType.SUPERUSER

        if self.has_group_name("TaxAuthority"):
            return UserType.TAX_AUTHORITY

        if self.has_group_name("PortAuthority"):
            return UserType.PORT_AUTHORITY

        if self.shipping_agent:
            return UserType.SHIPPING_AGENT

        if self.has_group_name("Ship"):
            return UserType.SHIP

    @property
    def display_name(self) -> str:
        # Ship users
        if self.user_type == UserType.SHIP:
            # "<IMO number> / <Vessel name>"
            return f"{self.username} / {self.organization}"
        # Shipping agent users
        elif (
            self.user_type == UserType.SHIPPING_AGENT
            and self.shipping_agent is not None
        ):
            # "<Username> / <Agent name>"
            return f"{self.username} / {self.shipping_agent.name}"
        # Port authority users: admin and individual port users
        elif (
            self.user_type == UserType.PORT_AUTHORITY
            and self.port_authority is not None
        ):
            if self.port is None:
                # "<Authority name> / admin"
                return f"{self.port_authority.name} / admin"
            else:
                # "<Port name> / <Authority name>"
                return f"{self.port.name} / {self.port_authority.name}"
        # Tax authority users
        elif self.user_type == UserType.TAX_AUTHORITY:
            # "AKA - <E-mail>"
            return f"AKA - {self.email}"
        # Any other user type (including `None`)
        else:
            return self.username

    @property
    def can_create(self) -> bool:
        user_type: UserType | None = getattr(self, "user_type", None)
        if user_type is None:
            return False
        else:
            return user_type in (
                UserType.SHIP,
                UserType.SHIPPING_AGENT,
                UserType.SUPERUSER,
                UserType.ADMIN,
            )

    @property
    def can_view_list(self) -> bool:
        # All user types can see (links to the) form list (for now.)
        return True

    @property
    def can_view_statistics(self) -> bool:
        user_type: UserType | None = getattr(self, "user_type", None)
        if user_type is None:
            return False
        else:
            return user_type in (UserType.TAX_AUTHORITY, UserType.ADMIN)


class PermissionsMixin(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def permission_name(cls, action: str) -> str:
        return f"havneafgifter.{action}_{cls._meta.model_name}"

    @classmethod
    def filter_user_permissions(cls, qs: QuerySet, user: User, action: str) -> QuerySet:
        if user.is_anonymous or not user.is_active:
            return qs.none()
        if user.is_superuser:
            return qs
        if user.has_perm(cls.permission_name(action), None):
            # User has permission for all instances through
            # the standard Django permission system
            return qs

        qs1 = cls._filter_user_permissions(qs, user, action)
        if qs1 is not None:
            # User has permission to these specific instances
            return qs1
        return qs.none()

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        return qs.none()

    def has_permission(self, user: User, action: str, from_group: bool = False) -> bool:
        if user.is_anonymous or not user.is_active:
            return False
        if user.is_superuser:
            return True
        if user.has_perm(self.permission_name(action), None):
            # User has permission for all instances through
            # the standard Django permission system
            return True
        if self._has_permission(user, action, from_group):
            # User has permission to this specific instance
            return True
        return False

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return (
            not from_group
            and self.filter_user_permissions(
                self.__class__.objects.filter(pk=self.pk), user, action  # type: ignore
            ).exists()
        )


class ShipType(models.TextChoices):
    FREIGHTER = "FREIGHTER", _("Freighter")
    FISHER = "FISHER", _("Foreign fishing ship")
    PASSENGER = "PASSENGER", _("Passenger ship")
    CRUISE = "CRUISE", _("Cruise ship")
    OTHER = "OTHER", _("Other vessel")


class Nationality(models.TextChoices):
    AUSTRALIA = "AU", _("Australia")
    AUSTRIA = "AT", _("Austria")
    BELGIUM = "BE", _("Belgium")
    CANADA = "CA", _("Canada")
    CHINA = "CN", _("China")
    CZECH = "CZ", _("Czech Republic")
    DENMARK = "DK", _("Denmark")
    FINLAND = "FI", _("Finland")
    FRANCE = "FR", _("France")
    GERMANY = "DE", _("Germany")
    UK = "UK", _("United Kingdom")
    GREENLAND = "GL", _("Greenland")
    HONG_KONG = "HK", _("Hong Kong")
    ICELAND = "IS", _("Iceland")
    INDONESIA = "ID", _("Indonesia")
    ITALY = "IT", _("Italy")
    JAPAN = "JP", _("Japan")
    LUXEMBOURG = "LU", _("Luxembourg")
    MALAYSIA = "MY", _("Malaysia")
    NETHERLANDS = "NL", _("Netherlands")
    NEW_ZEALAND = "NZ", _("New Zealand")
    NORWAY = "NO", _("Norway")
    POLAND = "PL", _("Poland")
    RUSSIA = "RU", _("Russia")
    SINGAPORE = "SG", _("Singapore")
    SOUTH_KOREA = "KO", _("South Korea")
    SPAIN = "ES", _("Spain")
    SWEDEN = "SE", _("Sweden")
    SWITZERLAND = "CH", _("Switzerland")
    TAIWAN = "TW", _("Taiwan")
    USA = "US", _("United States of America")
    OTHER_ASIA = "AS", _("Other asian country")
    OTHER_EUROPE = "EU", _("Other European country")
    OTHERS = "OT", _("Other")


class Status(models.TextChoices):
    DRAFT = ("DRAFT", _("Draft"))
    NEW = ("NEW", _("Awaiting approval"))  # NEW is kept to align with other products
    APPROVED = ("APPROVED", _("Approved"))
    REJECTED = ("REJECTED", _("Rejected"))
    # TODO: DONE or something similar will be introduced when the system
    # handles invoicing. For now, we won't be needing it.
    # DONE = ("DONE", _("Done"))


class Municipality(models.IntegerChoices):
    KUJALLEQ = 955, "Kujalleq"
    QEQQATA = 957, "Qeqqata"
    SERMERSOOQ = 956, "Sermersooq"
    QEQERTALIK = 959, "Qeqertalik"
    AVANNAATA = 960, "Avannaata"
    NATIONAL_PARK = 961, _("Northeast Greenland National Park")


class UserType(models.TextChoices):
    ADMIN = "admin", _("administrator")
    SUPERUSER = "superuser", _("superuser")
    TAX_AUTHORITY = "tax_authority", _("tax authority")
    PORT_AUTHORITY = "port_authority", _("port authority")
    SHIPPING_AGENT = "shipping_agent", _("shipping agent")
    SHIP = "ship", _("ship")


class ShippingAgent(PermissionsMixin, models.Model):
    class Meta:
        ordering = ["name"]

    name = models.CharField(
        max_length=100,
        null=False,
        blank=False,
        verbose_name=_("Name"),
    )

    email = models.EmailField(
        null=False,
        blank=False,
        verbose_name=_("Email address"),
    )

    def __str__(self) -> str:
        return self.name

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        # Filter the qs based on what the user is allowed to do
        # These come on top of class-wide permissions (access to all instances)
        #
        if (
            action == "change"
            and user.shipping_agent
            and user.has_group_name("Shipping")
        ):
            return qs.filter(pk=user.shipping_agent_id)
        return None

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return action == "change" and not from_group and user.shipping_agent == self


def imo_validator(value: str):
    if len(value) != 7:
        raise ValidationError("IMO has incorrect length (must be 7 digits)")
    if not re.match(r"\d{7}", value):
        raise ValidationError("IMO has incorrect content (must be 7 digits)")
    # https://en.wikipedia.org/wiki/IMO_number
    if sum([int(value[i]) * (7 - i) for i in range(0, 6)]) % 10 != int(value[6]):
        raise ValidationError("IMO Check failed")


def imo_validator_bool(value: str) -> bool:
    # We could do this with an optional param to imo_validator, but MyPy complains
    try:
        imo_validator(value)
    except ValidationError:
        return False
    return True


class PortAuthority(PermissionsMixin, models.Model):
    class Meta:
        ordering = ["name"]
        verbose_name_plural = _("Port authorities")

    name = models.CharField(
        max_length=32,
        null=False,
        blank=False,
        verbose_name=_("Port authority company name"),
    )
    email = models.EmailField(
        null=False, blank=False, verbose_name=_("Port authority contact email")
    )

    def __str__(self) -> str:
        return self.name

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        # Filter the qs based on what the user is allowed to do
        if (
            action == "change"
            and user.port_authority
            and user.has_group_name("PortAuthority")
        ):
            return qs.filter(pk=user.port_authority_id)
        return None

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return action == "change" and not from_group and user.port_authority == self


class Port(PermissionsMixin, models.Model):
    class Meta:
        ordering = ["portauthority__name", "name"]

    name = models.CharField(
        max_length=16, null=False, blank=False, verbose_name=_("Port name")
    )
    portauthority = models.ForeignKey(
        PortAuthority, null=True, blank=True, on_delete=models.SET_NULL
    )

    def __str__(self) -> str:
        if self.portauthority:
            return f"{self.name} ({self.portauthority})"
        else:
            return self.name


class Reason(models.Model):
    """Abstract model class used to enhance the history entries for
    `HarborDuesForm` and `CruiseTaxForm`.
    """

    class Meta:
        abstract = True

    reason_text = models.TextField(
        null=True,
        verbose_name=_("Reason text"),
    )


class HarborDuesForm(PermissionsMixin, models.Model):
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (Q(vessel_type=ShipType.CRUISE) | Q(nationality__isnull=False))
                ),
                name="nationality_cannot_be_null_for_non_drafts",
                violation_error_code="constraint_violated",  # type: ignore
            ),
            # `port_of_call` can only be left blank/NULL for cruise ships
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (Q(vessel_type=ShipType.CRUISE) | Q(port_of_call__isnull=False))
                ),
                name="port_of_call_cannot_be_null_for_non_cruise_ships",
                violation_error_code="constraint_violated",  # type: ignore
            ),
            # `gross_tonnage` can only be left blank/NULL for cruise ships
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (Q(vessel_type=ShipType.CRUISE) | Q(gross_tonnage__isnull=False))
                ),
                name="gross_tonnage_cannot_be_null_for_non_cruise_ships",
                violation_error_code="constraint_violated",  # type: ignore
            ),
            # `datetime_of_arrival` can only be left blank/NULL for cruise ships
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (
                        Q(vessel_type=ShipType.CRUISE)
                        | Q(datetime_of_arrival__isnull=False)
                    )
                ),
                name="datetime_of_arrival_cannot_be_null_for_non_cruise_ships",
                violation_error_code="constraint_violated",  # type: ignore
            ),
            # `datetime_of_departure` can only be left blank/NULL for cruise ships
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (
                        Q(vessel_type=ShipType.CRUISE)
                        | Q(datetime_of_departure__isnull=False)
                    )
                ),
                name="datetime_of_departure_cannot_be_null_for_non_cruise_ships",
                violation_error_code="constraint_violated",  # type: ignore
            ),
            # `datetime_of_arrival` and `datetime_of_departure` must either both
            # be present, or both be blank/NULL.
            models.CheckConstraint(
                check=(
                    Q(status=Status.DRAFT)
                    | (
                        # Both present
                        (
                            Q(datetime_of_arrival__isnull=False)
                            & Q(datetime_of_departure__isnull=False)
                        )
                        # Both absent
                        | (
                            Q(datetime_of_arrival__isnull=True)
                            & Q(datetime_of_departure__isnull=True)
                        )
                    )
                ),
                name="datetime_of_arrival_and_departure_must_both_be_present_"
                "or_both_be_null",
                violation_error_code="constraint_violated",  # type: ignore
            ),
        ]

    history = HistoricalRecords(
        bases=[Reason],
        history_change_reason_field=models.TextField(null=True),
        related_name="harbor_dues_form_history_entries",
        excluded_fields=["harbour_tax", "pdf"],  # exclude system-maintained fields
    )

    status = FSMField(
        default=Status.DRAFT,
        choices=Status.choices,
        protected=True,
        verbose_name=_("Status"),
    )

    date = models.DateField(
        null=False,
        blank=False,
        auto_now_add=True,
        verbose_name=_("Submission date"),
    )

    port_of_call = models.ForeignKey(
        Port,
        null=True,
        blank=True,
        verbose_name=_("Port of call"),
        on_delete=models.PROTECT,
    )

    nationality = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        choices=countries,
        verbose_name=_("Vessel nationality"),
    )

    vessel_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Vessel name"),
    )

    vessel_imo = models.CharField(
        max_length=7,
        null=True,
        blank=True,
        validators=[
            MinLengthValidator(7),
            MaxLengthValidator(7),
            RegexValidator(r"\d{7}"),
            imo_validator,
        ],
        verbose_name=_("IMO-number"),
    )

    vessel_owner = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Vessel owner"),
    )

    vessel_master = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Vessel captain"),
    )

    shipping_agent = models.ForeignKey(
        ShippingAgent,
        null=True,
        blank=True,
        verbose_name=_("Shipping agent"),
        on_delete=models.SET_NULL,
    )

    datetime_of_arrival = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Arrival date/time"),
    )

    datetime_of_departure = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Departure date/time"),
    )

    gross_tonnage = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Gross tonnage"),
    )

    vessel_type = models.CharField(
        null=True,
        blank=True,
        max_length=9,
        choices=ShipType,
        verbose_name=_("Vessel type"),
    )

    harbour_tax = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
        verbose_name=_("Calculated harbour tax"),
    )

    pdf = models.FileField(
        null=True,
        blank=True,
        storage=pdf_storage,
        verbose_name=_("PDF file"),
    )

    @transition(
        field=status,
        source=[Status.DRAFT, Status.REJECTED],
        target=Status.NEW,
        permission=lambda instance, user: instance.has_permission(
            user, "submit_for_review", False
        ),
    )
    def submit_for_review(self):
        self._change_reason = Status.NEW.label

    @transition(
        field=status,
        source=Status.NEW,
        target=Status.APPROVED,
        permission=lambda instance, user: instance.has_permission(
            user, "approve", False
        ),
    )
    def approve(self):
        self._change_reason = Status.APPROVED.label

    @transition(
        field=status,
        source=Status.NEW,
        target=Status.REJECTED,
        permission=lambda instance, user: instance.has_permission(
            user, "reject", False
        ),
    )
    def reject(self, reason: str):
        self._rejection_reason = reason
        self._change_reason = Status.REJECTED.label

    def save(self, *args, **kwargs):
        initial = self.pk is None
        super().save(*args, **kwargs)
        if initial:
            update_change_reason(self, Status.DRAFT.label)

    def __str__(self) -> str:
        port_of_call = self.port_of_call or _("no port of call")
        return (
            f"{self.vessel_name}, {port_of_call} "
            f"({self.datetime_of_arrival} - {self.datetime_of_departure})"
        )

    def _any_is_none(self, *vals) -> bool:
        return any(val is None for val in vals)

    def _period_is_not_none(self):
        return (
            self.datetime_of_arrival is not None
            and self.datetime_of_departure is not None
        )

    @property
    def duration_in_days(self) -> int | None:
        if self._period_is_not_none():
            range = DateTimeRange(
                self.datetime_of_arrival,  # type: ignore
                self.datetime_of_departure,  # type: ignore
            )
            return range.started_days
        else:
            return None

    @property
    def duration_in_weeks(self) -> int | None:
        if self._period_is_not_none():
            range = DateTimeRange(
                self.datetime_of_arrival,  # type: ignore
                self.datetime_of_departure,  # type: ignore
            )
            return range.started_weeks
        else:
            return None

    @property
    def form_id(self):
        # Return "løbenummer" for this form object, on the form "00001APR2024", where
        # "00001" is the primary key, "APR" is the month, and "2024" is the year.
        # Always use English locale to ensure consistent formatting of the month names.
        with translation.override("en"):
            return f"{self.pk:05}{date(self.date, 'bY').upper()}"

    @property
    def has_port_of_call(self) -> bool:
        # Cruise ships *can* have a port of call, but are not required to have it.
        # Non-cruise ships *must* have a port of call.
        return self.vessel_type != ShipType.CRUISE or self.port_of_call is not None

    def get_pdf_filename(self) -> str:
        if self.pdf and self.pdf.name:
            return self.pdf.name
        else:
            return f"{self.form_id}.pdf"

    def calculate_tax(self, save: bool = True):
        self.calculate_harbour_tax(save=save)

    def calculate_harbour_tax(
        self, save: bool = True
    ) -> dict[str, Decimal | list[dict] | None]:
        if self._any_is_none(
            self.port_of_call,
            self.datetime_of_arrival,
            self.datetime_of_departure,
            self.gross_tonnage,
        ):
            return {"harbour_tax": None, "details": []}

        taxrates = TaxRates.objects.filter(
            Q(start_datetime__isnull=True)
            | Q(start_datetime__lte=self.datetime_of_departure),
            Q(end_datetime__isnull=True)
            | Q(end_datetime__gte=self.datetime_of_arrival),
        )
        harbour_tax = Decimal(0)
        details = []
        for taxrate in taxrates:
            datetime_range = taxrate.get_overlap(
                self.datetime_of_arrival,  # type: ignore
                self.datetime_of_departure,  # type: ignore
            )
            port_taxrate: PortTaxRate | None = taxrate.get_port_tax_rate(
                port=self.port_of_call,  # type: ignore
                vessel_type=self.vessel_type,  # type: ignore
                gross_ton=self.gross_tonnage,  # type: ignore
            )
            range_port_tax = Decimal(0)
            if port_taxrate is not None:
                gross_tonnage: int = max(
                    self.gross_tonnage,  # type: ignore
                    port_taxrate.round_gross_ton_up_to,
                )
                if self.vessel_type in (
                    ShipType.FREIGHTER,
                    ShipType.OTHER,
                ):
                    payments = datetime_range.started_weeks
                else:
                    payments = datetime_range.started_days
                range_port_tax = payments * port_taxrate.port_tax_rate * gross_tonnage
                harbour_tax += range_port_tax
            details.append(
                {
                    "port_taxrate": port_taxrate,
                    "date_range": datetime_range,
                    "harbour_tax": range_port_tax,
                }
            )
        if save:
            self.harbour_tax = harbour_tax
            self.save(update_fields=("harbour_tax",))
        return {"harbour_tax": harbour_tax, "details": details}

    @cached_property
    def tax_per_gross_ton(self) -> Decimal | None:
        result = None
        harbour_tax = self.calculate_harbour_tax(save=False)
        for detail in harbour_tax["details"]:  # type: ignore
            current = detail["port_taxrate"].port_tax_rate
            if (result is None) or (result < current):
                result = current
        return result

    def get_receipt(self, **kwargs):
        from havneafgifter.receipts import HarborDuesFormReceipt

        return HarborDuesFormReceipt(self, **kwargs)

    def send_email(self) -> tuple[EmailMessage, int]:
        logger.info("Sending email %r to %r", self.mail_subject, self.mail_recipients)
        msg = EmailMessage(
            self.mail_subject,
            self.mail_body,
            from_email=settings.EMAIL_SENDER,
            bcc=self.mail_recipients,
        )
        receipt = self.get_receipt()
        msg.attach(
            filename=self.get_pdf_filename(),
            content=receipt.pdf,
            mimetype="application/pdf",
        )
        result = msg.send(fail_silently=False)
        if result:
            self.pdf = File(BytesIO(receipt.pdf), name=self.get_pdf_filename())
            self.save(update_fields=["pdf"])
        return msg, result

    @property
    def mail_subject(self):
        return f"Talippoq: {self.pk:05} ({self.date})"

    @property
    def mail_body(self):
        # The mail body consists of the same text repeated in English, Greenlandic, and
        # Danish.
        # The text varies depending on whether the form concerns a cruise ship, or any
        # other type of vessel.
        result = []
        for lang_code, lang_name in settings.LANGUAGES:
            with translation.override(lang_code):
                context = {
                    "date": localize(self.date),
                    "agent": self.shipping_agent.name if self.shipping_agent else "",
                }
                if self.vessel_type == ShipType.CRUISE:
                    text = (
                        _(
                            "%(agent)s has %(date)s reported port taxes, cruise "
                            "passenger taxes, as well as environmental and "
                            "maintenance fees in relation to a ship's call "
                            "at a Greenlandic port. See further details in the "
                            "attached overview."
                        )
                        % context
                    )
                else:
                    text = (
                        _(
                            "%(agent)s has %(date)s reported port taxes due to a "
                            "ship's call at a Greenlandic port. See further details "
                            "in the attached overview."
                        )
                        % context
                    )
                result.append(text)
        return "\n\n".join(result)

    @property
    def mail_recipients(self) -> list[str]:
        recipient_list: MailRecipientList = MailRecipientList(self)
        return recipient_list.recipient_emails

    @cached_property
    def latest_rejection(self):
        if self.status == Status.REJECTED:
            try:
                return self.history.filter(
                    status=Status.REJECTED,
                    reason_text__isnull=False,
                ).latest("history_date")
            except ObjectDoesNotExist:
                # No matching history entry
                return None

    @classmethod
    def _get_port_authority_filter(cls, user: User) -> Q:
        base_filter: Q = Q(
            # 1. Port authority users cannot see DRAFT forms
            status__in=[Status.NEW, Status.APPROVED, Status.REJECTED],
            # 2. Port authority users can only see forms whose port of call is a port
            # managed by the port authority in question.
            port_of_call__portauthority__isnull=False,
            port_of_call__portauthority_id=user.port_authority_id,
        )
        if user.port is None:
            # This port authority user has access to *all* ports belonging to the
            # port authority.
            return base_filter
        else:
            # This port authority user has access to *a specific* port belonging to the
            # port authority.
            filter_by_port: Q = Q(port_of_call=user.port)
            return base_filter & filter_by_port

    def _has_port_authority_permission(self, user: User) -> bool:
        # Shortcut check if various nullable fields are indeed NULL
        if self.port_of_call is None:
            return False
        if getattr(self.port_of_call, "portauthority", None) is None:
            return False
        if user.port_authority is None:
            return False

        # Shortcut check if form status is DRAFT:
        if self.status == Status.DRAFT:
            return False

        if user.port is None:
            # This port authority user has access to *all* ports belonging to the
            # port authority.
            return user.port_authority == self.port_of_call.portauthority
        else:
            # This port authority user has access to *a specific* port belonging to the
            # port authority.
            return (user.port_authority == self.port_of_call.portauthority) and (
                user.port == self.port_of_call
            )

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        # Filter the qs based on what the user is allowed to do
        if action in (
            "view",
            "change",
        ):
            filter: Q = Q()
            if user.has_group_name("Shipping"):
                filter |= Q(shipping_agent__isnull=False) & Q(
                    shipping_agent_id=user.shipping_agent_id
                )
            if user.has_group_name("PortAuthority"):
                filter |= cls._get_port_authority_filter(user)
            if user.has_group_name("Ship") and imo_validator_bool(user.username):
                filter |= Q(vessel_imo=user.username)

            if filter.children:
                return qs.filter(filter)

        if action in (
            "approve",
            "reject",
            "invoice",
        ):
            if user.has_group_name("PortAuthority"):
                return qs.filter(cls._get_port_authority_filter(user))
        return qs.none()

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return not from_group and (
            (
                action in ("view", "change")
                and (
                    (self.port_of_call is None)
                    or (
                        user.has_group_name("PortAuthority")
                        and self._has_port_authority_permission(user)
                    )
                    or (
                        user.has_group_name("Shipping")
                        and user.shipping_agent == self.shipping_agent
                    )
                    or (
                        user.has_group_name("Ship")
                        and imo_validator_bool(user.username)
                        and user.username == self.vessel_imo
                    )
                )
            )
            or (
                action == "submit_for_review"
                and (user.has_group_name("Ship") or user.has_group_name("Shipping"))
            )
            or (
                action in ("approve", "reject", "invoice")
                and (
                    (self.port_of_call is None)
                    or (
                        user.has_group_name("PortAuthority")
                        and self._has_port_authority_permission(user)
                    )
                )
            )
        )


class CruiseTaxForm(HarborDuesForm):
    number_of_passengers = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=0,
        verbose_name=_("Number of passengers"),
    )

    pax_tax = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
        verbose_name=_("Calculated passenger tax"),
    )

    disembarkment_tax = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=12,
        verbose_name=_("Calculated disembarkment tax"),
    )

    history = HistoricalRecords(
        bases=[Reason],
        history_change_reason_field=models.TextField(null=True),
        related_name="cruise_tax_form_history_entries",
        # Exclude system-maintained fields
        excluded_fields=[
            "harbour_tax",
            "pax_tax",
            "disembarkment_tax",
            "pdf",
        ],
    )

    def calculate_tax(self, save: bool = True):
        super().calculate_tax(save=save)  # calculates harbour tax
        self.calculate_passenger_tax(save=save)
        self.calculate_disembarkment_tax(save=save)

    def calculate_disembarkment_tax(self, save: bool = True):
        disembarkment_date = self.datetime_of_arrival or self.date
        taxrate = TaxRates.objects.filter(
            Q(start_datetime__isnull=True) | Q(start_datetime__lte=disembarkment_date),
            Q(end_datetime__isnull=True) | Q(end_datetime__gte=disembarkment_date),
        ).first()
        disembarkment_tax = Decimal(0)
        details = []
        for disembarkment in self.disembarkment_set.all():
            disembarkment_site = disembarkment.disembarkment_site
            disembarkment_tax_rate = (
                taxrate.get_disembarkment_tax_rate(disembarkment_site)
                if taxrate
                else None
            )
            tax = Decimal(0)
            if disembarkment_tax_rate is not None:
                tax = (
                    disembarkment.number_of_passengers
                    * disembarkment_tax_rate.disembarkment_tax_rate
                )
                disembarkment_tax += tax
            details.append(
                {
                    "disembarkment": disembarkment,
                    "date": disembarkment_date,
                    "taxrate": disembarkment_tax_rate,
                    "tax": tax,
                }
            )
        if save:
            self.disembarkment_tax = disembarkment_tax
            self.save(update_fields=("disembarkment_tax",))
        return {"disembarkment_tax": disembarkment_tax, "details": details}

    def calculate_passenger_tax(self, save: bool = True) -> dict[str, Decimal | None]:
        if self._any_is_none(
            self.number_of_passengers,
            self.datetime_of_arrival,
            self.datetime_of_departure,
        ):
            return {"passenger_tax": None, "taxrate": Decimal("0")}

        arrival_date = self.datetime_of_arrival
        taxrate = TaxRates.objects.filter(
            Q(start_datetime__isnull=True) | Q(start_datetime__lte=arrival_date),
            Q(end_datetime__isnull=True) | Q(end_datetime__gte=arrival_date),
        ).first()
        rate: Decimal = taxrate and taxrate.pax_tax_rate or Decimal(0)
        pax_tax: Decimal = self.number_of_passengers * rate  # type: ignore
        if save:
            self.pax_tax = pax_tax
            self.save(update_fields=("pax_tax",))
        return {"passenger_tax": pax_tax, "taxrate": rate}

    @property
    def total_tax(self) -> Decimal:
        def value_or_zero(val: Decimal | None) -> Decimal:
            return val or Decimal("0")

        return (
            value_or_zero(self.harbour_tax)
            + value_or_zero(self.pax_tax)
            + value_or_zero(self.disembarkment_tax)
        )

    def get_receipt(self, **kwargs):
        from havneafgifter.receipts import CruiseTaxFormReceipt

        return CruiseTaxFormReceipt(self, **kwargs)


class PassengersByCountry(PermissionsMixin, models.Model):
    class Meta:
        ordering = [
            "cruise_tax_form",
            "nationality",
        ]
        unique_together = [
            "cruise_tax_form",
            "nationality",
        ]

    cruise_tax_form = models.ForeignKey(
        CruiseTaxForm,
        null=False,
        on_delete=models.CASCADE,
        related_name="passengers_by_country",
    )

    nationality = models.CharField(
        max_length=2,
        null=False,
        blank=False,
        choices=Nationality,
        verbose_name=_("Nationality"),
    )

    number_of_passengers = models.PositiveIntegerField(
        null=False,
        blank=False,
        verbose_name=_("Number of passengers from nationality"),
    )

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        # Filter the qs based on what the user is allowed to do
        return qs.filter(
            cruise_tax_form__in=CruiseTaxForm.filter_user_permissions(
                CruiseTaxForm.objects.all(), user, action
            )
        )

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return self.cruise_tax_form._has_permission(user, action, from_group)


class DisembarkmentSite(PermissionsMixin, models.Model):
    class Meta:
        ordering = ["municipality", "pk"]

    name = models.CharField(
        max_length=200,
        null=False,
        blank=False,
        verbose_name=_("Disembarkment site"),
    )

    municipality = models.PositiveSmallIntegerField(
        choices=Municipality,
        null=False,
        blank=False,
        verbose_name=_("Municipality"),
    )

    is_outside_populated_areas = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        verbose_name=_("Other disembarkation outside of populated areas"),
    )

    def __str__(self) -> str:
        return f"{self.name} ({self.get_municipality_display()})"


class Disembarkment(PermissionsMixin, models.Model):
    class Meta:
        ordering = [
            "cruise_tax_form",
            "disembarkment_site__municipality",
            "disembarkment_site__name",
        ]
        unique_together = [
            "cruise_tax_form",
            "disembarkment_site",
        ]

    cruise_tax_form = models.ForeignKey(
        CruiseTaxForm, null=False, blank=False, on_delete=models.CASCADE
    )

    number_of_passengers = models.PositiveIntegerField(
        null=False,
        blank=False,
        verbose_name=_("Number of passengers disembarking"),
    )

    disembarkment_site = models.ForeignKey(
        DisembarkmentSite, null=False, blank=False, on_delete=models.CASCADE
    )

    @classmethod
    def _filter_user_permissions(
        cls, qs: QuerySet, user: User, action: str
    ) -> QuerySet | None:
        # Filter the qs based on what the user is allowed to do
        return qs.filter(
            cruise_tax_form__in=CruiseTaxForm.filter_user_permissions(
                CruiseTaxForm.objects.all(), user, action
            )
        )

    def _has_permission(self, user: User, action: str, from_group: bool) -> bool:
        return self.cruise_tax_form._has_permission(user, action, from_group)


class TaxRates(PermissionsMixin, models.Model):
    class Meta:
        ordering = [F("start_datetime").asc(nulls_first=True)]
        verbose_name_plural = "TaxRates objects"

    pax_tax_rate = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=6,
        verbose_name=_("Tax per passenger"),
    )

    start_datetime = models.DateTimeField(null=True, blank=True)

    end_datetime = models.DateTimeField(null=True, blank=True)

    def get_port_tax_rate(
        self, port: Port, vessel_type: str, gross_ton: int
    ) -> PortTaxRate | None:
        qs = self.port_tax_rates.filter(gt_start__lte=gross_ton).filter(
            Q(gt_end__gte=gross_ton) | Q(gt_end__isnull=True)
        )
        for key, value in (("vessel_type", vessel_type), ("port", port)):
            qs1 = qs.filter(**{key: value})
            if qs1.exists():
                qs = qs1
            else:
                qs = qs.filter(**{f"{key}__isnull": True})
        return qs.first()

    def get_overlap(self, rangestart: datetime, rangeend: datetime) -> DateTimeRange:
        if self.end_datetime is not None and self.end_datetime < rangeend:
            rangeend = self.end_datetime
        if self.start_datetime is not None and self.start_datetime > rangestart:
            rangestart = self.start_datetime
        return DateTimeRange(rangestart, rangeend)

    def get_disembarkment_tax_rate(
        self, disembarkment_site: DisembarkmentSite
    ) -> DisembarkmentTaxRate | None:
        qs = DisembarkmentTaxRate.objects.filter(
            tax_rates=self, disembarkment_site=disembarkment_site
        )
        if not qs.exists():
            qs = DisembarkmentTaxRate.objects.filter(
                tax_rates=self, municipality=disembarkment_site.municipality
            )
        return qs.first()

    def save(self, *args, **kwargs):
        super().full_clean()
        super().save(*args, **kwargs)

    @staticmethod
    def on_update(sender, instance: TaxRates, **kwargs):
        # En TaxRates-tabel har (måske) fået ændret sin `start_datetime`
        # Opdatér `end_datetime` på alle tabeller som er påvirkede
        # (tidl. prev, ny prev, tabellen selv)
        # Det er nemmest og sikrest at loope over hele banden,
        # så vi er sikre på at ramme alle
        update_fields = kwargs.get("update_fields")
        if not update_fields or "start_datetime" in update_fields:
            end_datetime = None
            for item in TaxRates.objects.all().order_by(
                F("start_datetime").desc(nulls_last=True)
            ):
                # Loop over alle tabeller fra sidste til første
                # (reverse af default ordering)
                if item.end_datetime != end_datetime:
                    item.end_datetime = end_datetime
                    # Sæt kun `end_datetime`, så vi forhindrer rekursion
                    item.save(update_fields=("end_datetime",))
                end_datetime = item.start_datetime

    def __str__(self) -> str:
        start = self.start_datetime.date() if self.start_datetime else "-∞"
        end = self.end_datetime.date() if self.end_datetime else "∞"
        return f"{start} - {end}"


post_save.connect(TaxRates.on_update, sender=TaxRates, dispatch_uid="TaxRates_update")


class PortTaxRate(PermissionsMixin, models.Model):
    tax_rates = models.ForeignKey(
        TaxRates,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="port_tax_rates",
    )

    port = models.ForeignKey(
        Port,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Harbour"),
    )

    vessel_type = models.CharField(
        max_length=9,
        choices=ShipType,
        null=True,
        blank=True,
        verbose_name=_("Vessel type"),
    )

    gt_start = models.PositiveIntegerField(
        null=False,
        blank=False,
        verbose_name=_("Vessel gross tonnage (lower)"),
    )

    gt_end = models.PositiveIntegerField(
        verbose_name=_("Vessel gross tonnage (upper)"),
        null=True,
        blank=True,
    )

    port_tax_rate = models.DecimalField(
        null=False,
        blank=False,
        decimal_places=2,
        max_digits=12,
        default=Decimal(0),
        verbose_name=_("Tax per gross ton"),
    )

    round_gross_ton_up_to = models.PositiveIntegerField(
        null=False, blank=False, default=0, verbose_name=_("Round GT up to")
    )

    def __str__(self) -> str:
        tax_rates = self.tax_rates
        port = self.port.name if self.port else ""
        vessel_type = self.vessel_type
        gt_start = self.gt_start
        gt_end = self.gt_end
        return f"{tax_rates}, {port}, {vessel_type}, {gt_start} t - {gt_end} t"

    @property
    def name(self):
        vessel_label = (
            ShipType[self.vessel_type].label
            if self.vessel_type
            else _("Enhver skibstype")
        )
        port = self.port.name if self.port else _("enhver havn")
        return f"{vessel_label}, {port}"


class DisembarkmentTaxRate(PermissionsMixin, models.Model):
    class Meta:
        unique_together = ("tax_rates", "municipality", "disembarkment_site")

    tax_rates = models.ForeignKey(
        TaxRates,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="disembarkment_tax_rates",
    )

    disembarkment_site = models.ForeignKey(
        DisembarkmentSite,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="disembarkment_tax_rates",
        verbose_name=_("Disembarkment site"),
    )

    municipality = models.PositiveSmallIntegerField(
        choices=Municipality,
        null=False,
        blank=False,
        verbose_name=_("Municipality"),
    )

    disembarkment_tax_rate = models.DecimalField(
        null=False,
        blank=False,
        decimal_places=2,
        max_digits=12,
        verbose_name=_("Disembarkment tax rate"),
    )

    def __str__(self) -> str:
        tax_rates = self.tax_rates
        municipality = self.get_municipality_display()
        rate = self.disembarkment_tax_rate
        return f"{tax_rates}, {municipality}, {rate}"

    @property
    def name(self):
        municipality = self.get_municipality_display()
        disembarkment_site = (
            self.disembarkment_site.name
            if self.disembarkment_site
            else _("ethvert ilandsætningssted")
        )
        return f"{municipality}, {disembarkment_site}"


@receiver(pre_create_historical_record, sender=HarborDuesForm.history.model)
def pre_create_historical_record_callback(
    sender, signal, instance, history_instance, **kwargs
):
    # Save the rejection reason on the corresponding `HistoricalHarborDuesForm`
    reason = getattr(instance, "_rejection_reason", None)
    if reason is not None:
        history_instance.reason_text = reason
