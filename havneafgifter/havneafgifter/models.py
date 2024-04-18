from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django.utils.translation import gettext as _


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
    # https://en.wikipedia.org/wiki/IMO_number
    if sum([int(value[i]) * (7 - i) for i in range(0, 6)]) != int(value[6]):
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

    class ShipType(models.TextChoices):
        FREIGHTER = "FREIGHTER", _("Freighter")
        FISHER = "FISHER", _("Fishing ship")
        PASSENGER = "PASSENGER", _("Passenger ship")
        CRUISE = "CRUISE", _("Cruise ship")

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


class PassengersByCountry(models.Model):
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
    class Municipality(models.IntegerChoices):
        KUJALLEQ = 955, "Kujalleq"
        QAASUITSUP = 958, "Qaasuitsup"
        QEQQATA = 957, "Qeqqata"
        SERMERSOOQ = 956, "Sermersooq"
        QEQERTALIK = 959, "Qeqertalik"
        AVANNAATA = 960, "Avannaata"
        NATIONAL_PARK = 961, _("Northeast Greenland National Park")

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
