from typing import List

import djangosaml2
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: List[URLResolver | URLPattern] = [
    path("django-admin/", admin.site.urls),
    path(
        "havneafgifter/",
        include(
            "havneafgifter.urls",
            namespace="havneafgifter",
        ),
    ),
    path("saml2/", include("djangosaml2.urls")),
]
