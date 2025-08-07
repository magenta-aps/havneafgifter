from typing import List

from django.urls import URLPattern, URLResolver, path
from django.views.generic import TemplateView
from django_mitid_auth.saml.views import AccessDeniedView

from havneafgifter.views import (
    ApproveView,
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
    RejectView,
    RootView,
    SignupVesselView,
    StatisticsView,
    TaxRateDetailView,
    TaxRateFormView,
    TaxRateListView,
    UpdateVesselView,
    WithdrawView,
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
        "error/login-timeout/",
        AccessDeniedView.as_view(
            template_name="havneafgifter/error/login_timeout.html"
        ),
        name="login-timeout",
    ),
    path(
        "error/login-repeat/",
        AccessDeniedView.as_view(template_name="havneafgifter/error/login_repeat.html"),
        name="login-repeat",
    ),
    path(
        "error/login-nocpr/",
        AccessDeniedView.as_view(template_name="havneafgifter/error/login_no_cpr.html"),
        name="login-no-cpr",
    ),
    path(
        "error/login-failed/",
        AccessDeniedView.as_view(template_name="havneafgifter/error/login_failed.html"),
        name="login-failed",
    ),
    path(
        "error/login_assurance/",
        AccessDeniedView.as_view(
            template_name="havneafgifter/error/login_assurance.html"
        ),
        name="login-assurance-level",
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
        "blanket/<int:pk>/tilbagetraek/",
        WithdrawView.as_view(),
        name="withdraw",
    ),
    path(
        "blanket/<int:pk>/godkend/",
        ApproveView.as_view(),
        name="approve",
    ),
    path(
        "blanket/<int:pk>/afvis/",
        RejectView.as_view(),
        name="reject",
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
