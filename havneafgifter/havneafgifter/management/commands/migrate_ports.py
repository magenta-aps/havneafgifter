from django.core.management.base import BaseCommand

from havneafgifter.models import Port


class Command(BaseCommand):

    localities = {
        960: {
            "avannaata kommunia fælles": 10700,
            "ilulissat": 10720,
            "oqaatsut": 10721,
            "qeqertaq": 10722,
            "saqqaq": 10723,
            "ilimanaq": 10724,
            "uummannaq": 10750,
            "niaqornat": 10751,
            "qaarsut": 10752,
            "ikerasak": 10753,
            "saattut": 10754,
            "ukkusissat": 10755,
            "illorsuit": 10756,
            "nuugaatsiaq": 10757,
            "upernavik": 10760,
            "upernavik kujalleq": 10761,
            "kangersuatsiaq": 10762,
            "aappilattoq": 10763,
            "tussaaq": 10764,
            "tasiusaq": 10765,
            "nuussuaq": 10766,
            "kullorsuaq": 10767,
            "naajaat": 10768,
            "innaarsuit": 10769,
            "qaanaaq": 10770,
            "savissivik": 10771,
            "uummannaq (dundas)": 10772,
            "qeqertarsuaq (bosted)": 10773,
            "siorapaluk": 10774,
            "moriusaq": 10776,
            "qeqertat": 10777,
            "nutaarmiut": 10779,
            "udenfor kommuneinddeling": 19000,
            "pituffik": 19078,
        },
        955: {
            "kommune kujalleq fælles": 10300,
            "aappilattoq": 10301,
            "narsarmijiit": 10301,
            "ammassivik": 10302,
            "qallumiut": 10302,
            "eqalugaarsuit": 10303,
            "igaliko": 10304,
            "illorpaat": 10305,
            "angisoq": 10306,
            "nalunaq": 10309,
            "nanortalik": 10310,
            "ikerasassuaq": 10311,
            "prins chr. sund": 10311,
            "aappilattoq v/ nanortalik": 10312,
            "narsaq kujalleq": 10313,
            "tasiusaq": 10314,
            "ammassivik/qallumiut": 10316,
            "alluitsoq": 10317,
            "alluitsup paa": 10318,
            "qallimiut": 10319,
            "qaqortoq": 10320,
            "saarloq": 10321,
            "eqalugaatsuit": 10322,
            "upernaviarsuk": 10323,
            "qassimiut": 10324,
            "simiutaq": 10325,
            "illorsuit": 10326,
            "tasilikulooq": 10327,
            "diverse fåreholdersteder": 10329,
            "narsaq": 10330,
            "igaliku kujalleq": 10331,
            "igaliku": 10332,
            "narsarsuaq": 10333,
            "qassiarsuk": 10335,
        },
        956: {
            "kommuneqarfik sermersooq fælles": 10400,
            "ivittuut": 10440,
            "kangilinnguit": 10441,
            "paamiut": 10450,
            "arsuk": 10451,
            "narsalik": 10453,
            "avigaat": 10456,
            "nuuk": 10460,
            "qeqertarsuatsiaat": 10461,
            "kangerluarsoruseq": 10462,
            "qoornoq": 10463,
            "kapisillit": 10465,
            "nuussuaq": 10469,
            "tasiilaq": 10480,
            "sermiligaaq": 10482,
            "isortoq / isertoq": 10483,
            "kulusuk": 10484,
            "tiniteqilaaq / tiilerilaaq": 10485,
            "kuummiut / kuummiit": 10486,
            "qernertuarsuit": 10488,
            "ikkatteq": 10489,
            "ittoqqortoormiit": 10490,
            "uun artoq": 10491,
            "ittaajimmiit": 10492,
            "nerlerit inaat": 10496,
        },
        957: {
            "qeqqata kommunia fælles": 10500,
            "maniitsoq": 10570,
            "atammik": 10571,
            "napasoq": 10572,
            "kangaamiut": 10573,
            "sisimiut": 10580,
            "itilleq": 10581,
            "kangerlussuaq": 10582,
            "sarfannguaq": 10583,
            "sarfannguit": 10583,
        },
        959: {
            "kommune qeqertalik fælles": 10600,
            "aasiaat": 10601,
            "akunnaaq": 10603,
            "kitsissuarsuit": 10604,
            "qasigiannguit": 10610,
            "ikamiut": 10611,
            "qeqertarsuaq": 10640,
            "kangerluk": 10643,
            "kangaatsiaq": 10690,
            "attu": 10692,
            "iginniarfik": 10695,
            "niaqornaarsuk": 10696,
            "ikerasarrsuk": 10698,
            "ikerasaarsuk": 10698,
        },
    }

    # Convert city names to locality names
    map = {"testby": "Nuuk"}

    def handle(self, *args, **options):
        for port in Port.objects.filter(prisme_code__isnull=True):
            placename = port.name.lower()
            for municipality, places in self.localities.items():
                if placename in places:
                    port.prisme_code = places[placename]
                    port.save()
                    break

            if port.prisme_code is not None:
                print(
                    f"Found locality for port {port.pk} "
                    f"directly by string match: {placename}"
                )
            else:
                print(f"Could not find locality for port " f"{port.pk} ({placename})")
        print(
            f"There are now "
            f"{Port.objects.filter(prisme_code__isnull=True).count()} "
            f"ports without locality set."
        )
