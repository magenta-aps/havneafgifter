# SPDX-FileCopyrightText: 2026 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
from django.urls import reverse_lazy
from project.settings.base import DEBUG

AUTHENTICATION_BACKENDS = [
    "havneafgifter.permissions.HavneafgiftPermissionBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation"
        ".UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
AUTH_USER_MODEL = "havneafgifter.User"


SESSION_COOKIE_SECURE = not DEBUG
if not DEBUG:
    SESSION_COOKIE_SAMESITE = "None"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

LOGIN_REDIRECT_URL = reverse_lazy("havneafgifter:post_login")
LOGIN_URL = reverse_lazy("havneafgifter:login")
LOGOUT_REDIRECT_URL = reverse_lazy("havneafgifter:logged_out")
