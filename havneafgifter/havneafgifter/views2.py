from django.forms import formset_factory
from django.http import HttpResponse
from django.views.generic import DetailView

from havneafgifter.forms import (
    DisembarkmentForm2,
    HarborDuesFormForm,
    PassengersByCountryForm2,
)
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    Nationality,
    PassengersByCountry,
)


class HarborDuesFormCreateView(DetailView):
    template_name = "havneafgifter/form_create.html"
    http_method_names = ["get", "post"]

    def get_object(self):
        return CruiseTaxForm.objects.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_form"] = self.get_base_form(instance=self.get_object())
        context["passenger_formset"] = self.get_passenger_formset(
            initial=self.get_passenger_formset_initial()
        )
        context["disembarkment_formset"] = self.get_disembarkment_formset(
            initial=self.get_disembarkment_formset_initial()
        )
        return context

    def get_base_form(self, **form_kwargs):
        return HarborDuesFormForm(self.request.user, prefix="base", **form_kwargs)

    def get_formset_factory(self, form_class):
        return formset_factory(form_class, can_order=False, can_delete=True, extra=1)

    def get_passenger_formset(self, **form_kwargs):
        factory = self.get_formset_factory(PassengersByCountryForm2)
        return factory(prefix="passengers", **form_kwargs)

    def get_disembarkment_formset(self, **form_kwargs):
        factory = self.get_formset_factory(DisembarkmentForm2)
        return factory(prefix="disembarkment", **form_kwargs)

    def get_passenger_formset_initial(self) -> list[dict]:
        return [
            {
                "pk": pbc.pk,
                "number_of_passengers": pbc.number_of_passengers,
                "nationality": Nationality(pbc.nationality),
            }
            for pbc in PassengersByCountry.objects.filter(
                cruise_tax_form=self.get_object(),
            )
        ]

    def get_disembarkment_formset_initial(self):
        return [
            {
                "pk": dis.pk,
                "number_of_passengers": dis.number_of_passengers,
                "disembarkment_site": dis.disembarkment_site,
            }
            for dis in Disembarkment.objects.filter(cruise_tax_form=self.get_object())
        ]

    def post(self, request, *args, **kwargs):
        debug = []

        base_form = self.get_base_form(
            instance=self.get_object(), data=self.request.POST
        )
        base_form.is_valid()
        debug.append(base_form.cleaned_data)

        passenger_formset = self.get_passenger_formset(
            initial=self.get_passenger_formset_initial(),
            data=self.request.POST,
        )
        if passenger_formset.is_valid():
            debug.append(passenger_formset.cleaned_data)
        else:
            raise ValueError(passenger_formset.errors)

        disembarkment_formset = self.get_disembarkment_formset(
            initial=self.get_disembarkment_formset_initial(),
            data=self.request.POST,
        )
        if disembarkment_formset.is_valid():
            debug.append(disembarkment_formset.cleaned_data)
        else:
            raise ValueError(disembarkment_formset.errors)

        return HttpResponse(str(debug), content_type="text/base")
