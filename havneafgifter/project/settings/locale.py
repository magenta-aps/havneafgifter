# SPDX-FileCopyrightText: 2026 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import os

import django.conf.locale

LANGUAGE_CODE = "en-US"
LANGUAGES = [
    ("en", "English"),
    ("kl", "Kalaallisut"),
    ("da", "Dansk"),
]
EXTRA_LANG_INFO = {
    "kl": {
        "code": "kl",
        "name": "Kalaallisut",
        "name_local": "Kalaallisut",
        "bidi": False,
    },
}
# Add custom languages not provided by Django
LANG_INFO = dict(django.conf.locale.LANG_INFO, **EXTRA_LANG_INFO)
django.conf.locale.LANG_INFO = LANG_INFO

TIME_ZONE = os.environ.get("DJANGO_TIMEZONE", "America/Nuuk")
USE_I18N = True
USE_L10N = True
USE_TZ = True
THOUSAND_SEPARATOR = "."
DECIMAL_SEPARATOR = ","
FORMAT_MODULE_PATH = ["havneafgifter.formats"]
