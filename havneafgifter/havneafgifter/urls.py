from typing import List

from django.urls import URLPattern, URLResolver, path
from django.views.generic import TemplateView

from havneafgifter.views import (
    EnvironmentalTaxCreateView,
    HarborDuesFormCreateView,
    LoginView,
    LogoutView,
    PassengerTaxCreateView,
    PreviewPDFView,
    ReceiptDetailView,
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
        "blanket/<int:pk>/",
        ReceiptDetailView.as_view(),
        name="receipt_detail_html",
    ),
    path(
        "blanket/pdf/<int:pk>/",
        PreviewPDFView.as_view(),
        name="receipt_detail_pdf",
    ),
]
