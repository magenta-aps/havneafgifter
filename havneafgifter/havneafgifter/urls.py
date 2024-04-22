from typing import List

from django.urls import URLPattern, URLResolver, path
from .views import HarborDuesFormCreateView


app_name = "havneafgifter"

urlpatterns: List[URLResolver | URLPattern] = [
    path(
        "blanket/opret/",
        HarborDuesFormCreateView.as_view(),
        name="harbor_dues_form_create",
    ),
]
