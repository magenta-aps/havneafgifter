from typing import List

from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: List[URLResolver | URLPattern] = [
    path("django-admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("select2/", include("django_select2.urls")),
    path(
        "havneafgifter/",
        include(
            "havneafgifter.urls",
            namespace="havneafgifter",
        ),
    ),
    path("saml2/", include("djangosaml2.urls")),
]
