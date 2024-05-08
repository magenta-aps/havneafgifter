import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from project.util import lenient_get

logger = logging.getLogger(__name__)


class Saml2Backend(ModelBackend):
    def authenticate(
        self,
        request,
        saml_data=None,
        create_unknown_user=True,
        assertion_info=None,
        **kwargs,
    ):
        if saml_data is None:
            return None
        if "ava" not in saml_data:
            return None

        if saml_data is None:
            logger.info("Session info is None")
            return None

        if "ava" not in saml_data:
            logger.error('"ava" key not found in session_info')
            return None

        ava = saml_data["ava"]

        user_model = get_user_model()

        map = {
            "username": "cpr",
            "cpr": "cpr",
            "cvr": "cvr",
            "first_name": "firstname",
            "last_name": "lastname",
            "email": "email",
        }

        if not ava.get(map["username"]):
            logger.error(f"unique identifier {map['username']} not found in saml data")
            return None

        user, created = user_model.objects.update_or_create(
            **{"username": lenient_get(ava, map["username"], 0)},
            defaults={
                user_attr: lenient_get(ava, saml_attr, 0)
                for user_attr, saml_attr in map.items()
                if user_attr != "username"
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=("password",))
        return user
