import os
from pathlib import Path

import saml2
from django.urls import reverse_lazy

from project.util import strtobool


SAML_SESSION_COOKIE_NAME = "saml_session"
SAML_SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True
SAML_CREATE_UNKNOWN_USER = True
SAML_ACS_FAILURE_RESPONSE_FUNCTION = "project.util.template_failure"
ACS_DEFAULT_REDIRECT_URL = reverse_lazy("havneafgifter:harbor_dues_form_create")

BASE_DIR = Path(__file__).resolve().parent.parent
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'djangosaml2.backends.Saml2Backend',
)
LOGIN_URL = '/saml2/login/'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SAML_DEFAULT_BINDING = saml2.BINDING_HTTP_REDIRECT
SAML_ATTRIBUTE_MAPPING = {
    "https://data.gov.dk/model/core/eid/cprNumber": ("username", "cpr"),
    "https://data.gov.dk/model/core/eid/firstName": ("first_name",),
    "https://data.gov.dk/model/core/eid/lastName": ("last_name",),
    "https://data.gov.dk/model/core/eid/email": ("email",),
    "https://data.gov.dk/model/core/eid/professional/cvr": ("cvr",),
    "https://data.gov.dk/model/core/eid/professional/orgName": ("organization")
}

SAML_CONFIG = {
    "enabled": bool(strtobool(os.environ.get("SAML_ENABLED", "False"))),
    "debug": 1,
    "entityid": os.environ.get("SAML_SP_ENTITY_ID"),
    "idp_entity_id": os.environ.get("SAML_IDP_ENTITY_ID"),
    "name": os.environ.get("SAML_SP_NAME") or "Toldbehandling",
    "description": os.environ.get("SAML_SP_DESCRIPTION") or "Toldregistrering",
    "verify_ssl_cert": False,
    "metadata_remote": os.environ.get("SAML_IDP_METADATA"),
    # Til metadata-fetch mellem containere
    "metadata_remote_container": os.environ.get("SAML_IDP_METADATA_CONTAINER"),
    "metadata": {"local": ["/var/cache/told/idp_metadata.xml"]},  # IdP Metadata
    "service": {
        "sp": {
            "name": os.environ.get("SAML_SP_NAME") or "Told",
            "hide_assertion_consumer_service": False,
            "endpoints": {
                "assertion_consumer_service": [
                    (
                        'http://localhost:8000/saml2/acs/',
                        "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                    )
                ],
                "single_logout_service": [
                    (
                        os.environ.get("SAML_SP_LOGOUT_CALLBACK_URI"),
                        "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                    ),
                ],
            },
            "required_attributes": [
                "https://data.gov.dk/model/core/eid/professional/orgName",
                "https://data.gov.dk/model/core/specVersion",
                "https://data.gov.dk/concept/core/nsis/loa",
                "https://data.gov.dk/model/core/eid/cprNumber",
                "https://data.gov.dk/model/core/eid/firstName",
                "https://data.gov.dk/model/core/eid/lastName",
                "https://data.gov.dk/model/core/eid/email",
            ],
            "optional_attributes": [
                "https://data.gov.dk/model/core/eid/professional/cvr",
            ],
            "name_id_format": [
                "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
            ],
            "signing_algorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",

            'digest_algorithm':  "http://www.w3.org/2000/09/xmldsig#sha1",
            "authn_requests_signed": True,
            "want_assertions_signed": True,
            "want_response_signed": False,
            "allow_unsolicited": True,
            "logout_responses_signed": True,
        }
    },
    "key_file": os.environ.get("SAML_SP_KEY"),
    "cert_file": os.environ.get("SAML_SP_CERTIFICATE"),
    "encryption_keypairs": [
        {
            "key_file": os.environ.get("SAML_SP_KEY"),
            "cert_file": os.environ.get("SAML_SP_CERTIFICATE"),
        },
    ],
    "xmlsec_binary": "/usr/bin/xmlsec1",
    # 'attribute_map_dir': os.path.join(BASE_DIR, 'attribute-maps'),
    "allow_unknown_attributes": True,
    "delete_tmpfiles": True,
    "organization": {
        "name": [("Skattestyrelsen", "da")],
        "display_name": ["Skattestyrelsen"],
        "url": [("https://nanoq.gl", "da")],
    },
    "contact_person": [
        {
            "given_name": os.environ["SAML_CONTACT_TECHNICAL_NAME"],
            "email_address": os.environ["SAML_CONTACT_TECHNICAL_EMAIL"],
            "type": "technical",
        },
        {
            "given_name": os.environ["SAML_CONTACT_SUPPORT_NAME"],
            "email_address": os.environ["SAML_CONTACT_SUPPORT_EMAIL"],
            "type": "support",
        },
    ],
    "preferred_binding": {
        "attribute_consuming_service": [
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        ],
        "single_logout_service": [
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        ],
    },

}
