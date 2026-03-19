# SPDX-FileCopyrightText: 2026 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

import os

from project.util import strtobool

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", None)
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 25))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", None)
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", None)
EMAIL_USE_TLS = bool(strtobool(os.environ.get("EMAIL_USE_TLS", "False")))
EMAIL_USE_SSL = bool(strtobool(os.environ.get("EMAIL_USE_SSL", "False")))
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "noreply@nanoq.gl")
EMAIL_ADDRESS_SKATTESTYRELSEN = os.environ.get("EMAIL_ADDRESS_SKATTESTYRELSEN")
EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL = os.environ.get(
    "EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL"
)
