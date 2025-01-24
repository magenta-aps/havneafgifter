from csp_helpers.mixins import CSPViewMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import formset_factory
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django_fsm import can_proceed, has_transition_perm

from havneafgifter.forms import (
    DisembarkmentForm2,
    HarborDuesFormForm,
    PassengersByCountryForm2,
    PassengersTotalForm,
)
from havneafgifter.mails import OnSubmitForReviewMail
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    HarborDuesForm,
    Nationality,
    PassengersByCountry,
    ShipType,
    Status,
)
from havneafgifter.responses import HavneafgifterResponseForbidden
from havneafgifter.view_mixins import HandleNotificationMailMixin, HavneafgiftView


class HarborDuesFormCreateView(
    LoginRequiredMixin,
    CSPViewMixin,
    HandleNotificationMailMixin,
    HavneafgiftView,
    DetailView,
):
    template_name = "havneafgifter/form_create.html"
    http_method_names = ["get", "post"]

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        self.object = None

        if pk:
            try:
                self.object = CruiseTaxForm.objects.get(pk=pk)
            except CruiseTaxForm.DoesNotExist:
                try:
                    self.object = HarborDuesForm.objects.get(pk=pk)
                except HarborDuesForm.DoesNotExist:
                    return self.object
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_form"] = self.get_base_form(instance=self.get_object())
        context["passenger_formset"] = self.get_passenger_formset(
            initial=self.get_passenger_formset_initial()
        )
        context["disembarkment_formset"] = self.get_disembarkment_formset(
            initial=self.get_disembarkment_formset_initial()
        )

        if isinstance(self.object, CruiseTaxForm):
            total_num = self.object.number_of_passengers
        else:
            total_num = 0

        context["passenger_total_form"] = self.get_passenger_total_form(
            initial={"total_number_of_passengers": total_num}
        )

        return context

    def form_valid(self, form):
        harbor_dues_form = form.save(commit=False)

        if can_proceed(harbor_dues_form.submit_for_review) and not has_transition_perm(
            harbor_dues_form.submit_for_review,
            self.request.user,
        ):
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions to submit "
                    "harbor dues forms for review"
                ),
            )

        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            self.object = self._create_or_update_cruise_tax_form(harbor_dues_form)

        else:
            self.object = harbor_dues_form.save()

        status = form.cleaned_data.get("status")

        if status == Status.NEW:
            self.object.submit_for_review()
            self.object.save()
            self.handle_notification_mail(OnSubmitForReviewMail, self.object)
        else:
            self.object.save()

        # Go to detail view to display result.
        return self.get_redirect_for_form(
            "havneafgifter:receipt_detail_html",
            self.object,
        )

    def _create_or_update_cruise_tax_form(
        self, harbor_dues_form: HarborDuesForm
    ) -> CruiseTaxForm:
        field_vals = {
            k: v
            for k, v in harbor_dues_form.__dict__.items()
            if not k.startswith("_")  # skip `_state`, etc.
        }

        if harbor_dues_form.pk is None:
            # The `HarborDuesForm` has not yet been saved to the database.
            # If we create the corresponding `CruiseTaxForm`, the corresponding
            # `HarborDuesForm` will be created automatically.
            return CruiseTaxForm.objects.create(**field_vals)
        else:
            # A `CruiseTaxForm` object may already exist for this PK.
            try:
                cruise_tax_form = CruiseTaxForm.objects.get(
                    harborduesform_ptr=harbor_dues_form.pk
                )
            except CruiseTaxForm.DoesNotExist:
                # A `CruiseTaxForm` does not exist, but the user is trying to save a
                # cruise tax form, i.e. they are editing a harbor dues form and have
                # changed the vessel type to `CRUISE`. Create the corresponding
                # `CruiseTaxForm`.
                return CruiseTaxForm.objects.create(
                    harborduesform_ptr=harbor_dues_form,
                    # Copy all fields from `HarborDuesForm` except `status`
                    **{
                        k: v
                        for k, v in field_vals.items()
                        if k not in ("harborduesform_ptr", "status")
                    },
                )
            else:
                # A `CruiseTaxForm` exists for this PK.
                # Update all its fields, except `status`.
                for k, v in field_vals.items():
                    if k == "status":
                        continue
                    setattr(cruise_tax_form, k, v)
                cruise_tax_form.save()
                return cruise_tax_form

    def get_base_form(self, **form_kwargs):
        return HarborDuesFormForm(self.request.user, prefix="base", **form_kwargs)

    def get_passenger_total_form(self, **form_kwargs):
        return PassengersTotalForm(prefix="passenger_total_form", **form_kwargs)

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
        base_form = self.get_base_form(
            instance=self.get_object(), data=self.request.POST
        )

        passenger_total_form = self.get_passenger_total_form(data=self.request.POST)

        passenger_formset = self.get_passenger_formset(
            initial=self.get_passenger_formset_initial(),
            data=self.request.POST,
        )

        disembarkment_formset = self.get_disembarkment_formset(
            initial=self.get_disembarkment_formset_initial(),
            data=self.request.POST,
        )

        if passenger_formset.is_valid() and len(passenger_formset.cleaned_data) > 0:
            actual_total = 0
            for item in self._get_passengers_by_country_objects(passenger_formset):
                actual_total += item.number_of_passengers

            passenger_total_form.is_valid()
            passenger_total_form.validate_total(actual_total)

            if not passenger_total_form.is_valid():
                return self.render_to_response(
                    context={
                        "base_form": base_form,
                        "passenger_total_form": passenger_total_form,
                        "passenger_formset": passenger_formset,
                        "disembarkment_formset": disembarkment_formset,
                    }
                )

        if (
            base_form.is_valid()
            and passenger_formset.is_valid()
            and disembarkment_formset.is_valid()
        ):
            response = self.form_valid(base_form)

            # Create or update `PassengersByCountry` objects based on formset data
            passengers_by_country_objects = self._get_passengers_by_country_objects(
                passenger_formset
            )

            PassengersByCountry.objects.bulk_create(
                passengers_by_country_objects,
                update_conflicts=True,
                unique_fields=["cruise_tax_form", "nationality"],
                update_fields=["number_of_passengers"],
            )

            # Remove any `PassengersByCountry` objects which have 0 passengers after the
            # "create or update" processing above.
            PassengersByCountry.objects.filter(
                cruise_tax_form=self.object,
                number_of_passengers=0,
            ).delete()

            # Create or update `Disembarkment` objects based on formset data
            disembarkment_objects = self._get_disembarkment_objects(
                disembarkment_formset
            )
            Disembarkment.objects.bulk_create(
                disembarkment_objects,
                update_conflicts=True,
                unique_fields=["cruise_tax_form", "disembarkment_site"],
                update_fields=["number_of_passengers"],
            )

            # Remove any `Disembarkment` objects which have 0 passengers after the
            # "create or update" processing above.
            Disembarkment.objects.filter(
                cruise_tax_form=self.object,
                number_of_passengers=0,
            ).delete()

            return response

        else:
            return self.render_to_response(
                context={
                    "base_form": base_form,
                    "passenger_total_form": passenger_total_form,
                    "passenger_formset": passenger_formset,
                    "disembarkment_formset": disembarkment_formset,
                }
            )

    def _get_passengers_by_country_objects(self, formset) -> list[PassengersByCountry]:
        return [
            PassengersByCountry(
                cruise_tax_form=self.object,
                nationality=cleaned_data["nationality"],
                number_of_passengers=cleaned_data["number_of_passengers"],
            )
            for cleaned_data in formset.cleaned_data  # type: ignore
            if not cleaned_data.get("DELETE")
        ]

    def _get_disembarkment_objects(self, formset) -> list[Disembarkment]:
        return [
            Disembarkment(
                cruise_tax_form=self.object,
                number_of_passengers=cleaned_data["number_of_passengers"],
                disembarkment_site=cleaned_data["disembarkment_site"],
            )
            for cleaned_data in formset.cleaned_data  # type: ignore
            if cleaned_data != {} and not cleaned_data.get("DELETE")
        ]
