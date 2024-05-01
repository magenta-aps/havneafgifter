from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import post_save
from django.templatetags.l10n import localize
from django.utils.translation import gettext as _

from havneafgifter.data import DateTimeRange

logger = logging.getLogger(__name__)


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


class ShipType(models.TextChoices):
    FREIGHTER = "FREIGHTER", _("Freighter")
    FISHER = "FISHER", _("Fishing ship")
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


class Municipality(models.IntegerChoices):
    KUJALLEQ = 955, "Kujalleq"
    QAASUITSUP = 958, "Qaasuitsup"
    QEQQATA = 957, "Qeqqata"
    SERMERSOOQ = 956, "Sermersooq"
    QEQERTALIK = 959, "Qeqertalik"
    AVANNAATA = 960, "Avannaata"
    NATIONAL_PARK = 961, _("Northeast Greenland National Park")


class ShippingAgent(models.Model):
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


def imo_validator(value: str):
    if len(value) != 7:
        raise ValidationError("IMO has incorrect length (must be 7 digits)")
    if not re.match(r"\d{7}", value):
        raise ValidationError("IMO has incorrect content (must be 7 digits)")
    # https://en.wikipedia.org/wiki/IMO_number
    if sum([int(value[i]) * (7 - i) for i in range(0, 6)]) % 10 != int(value[6]):
        raise ValidationError("IMO Check failed")


class PortAuthority(models.Model):
    class Meta:
        ordering = ["name"]

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


class Port(models.Model):
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


class HarborDuesForm(models.Model):
    class Country(models.TextChoices):
        DENMARK = "DK", _("Denmark")

    date = models.DateField(
        null=False,
        blank=False,
        auto_now_add=True,
        verbose_name=_("Form submission date"),
    )

    port_of_call = models.ForeignKey(
        Port,
        null=False,
        blank=False,
        verbose_name=_("Port of call"),
        on_delete=models.PROTECT,
    )

    nationality = models.CharField(
        max_length=2,
        choices=Country,
        null=False,
        blank=False,
        verbose_name=_("Vessel nationality"),
    )

    vessel_name = models.CharField(
        max_length=255,
        null=False,
        blank=False,
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
        null=False,
        blank=False,
        verbose_name=_("Vessel owner"),
    )

    vessel_master = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        verbose_name=_("Vessel captain"),
    )

    shipping_agent = models.ForeignKey(
        ShippingAgent,
        null=True,
        blank=False,
        verbose_name=_("Shipping agent"),
        on_delete=models.SET_NULL,
    )

    datetime_of_arrival = models.DateTimeField(
        null=False, blank=False, verbose_name=_("Arrival date/time")
    )

    datetime_of_departure = models.DateTimeField(
        null=False, blank=False, verbose_name=_("Departure date/time")
    )

    gross_tonnage = models.PositiveIntegerField(
        null=False,
        blank=False,
        verbose_name=_("Gross tonnage"),
    )

    vessel_type = models.CharField(
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

    def __str__(self) -> str:
        return (
            f"{self.vessel_name}, {self.port_of_call} "
            f"({self.datetime_of_arrival} - {self.datetime_of_departure})"
        )

    def _get_num_periods_in_duration(self, period: int) -> int:
        duration: timedelta = self.datetime_of_departure - self.datetime_of_arrival
        num: int = int(round(duration.total_seconds() / period))
        return num

    @property
    def duration_in_days(self) -> int:
        return self._get_num_periods_in_duration(24 * 60 * 60)

    @property
    def duration_in_weeks(self) -> int:
        # This assumes that we are counting the number of 7-day periods, rather than the
        # number of calendar weeks (e.g. 7-day periods starting on Monday or Sunday,
        # depending on the local convention.)
        return self._get_num_periods_in_duration(7 * 24 * 60 * 60)

    def calculate_tax(self, save: bool = True):
        self.calculate_harbour_tax(save=save)

    def calculate_harbour_tax(
        self, save: bool = True
    ) -> Dict[str, Decimal | List[dict]]:
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
                self.datetime_of_arrival,
                self.datetime_of_departure,
            )
            port_taxrate: PortTaxRate | None = taxrate.get_port_tax_rate(
                port=self.port_of_call,
                vessel_type=self.vessel_type,
                gross_ton=self.gross_tonnage,
            )
            range_port_tax = Decimal(0)
            if port_taxrate is not None:
                if self.vessel_type in (ShipType.FISHER, ShipType.OTHER):
                    payments = datetime_range.started_weeks
                else:
                    payments = datetime_range.started_days
                range_port_tax = payments * port_taxrate.port_tax_rate
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
            filename=f"{self.pk}.pdf",
            content=receipt.pdf,
            mimetype="application/pdf",
        )
        result = msg.send(fail_silently=False)
        return msg, result

    @property
    def mail_subject(self):
        # TODO: verify content
        # TODO: include data from object?
        return _("New harbor dues report")  # pragma: nocover

    @property
    def mail_body(self):
        return _(
            "On %(date)s, %(agent)s has reported harbor dues, cruise tax, and "
            "environmental and maintenance fees related to the entry of %(vessel)s "
            "in %(port)s"
        ) % {
            "date": localize(self.date),
            "agent": self.shipping_agent.name,
            "vessel": self.vessel_name,
            "port": self.port_of_call.name,
        }

    @property
    def mail_recipients(self) -> list[str]:
        recipients: list[str] = []

        if self.port_of_call.portauthority:
            recipients.append(self.port_of_call.portauthority.email)
        else:
            logger.info(
                "%r is not linked to a port authority, excluding from mail recipients",
                self,
            )

        if self.shipping_agent:
            recipients.append(self.shipping_agent.email)
        else:
            logger.info(
                "%r is not linked to a shipping agent, excluding from mail recipients",
                self,
            )

        if settings.EMAIL_ADDRESS_SKATTESTYRELSEN:
            recipients.append(settings.EMAIL_ADDRESS_SKATTESTYRELSEN)
        else:
            logger.info(
                "Skattestyrelsen email not configured, excluding from mail recipients",
            )

        return recipients


class CruiseTaxForm(HarborDuesForm):
    number_of_passengers = models.PositiveIntegerField(
        null=False,
        blank=False,
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

    def calculate_tax(self, save: bool = True):
        super().calculate_tax(save=save)  # calculates harbour tax
        self.calculate_passenger_tax(save=save)
        self.calculate_disembarkment_tax(save=save)

    def calculate_disembarkment_tax(self, save: bool = True):
        disembarkment_date = self.datetime_of_arrival
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

    def calculate_passenger_tax(self, save: bool = True) -> Dict[str, Decimal]:
        arrival_date = self.datetime_of_arrival
        taxrate = TaxRates.objects.filter(
            Q(start_datetime__isnull=True) | Q(start_datetime__lte=arrival_date),
            Q(end_datetime__isnull=True) | Q(end_datetime__gte=arrival_date),
        ).first()
        rate: Decimal = taxrate and taxrate.pax_tax_rate or Decimal(0)
        pax_tax: Decimal = self.number_of_passengers * rate
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


class PassengersByCountry(models.Model):
    class Meta:
        ordering = [
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


class DisembarkmentSite(models.Model):
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

    def __str__(self) -> str:
        return f"{self.name} ({self.get_municipality_display()})"


class Disembarkment(models.Model):
    class Meta:
        ordering = [
            "cruise_tax_form",
            "disembarkment_site__municipality",
            "disembarkment_site__name",
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


class TaxRates(models.Model):
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


post_save.connect(TaxRates.on_update, sender=TaxRates, dispatch_uid="TaxRates_update")


class PortTaxRate(models.Model):
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


class DisembarkmentTaxRate(models.Model):
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
