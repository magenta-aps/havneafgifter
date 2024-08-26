from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.template.response import TemplateResponse


class MessageTemplateMixin(TemplateResponse):
    """Render an error response using the template specified via `template_name`."""

    message_context_var_name: str = "exception"

    def __init__(self, request: HttpRequest, message: str, *args, **kwargs):
        super().__init__(request, self.template_name, *args, **kwargs)
        self.context_data = {self.message_context_var_name: message}


class HavneafgifterResponseBadRequest(MessageTemplateMixin, HttpResponseBadRequest):
    template_name = "400.html"


class HavneafgifterResponseForbidden(MessageTemplateMixin, HttpResponseForbidden):
    template_name = "403.html"


class HavneafgifterResponseNotFound(MessageTemplateMixin, HttpResponseNotFound):
    template_name = "404.html"
