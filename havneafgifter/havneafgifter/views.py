from django.contrib import messages
from django.forms import formset_factory
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import CreateView, FormView

from .forms import HarborDuesFormForm, PassengersByCountryForm
from .models import (
    CruiseTaxForm,
    HarborDuesForm,
    Nationality,
    PassengersByCountry,
    ShipType,
)


class HarborDuesFormCreateView(CreateView):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def form_valid(self, form):
        harbor_dues_form = form.save(commit=False)
        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            cruise_tax_form = CruiseTaxForm.objects.create(
                **{
                    k: v
                    for k, v in harbor_dues_form.__dict__.items()
                    if not k.startswith("_")  # skip `_state`, etc.
                }
            )
            # Send user to next step - filling out passenger tax info
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:passenger_tax_create",
                    kwargs={"pk": cruise_tax_form.pk},
                )
            )
        else:
            # User is all done filling out data for this vessel
            harbor_dues_form.save()
            messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
            return reverse("havneafgifter:harbor_dues_form_create")


class PassengerTaxCreateView(FormView):
    template_name = "havneafgifter/passenger_tax_create.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self._cruise_tax_form = CruiseTaxForm.objects.get(pk=kwargs["pk"])

    def get_form(self, form_class=None):
        factory = formset_factory(
            PassengersByCountryForm,
            can_order=False,
            can_delete=False,
            extra=0,
        )
        return factory(**self.get_form_kwargs())

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = [
            {"nationality": nationality, "number_of_passengers": 0}
            for nationality in Nationality
        ]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["passengers_by_country_formset"] = self.get_form()
        return context_data

    def form_valid(self, form):
        passengers_by_country_objects = [
            PassengersByCountry(cruise_tax_form=self._cruise_tax_form, **cleaned_data)
            for cleaned_data in self.get_form().cleaned_data
            if cleaned_data["number_of_passengers"] > 0
        ]
        PassengersByCountry.objects.bulk_create(passengers_by_country_objects)

        self._cruise_tax_form.number_of_passengers = sum(
            pbc.number_of_passengers for pbc in passengers_by_country_objects
        )
        self._cruise_tax_form.save()

        # TOOD: go to next and final step (environmental dues form)
        return HttpResponseRedirect(
            reverse(
                "havneafgifter:passenger_tax_create",
                kwargs={"pk": self._cruise_tax_form.pk},
            )
        )
