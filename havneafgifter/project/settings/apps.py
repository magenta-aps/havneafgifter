# SPDX-FileCopyrightText: 2026 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
from project.settings.base import TESTING

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bootstrap5",
    "django_tables2",
    "havneafgifter",
    "django_select2",
    "django_filters",
    "csp",
    "csp_helpers",
    "metrics",
    "tempus_dominus",
    "simple_history",
    "django_extensions",
    "compressor",
]
if not TESTING:
    INSTALLED_APPS.append("debug_toolbar")
