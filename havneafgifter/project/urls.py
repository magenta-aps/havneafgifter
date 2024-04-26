from typing import List

from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from django.views.generic import TemplateView
from django_mitid_auth.saml.views import AccessDeniedView

urlpatterns: List[URLResolver | URLPattern] = [
    path("django-admin/", admin.site.urls),
    path(
        "havneafgifter/",
        include(
            "havneafgifter.urls",
            namespace="havneafgifter",
        ),
    ),
    path("", include("django_mitid_auth.urls", namespace=settings.LOGIN_NAMESPACE)),
    path(
        "error/login-timeout/",
        AccessDeniedView.as_view(template_name="havneafgifter/error/login_timeout.html"),
        name="login-timeout",
    ),
    path(
        "error/login-repeat/",
        AccessDeniedView.as_view(template_name="havneafgifter/error/login_repeat.html"),
        name="login-repeat",
    ),
    path(
        "logged-out/",
        TemplateView.as_view(template_name="havneafgifter/loggedout.html"),
        name="logged-out",
    ),

]
