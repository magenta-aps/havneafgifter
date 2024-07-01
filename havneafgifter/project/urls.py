from typing import List

from django.conf import settings
from django.contrib import admin
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
]
if settings.MITID_TEST_ENABLED:
    urlpatterns.append(
        path("mitid_test/", include("mitid_test.urls", namespace="mitid_test"))
    )
