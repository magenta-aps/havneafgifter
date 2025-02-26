from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import urlencode
from django.views.generic import FormView

from havneafgifter.mails import NotificationMail
from havneafgifter.models import CruiseTaxForm, HarborDuesForm, UserType


class HavneafgiftView:
    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "version": settings.VERSION,
                "contact_email": settings.CONTACT_EMAIL,
                "landing_modal": HavneafgiftView.landing_modal(self.request),
            }
        )

    def get_redirect_for_form(
        self,
        viewname: str,
        form: HarborDuesForm | CruiseTaxForm,
        **query,
    ):
        return HttpResponseRedirect(
            reverse(viewname, kwargs={"pk": form.pk})
            + (f"?{urlencode(query)}" if query else "")
        )

    @staticmethod
    def landing_modal(request):
        return (
            hasattr(request, "user")
            and hasattr(request, "session")
            and request.user.is_authenticated
            and request.user.user_type == UserType.PORT_AUTHORITY
            and not request.session.get("harbor_user_modal")
        )


class HandleNotificationMailMixin:
    def handle_notification_mail(
        self,
        mail_class: type[NotificationMail],
        form: HarborDuesForm | CruiseTaxForm,
    ):
        mail = mail_class(form, self.request.user)  # type: ignore
        result = mail.send_email()
        messages.add_message(
            self.request,  # type: ignore
            messages.SUCCESS if result.succeeded else messages.ERROR,
            (
                result.mail.success_message
                if result.succeeded
                else result.mail.error_message
            ),
        )


class GetFormView(FormView):
    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def get_form_kwargs(self):
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }
        if self.request.method in ("GET"):
            kwargs.update(
                {
                    "data": self.request.GET,
                    "files": self.request.FILES,
                }
            )
        return kwargs


class CacheControlMixin:
    def prevent_response_caching(self, response: HttpResponse) -> HttpResponse:
        # Ensure that when/if users go back to this view from the receipt page,
        # their browser does not show a cached response (which may present them with a
        # seemingly "editable" form that cannot be submitted if the form status is NEW.
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, post-check=0, pre-check=0"
        )
        return response
