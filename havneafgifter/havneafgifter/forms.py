from django.core.exceptions import ValidationError
from django.forms import ChoiceField, Form, IntegerField, ModelForm, widgets
from django.utils.translation import gettext_lazy as _

from .models import DisembarkmentSite, HarborDuesForm, Nationality


class HTML5DateWidget(widgets.Input):
    input_type = "date"
    template_name = "django/forms/widgets/date.html"


class HarborDuesFormForm(ModelForm):
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
            "date_of_arrival",
            "date_of_departure",
            "gross_tonnage",
            "vessel_type",
        ]
        localized_fields = [
            "date_of_arrival",
            "date_of_departure",
        ]
        widgets = {
            "date_of_arrival": HTML5DateWidget(),
            "date_of_departure": HTML5DateWidget(),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_of_arrival = cleaned_data.get("date_of_arrival")
        date_of_departure = cleaned_data.get("date_of_departure")
        if date_of_arrival > date_of_departure:
            raise ValidationError(
                _("Date of departure cannot be before date of arrival"),
                code="date_of_departure_before_date_of_arrival",
            )


class PassengersByCountryForm(Form):
    nationality = ChoiceField(choices=Nationality, disabled=True)
    number_of_passengers = IntegerField()


class DisembarkmentForm(Form):
    disembarkment_site = ChoiceField(choices=[], disabled=True)
    number_of_passengers = IntegerField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["disembarkment_site"].choices = [
            (ds.pk, str(ds)) for ds in DisembarkmentSite.objects.all()
        ]

    def clean_disembarkment_site(self):
        disembarkment_site = self.cleaned_data.get("disembarkment_site")
        if isinstance(disembarkment_site, DisembarkmentSite):
            return disembarkment_site
        return DisembarkmentSite.objects.get(pk=disembarkment_site)