from typing import List

from django.urls import URLPattern, URLResolver, path
from django.views.generic import TemplateView

from havneafgifter.views import (
    HarborDuesFormCreateView,
    HarborDuesFormDeleteView,
    HarborDuesFormListView,
    LandingModalOkView,
    LoginView,
    LogoutView,
    PassengerStatisticsView,
    PostLoginView,
    PreviewPDFView,
    ReceiptDetailView,
    RootView,
    SignupVesselView,
    StatisticsView,
    TaxRateDetailView,
    TaxRateFormView,
    TaxRateListView,
    UpdateVesselView,
)

app_name = "havneafgifter"

urlpatterns: List[URLResolver | URLPattern] = [
    path("", RootView.as_view(), name="root"),
    path(
        "signup/vessel",
        SignupVesselView.as_view(),
        name="signup-vessel",
    ),
    path(
        "rediger/vessel",
        UpdateVesselView.as_view(),
        name="update_vessel",
    ),
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
        "post_login",
        PostLoginView.as_view(),
        name="post_login",
    ),
    path(
        "error/login-failed/",
        TemplateView.as_view(template_name="havneafgifter/error/login_failed.html"),
        name="login-failed",
    ),
    path(
        "blanket/opret/",
        HarborDuesFormCreateView.as_view(),
        name="harbor_dues_form_create",
    ),
    path(
        "blanket/rediger/<int:pk>/",
        HarborDuesFormCreateView.as_view(),
        name="harbor_dues_form_edit",
    ),
    path(
        "blanket/",
        HarborDuesFormListView.as_view(),
        name="harbor_dues_form_list",
    ),
    path(
        "blanket/<int:pk>/",
        ReceiptDetailView.as_view(),
        name="receipt_detail_html",
    ),
    path(
        "blanket/<int:pk>/slet/",
        HarborDuesFormDeleteView.as_view(),
        name="delete",
    ),
    path(
        "blanket/pdf/<int:pk>/",
        PreviewPDFView.as_view(),
        name="receipt_detail_pdf",
    ),
    path("blanket/statistik/", StatisticsView.as_view(), name="statistik"),
    path("sats/", TaxRateListView.as_view(), name="tax_rate_list"),
    path("sats/<int:pk>/", TaxRateDetailView.as_view(), name="tax_rate_details"),
    path("sats/<int:pk>/edit/", TaxRateFormView.as_view(), name="edit_taxrate"),
    path(
        "sats/<int:pk>/clone/",
        TaxRateFormView.as_view(clone=True),
        name="tax_rate_clone",
    ),
    path("modal/ok", LandingModalOkView.as_view(), name="landing_modal_ok"),
    path(
        "statistik/passagerer/",
        PassengerStatisticsView.as_view(),
        name="passenger_statistics",
    ),
]
