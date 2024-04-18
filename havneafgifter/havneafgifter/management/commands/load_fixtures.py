from django.core.management.base import BaseCommand

from havneafgifter.models import Port, PortAuthority


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.load_ports()

    def load_ports(self):
        for authority_name, authority_email in (
            ("Royal Arctic Line A/S", "ral@ral.gl"),
            ("KNI Pilersuisoq A/S", "info@kni.gl"),
            ("Mittarfeqarfiit", "mit@mit.gl"),
            ("Sikuki Harbour A/S", "sikuki@sikuki.gl"),
        ):
            PortAuthority.objects.get_or_create(
                name=authority_name, defaults={"email": authority_email}
            )
        for port_name, port_authority_name in (
            ("Qaanaaq", None),
            ("Upernavik", "Royal Arctic Line A/S"),
            ("Uummannaq", "Royal Arctic Line A/S"),
            ("Qeqertarsuaq", "KNI Pilersuisoq A/S"),
            ("Ilulissat", "Royal Arctic Line A/S"),
            ("Qasigiannguit", "Royal Arctic Line A/S"),
            ("Aasiaat ", "Royal Arctic Line A/S"),
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
            Port.objects.get_or_create(
                name=port_name, defaults={"portauthority": authority}
            )
