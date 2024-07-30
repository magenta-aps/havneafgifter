from typing import List

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import URLPattern, URLResolver, include, path
from django.views.i18n import JavaScriptCatalog
from django_mitid_auth.saml.views import MetadataView

urlpatterns: List[URLResolver | URLPattern] = [
    path("django-admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("select2/", include("django_select2.urls")),
    path(
        "",
        include(
            "havneafgifter.urls",
            namespace="havneafgifter",
        ),
    ),
    path("saml/", include("django_mitid_auth.urls", namespace="mitid")),
    path("saml2/metadata/", MetadataView.as_view(), name="saml_metadata_override"),
    path("metrics/", include("metrics.urls")),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="havneafgifter/user/password/reset_begin.html",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="havneafgifter/user/password/reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="havneafgifter/user/password/reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="havneafgifter/user/password/reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
if settings.MITID_TEST_ENABLED:
    urlpatterns.append(
        path("mitid_test/", include("mitid_test.urls", namespace="mitid_test"))
    )
