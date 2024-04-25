from typing import List

from django.urls import URLPattern, URLResolver, path
from django.views.generic import TemplateView

from havneafgifter.views import (
    CruiseTaxFormDetailView,
    EnvironmentalTaxCreateView,
    HarborDuesFormCreateView,
    HarborDuesFormDetailView,
    LoginView,
    LogoutView,
    PassengerTaxCreateView,
)

app_name = "havneafgifter"

urlpatterns: List[URLResolver | URLPattern] = [
    path(
        "login",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "logout",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "logged_out",
        TemplateView.as_view(template_name="havneafgifter/logged_out.html"),
        name="logged_out",
    ),
    path(
        "blanket/opret/",
        HarborDuesFormCreateView.as_view(),
        name="harbor_dues_form_create",
    ),
    path(
        "blanket/<int:pk>/",
        HarborDuesFormDetailView.as_view(),
        name="harbor_dues_form_detail",
    ),
    path(
        "blanket/opret/passagerer/<int:pk>/",
        PassengerTaxCreateView.as_view(),
        name="passenger_tax_create",
    ),
    path(
        "blanket/opret/miljoe/<int:pk>/",
        EnvironmentalTaxCreateView.as_view(),
        name="environmental_tax_create",
    ),
    path(
        "blanket/krydstogt/<int:pk>/",
        CruiseTaxFormDetailView.as_view(),
        name="cruise_tax_form_detail",
    ),
]
