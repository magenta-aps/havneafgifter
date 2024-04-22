from django.contrib import messages
from django.urls import reverse
from django.views.generic.edit import CreateView
from django.utils.translation import gettext_lazy as _

from .forms import HarborDuesFormForm
from .models import HarborDuesForm


class HarborDuesFormCreateView(CreateView):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def get_success_url(self):
        messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
        return reverse("havneafgifter:harbor_dues_form_create")
