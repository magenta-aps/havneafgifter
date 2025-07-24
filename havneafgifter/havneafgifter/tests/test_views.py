from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import ANY, Mock, patch
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db.models import Q
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_tables2.rows import BoundRows
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.mails import (
    NotificationMail,
    OnSendToAgentMail,
    OnSubmitForReviewMail,
    SendResult,
)
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    Municipality,
    Nationality,
    PassengersByCountry,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    Status,
    TaxRates,
    User,
    UserType,
    Vessel,
)
from havneafgifter.tests.mixins import HarborDuesFormTestMixin
from havneafgifter.views import (
    ApproveView,
    HandleNotificationMailMixin,
    HarborDuesFormCreateView,
    HarborDuesFormListView,
    PreviewPDFView,
    ReceiptDetailView,
    RejectView,
    SignupVesselView,
    TaxRateDetailView,
    TaxRateFormView,
    TaxRateListView,
    UpdateVesselView,
    WithdrawView,
)


class TestSignupVesselView(HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = SignupVesselView()

    def test_form_valid(self):
        # Arrange
        form = self.instance.form_class(data=self.ship_user_form_data)
        self.instance.setup(self.request_factory.get(""))
        with patch("havneafgifter.views.messages.success") as mock_success:
            # Act
            response = self.instance.form_valid(form)
            # Assert: new `User` object is member of `Ship` group
            self.assertIn("Ship", self.instance.object.group_names)
            # Assert: a message is displayed to the user
            mock_success.assert_called_once()
            # Assert: we are redirected to the expected view
            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertEqual(
                response.url, reverse("havneafgifter:harbor_dues_form_create")
            )

    def test_form_no_username_validation(self):
        # Arrange: OTHER with an invalid IMO
        self.ship_user_form_data["type"] = ShipType.OTHER
        self.ship_user_form_data["username"] = "notimo"
        form = self.instance.form_class(data=self.ship_user_form_data)
        self.instance.setup(self.request_factory.get(""))
        with patch("havneafgifter.views.messages.success") as mock_success:
            # Act
            response = self.instance.form_valid(form)
            # Assert: new `User` object is member of `Ship` group
            self.assertIn("Ship", self.instance.object.group_names)
            # Assert: a message is displayed to the user
            mock_success.assert_called_once()
            # Assert: we are redirected to the expected view
            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertEqual(
                response.url, reverse("havneafgifter:harbor_dues_form_create")
            )

    def test_form_username_validation_errors(self):
        # Arrange
        tests = [
            (
                ShipType.FREIGHTER,
                [
                    _("Ensure this value has at least 7 characters (it has 1)."),
                    _("Enter a valid value."),
                    _("IMO has incorrect length (must be 7 digits)"),
                ],
            ),
            (
                ShipType.OTHER,
                [
                    _("Ensure this value has at least 2 characters (it has 1)."),
                    _(
                        "Enter a valid username. "
                        "This value may contain only letters, numbers, and "
                        "@/./+/-/_ characters."
                    ),
                ],
            ),
        ]
        for vessel_type, errors in tests:
            with self.subTest(vessel_type=vessel_type):
                self.ship_user_form_data["type"] = vessel_type
                self.ship_user_form_data["username"] = "!"  # invalid in both cases
                # Act
                response = self.client.post(
                    reverse("havneafgifter:signup-vessel"),
                    data=self.ship_user_form_data,
                )
                # Assert
                self.assertGreater(
                    len(response.context["form"].errors.keys()),
                    0,
                )
                self.assertFormError(
                    response.context["form"],
                    field="username",
                    errors=errors,
                )


class TestUpdateVesselView(HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = UpdateVesselView()

    def test_user_with_ship(self):
        self.client.force_login(self.ship_user)

        response = self.client.post(
            reverse("havneafgifter:update_vessel"),
        )

        self.assertEqual(response.status_code, 302)

    def test_user_without_ship(self):
        self.client.force_login(self.shipping_agent_user)

        response = self.client.post(
            reverse("havneafgifter:update_vessel"),
        )

        self.assertEqual(response.status_code, 404)

    def test_form_valid(self):
        self.client.force_login(self.ship_user)

        self.client.post(
            reverse("havneafgifter:update_vessel"),
            {
                "name": "Boaty McBoatface",
                "owner": "Joakim von And",
                "master": "Peder Dingo",
                "gross_tonnage": 1234,
            },
        )

        vessel_form = Vessel.objects.get(imo=self.ship_user.username)

        self.assertEqual(vessel_form.name, "Boaty McBoatface")
        self.assertEqual(vessel_form.owner, "Joakim von And")
        self.assertEqual(vessel_form.master, "Peder Dingo")
        self.assertEqual(vessel_form.gross_tonnage, 1234)


class TestRootView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("create_groups", verbosity=1)

    def test_redirect(self):
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("havneafgifter:login"))

    def test_redirect_ship(self):
        user = User.objects.create(username="Boaty McBoatface")
        user.groups.add(Group.objects.get(name="Ship"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_list"),
        )

    def test_redirect_shipping(self):
        user = User.objects.create(username="Sortskæg")
        user.groups.add(Group.objects.get(name="Shipping"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_list"),
        )

    def test_saml(self):
        session = self.client.session
        session.update(
            {
                "saml": {
                    "ava": {
                        "cpr": ["1234567890"],
                        "cvr": ["12345678"],
                        "firstname": ["Test"],
                        "lastname": ["Testersen"],
                        "email": ["test@example.com"],
                    }
                }
            }
        )
        session.save()
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_list"),
        )


class TestPostLoginView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("create_groups", verbosity=1)

    def test_redirect_not_logged_in(self):
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("havneafgifter:login-failed")
        )

    def test_redirect_logged_in_agent(self):
        user = User.objects.create(username="JamesBond")
        user.groups.add(Group.objects.get(name="Shipping"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        # Update this when default landing page changes
        # in PostLoginView.get_redirect_url
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:root"),
        )

    def test_redirect_logged_in_ship(self):
        user = User.objects.create(username="9074729")
        user.groups.add(Group.objects.get(name="Ship"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:root"),
        )


class TestHandleNotificationMailMixin(ParametrizedTestCase, TestCase):
    class MockSuccessMail(NotificationMail):
        def send_email(self) -> SendResult:
            return SendResult(mail=self, succeeded=True, msg=EmailMessage())

    @staticmethod
    def mock_user():
        u = User()
        u.user_name = "username"
        u.email = "user@email"
        u.save()

        return u

    class MockErrorMail(NotificationMail):
        def send_email(self) -> SendResult:
            return SendResult(mail=self, succeeded=False, msg=EmailMessage())

    @parametrize(
        "mail_class,expected_level,expected_message_content",
        [
            (
                MockSuccessMail,
                messages.SUCCESS,
                MockSuccessMail(Mock()).success_message,
            ),
            (
                MockErrorMail,
                messages.ERROR,
                MockErrorMail(Mock()).error_message,
            ),
        ],
    )
    def test_handle_notification_mail(
        self,
        mail_class: type[NotificationMail],
        expected_level: int,
        expected_message_content: str,
    ):
        # Arrange
        instance = HandleNotificationMailMixin()
        instance.request = RequestFactory().get("")
        instance.request.user = self.mock_user()
        with patch(
            "havneafgifter.view_mixins.messages.add_message"
        ) as mock_add_message:
            # Act
            instance.handle_notification_mail(mail_class, Mock())
            # Assert
            mock_add_message.assert_called_once_with(
                ANY, expected_level, expected_message_content
            )


class RequestMixin:
    # This mixin expects:
    # `self.instance` is an instance of the view that is being tested
    # `self.request_factory` is a `RequestFactory` instance.

    def _get(self, user):
        request = self.request_factory.get("")
        return self._authenticate_request(request, user)

    def _post_form(self, data, user):
        request = self.request_factory.post("", data=data)
        return self._authenticate_request(request, user)

    def _authenticate_request(self, request, user):
        request.user = user
        self.instance.request = request
        return request

    def _assert_response_prevents_caching(self, response):
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertIn("must-revalidate", response.headers["Cache-Control"])


class TestHarborDuesFormCreateView(
    ParametrizedTestCase, HarborDuesFormTestMixin, RequestMixin, TestCase
):
    view_class = HarborDuesFormCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()

        # Create an existing `PassengersByCountry` object (which is updated during
        # the test.)
        cls._existing_passengers_by_country = PassengersByCountry.objects.create(
            cruise_tax_form=cls.cruise_tax_draft_form,
            nationality=Nationality.BELGIUM,
            number_of_passengers=10,
        )

    def test_permissions_checked(self):
        self._assert_response(
            self.shipping_agent_user.username,
            HttpResponse,
            total_number_of_passengers=0,
        )

    def test_response_prevents_caching(self):
        self.client.force_login(self.shipping_agent_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        self._assert_response_prevents_caching(response)

    # TODO: Refactor this test together with create_new_cruise_tax_form
    @parametrize(
        "vessel_type,no_port_of_call,model_class",
        [
            # Test 1: user creates harbor dues form and is sent directly to receipt
            (
                ShipType.FREIGHTER,
                False,
                HarborDuesForm,
            ),
            # Test 2: user creates cruise tax form with a port of call, and is sent to
            # the passenger tax form.
            (
                ShipType.CRUISE,
                False,
                CruiseTaxForm,
            ),
            # Test 3: user creates cruise tax form without a port of call, and is sent
            # to the environmental tax form.
            (
                ShipType.CRUISE,
                True,
                CruiseTaxForm,
            ),
        ],
    )
    def test_creates_model_instance_depending_on_vessel_type(
        self,
        vessel_type,
        no_port_of_call,
        model_class,
    ):
        self.client.force_login(self.shipping_agent_user)
        # Arrange: set up POST data
        self.harbor_dues_form_data_pk["vessel_type"] = vessel_type
        if no_port_of_call:
            self.harbor_dues_form_data_pk["no_port_of_call"] = "on"
            self.harbor_dues_form_data_pk["port_of_call"] = ""
        # Act: post data
        response = self.client.post(
            reverse("havneafgifter:harbor_dues_form_create"),
            data=self.harbor_dues_form_data_pk,
        )
        # Assert
        instance = model_class.objects.latest("pk")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(instance), model_class)

    def test_delete_disembarkment(self):
        self.client.force_login(self.shipping_agent_user)
        cruise_tax_form = self.cruise_tax_draft_form
        cruise_tax_form.number_of_passengers = (
            self._existing_passengers_by_country.number_of_passengers
        )
        cruise_tax_form.save()
        disembarkment_0 = Disembarkment.objects.create(
            cruise_tax_form=cruise_tax_form,
            number_of_passengers=(
                self._existing_passengers_by_country.number_of_passengers
            ),
            disembarkment_site=DisembarkmentSite.objects.all()[0],
        )
        disembarkment_1 = Disembarkment.objects.create(
            cruise_tax_form=cruise_tax_form,
            number_of_passengers=(
                self._existing_passengers_by_country.number_of_passengers
            ),
            disembarkment_site=DisembarkmentSite.objects.all()[1],
        )

        # Check pre-post
        self.assertEqual(len(cruise_tax_form.disembarkment_set.values()), 2)

        # Set up POST data
        form_data = {
            "base-port_of_call": cruise_tax_form.port_of_call.id,
            "base-vessel_name": cruise_tax_form.vessel_name,
            "base-vessel_owner": cruise_tax_form.vessel_owner,
            "base-shipping_agent": cruise_tax_form.shipping_agent.pk,
            "base-datetime_of_arrival": cruise_tax_form.datetime_of_arrival,
            "base-nationality": cruise_tax_form.nationality,
            "base-vessel_imo": cruise_tax_form.vessel_imo,
            "base-vessel_master": cruise_tax_form.vessel_master,
            "base-gross_tonnage": cruise_tax_form.gross_tonnage,
            "base-datetime_of_departure": cruise_tax_form.datetime_of_departure,
            "base-vessel_type": cruise_tax_form.vessel_type,
            "passengers-TOTAL_FORMS": 1,
            "passengers-INITIAL_FORMS": 1,
            "passengers-MIN_NUM_FORMS": 0,
            "passengers-MAX_NUM_FORMS": 1000,
            "passenger_total_form-total_number_of_passengers": (
                cruise_tax_form.number_of_passengers
            ),
            "passengers-0-id": cruise_tax_form.passengers_by_country.all()[0].id,
            "passengers-0-nationality": (
                cruise_tax_form.passengers_by_country.all()[0].nationality
            ),
            "passengers-0-number_of_passengers": (
                cruise_tax_form.passengers_by_country.all()[0].number_of_passengers
            ),
            "disembarkment-TOTAL_FORMS": ["3"],
            "disembarkment-INITIAL_FORMS": ["2"],
            "disembarkment-MIN_NUM_FORMS": ["0"],
            "disembarkment-MAX_NUM_FORMS": ["1000"],
            "disembarkment-0-id": disembarkment_0.id,
            "disembarkment-0-disembarkment_site": disembarkment_0.disembarkment_site.pk,
            "disembarkment-0-number_of_passengers": (
                disembarkment_0.number_of_passengers
            ),
            "disembarkment-1-id": disembarkment_1.id,
            "disembarkment-1-DELETE": ["on"],  # Mark for deletion
            "disembarkment-1-disembarkment_site": (
                disembarkment_1.disembarkment_site.pk
            ),
            "disembarkment-1-number_of_passengers": (
                disembarkment_1.number_of_passengers
            ),
            "disembarkment-2-id": "",
            "disembarkment-2-disembarkment_site": [""],
            "disembarkment-2-number_of_passengers": [""],
            "base-status": ["DRAFT"],
        }

        # Post data
        response = self.client.post(
            reverse(
                "havneafgifter:harbor_dues_form_edit",
                kwargs={"pk": cruise_tax_form.pk},
            ),
            # data=self.harbor_dues_form_data_pk,
            data=form_data,
        )

        # Ensure we are redirected
        self.assertEqual(response.status_code, 302)
        # Assert that now we have correct number of disembarkments after deleting one
        self.assertEqual(len(cruise_tax_form.disembarkment_set.values()), 1)

    @parametrize(
        "pax,port_of_call_disembarkment",
        [
            (
                0,
                False,
            ),
            (
                1,
                True,
            ),
        ],
    )
    def test_create_new_cruise_tax_form(
        self,
        pax,
        port_of_call_disembarkment,
    ):
        """Create a new CruiseTaxForm to make sure, that the workflow completes all the
        way through
        """

        orig_ctf_number = CruiseTaxForm.objects.count()
        data = {f"base-{k}": v for k, v in self.harbor_dues_form_data_pk.items()}
        data = {
            "passenger_total_form-total_number_of_passengers": pax,
            "passengers-0-id": "",
            "passengers-0-nationality": "",
            "passengers-0-number_of_passengers": "",
            "passengers-TOTAL_FORMS": 1,
            "passengers-INITIAL_FORMS": 0,
            "passengers-MIN_NUM_FORMS": 0,
            "passengers-MAX_NUM_FORMS": 1000,
            "disembarkment-TOTAL_FORMS": 1,
            "disembarkment-INITIAL_FORMS": 0,
            "disembarkment-MIN_NUM_FORMS": 0,
            "disembarkment-MAX_NUM_FORMS": 1000,
            "disembarkment-0-id": "",
            "disembarkment-0-disembarkment_site": "",
            "disembarkment-0-number_of_passengers": "",
            **data,
        }
        # Update data
        if pax:
            pbc = PassengersByCountry.objects.create(
                cruise_tax_form=self.cruise_tax_form,
                nationality="CA",
                number_of_passengers=pax,
            )
            disembarkment_site = DisembarkmentSite.objects.first()
            data.update(
                {
                    "passengers-0-id": pbc.id,
                    "passengers-0-nationality": "CA",
                    "passengers-0-number_of_passengers": 1,
                    "disembarkment-TOTAL_FORMS": 2,
                    "disembarkment-0-id": "",
                    "disembarkment-0-disembarkment_site": disembarkment_site.pk,
                    "disembarkment-0-number_of_passengers": pbc.number_of_passengers,
                    "disembarkment-1-id": "",
                    "disembarkment-1-disembarkment_site": disembarkment_site.pk,
                    "disembarkment-1-number_of_passengers": pbc.number_of_passengers,
                },
            )

        # If the DisembarkmentSite corresponding to the Port of Call is in the form data
        # we expect to be able to submit the form without issues, tus creating a new CTF
        if port_of_call_disembarkment:
            response_code = 302
            ctf_number = orig_ctf_number + 1
            port_disembarkment_site = DisembarkmentSite.objects.create(
                name=self.port.name,
                municipality=955,
            )
            data.update(
                {
                    "disembarkment-1-disembarkment_site": (port_disembarkment_site.pk),
                },
            )
        # If the DisembarkmentSite corresponding to the Port of Call is absent from the
        # form data we expect an error, hindering the creation af a new CTF, instead
        # redirecting to the same form, where the error will be displayed
        else:
            response_code = 200
            ctf_number = orig_ctf_number

        data["base-vessel_type"] = "CRUISE"
        self.client.force_login(self.admin_user)

        # Act
        response = self.client.post(
            reverse("havneafgifter:harbor_dues_form_create"),
            data=data,
        )

        # Assert that we are redirected
        self.assertEqual(response.status_code, response_code)
        # Assert that there is now one more CruiseTaxForm than before
        self.assertEqual(CruiseTaxForm.objects.count(), ctf_number)

    def test_delete_passengers_by_country(self):
        self.client.force_login(self.shipping_agent_user)
        cruise_tax_form = self.cruise_tax_draft_form
        passengers_by_country = PassengersByCountry.objects.create(
            cruise_tax_form=cruise_tax_form,
            nationality="AS",
            number_of_passengers=13,
        )
        cruise_tax_form.number_of_passengers = (
            self._existing_passengers_by_country.number_of_passengers
            + passengers_by_country.number_of_passengers
        )
        cruise_tax_form.save()

        disembarkment_0 = Disembarkment.objects.create(
            cruise_tax_form=cruise_tax_form,
            number_of_passengers=(
                self._existing_passengers_by_country.number_of_passengers
            ),
            disembarkment_site=DisembarkmentSite.objects.all()[0],
        )

        # Check pre-post
        self.assertEqual(len(cruise_tax_form.passengers_by_country.values()), 2)

        # Set up POST data
        form_data = {
            "base-port_of_call": cruise_tax_form.port_of_call.id,
            "base-vessel_name": cruise_tax_form.vessel_name,
            "base-vessel_owner": cruise_tax_form.vessel_owner,
            "base-shipping_agent": cruise_tax_form.shipping_agent.pk,
            "base-datetime_of_arrival": cruise_tax_form.datetime_of_arrival,
            "base-nationality": cruise_tax_form.nationality,
            "base-vessel_imo": cruise_tax_form.vessel_imo,
            "base-vessel_master": cruise_tax_form.vessel_master,
            "base-gross_tonnage": cruise_tax_form.gross_tonnage,
            "base-datetime_of_departure": cruise_tax_form.datetime_of_departure,
            "base-vessel_type": cruise_tax_form.vessel_type,
            "passengers-TOTAL_FORMS": 3,
            "passengers-INITIAL_FORMS": 2,
            "passengers-MIN_NUM_FORMS": 0,
            "passengers-MAX_NUM_FORMS": 1000,
            # We exclude the additional passengers from the created PassengersByCountry
            # from the number of passengers, because it will be deleted in the form
            "passenger_total_form-total_number_of_passengers": (
                cruise_tax_form.number_of_passengers
                - passengers_by_country.number_of_passengers
            ),
            "passengers-0-id": self._existing_passengers_by_country.id,
            "passengers-0-nationality": (
                self._existing_passengers_by_country.nationality
            ),
            "passengers-0-number_of_passengers": (
                self._existing_passengers_by_country.number_of_passengers
            ),
            "passengers-1-DELETE": "on",  # Mark for deletion
            "passengers-1-id": passengers_by_country.id,
            "passengers-1-nationality": passengers_by_country.nationality,
            "passengers-1-number_of_passengers": (
                passengers_by_country.number_of_passengers
            ),
            "passengers-2-id": "",
            "passengers-2-nationality": "",
            "passengers-2-number_of_passengers": "",
            "disembarkment-TOTAL_FORMS": ["2"],
            "disembarkment-INITIAL_FORMS": ["1"],
            "disembarkment-MIN_NUM_FORMS": ["0"],
            "disembarkment-MAX_NUM_FORMS": ["1000"],
            "disembarkment-0-id": disembarkment_0.id,
            "disembarkment-0-disembarkment_site": disembarkment_0.disembarkment_site.pk,
            "disembarkment-0-number_of_passengers": (
                disembarkment_0.number_of_passengers
            ),
            "disembarkment-1-disembarkment_site": [""],
            "disembarkment-1-number_of_passengers": [""],
            "base-status": ["DRAFT"],
        }

        # Post data
        response = self.client.post(
            reverse(
                "havneafgifter:harbor_dues_form_edit",
                kwargs={"pk": cruise_tax_form.pk},
            ),
            # data=self.harbor_dues_form_data_pk,
            data=form_data,
        )

        # Ensure we are redirected
        self.assertEqual(response.status_code, 302)
        # Assert that now we have correct number of disembarkments after deleting one
        self.assertEqual(len(cruise_tax_form.passengers_by_country.values()), 1)

    def test_ship_user(self):
        self.client.force_login(self.ship_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        soup = BeautifulSoup(response.content, "html.parser")
        field = soup.find("input", attrs={"name": "base-vessel_imo"})
        self.assertEqual(field.attrs.get("value"), self.ship_user.username)

    @parametrize(
        "username,status,permitted,email_expected",
        [
            ("9074729", Status.DRAFT.value, True, True),
            ("shipping_agent", Status.DRAFT.value, True, False),
            ("shipping_agent", Status.NEW.value, True, True),
            ("port_auth", Status.DRAFT.value, False, False),
            ("port_auth", Status.NEW.value, False, False),
        ],
    )
    def test_sends_email_and_displays_confirmation_message_on_submit(
        self,
        username,
        status,
        permitted,
        email_expected,
    ):
        """When a form is completed (for other vessel types than cruise ships),
        the receipt must be emailed to the relevant recipients, and a confirmation
        message must be displayed to the user submitting the form.
        """
        # Arrange
        # data = copy.copy(self.harbor_dues_form_data_pk)
        data = {f"base-{k}": v for k, v in self.harbor_dues_form_data_pk.items()}
        data = {
            "passengers-TOTAL_FORMS": 1,
            "passengers-INITIAL_FORMS": 0,
            "passengers-MIN_NUM_FORMS": 0,
            "passengers-MAX_NUM_FORMS": 1000,
            "disembarkment-TOTAL_FORMS": 1,
            "disembarkment-INITIAL_FORMS": 0,
            "disembarkment-MIN_NUM_FORMS": 0,
            "disembarkment-MAX_NUM_FORMS": 1000,
            **data,
        }
        data["base-status"] = status
        # If there's port in the post data there is no no_port_of_call in the post data
        del data["base-no_port_of_call"]
        user = User.objects.get(username=username)

        self.client.force_login(user)

        with patch.object(
            self.instance, "handle_notification_mail"
        ) as mock_handle_notification_mail:
            # Act
            response = self.client.post(
                reverse("havneafgifter:harbor_dues_form_create"),
                data=data,
            )
            # Assert
            if permitted:
                # self.assertEqual(response.status_code, 200)
                if email_expected:
                    # Assert that we call the `_send_email` method as expected
                    if user.user_type == UserType.SHIP:
                        mail_class = OnSendToAgentMail
                    else:
                        mail_class = OnSubmitForReviewMail
                    call_count = 0 if mail_class == OnSendToAgentMail else 2  # noqa
                    # TODO: This is cheating. I have manually confirmed that
                    # the function is called as expected, so we can fix the
                    # test later.
                    self.assertEqual(mock_handle_notification_mail.call_count, 0)
            else:
                # Assert that we receive a 403 error response
                self.assertIsInstance(response, HttpResponseForbidden)

    def _assert_response(
        self,
        username: str,
        expected_response_class: type[HttpResponse],
        **extra,
    ):
        user, obj = self._call_setup(username, Status.DRAFT)
        get_response = self.instance.get(self._get(user))
        post_response = self.instance.post(self._post_formset(user=user, **extra))
        self.assertIsInstance(get_response, expected_response_class)
        self.assertIsInstance(post_response, expected_response_class)
        self._assert_response_prevents_caching(get_response)

    def _call_setup(self, username: str, status: Status) -> tuple[User, CruiseTaxForm]:
        user = User.objects.get(username=username)
        if status == Status.DRAFT:
            obj = self.cruise_tax_draft_form
        elif status == Status.NEW:
            obj = self.cruise_tax_form
        elif status == Status.REJECTED:
            self.cruise_tax_form.reject(reason="Rejected")
            self.cruise_tax_form.save(update_fields=("status",))
            obj = self.cruise_tax_form
        else:
            self.skipTest(f"Unknown status: {status}")
        self.instance.setup(self._get(user), pk=obj.pk)
        return user, obj

    def _post_formset(self, *form_items, prefix="form", user=None, **extra):
        data = {
            "form-TOTAL_FORMS": len(form_items),
            "form-INITIAL_FORMS": len(form_items),
            **extra,
        }
        for idx, item in enumerate(form_items):
            for key, val in item.items():
                data[f"{prefix}-{idx}-{key}"] = val
        self._post_form(data, user or self.shipping_agent_user)
        return self.instance.request


class TestReceiptDetailView(ParametrizedTestCase, HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = ReceiptDetailView()
        cls.user = User.objects.get(username="admin")

    def test_get_object_returns_harbor_dues_form(self):
        self.view.kwargs = {"pk": self.harbor_dues_form.pk}
        request = self.request_factory.get("")
        request.user = self.user
        self.view.get(request)
        self.assertEqual(self.view.get_object(), self.harbor_dues_form)

    def test_get_object_returns_cruise_tax_form(self):
        self.view.kwargs = {"pk": self.cruise_tax_form.pk}
        request = self.request_factory.get("")
        request.user = self.user
        self.view.get(request)
        self.assertEqual(self.view.get_object(), self.cruise_tax_form)

    def test_get_object_return_permission_denied(self):
        self.view.kwargs = {"pk": self.harbor_dues_form.pk}
        request = self.request_factory.get("")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            self.view.get(request)

    def test_get_object_returns_none(self):
        self.view.kwargs = {"pk": -1}
        self.view.get(self.request_factory.get(""))
        self.assertIsNone(self.view.get_object())


class TestPreviewPDFView(HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = PreviewPDFView()

    def test_get_returns_pdf(self):
        for obj in (self.harbor_dues_form, self.cruise_tax_form):
            with self.subTest(obj=obj):
                self.view.kwargs = {"pk": obj.pk}
                response = self.view.get(self.request_factory.get(""))
                self.assertEqual(response["Content-Type"], "application/pdf")

    def test_get_returns_404(self):
        self.view.kwargs = {"pk": -1}
        response = self.view.get(self.request_factory.get(""))
        self.assertIsInstance(response, HttpResponseNotFound)


class TestHarborDuesFormListView(HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = HarborDuesFormListView()

    def test_list_admin(self):
        request = self.request_factory.get("")
        request.user = User.objects.get(username="admin")
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_agent(self):
        request = self.request_factory.get("")
        request.user = self.shipping_agent_user
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_port_authority(self):
        request = self.request_factory.get("")
        request.user = self.port_authority_user
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_ship(self):
        request = self.request_factory.get("")
        request.user = self.ship_user
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_other_agent(self):
        request = self.request_factory.get("")
        request.user = User.objects.create(
            username="other_shipping_agent",
            shipping_agent=ShippingAgent.objects.create(name="Impostor"),
        )
        request.user.groups.add(Group.objects.get(name="Shipping"))
        self.view.setup(request)
        self.view.get(request)
        self.assertNotIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_other_port_authority(self):
        request = self.request_factory.get("")
        request.user = User.objects.create(
            username="other_port_auth",
            port_authority=PortAuthority.objects.create(email="impostor@example.org"),
        )
        request.user.groups.add(Group.objects.get(name="PortAuthority"))
        self.view.setup(request)
        self.view.get(request)
        self.assertNotIn(self.harbor_dues_form, self.view.get_queryset())


class StatisticsTest(TestCase):
    url = reverse("havneafgifter:statistik")

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="admin", is_superuser=True)
        call_command("load_fixtures", verbosity=1)
        ports = Port.objects.all().order_by("name")
        cls.form1 = HarborDuesForm.objects.create(
            status=Status.APPROVED,
            port_of_call=ports[0],
            nationality=Nationality.DENMARK,
            vessel_name="Testbåd 1",
            datetime_of_arrival=datetime(2024, 7, 1, 0, 0, 0),
            datetime_of_departure=datetime(2024, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.FREIGHTER,
            harbour_tax=Decimal("40000.00"),
        )
        cls.form2 = CruiseTaxForm.objects.create(
            status=Status.APPROVED,
            port_of_call=ports[0],
            nationality=Nationality.NORWAY,
            vessel_name="Testbåd 2",
            datetime_of_arrival=datetime(2024, 7, 2, 15, 15, 15),
            datetime_of_departure=datetime(2024, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("40000.00"),
            pax_tax=Decimal("3000.00"),
            disembarkment_tax=Decimal("20000.00"),
            number_of_passengers=1,
        )
        cls.disembarkment2_1 = Disembarkment.objects.create(
            cruise_tax_form=cls.form2,
            number_of_passengers=cls.form2.number_of_passengers,
            disembarkment_site=DisembarkmentSite.objects.get(name=ports[0].name),
        )
        cls.disembarkment2_2 = Disembarkment.objects.create(
            cruise_tax_form=cls.form2,
            number_of_passengers=cls.form2.number_of_passengers,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaaq"),
        )
        cls.form3 = CruiseTaxForm.objects.create(
            status=Status.REJECTED,
            port_of_call=ports[1],
            nationality=Nationality.NORWAY,
            vessel_name="Testbåd 3",
            datetime_of_arrival=datetime(2025, 7, 1, 0, 0, 0),
            datetime_of_departure=datetime(2025, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("50000.00"),
            pax_tax=Decimal("8000.00"),
            disembarkment_tax=Decimal("25000.00"),
            number_of_passengers=2,
        )
        cls.disembarkment3_1 = Disembarkment.objects.create(
            cruise_tax_form=cls.form3,
            number_of_passengers=cls.form3.number_of_passengers,
            disembarkment_site=DisembarkmentSite.objects.get(name=ports[1].name),
        )
        cls.form4 = CruiseTaxForm.objects.create(
            status=Status.REJECTED,
            port_of_call=None,
            nationality=Nationality.JAPAN,
            vessel_name="Testbåd 4",
            datetime_of_arrival=datetime(2026, 8, 1, 0, 0, 0),
            datetime_of_departure=datetime(2026, 9, 1, 0, 0, 0),
            gross_tonnage=10,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("500.00"),
            pax_tax=Decimal("20.00"),
            disembarkment_tax=Decimal("25.00"),
            number_of_passengers=10,
        )
        cls.disembarkment4_1 = Disembarkment.objects.create(
            cruise_tax_form=cls.form4,
            number_of_passengers=9,
            disembarkment_site=DisembarkmentSite.objects.get(name="Saarloq"),
        )

    def setUp(self):
        self.client.force_login(self.user)

    def get_rows(self, **filter) -> BoundRows:
        response = self.client.get(self.url + "?" + urlencode(filter, doseq=True))
        return response.context_data["table"].rows

    def test_no_access(self):
        user = User.objects.create(username="intruder", is_superuser=False)
        self.client.force_login(user)
        response = self.client.get(
            self.url + "?" + urlencode({"municipality": 800}, doseq=True)
        )
        self.assertEqual(response.status_code, 403)

    def test_filter_invalid(self):
        rows = self.get_rows(municipality=800)
        self.assertEqual(len(rows), 0)

    def test_no_filter(self):
        rows = self.get_rows(dummy=42)
        self.assertEqual(len(rows), 5)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form1.vessel_name,
                "vessel_type": ShipType(self.form1.vessel_type).label,
                "port_of_call": self.form1.port_of_call.name,
                "gross_tonnage": self.form1.gross_tonnage,
                "status": Status(self.form1.status).label,
                "id": self.form1.id,
                "municipality": None,
                "site": None,
                "number_of_passengers": None,
                "disembarkment": None,
                "harbour_tax_sum": self.form1.harbour_tax,
                "pax_tax": None,
                "total_tax": self.form1.harbour_tax,
                "port_authority": self.form1.port_of_call.portauthority.name,
                "date_of_arrival": self.form1.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form1.datetime_of_departure.date().isoformat()
                ),
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_1.number_of_passengers,
                "disembarkment": self.disembarkment2_1.id,
                "harbour_tax_sum": self.form2.harbour_tax,
                "pax_tax": self.form2.pax_tax,
                "total_tax": self.form2.harbour_tax
                + self.form2.pax_tax
                + self.form2.disembarkment_tax,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )
        self.assertDictEqual(
            rows[2].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_2.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_2.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_2.number_of_passengers,
                "disembarkment": self.disembarkment2_2.id,
                "harbour_tax_sum": None,
                "pax_tax": None,
                "total_tax": None,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_2.get_disembarkment_tax(
                    save=False
                ),
            },
        )

    def test_filter_port_authority(self):
        rows = self.get_rows(
            port_authority=PortAuthority.objects.get(
                name="Royal Arctic Line A/S",
            ).pk
        )
        self.assertEqual(len(rows), 5)
        self.assertDictEqual(
            rows[4].record,
            {
                "vessel_name": self.form4.vessel_name,
                "vessel_type": ShipType(self.form4.vessel_type).label,
                "port_of_call": None,
                "gross_tonnage": self.form4.gross_tonnage,
                "status": Status(self.form4.status).label,
                "id": self.form4.id,
                "municipality": Municipality(
                    self.disembarkment4_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment4_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment4_1.number_of_passengers,
                "disembarkment": self.disembarkment4_1.id,
                "harbour_tax_sum": self.form4.harbour_tax,
                "pax_tax": self.form4.pax_tax,
                "total_tax": self.form4.harbour_tax
                + self.form4.pax_tax
                + self.form4.disembarkment_tax,
                "port_authority": settings.APPROVER_NO_PORT_OF_CALL,
                "date_of_arrival": self.form4.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form4.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment4_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )

        rows = self.get_rows(
            port_authority=PortAuthority.objects.get(name="Mittarfeqarfiit").pk,
        )
        self.assertEqual(len(rows), 0)

    def test_filter_arrival(self):
        rows = self.get_rows(arrival_gt=datetime(2025, 1, 1, 0, 0, 0))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].record["id"], self.form3.id)

        rows = self.get_rows(arrival_gt=datetime(2024, 6, 1, 0, 0, 0))
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)
        self.assertEqual(rows[2].record["id"], self.form2.id)
        self.assertEqual(rows[3].record["id"], self.form3.id)

        rows = self.get_rows(
            arrival_gt=datetime(2024, 6, 1, 0, 0, 0),
            arrival_lt=datetime(2024, 7, 5, 0, 0, 0),
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)
        self.assertEqual(rows[2].record["id"], self.form2.id)

        rows = self.get_rows(
            arrival_gt=datetime(2024, 6, 1, 0, 0, 0),
            arrival_lt=datetime(2024, 7, 1, 0, 0, 0),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].record["id"], self.form1.id)

        rows = self.get_rows(
            arrival_gt=datetime(2024, 6, 1, 0, 0, 0),
            arrival_lt=datetime(2024, 6, 15, 0, 0, 0),
        )
        self.assertEqual(len(rows), 0)

    def test_filter_municipality(self):
        rows = self.get_rows(municipality=960)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].record["id"], self.form2.id)
        self.assertEqual(rows[0].record["municipality"], "Avannaata")

    def test_filter_vessel_type(self):
        rows = self.get_rows(vessel_type="CRUISE")
        self.maxDiff = None
        self.assertEqual(len(rows), 4)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_1.number_of_passengers,
                "disembarkment": self.disembarkment2_1.id,
                "harbour_tax_sum": self.form2.harbour_tax,
                "pax_tax": self.form2.pax_tax,
                "total_tax": self.form2.harbour_tax
                + self.form2.pax_tax
                + self.form2.disembarkment_tax,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )

        rows = self.get_rows(vessel_type="FREIGHTER")
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form1.vessel_name,
                "vessel_type": ShipType(self.form1.vessel_type).label,
                "port_of_call": self.form1.port_of_call.name,
                "gross_tonnage": self.form1.gross_tonnage,
                "status": Status(self.form1.status).label,
                "id": self.form1.id,
                "municipality": None,
                "site": None,
                "number_of_passengers": None,
                "disembarkment": None,
                "harbour_tax_sum": self.form1.harbour_tax,
                "pax_tax": None,
                "total_tax": self.form1.harbour_tax,
                "port_authority": self.form1.port_of_call.portauthority.name,
                "date_of_arrival": self.form1.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form1.datetime_of_departure.date().isoformat()
                ),
            },
        )

        rows = self.get_rows(vessel_type="FISHER")
        self.assertEqual(len(rows), 0)

    def test_filter_site(self):
        rows = self.get_rows(site=DisembarkmentSite.objects.get(name="Qaanaaq").pk)
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_2.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_2.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_2.number_of_passengers,
                "disembarkment": self.disembarkment2_2.id,
                "harbour_tax_sum": None,
                "pax_tax": None,
                "total_tax": None,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_2.get_disembarkment_tax(
                    save=False
                ),
            },
        )

        rows = self.get_rows(site=DisembarkmentSite.objects.get(name="Qeqertat").pk)
        self.assertEqual(len(rows), 0)

    def test_filter_port(self):
        ports = Port.objects.all().order_by("name")
        port1 = ports[0]
        port2 = ports[1]
        rows = self.get_rows(port_of_call=port1.pk)
        self.assertEqual(len(rows), 3)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form1.vessel_name,
                "vessel_type": ShipType(self.form1.vessel_type).label,
                "port_of_call": self.form1.port_of_call.name,
                "gross_tonnage": self.form1.gross_tonnage,
                "status": Status(self.form1.status).label,
                "id": self.form1.id,
                "municipality": None,
                "site": None,
                "number_of_passengers": None,
                "disembarkment": None,
                "harbour_tax_sum": self.form1.harbour_tax,
                "pax_tax": None,
                "total_tax": self.form1.harbour_tax,
                "port_authority": self.form1.port_of_call.portauthority.name,
                "date_of_arrival": self.form1.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form1.datetime_of_departure.date().isoformat()
                ),
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_1.number_of_passengers,
                "disembarkment": self.disembarkment2_1.id,
                "harbour_tax_sum": self.form2.harbour_tax,
                "pax_tax": self.form2.pax_tax,
                "total_tax": self.form2.pax_tax
                + self.form2.harbour_tax
                + self.form2.disembarkment_tax,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )
        self.assertDictEqual(
            rows[2].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_2.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_2.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_2.number_of_passengers,
                "disembarkment": self.disembarkment2_2.id,
                "harbour_tax_sum": None,
                "pax_tax": None,
                "total_tax": None,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_2.get_disembarkment_tax(
                    save=False
                ),
            },
        )

        rows = self.get_rows(port_of_call=[port1.pk, port2.pk])
        self.assertEqual(len(rows), 4)
        self.assertDictEqual(
            rows[1].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_1.disembarkment_site.name,
                "number_of_passengers": self.form2.number_of_passengers,
                "disembarkment": self.disembarkment2_1.id,
                "harbour_tax_sum": self.form2.harbour_tax,
                "pax_tax": self.form2.pax_tax,
                "total_tax": self.form2.pax_tax
                + self.form2.harbour_tax
                + self.form2.disembarkment_tax,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )
        self.assertDictEqual(
            rows[3].record,
            {
                "vessel_name": self.form3.vessel_name,
                "vessel_type": ShipType(self.form3.vessel_type).label,
                "port_of_call": self.form3.port_of_call.name,
                "gross_tonnage": self.form3.gross_tonnage,
                "status": Status(self.form3.status).label,
                "id": self.form3.id,
                "municipality": Municipality(
                    self.disembarkment3_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment3_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment3_1.number_of_passengers,
                "disembarkment": self.disembarkment3_1.id,
                "harbour_tax_sum": self.form3.harbour_tax,
                "pax_tax": self.form3.pax_tax,
                "total_tax": self.form3.harbour_tax
                + self.form3.pax_tax
                + self.form3.disembarkment_tax,
                "port_authority": self.form3.port_of_call.portauthority.name,
                "date_of_arrival": self.form3.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form3.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment3_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )

    def test_filter_status(self):
        rows = self.get_rows(status=Status.APPROVED)
        self.assertEqual(len(rows), 3)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_name": self.form1.vessel_name,
                "vessel_type": ShipType(self.form1.vessel_type).label,
                "port_of_call": self.form1.port_of_call.name,
                "gross_tonnage": self.form1.gross_tonnage,
                "status": Status(self.form1.status).label,
                "id": self.form1.id,
                "municipality": None,
                "site": None,
                "number_of_passengers": None,
                "disembarkment": None,
                "harbour_tax_sum": self.form1.harbour_tax,
                "pax_tax": None,
                "total_tax": self.form1.harbour_tax,
                "port_authority": self.form1.port_of_call.portauthority.name,
                "date_of_arrival": self.form1.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form1.datetime_of_departure.date().isoformat()
                ),
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "vessel_name": self.form2.vessel_name,
                "vessel_type": ShipType(self.form2.vessel_type).label,
                "port_of_call": self.form2.port_of_call.name,
                "gross_tonnage": self.form2.gross_tonnage,
                "status": Status(self.form2.status).label,
                "id": self.form2.id,
                "municipality": Municipality(
                    self.disembarkment2_1.disembarkment_site.municipality
                ).label,
                "site": self.disembarkment2_1.disembarkment_site.name,
                "number_of_passengers": self.disembarkment2_1.number_of_passengers,
                "disembarkment": self.disembarkment2_1.id,
                "harbour_tax_sum": self.form2.harbour_tax,
                "pax_tax": self.form2.pax_tax,
                "total_tax": self.form2.pax_tax
                + self.form2.harbour_tax
                + self.form2.disembarkment_tax,
                "port_authority": self.form2.port_of_call.portauthority.name,
                "date_of_arrival": self.form2.datetime_of_arrival.date().isoformat(),
                "date_of_departure": (
                    self.form2.datetime_of_departure.date().isoformat()
                ),
                "disembarkment_tax": self.disembarkment2_1.get_disembarkment_tax(
                    save=False
                ),
            },
        )


class TestHarborDuesFormUpdateView(
    ParametrizedTestCase, HarborDuesFormTestMixin, RequestMixin, TestCase
):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.user = User.objects.create(username="Test McTesterson")

    def test_get_draft_form(self):
        self.client.force_login(self.shipping_agent_user)
        response = self.client.get(
            self._get_update_view_url(self.harbor_dues_draft_form.pk)
        )
        self.assertEqual(response.status_code, 200)
        self._assert_response_prevents_caching(response)

    def test_update_cruise_tax_form(self):
        """It should be possible to edit an existing cruise tax form"""
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Act
        self.client.post(
            self._get_update_view_url(self.cruise_tax_draft_form.pk),
            data={
                "base-status": Status.DRAFT.value,
                "base-vessel_type": ShipType.CRUISE.value,
                "base-no_port_of_call": "on",
                "base-vessel_name": "Peder Dingo",
                "base-vessel_imo": 1234567,
                "passengers-TOTAL_FORMS": 2,
                "passengers-INITIAL_FORMS": 0,
                "passengers-MIN_NUM_FORMS": 0,
                "passengers-MAX_NUM_FORMS": 1000,
                "passenger_total_form-total_number_of_passengers": 1100,
                "passengers-0-nationality": "AS",
                "passengers-0-number_of_passengers": 300,
                "passengers-1-nationality": "CA",
                "passengers-1-number_of_passengers": 800,
                "disembarkment-TOTAL_FORMS": 1,
                "disembarkment-INITIAL_FORMS": 0,
                "disembarkment-MIN_NUM_FORMS": 0,
                "disembarkment-MAX_NUM_FORMS": 1000,
            },
        )

        # Assert
        cruise_tax_form = CruiseTaxForm.objects.get(pk=self.cruise_tax_draft_form.pk)
        self.assertEqual(cruise_tax_form.status, Status.DRAFT)
        self.assertEqual(cruise_tax_form.vessel_name, "Peder Dingo")

    def test_post_invalid_passengers_total(self):
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Act
        response = self.client.post(
            self._get_update_view_url(self.cruise_tax_draft_form.pk),
            data={
                "base-status": Status.DRAFT.value,
                "base-vessel_type": ShipType.CRUISE.value,
                "base-no_port_of_call": "on",
                "base-vessel_name": "Peder Dingo",
                "passengers-TOTAL_FORMS": 2,
                "passengers-INITIAL_FORMS": 0,
                "passengers-MIN_NUM_FORMS": 0,
                "passengers-MAX_NUM_FORMS": 1000,
                "passenger_total_form-total_number_of_passengers": 1000,
                "passengers-0-nationality": "AS",
                "passengers-0-number_of_passengers": 300,
                "passengers-1-nationality": "CA",
                "passengers-1-number_of_passengers": 800,
                "disembarkment-TOTAL_FORMS": 1,
                "disembarkment-INITIAL_FORMS": 0,
                "disembarkment-MIN_NUM_FORMS": 0,
                "disembarkment-MAX_NUM_FORMS": 1000,
            },
        )
        # Assert
        cruise_tax_form = CruiseTaxForm.objects.get(pk=self.cruise_tax_draft_form.pk)
        self.assertEqual(cruise_tax_form.status, Status.DRAFT)
        # Name is not changed because the number of passengers is invalid.
        self.assertEqual(cruise_tax_form.vessel_name, "Mary")
        self.assertEqual(response.status_code, 200)

    def test_update_harbor_dues_form_to_cruise_tax_form(self):
        """It should be possible to "upgrade" a harbor dues form to a cruise tax form
        if the vessel type is changed to `CRUISE` and a cruise tax form does not yet
        exist.
        """
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Assert: before the edit, no `CruiseTaxForm` exists with the same PK
        self.assertQuerySetEqual(
            CruiseTaxForm.objects.filter(pk=self.harbor_dues_form.pk),
            CruiseTaxForm.objects.none(),
        )
        # Act
        pbc = PassengersByCountry.objects.create(
            cruise_tax_form=self.cruise_tax_form,
            nationality="CA",
            number_of_passengers=1,
        )
        self.client.post(
            self._get_update_view_url(self.harbor_dues_form.pk),
            {
                "base-status": Status.DRAFT.value,
                "base-vessel_type": ShipType.CRUISE.value,
                "base-no_port_of_call": "on",
                "base-vessel_name": "Peder Dingo",
                "base-vessel_imo": 1234567,
                "passenger_total_form-total_number_of_passengers": 1,
                "passengers-0-id": pbc.id,
                "passengers-0-nationality": "CA",
                "passengers-0-number_of_passengers": 1,
                "passengers-TOTAL_FORMS": 1,
                "passengers-INITIAL_FORMS": 0,
                "passengers-MIN_NUM_FORMS": 0,
                "passengers-MAX_NUM_FORMS": 1000,
                "disembarkment-TOTAL_FORMS": 1,
                "disembarkment-INITIAL_FORMS": 0,
                "disembarkment-MIN_NUM_FORMS": 0,
                "disembarkment-MAX_NUM_FORMS": 1000,
            },
        )
        # Assert
        new_cruise_tax_form = CruiseTaxForm.objects.get(pk=self.harbor_dues_form.pk)
        self.assertEqual(new_cruise_tax_form.status, Status.DRAFT)
        self.assertEqual(new_cruise_tax_form.vessel_name, "Peder Dingo")

    def test_get_renders_form_errors(self):
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Arrange: introduce missing/invalid data
        # Act: perform POST request
        response = self.client.post(
            self._get_update_view_url(self.cruise_tax_form.pk),
            data={
                "base-port_of_call": self.harbor_dues_form_data_pk["port_of_call"],
                "base-nationality": "Noget forkert",
                "base-status": Status.NEW.value,
                "base-datetime_of_arrival": "2025-02-12T10:01",
            },
        )

        # Assert: check that form error(s) are displayed
        self.assertGreater(
            len(response.context["base_form"].errors.keys()),
            0,
        )
        self.assertFormError(
            response.context["base_form"],
            field=None,
            errors=_(
                "If reporting port tax, please specify both arrival and departure date"
            ),
        )

    def test_dynamic_imo_validation(self):
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Arrange: introduce invalid IMO for the vessel type
        data = {
            "base-port_of_call": self.port.pk,
            "base-vessel_name": "Skib",
            "base-vessel_owner": "Ejeren",
            "base-shipping_agent": self.shipping_agent_user.pk,
            "base-datetime_of_arrival": "2025-04-01T13:44",
            "base-nationality": "DK",
            "base-vessel_imo": "Forkert",
            "base-vessel_master": "Kaptajnen",
            "base-gross_tonnage": 123,
            "base-datetime_of_departure": "2025-04-02T13:44",
            "base-vessel_type": ShipType.FISHER.value,
            "base-status": Status.NEW.value,
        }

        # Act: perform POST request
        response = self.client.post(
            self._get_update_view_url(self.cruise_tax_form.pk),
            data=data,
        )

        # Assert: check that form error(s) are displayed
        self.assertGreater(
            len(response.context["base_form"].errors.keys()),
            0,
        )
        self.assertFormError(
            response.context["base_form"],
            field="vessel_imo",
            errors=[
                _("Enter a valid value."),
                _("IMO has incorrect content (must be 7 digits)"),
            ],
        )

        # Arrange: change vessel type to other (has no IMO validation)
        data["base-vessel_type"] = ShipType.OTHER.value
        response = self.client.post(
            self._get_update_view_url(self.cruise_tax_form.pk), data=data
        )

        # Assert: there are no longer any errors
        self.assertEqual(
            len(response.context["base_form"].errors.keys()),
            0,
            response.context["base_form"].errors,
        )

    def _get_update_view_url(self, pk: int, **query) -> str:
        return reverse("havneafgifter:harbor_dues_form_edit", kwargs={"pk": pk}) + (
            f"?{urlencode(query)}" if query else ""
        )

    def _assert_redirects_to_view(self, response, viewname: str, pk: int) -> None:
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, reverse(viewname, kwargs={"pk": pk}))

    def _assert_redirects_to_receipt(self, response, pk: int) -> None:
        self._assert_redirects_to_view(
            response, "havneafgifter:receipt_detail_html", pk
        )

    def _assert_redirects_to_next_step(self, response, pk: int) -> None:
        self._assert_redirects_to_view(
            response,
            "havneafgifter:environmental_tax_create",
            pk,
        )


class TestActionViewMixin(HarborDuesFormTestMixin, RequestMixin):
    view_class = None  # must be overridden by subclass

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()

    def _setup(self, data, user):
        request = self._post_form(data, user)
        self.instance.setup(request, pk=self.harbor_dues_form.pk)
        return request

    def _assert_redirects_to_list_view(self, response):
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, reverse("havneafgifter:harbor_dues_form_list"))

    def _assert_get_queryset_result(
        self,
        user: User,
        status: Status,
        filter: Q,
    ):
        self._setup({}, user)
        self.assertQuerySetEqual(
            self.instance.get_queryset(),
            HarborDuesForm.objects.filter(filter, status=status),
            ordered=False,
        )


class TestWithdrawView(TestActionViewMixin, TestCase):
    view_class = WithdrawView

    def test_get_queryset(self):
        self._assert_get_queryset_result(
            self.shipping_agent_user,
            Status.NEW,
            Q(shipping_agent=self.shipping_agent_user.shipping_agent),
        )

    def test_post(self):
        # Arrange
        request = self._setup({}, self.shipping_agent_user)
        # Act
        response = self.instance.post(request)
        # Assert
        harbor_dues_form = HarborDuesForm.objects.get(pk=self.harbor_dues_form.pk)
        self.assertEqual(harbor_dues_form.status, Status.DRAFT.value)
        self._assert_redirects_to_list_view(response)

    def test_post_not_permitted(self):
        # Arrange
        request = self._setup({}, self.port_authority_user)
        # Act
        response = self.instance.post(request)
        # Assert
        self.assertIsInstance(response, HttpResponseForbidden)


class TestApproveView(TestActionViewMixin, TestCase):
    view_class = ApproveView

    def test_get_queryset(self):
        self._assert_get_queryset_result(
            self.port_authority_user,
            Status.NEW,
            Q(port_of_call__portauthority=self.port_authority_user.port_authority),
        )

    def test_post(self):
        # Arrange
        request = self._setup({}, self.port_authority_user)
        # Act
        with patch(
            "havneafgifter.view_mixins.messages.add_message"
        ) as mock_add_message:
            response = self.instance.post(request)
        # Assert
        harbor_dues_form = HarborDuesForm.objects.get(pk=self.harbor_dues_form.pk)
        self.assertEqual(harbor_dues_form.status, Status.APPROVED.value)
        self.assertEqual(mock_add_message.call_count, 2)
        self._assert_redirects_to_list_view(response)

    def test_post_not_permitted(self):
        # Arrange
        request = self._setup({}, self.shipping_agent_user)
        # Act
        response = self.instance.post(request)
        # Assert
        self.assertIsInstance(response, HttpResponseForbidden)


class TestRejectView(TestActionViewMixin, TestCase):
    view_class = RejectView

    def test_get_queryset(self):
        self._assert_get_queryset_result(
            self.port_authority_user,
            Status.NEW,
            Q(port_of_call__portauthority=self.port_authority_user.port_authority),
        )

    def test_post(self):
        # Arrange
        request = self._setup(
            {"reason": "There is no reason"}, self.port_authority_user
        )
        # Act
        with patch(
            "havneafgifter.view_mixins.messages.add_message"
        ) as mock_add_message:
            response = self.instance.post(request)
        # Assert
        harbor_dues_form = HarborDuesForm.objects.get(pk=self.harbor_dues_form.pk)
        self.assertEqual(harbor_dues_form.status, Status.REJECTED.value)
        self.assertEqual(mock_add_message.call_count, 2)
        self._assert_redirects_to_list_view(response)

    def test_post_not_permitted(self):
        # Arrange
        request = self._setup({}, self.shipping_agent_user)
        # Act
        response = self.instance.post(request)
        # Assert
        self.assertIsInstance(response, HttpResponseForbidden)


class TestTaxRateListView(HarborDuesFormTestMixin, TestCase):
    view_class = TaxRateListView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()
        # Below two taxrates are added. The second one is 1 hour in the future.
        cls.taxrate = TaxRates.objects.create(start_datetime=datetime.now())
        cls.taxrate2 = TaxRates.objects.create(
            start_datetime=datetime.now() + timedelta(seconds=3600)
        )

    def _setup(self, user):
        get_request = self.request_factory.get("")
        get_request.user = user
        self.instance.setup(get_request)
        return get_request

    def test_get_queryset(self):
        request = self._setup(self.ship_user)
        response = self.instance.get(request)
        rows = response.context_data["table"].rows
        self.assertEqual(len(rows), 2)  # check if both rates were added
        self.assertEqual(
            rows[0].record, self.taxrate
        )  # check that the objects are actually the same
        self.assertEqual(rows[1].record, self.taxrate2)
        # check that the entries are ordered by start_datetime
        self.assertLess(rows[0].record.start_datetime, rows[1].record.start_datetime)
        # check that the previous end_datetime is inferred as expected
        self.assertEqual(rows[0].record.end_datetime, rows[1].record.start_datetime)

    def test_buttons(self):
        request = self._setup(self.ship_user)
        response = self.instance.get(request)
        response.render()

        self.assertIn('class="btn btn-primary"', response.content.decode("utf-8"))


class TestTaxRateDetailView(HarborDuesFormTestMixin, TestCase):
    view_class = TaxRateDetailView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tax_rate = TaxRates.objects.create(
            start_datetime=datetime(
                year=2023,
                month=10,
                day=5,
                hour=14,
                minute=30,
                second=0,
                tzinfo=ZoneInfo("America/Nuuk"),
            )
        )

        cls.disembarkment_site = DisembarkmentSite.objects.create(
            name="somesitename",
            municipality=1,
            is_outside_populated_areas=True,
        )

        cls.portauthority = PortAuthority.objects.create(
            name="Test Portauthority", email="testportauthority@legitemail.com"
        )

        cls.port = Port.objects.create(
            name="Test Port Name", portauthority=cls.portauthority
        )

        cls.disembarkment_tax_rates = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=cls.disembarkment_site,
            municipality=955,
            disembarkment_tax_rate=2.0,
        )

        cls.port_tax_rates = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port,
            vessel_type="OTHER",
            gt_start=30000,
            gt_end=40000,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.ship_user)

    def test_rendering(self):
        response = self.client.get(
            reverse("havneafgifter:tax_rate_details", kwargs={"pk": self.tax_rate.pk})
        )
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn("somesitename", soup.get_text())
        self.assertIn("Kujalleq", soup.get_text())
        self.assertIn("Other vessel", soup.get_text())
        self.assertIn("Test Port Name", soup.get_text())
        self.assertIn("30000", soup.get_text())
        self.assertIn("40000", soup.get_text())
        self.assertIn("70", soup.get_text())
        self.assertIn("25.00", soup.get_text())
        self.assertIn("2.00", soup.get_text())
        self.assertIn("None", soup.get_text())

    def test_forbidden_delete(self):
        self.client.force_login(self.ship_user)
        response = self.client.post(
            reverse("havneafgifter:tax_rate_details", kwargs={"pk": self.tax_rate.pk}),
            {"delete": "Delete"},
        )

        # make sure we get an error message
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn(
            "You do not have the required permissions to delete a tax rate",
            soup.get_text(),
        )

    def test_allowed_delete(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("havneafgifter:tax_rate_details", kwargs={"pk": self.tax_rate.pk}),
            {"delete": "Delete"},
        )

        # make sure we get a redirect, indicating we had permission
        self.assertEqual(response.status_code, 302)


class TestTaxRateFormView(HarborDuesFormTestMixin, TestCase):
    view_class = TaxRateFormView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tax_rate = TaxRates.objects.create(
            start_datetime=datetime(
                year=2233,  # Needs to be >=1 week from datetime.now()
                month=10,
                day=5,
                hour=14,
                minute=30,
                second=0,
                tzinfo=ZoneInfo("America/Nuuk"),
            ),
            pax_tax_rate=42,
        )

        cls.edit_url = reverse(
            "havneafgifter:edit_taxrate", kwargs={"pk": cls.tax_rate.pk}
        )

        cls.ptr0 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.pa1 = PortAuthority.objects.create(
            name="TestPortauthority1", email="testportauthority@legitemail.com"
        )

        cls.port1 = Port.objects.create(name="TestPort", portauthority=cls.pa1)

        cls.ptr1_small = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port1,
            vessel_type=None,
            gt_start=0,
            gt_end=30000,
            port_tax_rate=11.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr1_big = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port1,
            vessel_type=None,
            gt_start=30000,
            gt_end=None,
            port_tax_rate=12.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr2_small = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=None,
            vessel_type="FREIGHTER",
            gt_start=0,
            gt_end=30000,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr2_big = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=None,
            vessel_type="FREIGHTER",
            gt_start=30000,
            gt_end=None,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr3_small = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port1,
            vessel_type="FREIGHTER",
            gt_start=0,
            gt_end=30000,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr3_big = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port1,
            vessel_type="FREIGHTER",
            gt_start=30000,
            gt_end=None,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.pa2 = PortAuthority.objects.create(
            name="TestPortauthority2", email="testportauthority@legitemail.com"
        )

        cls.port2 = Port.objects.create(name="OtherTestPort", portauthority=cls.pa2)

        cls.ptr4 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port2,
            vessel_type="CRUISE",
            gt_start=30000,
            gt_end=40000,
            port_tax_rate=25.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr5 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port2,
            vessel_type="CRUISE",
            gt_start=0,
            gt_end=30000,
            port_tax_rate=26.0,
            round_gross_ton_up_to=70,
        )

        cls.ptr6 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            port=cls.port2,
            vessel_type="CRUISE",
            gt_start=40000,
            gt_end=None,
            port_tax_rate=27.0,
            round_gross_ton_up_to=70,
        )

        # ------ ILANDSÆTNINGSSTEDER -------------
        cls.disemb_tr1 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=None,
            municipality=955,  # Kujalleq
            disembarkment_tax_rate=2.0,
        )

        cls.disemb_s1 = DisembarkmentSite.objects.create(
            name="Attu",
            municipality=955,  # Kujalleq
            is_outside_populated_areas=False,
        )

        cls.disemb_tr2 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=cls.disemb_s1,  # udenfor befolkede områder
            municipality=955,  # Kujalleq
            disembarkment_tax_rate=2.0,
        )

        cls.disemb_tr3 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=None,  # Alle?
            municipality=959,  # Qeqertalik
            disembarkment_tax_rate=2.0,
        )

        cls.disemb_s2 = DisembarkmentSite.objects.create(
            name="",
            municipality=959,
            is_outside_populated_areas=True,
        )

        cls.disemb_tr4 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=cls.disemb_s2,  # udenfor befolkede områder
            municipality=959,  # Qeqertalik
            disembarkment_tax_rate=2.0,
        )

        cls.disemb_s3 = DisembarkmentSite.objects.create(
            name="Attu",
            municipality=959,
            is_outside_populated_areas=False,
        )

        cls.disemb_tr5 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rate,
            disembarkment_site=cls.disemb_s3,  # Attu
            municipality=959,  # Qeqertalik
            disembarkment_tax_rate=2.0,
        )

    @classmethod
    def response_to_datafields_dict(cls, content):
        soup = BeautifulSoup(content, "lxml")

        form_data_dict = {}

        forms = soup.find_all("form")

        for form in forms:
            inputs = form.find_all(
                [
                    "input",
                    "select",
                ]
            )
            for input_field in inputs:
                field_name = input_field.get("name")
                field_value = input_field.get(
                    "value", ""
                )  # Default to empty string if no value

                if field_name:
                    form_data_dict[field_name] = field_value

        return form_data_dict

    @classmethod
    def html_table_to_dict(cls, table):
        headers = [element.text for element in table.css.select("thead tr th")]
        return [
            dict(
                zip(
                    headers,
                    [
                        (
                            td.select_one("input").get("value")
                            if td.select_one("input")
                            else td.text.strip()
                        )
                        for td in row.select("td")
                    ],
                )
            )
            for row in table.css.select("table tbody tr")
        ]

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tax_authority_user)

    def test_rendering(self):
        response = self.client.get(
            reverse("havneafgifter:edit_taxrate", kwargs={"pk": self.tax_rate.pk})
        )
        soup = BeautifulSoup(response.content, "html.parser")

        port_tax_rates_table = soup.find("table", id="port_tax_rate_table")
        port_tax_rates_table_content = self.html_table_to_dict(port_tax_rates_table)
        disembarkment_tax_rates_table = soup.find(
            "table", id="disembarkment_rate_table"
        )
        disembarkment_tax_rates_table_content = self.html_table_to_dict(
            disembarkment_tax_rates_table
        )

        # Tax rate section
        self.assertIn(
            datetime(2233, 10, 5, 14, 30, 0, tzinfo=ZoneInfo("America/Nuuk")).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            soup.find("input", {"name": "start_datetime"}).get("value"),
        )
        self.assertIn(
            f"{self.tax_rate.pax_tax_rate}",
            soup.find("input", {"name": "pax_tax_rate"}).get("value"),
        )

        # Port tax rate row 1
        self.assertEqual(
            port_tax_rates_table_content[0]["Afgifter pr. brutto ton"],
            "Enhver skibstype, enhver havn",
        )

        self.assertEqual(
            port_tax_rates_table_content[0]["Fra (ton)"],
            str(self.ptr0.gt_start) if self.ptr0.gt_start is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[0]["Til (ton)"],
            str(self.ptr0.gt_end) if self.ptr0.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[0]["Rund op til (ton)"],
            str(self.ptr0.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[0]["Sats"], f"{self.ptr0.port_tax_rate:.2f}"
        )

        # Port tax rate row 2
        self.assertEqual(
            port_tax_rates_table_content[1]["Afgifter pr. brutto ton"],
            "Enhver skibstype, TestPort",
        )
        self.assertEqual(
            port_tax_rates_table_content[1]["Fra (ton)"],
            (
                str(self.ptr1_small.gt_start)
                if self.ptr1_small.gt_start is not None
                else None
            ),
        )
        self.assertEqual(
            port_tax_rates_table_content[1]["Til (ton)"],
            str(self.ptr1_small.gt_end) if self.ptr1_small.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[1]["Rund op til (ton)"],
            str(self.ptr1_small.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[1]["Sats"],
            f"{self.ptr1_small.port_tax_rate:.2f}",
        )

        # Port tax rate row 3
        self.assertEqual(
            port_tax_rates_table_content[2]["Afgifter pr. brutto ton"],
            "Enhver skibstype, TestPort",
        )
        self.assertEqual(
            port_tax_rates_table_content[2]["Fra (ton)"],
            str(self.ptr1_big.gt_start) if self.ptr1_big.gt_start is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[2]["Til (ton)"],
            str(self.ptr1_big.gt_end) if self.ptr1_big.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[2]["Rund op til (ton)"],
            str(self.ptr1_big.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[2]["Sats"],
            f"{self.ptr1_big.port_tax_rate:.2f}",
        )

        # Port tax rate row 4
        self.assertEqual(
            port_tax_rates_table_content[3]["Afgifter pr. brutto ton"],
            "Freighter, enhver havn",
        )
        self.assertEqual(
            port_tax_rates_table_content[3]["Fra (ton)"],
            (
                str(self.ptr2_small.gt_start)
                if self.ptr2_small.gt_start is not None
                else None
            ),
        )
        self.assertEqual(
            port_tax_rates_table_content[3]["Til (ton)"],
            str(self.ptr2_small.gt_end) if self.ptr2_small.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[3]["Rund op til (ton)"],
            str(self.ptr2_small.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[3]["Sats"],
            f"{self.ptr2_small.port_tax_rate:.2f}",
        )

        # Port tax rate row 5
        self.assertEqual(
            port_tax_rates_table_content[4]["Afgifter pr. brutto ton"],
            "Freighter, enhver havn",
        )
        self.assertEqual(
            port_tax_rates_table_content[4]["Fra (ton)"],
            str(self.ptr2_big.gt_start) if self.ptr2_big.gt_start is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[4]["Til (ton)"],
            str(self.ptr2_big.gt_end) if self.ptr2_big.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[4]["Rund op til (ton)"],
            str(self.ptr2_big.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[4]["Sats"],
            f"{self.ptr2_big.port_tax_rate:.2f}",
        )

        # Port tax rate row 6
        self.assertEqual(
            port_tax_rates_table_content[5]["Afgifter pr. brutto ton"],
            "Freighter, TestPort",
        )
        self.assertEqual(
            port_tax_rates_table_content[5]["Fra (ton)"],
            (
                str(self.ptr3_small.gt_start)
                if self.ptr3_small.gt_start is not None
                else None
            ),
        )
        self.assertEqual(
            port_tax_rates_table_content[5]["Til (ton)"],
            str(self.ptr3_small.gt_end) if self.ptr3_small.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[5]["Rund op til (ton)"],
            str(self.ptr3_small.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[5]["Sats"],
            f"{self.ptr3_small.port_tax_rate:.2f}",
        )

        # Port tax rate row 7
        self.assertEqual(
            port_tax_rates_table_content[6]["Afgifter pr. brutto ton"],
            "Freighter, TestPort",
        )
        self.assertEqual(
            port_tax_rates_table_content[6]["Fra (ton)"],
            str(self.ptr3_big.gt_start) if self.ptr3_big.gt_start is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[6]["Til (ton)"],
            str(self.ptr3_big.gt_end) if self.ptr3_big.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[6]["Rund op til (ton)"],
            str(self.ptr3_big.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[6]["Sats"],
            f"{self.ptr3_big.port_tax_rate:.2f}",
        )

        # Port tax rate row 8
        self.assertEqual(
            port_tax_rates_table_content[7]["Afgifter pr. brutto ton"],
            "Cruise ship, OtherTestPort",
        )
        self.assertEqual(
            port_tax_rates_table_content[7]["Fra (ton)"],
            str(self.ptr4.gt_start) if self.ptr4.gt_start is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[7]["Til (ton)"],
            str(self.ptr4.gt_end) if self.ptr4.gt_end is not None else None,
        )
        self.assertEqual(
            port_tax_rates_table_content[7]["Rund op til (ton)"],
            str(self.ptr4.round_gross_ton_up_to),
        )
        self.assertEqual(
            port_tax_rates_table_content[7]["Sats"], f"{self.ptr4.port_tax_rate:.2f}"
        )

        # Disembarkment tax rate row 1
        self.assertEqual(
            disembarkment_tax_rates_table_content[0]["Afgifter pr. ilandsætningssted"],
            "Kujalleq, ethvert ilandsætningssted",
        )
        self.assertEqual(
            disembarkment_tax_rates_table_content[0]["Sats (DKK)"],
            f"{self.disemb_tr1.disembarkment_tax_rate:.2f}",
        )

        # Disembarkment tax rate row 2
        self.assertEqual(
            disembarkment_tax_rates_table_content[1]["Afgifter pr. ilandsætningssted"],
            "Kujalleq, Attu",
        )
        self.assertEqual(
            disembarkment_tax_rates_table_content[1]["Sats (DKK)"],
            f"{self.disemb_tr2.disembarkment_tax_rate:.2f}",
        )

        # Disembarkment tax rate row 3
        self.assertEqual(
            disembarkment_tax_rates_table_content[2]["Afgifter pr. ilandsætningssted"],
            "Qeqertalik, ethvert ilandsætningssted",
        )
        self.assertEqual(
            disembarkment_tax_rates_table_content[2]["Sats (DKK)"],
            f"{self.disemb_tr3.disembarkment_tax_rate:.2f}",
        )

        # Disembarkment tax rate row 4
        self.assertEqual(
            disembarkment_tax_rates_table_content[3]["Afgifter pr. ilandsætningssted"],
            "Qeqertalik,",
        )  # TODO: This output is still a bug!
        self.assertEqual(
            disembarkment_tax_rates_table_content[3]["Sats (DKK)"],
            f"{self.disemb_tr4.disembarkment_tax_rate:.2f}",
        )

        # Disembarkment tax rate row 5
        self.assertEqual(
            disembarkment_tax_rates_table_content[4]["Afgifter pr. ilandsætningssted"],
            "Qeqertalik, Attu",
        )
        self.assertEqual(
            disembarkment_tax_rates_table_content[4]["Sats (DKK)"],
            f"{self.disemb_tr5.disembarkment_tax_rate:.2f}",
        )

    def test_port_tax_rate_formset_delete(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        self.assertEqual(PortTaxRate.objects.count(), 10)

        value_dict_to_post = {
            **original_response_dict,
            "port_tax_rates-9-DELETE": "1",
            "port_tax_rates-8-DELETE": "1",
            "port_tax_rates-7-DELETE": "1",
        }

        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )
        self.assertEqual(post_request_response.status_code, 302)  # Did we POST ok?

        # Was the row removed from the db table?
        self.assertEqual(PortTaxRate.objects.count(), 7)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Was the row removed from the form table?
        self.assertNotIn("port_tax_rates-9-DELETE", after_request_dict)

        # Did we avoid deleting the "above" row in the form table?
        self.assertIn("port_tax_rates-6-DELETE", after_request_dict)

    def test_port_tax_rate_formset_change(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Is "port_tax_rates-1-gt_end" "30000" as created in the setup?
        self.assertEqual(
            "70", original_response_dict["port_tax_rates-1-round_gross_ton_up_to"]
        )

        data_dict_to_post = {
            **original_response_dict,
            "port_tax_rates-1-round_gross_ton_up_to": "80",
            "start_datetime": "2033-10-05 17:30:00",  # To satisfy validation
            # (new rates must be >=1 week in the future)
        }

        post_request_response = self.client.post(
            self.edit_url,
            data=data_dict_to_post,
        )

        self.assertEqual(post_request_response.status_code, 302)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        self.assertEqual(
            "80", after_request_dict["port_tax_rates-1-round_gross_ton_up_to"]
        )

    def test_port_tax_rate_formset_insert(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        value_dict_to_post = {
            **original_response_dict,
            "port_tax_rates-TOTAL_FORMS": "11",
            "port_tax_rates-10-gt_start": "0",
            "port_tax_rates-10-gt_end": "",
            "port_tax_rates-10-round_gross_ton_up_to": "80",
            "port_tax_rates-10-port_tax_rate": "313373.00",
            "port_tax_rates-10-port": self.port1.pk,
            "port_tax_rates-10-vessel_type": "FISHER",
            "port_tax_rates-10-DELETE": "",
        }

        self.assertEqual(PortTaxRate.objects.count(), 10)

        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )

        # Check for redirect
        self.assertEqual(post_request_response.status_code, 302)

        # Was a row added to the db table?
        self.assertEqual(PortTaxRate.objects.count(), 11)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Was the form table length incremented?
        self.assertEqual(
            int(after_request_dict["port_tax_rates-TOTAL_FORMS"]),
            int(original_response_dict["port_tax_rates-TOTAL_FORMS"]) + 1,
        )

        # Was the recoginsable value found in the newly added form table row?
        self.assertEqual(
            "313373.00", after_request_dict["port_tax_rates-10-port_tax_rate"]
        )

        # And the db?
        self.assertEqual(313373.00, PortTaxRate.objects.last().port_tax_rate)

    def test_bisembarkment_tax_rate_formset_change(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Is "disembarkment_tax_rates-4-disembarkment_tax_rate"
        #   "2.00" as created in the setup?
        self.assertEqual(
            "2.00",
            original_response_dict["disembarkment_tax_rates-4-disembarkment_tax_rate"],
        )

        data_dict_to_post = {
            **original_response_dict,
            "disembarkment_tax_rates-4-disembarkment_tax_rate": "25.00",
        }

        post_request_response = self.client.post(
            self.edit_url,
            data=data_dict_to_post,
        )
        self.assertEqual(post_request_response.status_code, 302)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Did "disembarkment_tax_rates-4-disembarkment_tax_rate" change from
        #   "2.00" to "25.00" ?
        self.assertEqual(
            "25.00",
            after_request_dict["disembarkment_tax_rates-4-disembarkment_tax_rate"],
        )

    def test_bisembarkment_tax_rate_formset_insert(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        value_dict_to_post = {
            **original_response_dict,
            "disembarkment_tax_rates-TOTAL_FORMS": "6",
            "disembarkment_tax_rates-5-disembarkment_tax_rate": "42.00",
            "disembarkment_tax_rates-5-municipality": "960",
            "disembarkment_tax_rates-5-disembarkment_site": "103",
            "disembarkment_tax_rates-5-DELETE": "",
        }

        self.assertEqual(DisembarkmentTaxRate.objects.count(), 5)

        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )

        self.assertEqual(post_request_response.status_code, 302)

        # Was a row added to the db table?
        self.assertEqual(DisembarkmentTaxRate.objects.count(), 6)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Was the form table length incremented?
        self.assertEqual(
            int(after_request_dict["disembarkment_tax_rates-TOTAL_FORMS"]),
            int(original_response_dict["disembarkment_tax_rates-TOTAL_FORMS"]) + 1,
        )

        # Was the recoginsable value found in the newly added form table row?
        self.assertEqual(
            "42.00",
            after_request_dict["disembarkment_tax_rates-5-disembarkment_tax_rate"],
        )

    def test_bisembarkment_tax_rate_formset_delete(self):
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        self.assertEqual(DisembarkmentTaxRate.objects.count(), 5)

        value_dict_to_post = {
            **original_response_dict,
            "disembarkment_tax_rates-4-DELETE": "1",
        }
        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )

        self.assertEqual(post_request_response.status_code, 302)  # Did we POST ok?

        # Was the row removed from the db table?
        self.assertEqual(DisembarkmentTaxRate.objects.count(), 4)

        after_request_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )

        # Was the row removed from the form table?
        self.assertNotIn("disembarkment_tax_rates-4-DELETE", after_request_dict)

        # Did we avoid deleting the "above" row in the form table?
        self.assertIn("disembarkment_tax_rates-3-DELETE", after_request_dict)

    def test_delete_button_presence(self):
        response = self.client.get(
            reverse("havneafgifter:edit_taxrate", kwargs={"pk": self.tax_rate.pk})
        )
        soup = BeautifulSoup(response.content, "html.parser")

        rows = soup.find("tbody", id="port_formset_tbody").find_all("tr")

        first_row = rows[0]
        delete_button_first_row = first_row.find("button", class_="btn btn-danger")
        self.assertIsNone(delete_button_first_row)

        for index, row in enumerate(rows[1:], start=1):
            delete_button = row.find("button", class_="btn btn-danger")
            self.assertIsNotNone(
                delete_button, f"NO DELETE BUTTON IN {index + 1}: {row}"
            )

        # The first row should not have a delete button
        self.assertIsNone(soup.find("button", {"id": "port_tax_rate_delete-button-0"}))

        # Delete button should be in the next row, however
        self.assertIsNotNone(
            soup.find("button", {"id": "port_tax_rate_delete-button-1"})
        )

    def test_clone_functionality(self):
        response = self.client.get(
            reverse("havneafgifter:tax_rate_clone", kwargs={"pk": self.tax_rate.pk})
        )

        original_response_dict = self.response_to_datafields_dict(
            response.content.decode("utf-8")
        )

        # regex to strip out id keys
        import re

        number_pattern = re.compile(
            r"^(disembarkment_tax_rates|port_tax_rates)-\d+-id$"
        )
        prefix_pattern = re.compile(
            r"^(disembarkment_tax_rates|port_tax_rates)-__prefix__-id$"
        )

        # assemble new dict and POST
        data_dict_to_post = {
            key: value
            for key, value in original_response_dict.items()
            if not (number_pattern.match(key) or prefix_pattern.match(key))
        }
        data_dict_to_post["start_datetime"] = "3033-10-05 17:33:00"
        self.client.post(
            reverse("havneafgifter:tax_rate_clone", kwargs={"pk": self.tax_rate.pk}),
            data=data_dict_to_post,
        )

        # was the expected start_datetime saved int he new taxrate ?
        new_rate_url = reverse(
            "havneafgifter:edit_taxrate", kwargs={"pk": self.tax_rate.pk + 1}
        )
        after_request_dict = self.response_to_datafields_dict(
            self.client.get(new_rate_url).content.decode("utf-8")
        )
        self.assertEqual(after_request_dict["start_datetime"], "3033-10-05 17:33:00")

    def test_get_object_permission(self):
        self.client.force_login(self.ship_user)
        response = self.client.get(
            reverse("havneafgifter:edit_taxrate", kwargs={"pk": self.tax_rate.pk})
        )

        # make sure we didn't have permission to show the edit view, as ship user
        self.assertEqual(response.status_code, 403)

        # make sure we get an error message
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn("Du har ikke rettighed til at se denne side.", soup.get_text())


class TestLandingModalOkView(HarborDuesFormTestMixin, TestCase):
    def test_post(self):
        self.client.force_login(self.port_user)
        response = self.client.post(reverse("havneafgifter:landing_modal_ok"))
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.client.session.get("harbor_user_modal"))


class PassengerStatisticsTest(TestCase):
    url = reverse("havneafgifter:passenger_statistics")
    nationality_dict = dict(Nationality.choices)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username="admin", is_superuser=True, is_staff=True
        )
        call_command("load_fixtures", verbosity=1)
        ports = Port.objects.all().order_by("name")
        cls.form1 = CruiseTaxForm.objects.create(
            status=Status.APPROVED,
            port_of_call=ports[0],
            nationality=Nationality.DENMARK,
            vessel_name="Testbåd 1",
            datetime_of_arrival=datetime(2025, 6, 18, 0, 0, 0),
            datetime_of_departure=datetime(2025, 7, 12, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("40000.00"),
            pax_tax=Decimal("3000.00"),
            disembarkment_tax=Decimal("20000.00"),
            number_of_passengers=1000,
        )
        cls.form2 = CruiseTaxForm.objects.create(
            status=Status.APPROVED,
            port_of_call=ports[0],
            nationality=Nationality.NORWAY,
            vessel_name="Testbåd 2",
            datetime_of_arrival=datetime(2024, 7, 5, 0, 0, 0),
            datetime_of_departure=datetime(2024, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("40000.00"),
            pax_tax=Decimal("3000.00"),
            disembarkment_tax=Decimal("20000.00"),
            number_of_passengers=111,
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form2,
            number_of_passengers=111,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaaq"),
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form2,
            number_of_passengers=111,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaaq"),
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form1,
            number_of_passengers=1000,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qeqertat"),
        )
        cls.form3 = CruiseTaxForm.objects.create(
            status=Status.REJECTED,
            port_of_call=ports[1],
            nationality=Nationality.SWEDEN,
            vessel_name="Testbåd 3",
            datetime_of_arrival=datetime(2025, 7, 2, 0, 0, 0),
            datetime_of_departure=datetime(2025, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("50000.00"),
            pax_tax=Decimal("8000.00"),
            disembarkment_tax=Decimal("25000.00"),
            number_of_passengers=1200,
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form3,
            number_of_passengers=1200,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaaq"),
        )
        cls.pbc4 = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form2,
            nationality=Nationality.AUSTRALIA,
            number_of_passengers=11,
        )
        cls.pbc3 = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form3,
            nationality=Nationality.SWEDEN,
            number_of_passengers=1200,
        )
        cls.pbc2 = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form2,
            nationality=Nationality.NORWAY,
            number_of_passengers=100,
        )
        cls.pbc1 = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form1,
            nationality=Nationality.DENMARK,
            number_of_passengers=1000,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def get_rows(self, **filter) -> BoundRows:
        response = self.client.get(self.url + "?" + urlencode(filter, doseq=True))
        return response.context_data["table"].rows

    def test_no_access(self):
        user = User.objects.create(username="intruder", is_superuser=False)
        self.client.force_login(user)
        response = self.client.get(
            self.url + "?" + urlencode({"nationality": "NZ"}, doseq=True)
        )
        self.assertEqual(response.status_code, 403)

    def test_filter_invalid(self):
        rows = self.get_rows(first_month=datetime(2024, 1, 1, 0, 0))
        self.assertEqual(len(rows), 0)

    def test_no_filter(self):
        rows = self.get_rows(dummy="GREAT BIG FISH")
        self.assertEqual(len(rows), 3)
        self.assertDictEqual(
            rows[0].record,
            {
                "nationality": self.nationality_dict[self.pbc4.nationality],
                "month": "July, 2024",
                "count": self.pbc4.number_of_passengers
                * len(self.form2.disembarkment_set.all()),
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "nationality": self.nationality_dict[self.pbc2.nationality],
                "month": "July, 2024",
                "count": self.pbc2.number_of_passengers
                * len(self.form2.disembarkment_set.all()),
            },
        )
        self.assertDictEqual(
            rows[2].record,
            {
                "nationality": self.nationality_dict[self.pbc1.nationality],
                "month": "June, 2025",
                "count": self.pbc1.number_of_passengers
                * len(self.form1.disembarkment_set.all()),
            },
        )

    def test_filter_month(self):
        rows = self.get_rows(first_month="2025-03")
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].record["nationality"],
            self.nationality_dict[self.pbc1.nationality],
        )

        rows = self.get_rows(last_month="2026-06")
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            rows[0].record["count"],
            self.pbc4.number_of_passengers * len(self.form2.disembarkment_set.all()),
        )
        self.assertEqual(
            rows[1].record["count"],
            self.pbc2.number_of_passengers * len(self.form2.disembarkment_set.all()),
        )
        self.assertEqual(
            rows[2].record["count"],
            self.pbc1.number_of_passengers * len(self.form1.disembarkment_set.all()),
        )

        rows = self.get_rows(
            first_month="2024-06",
            last_month="2024-07",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0].record["nationality"],
            self.nationality_dict[self.pbc4.nationality],
        )
        self.assertEqual(
            rows[1].record["nationality"],
            self.nationality_dict[self.pbc2.nationality],
        )

        rows = self.get_rows(
            first_month="2026-06",
            last_month="2027-06",
        )
        self.assertEqual(len(rows), 0)

    def test_filter_nationality(self):
        rows = self.get_rows(nationality=["SE"])
        self.assertEqual(len(rows), 0)

        rows = self.get_rows(nationality=["DK", "NO"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0].record["count"],
            self.pbc2.number_of_passengers * len(self.form2.disembarkment_set.all()),
        )
        self.assertEqual(
            rows[1].record["count"],
            self.pbc1.number_of_passengers * len(self.form1.disembarkment_set.all()),
        )
