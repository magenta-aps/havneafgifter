from typing import List

from django.urls import URLPattern, URLResolver, path

from .views import (
    CruiseTaxFormDetailView,
    EnvironmentalTaxCreateView,
    HarborDuesFormCreateView,
    HarborDuesFormDetailView,
    PassengerTaxCreateView,
)

app_name = "havneafgifter"

urlpatterns: List[URLResolver | URLPattern] = [
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
