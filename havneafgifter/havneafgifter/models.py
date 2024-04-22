from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List

from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import F, Q
from django.db.models.signals import post_save
from django.utils.translation import gettext as _

from havneafgifter.data import DateRange


class ShipType(models.TextChoices):
    FREIGHTER = "FREIGHTER", _("Freighter")
    FISHER = "FISHER", _("Fishing ship")
    PASSENGER = "PASSENGER", _("Passenger ship")
    CRUISE = "CRUISE", _("Cruise ship")


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


def imo_validator(value: str):
    if len(value) != 7:
        raise ValidationError("IMO has incorrect length (must be 7 digits)")
    if not re.match(r"\d{7}", value):
        raise ValidationError("IMO has incorrect content (must be 7 digits)")
    # https://en.wikipedia.org/wiki/IMO_number
    if sum([int(value[i]) * (7 - i) for i in range(0, 6)]) % 10 != int(value[6]):
        raise ValidationError("IMO Check failed")


class PortAuthority(models.Model):
    name = models.CharField(
        max_length=32,
        null=False,
        blank=False,
        verbose_name=_("Port authority company name"),
    )
    email = models.EmailField(
        null=False, blank=False, verbose_name=_("Port authority contact email")
    )


class Port(models.Model):
    name = models.CharField(
        max_length=16, null=False, blank=False, verbose_name=_("Port name")
    )
    portauthority = models.ForeignKey(
        PortAuthority, null=True, blank=True, on_delete=models.SET_NULL
    )


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

    date_of_arrival = models.DateField(
        null=False, blank=False, verbose_name=_("Arrival date")
    )

    date_of_departure = models.DateField(
        null=False, blank=False, verbose_name=_("Departure date")
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

    def calculate_harbour_tax(
        self, save: bool = True
    ) -> Dict[str, Decimal | List[dict]]:
        taxrates = TaxRates.objects.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=self.date_of_departure),
            Q(end_date__isnull=True) | Q(end_date__gte=self.date_of_arrival),
        )
        harbour_tax = Decimal(0)
        details = []
        for taxrate in taxrates:
            date_range = taxrate.get_overlap(
                self.date_of_arrival,
                # Afrejsedagen er inkluderet i range.
                # TaxRates beregner overlap af datoer fra midnat til midnat,
                # så for at beregne korrekt overlap skal vi frem til den
                # efterfølgende midnat for afrejsen
                self.date_of_departure + timedelta(days=1),
            )
            port_taxrate: PortTaxRate | None = taxrate.get_port_tax_rate(
                port=self.port_of_call,
                vessel_type=self.vessel_type,
                gross_ton=self.gross_tonnage,
            )
            range_port_tax = Decimal(0)
            if port_taxrate is not None:
                range_port_tax = date_range.days * port_taxrate.port_tax_rate
                harbour_tax += range_port_tax
            details.append(
                {
                    "port_taxrate": port_taxrate,
                    "date_range": date_range,
                    "harbour_tax": range_port_tax,
                }
            )
        if save:
            self.harbour_tax = harbour_tax
            self.save(update_fields=("harbour_tax",))
        return {"harbour_tax": harbour_tax, "details": details}


class CruiseTaxForm(HarborDuesForm):
    number_of_passengers = models.PositiveIntegerField(
        null=True,
        blank=True,
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

    def calculate_disembarkment_tax(self, save: bool = True):
        disembarkment_date = self.date_of_arrival
        taxrate = TaxRates.objects.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=disembarkment_date),
            Q(end_date__isnull=True) | Q(end_date__gte=disembarkment_date),
        ).first()
        disembarkment_tax = Decimal(0)
        details = []
        for disembarkment in self.disembarkment_set.all():
            disembarkment_site = disembarkment.disembarkment_site
            disembarkment_tax_rate: DisembarkmentTaxRate | None = (
                (
                    taxrate.disembarkment_tax_rates.filter(
                        municipality=disembarkment_site.municipality
                    ).first()
                )
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


class PassengersByCountry(models.Model):
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
    name = models.CharField(
        max_length=100,
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


class Disembarkment(models.Model):
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
        ordering = [F("start_date").asc(nulls_first=True)]

    pax_tax_rate = models.DecimalField(
        null=True,
        blank=True,
        decimal_places=2,
        max_digits=6,
        verbose_name=_("Tax per passenger"),
    )

    start_date = models.DateField(
        null=True, blank=True, verbose_name=_("First day of taking effect")
    )

    end_date = models.DateField(
        null=True, blank=True, verbose_name=_("First day of no longer taking effect")
    )

    @property
    def last_date(self) -> date | None:
        if self.end_date is None:
            return None
        last_date = self.end_date - timedelta(days=1)
        if self.start_date is not None and self.start_date > last_date:
            return self.start_date
        return last_date

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

    def get_overlap(self, rangestart: date, rangeend: date) -> DateRange:
        if self.end_date is not None and self.end_date < rangeend:
            rangeend = self.end_date
        if self.start_date is not None and self.start_date > rangestart:
            rangestart = self.start_date
        return DateRange(rangestart, rangeend)

    def save(self, *args, **kwargs):
        super().full_clean()
        super().save(*args, **kwargs)

    @staticmethod
    def on_update(sender, instance: TaxRates, **kwargs):
        # En TaxRates-tabel har (måske) fået ændret sin `start_date`
        # Opdatér `end_date` på alle tabeller som er påvirkede
        # (tidl. prev, ny prev, tabellen selv)
        # Det er nemmest og sikrest at loope over hele banden,
        # så vi er sikre på at ramme alle
        update_fields = kwargs.get("update_fields")
        if not update_fields or "start_date" in update_fields:
            end_date = None
            for item in TaxRates.objects.all().order_by(
                F("start_date").desc(nulls_last=True)
            ):
                # Loop over alle tabeller fra sidste til første
                # (reverse af default ordering)
                if item.end_date != end_date:
                    item.end_date = end_date
                    # Sæt kun `end_date`, så vi forhindrer rekursion
                    item.save(update_fields=("end_date",))
                end_date = item.start_date


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
    tax_rates = models.ForeignKey(
        TaxRates,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="disembarkment_tax_rates",
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
