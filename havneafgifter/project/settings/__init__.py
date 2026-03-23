# SPDX-FileCopyrightText: 2026 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from split_settings.tools import include

include(
    "base.py",
    "apps.py",
    "middleware.py",
    "database.py",
    "templates.py",
    "locale.py",
    "logging.py",
    "login.py",
    "cache.py",
    "staticfiles.py",
    "bootstrap5.py",
    "csp.py",
    "email.py",
    "prisme.py",
    "tempus_dominus.py",
)
