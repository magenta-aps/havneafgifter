import os

from django.core.management import call_command
from django.core.management.base import BaseCommand

from havneafgifter.models import (
    DisembarkmentTaxRate,
    Port,
    PortAuthority,
    PortTaxRate,
    ShipType,
    TaxRates,
)


class Command(BaseCommand):
    def handle(self, *args, **options):
        print("loading fixtures")
        self.load_ports()
        self.load_disembarkment_sites()
        self.load_initial_rates()

    def load_ports(self):
        print("loading ports")
        for authority_name, authority_email in (
            ("Royal Arctic Line A/S", "ral@ral.gl"),
            ("KNI Pilersuisoq A/S", "info@kni.gl"),
            ("Mittarfeqarfiit", "mit@mit.gl"),
            ("Sikuki Harbour A/S", "sikuki@sikuki.gl"),
        ):
            port_authority, _ = PortAuthority.objects.get_or_create(
                name=authority_name, defaults={"email": authority_email}
            )

        for port_name, port_authority_name in (
            ("Qaanaaq", None),
            ("Upernavik", "Royal Arctic Line A/S"),
            ("Uummannaq", "Royal Arctic Line A/S"),
            ("Qeqertarsuaq", "KNI Pilersuisoq A/S"),
            ("Ilulissat", "Royal Arctic Line A/S"),
            ("Qasigiannguit", "Royal Arctic Line A/S"),
            ("Aasiaat", "Royal Arctic Line A/S"),
            ("Kangaatsiaq", "KNI Pilersuisoq A/S"),
            ("Sisimiut", "Royal Arctic Line A/S"),
            ("Kangerlussuaq", "Mittarfeqarfiit"),
            ("Maniitsoq", "Royal Arctic Line A/S"),
            ("Nuuk", "Sikuki Harbour A/S"),
            ("Paamiut", "Royal Arctic Line A/S"),
            ("Narsaq", "Royal Arctic Line A/S"),
            ("Narsarsuaq", "Mittarfeqarfiit"),
            ("Qaqortoq", "Royal Arctic Line A/S"),
            ("Nanortalik", "Royal Arctic Line A/S"),
            ("Tasiilaq", "Royal Arctic Line A/S"),
            ("Ittoqqortoormiit", "KNI Pilersuisoq A/S"),
        ):
            authority = (
                PortAuthority.objects.get(name=port_authority_name)
                if port_authority_name is not None
                else None
            )
            port, _ = Port.objects.get_or_create(
                name=port_name, defaults={"portauthority": authority}
            )
            print(f"{port.pk} loaded")
            # TODO: kobl på bruger eller gruppe
        print("ports were loaded")

    def load_rates(self):
        print("loading rates")
        if not TaxRates.objects.exists():
            tax_rates = TaxRates.objects.create(
                pax_tax_rate=0,
                start_date=None,
                end_date=None,
            )
            PortTaxRate.objects.create(
                tax_rates=tax_rates,
                port=None,
                vessel_type=None,
                gt_start=0,
                gt_end=None,
                port_tax_rate=70,
            )
            PortTaxRate.objects.create(
                tax_rates=tax_rates,
                port=None,
                vessel_type=ShipType.CRUISE,
                gt_start=0,
                gt_end=30_000,
                port_tax_rate=110,
            )
            PortTaxRate.objects.create(
                tax_rates=tax_rates,
                port=None,
                vessel_type=ShipType.CRUISE,
                gt_start=30_000,
                gt_end=None,
                port_tax_rate=220,
            )
            PortTaxRate.objects.create(
                tax_rates=tax_rates,
                port=Port.objects.get(name="Nuuk"),
                vessel_type=ShipType.CRUISE,
                gt_start=0,
                gt_end=30_000,
                port_tax_rate=0,
            )
            PortTaxRate.objects.create(
                tax_rates=tax_rates,
                port=Port.objects.get(name="Nuuk"),
                vessel_type=ShipType.CRUISE,
                gt_start=30_000,
                gt_end=None,
                port_tax_rate=110,
            )

        print("rates loaded")

    def load_disembarkment_sites(self):
        print("loading sites")
        # Load 73 disembarkment sites
        path = self._get_fixture_path("initial_disembarkment_sites.json")
        call_command("loaddata", path, verbosity=1)
        print("sites loaded")

    def load_initial_rates(self):

        print("loading initial rates")
        # Load initial data for TaxRates, PortTaxRate and DisembarkmentTaxRate
        path = self._get_fixture_path("initial_rates.json")
        nuuk = Port.objects.get(name="Nuuk")

        taxrates, _ = TaxRates.objects.get_or_create(
            pax_tax_rate="50.00",
            start_datetime="2020-01-01T03:00:00Z",
            end_datetime=None,
        )
        PortTaxRate.objects.get_or_create(
            tax_rates=taxrates,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate="0.70",
            round_gross_ton_up_to=70,
        )
        PortTaxRate.objects.get_or_create(
            tax_rates=taxrates,
            port=None,
            vessel_type="CRUISE",
            gt_start=0,
            gt_end=30000,
            port_tax_rate="1.10",
            round_gross_ton_up_to=70,
        )
        PortTaxRate.objects.get_or_create(
            tax_rates=taxrates,
            port=None,
            vessel_type="CRUISE",
            gt_start=30000,
            gt_end=None,
            port_tax_rate="2.20",
        )
        PortTaxRate.objects.get_or_create(
            tax_rates=taxrates,
            port=nuuk,
            vessel_type="CRUISE",
            gt_start=0,
            gt_end=30000,
            port_tax_rate="0.00",
            round_gross_ton_up_to=70,
        )
        PortTaxRate.objects.get_or_create(
            tax_rates=taxrates,
            port=nuuk,
            vessel_type="CRUISE",
            gt_start=30000,
            gt_end=None,
            port_tax_rate="1.10",
        )
        DisembarkmentTaxRate.objects.create(
            tax_rates=taxrates,
            disembarkment_site=None,
            municipality=960,
            disembarkment_tax_rate="50.00",
        )
        DisembarkmentTaxRate.objects.create(
            tax_rates=taxrates,
            disembarkment_site=None,
            municipality=959,
            disembarkment_tax_rate="25.00",
        )
        DisembarkmentTaxRate.objects.create(
            tax_rates=taxrates,
            disembarkment_site=None,
            municipality=957,
            disembarkment_tax_rate="50.00",
        )
        DisembarkmentTaxRate.objects.create(
            tax_rates=taxrates,
            disembarkment_site=None,
            municipality=955,
            disembarkment_tax_rate="50.00",
        )
        DisembarkmentTaxRate.objects.create(
            tax_rates=taxrates,
            disembarkment_site=None,
            municipality=956,
            disembarkment_tax_rate="50.00",
        )

        print("initial rates loaded")

    def _get_fixture_path(self, fixture_name: str) -> str:
        path: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../../fixtures",
            fixture_name,
        )
        return path
