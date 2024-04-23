from typing import List

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
]
