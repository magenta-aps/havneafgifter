from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.forms import formset_factory
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, FormView

from havneafgifter.forms import (
    AuthenticationForm,
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersByCountryForm,
)

from .models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    HarborDuesForm,
    Nationality,
    PassengersByCountry,
    ShipType,
)


class HavneafgiftView:
    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "version": settings.VERSION,
            }
        )


class LoginView(HavneafgiftView, DjangoLoginView):
    template_name = "havneafgifter/login.html"
    form_class = AuthenticationForm


class LogoutView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if self.request.COOKIES.get(settings.SAML_SESSION_COOKIE_NAME):
            # Logged in with saml2, redirect to saml2 logout
            return reverse("saml2_logout")
        else:
            # Redirect to django logout
            return reverse("logout")


class HarborDuesFormCreateView(HavneafgiftView, CreateView):
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
            # Go to detail view to display result.
            harbor_dues_form.save()
            messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:harbor_dues_form_detail",
                    kwargs={"pk": harbor_dues_form.pk},
                )
            )


class _CruiseTaxFormSetView(HavneafgiftView, FormView):
    """Shared base class for views that create a set of model objects related
    to a `CruiseTaxForm`, e.g. `PassengersByCountry` or `Disembarkment`.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self._cruise_tax_form = CruiseTaxForm.objects.get(pk=kwargs["pk"])

    def get_form(self, form_class=None):
        factory = formset_factory(
            self.form_class,
            can_order=False,
            can_delete=False,
            extra=0,
        )
        return factory(**self.get_form_kwargs())


class PassengerTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/passenger_tax_create.html"
    form_class = PassengersByCountryForm

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

        # Go to next step (environmental and maintenance fees)
        return HttpResponseRedirect(
            reverse(
                "havneafgifter:environmental_tax_create",
                kwargs={"pk": self._cruise_tax_form.pk},
            )
        )


class EnvironmentalTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/environmental_tax_create.html"
    form_class = DisembarkmentForm

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = [
            {"disembarkment_site": disembarkment_site.pk, "number_of_passengers": 0}
            for disembarkment_site in DisembarkmentSite.objects.all()
        ]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["disembarkment_formset"] = self.get_form()
        return context_data

    def form_valid(self, form):
        disembarkment_objects = [
            Disembarkment(cruise_tax_form=self._cruise_tax_form, **cleaned_data)
            for cleaned_data in self.get_form().cleaned_data
            if cleaned_data["number_of_passengers"] > 0
        ]
        Disembarkment.objects.bulk_create(disembarkment_objects)

        # User is all done filling out data for cruise ship.
        # Go to detail view to display result.
        messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
        return HttpResponseRedirect(
            reverse(
                "havneafgifter:cruise_tax_form_detail",
                kwargs={"pk": self._cruise_tax_form.pk},
            )
        )


class HarborDuesFormDetailView(HavneafgiftView, DetailView):
    model = HarborDuesForm


class CruiseTaxFormDetailView(HavneafgiftView, DetailView):
    model = CruiseTaxForm
