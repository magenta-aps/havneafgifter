import copy
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import ANY, Mock, patch
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db.models import Q
from django.forms import BaseFormSet
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.test import RequestFactory, TestCase
from django.urls import reverse
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
    EnvironmentalTaxCreateView,
    HandleNotificationMailMixin,
    HarborDuesFormCreateView,
    HarborDuesFormListView,
    HarborDuesFormUpdateView,
    PassengerTaxCreateView,
    PreviewPDFView,
    ReceiptDetailView,
    RejectView,
    SignupVesselView,
    TaxRateDetailView,
    TaxRateFormView,
    TaxRateListView,
    UpdateVesselView,
    WithdrawView,
    _CruiseTaxFormSetView,
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
                "type": "PASSENGER",
                "name": "Boaty McBoatface",
                "owner": "Joakim von And",
                "master": "Peder Dingo",
                "gross_tonnage": 1234,
            },
        )

        vessel_form = Vessel.objects.get(imo=self.ship_user.username)

        self.assertEqual(vessel_form.type, "PASSENGER")
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

    def test_response_prevents_caching(self):
        self.client.force_login(self.shipping_agent_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        self._assert_response_prevents_caching(response)

    @parametrize(
        "vessel_type,no_port_of_call,model_class,next_view_name",
        [
            # Test 1: user creates harbor dues form and is sent directly to receipt
            (
                ShipType.FREIGHTER,
                False,
                HarborDuesForm,
                "havneafgifter:receipt_detail_html",
            ),
            # Test 2: user creates cruise tax form with a port of call, and is sent to
            # the passenger tax form.
            (
                ShipType.CRUISE,
                False,
                CruiseTaxForm,
                "havneafgifter:passenger_tax_create",
            ),
            # Test 3: user creates cruise tax form without a port of call, and is sent
            # to the environmental tax form.
            (
                ShipType.CRUISE,
                True,
                CruiseTaxForm,
                "havneafgifter:environmental_tax_create",
            ),
        ],
    )
    def test_creates_model_instance_depending_on_vessel_type(
        self,
        vessel_type,
        no_port_of_call,
        model_class,
        next_view_name,
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
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            reverse(next_view_name, kwargs={"pk": instance.pk}),
        )

    def test_ship_user(self):
        self.client.force_login(self.ship_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        soup = BeautifulSoup(response.content, "html.parser")
        field = soup.find("input", attrs={"name": "vessel_imo"})
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
        data = copy.copy(self.harbor_dues_form_data_pk)
        data["status"] = status
        user = User.objects.get(username=username)
        with patch.object(
            self.instance, "handle_notification_mail"
        ) as mock_handle_notification_mail:
            # Act
            request = self._post_form(data, user)
            response = self.instance.post(request)
            # Assert
            if permitted:
                self.assertIsInstance(response, HttpResponseRedirect)
                if email_expected:
                    # Assert that we call the `_send_email` method as expected
                    if user.user_type == UserType.SHIP:
                        mail_class = OnSendToAgentMail
                    else:
                        mail_class = OnSubmitForReviewMail
                    call_count = 1 if mail_class == OnSendToAgentMail else 2
                    self.assertEqual(
                        mock_handle_notification_mail.call_count, call_count
                    )
            else:
                # Assert that we receive a 403 error response
                self.assertIsInstance(response, HttpResponseForbidden)


class TestCruiseTaxFormSetView(
    ParametrizedTestCase, HarborDuesFormTestMixin, RequestMixin, TestCase
):
    view_class = _CruiseTaxFormSetView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()
        cls.instance._cruise_tax_form = cls.cruise_tax_draft_form

    @parametrize(
        "username,status,can_access",
        [
            ("shipping_agent", Status.DRAFT, True),
            ("shipping_agent", Status.NEW, False),
            ("shipping_agent", Status.REJECTED, True),
            ("port_auth", Status.DRAFT, False),
            ("port_auth", Status.NEW, False),
            ("port_auth", Status.REJECTED, True),
        ],
    )
    def test_setup(self, username: str, status: Status, can_access: bool):
        user, obj = self._call_setup(username, status)
        if can_access:
            self.assertEqual(self.instance._cruise_tax_form, obj)
        else:
            self.assertIsNone(self.instance._cruise_tax_form)

    def _assert_get_form_returns_expected_formset(self):
        self._get(self.shipping_agent_user)
        formset = self.instance.get_form()
        self.assertIsInstance(formset, BaseFormSet)
        self.assertIs(formset.form, self.view_class.form_class)
        self.assertFalse(formset.can_order)
        self.assertFalse(formset.can_delete)
        self.assertEqual(formset.extra, 0)

    def _assert_get_context_data_includes_formset(self, name):
        self._get(self.shipping_agent_user)
        context_data = self.instance.get_context_data()
        self.assertIsInstance(context_data[name], BaseFormSet)

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


class TestPassengerTaxCreateView(TestCruiseTaxFormSetView):
    view_class = PassengerTaxCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
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
        self._assert_response(
            self.unprivileged_user.username,
            HttpResponseForbidden,
            total_number_of_passengers=0,
        )

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self._get(self.shipping_agent_user)
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {
                    "nationality": nationality,
                    "number_of_passengers": (
                        0
                        if nationality != Nationality.BELGIUM
                        else self._existing_passengers_by_country.number_of_passengers
                    ),
                    "pk": (
                        None
                        if nationality != Nationality.BELGIUM
                        else self._existing_passengers_by_country.pk
                    ),
                }
                for nationality in Nationality
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("passengers_by_country_formset")

    def test_form_valid_creates_objects(self):
        # Arrange
        request = self._post_formset(
            # Add new entry for Australia (index 0)
            {"number_of_passengers": 42},
            # Add new (empty) entry for Austria (index 1)
            {"number_of_passengers": 0},
            # Update existing entry for Belgium (index 2)
            {"number_of_passengers": 42},
            # Submit correct number of total passengers
            total_number_of_passengers=2 * 42,
        )
        # Act: trigger DB insert logic
        self.instance.post(request)
        # Assert: verify that the specified `PassengersByCountry` objects are
        # created.
        self.assertQuerySetEqual(
            self.cruise_tax_draft_form.passengers_by_country.values(
                "cruise_tax_form",
                "nationality",
                "number_of_passengers",
            ),
            [
                {
                    "cruise_tax_form": self.cruise_tax_draft_form.pk,
                    "nationality": Nationality.AUSTRALIA.value,
                    "number_of_passengers": 42,
                },
                {
                    "cruise_tax_form": self.cruise_tax_draft_form.pk,
                    "nationality": Nationality.BELGIUM.value,
                    "number_of_passengers": 42,
                },
            ],
        )

    def test_total_number_of_passengers_validation(self):
        request = self._post_formset(
            {"number_of_passengers": 40},
            {"number_of_passengers": 40},
            total_number_of_passengers=100,
        )
        response = self.instance.post(request)
        context_data = response.context_data
        passengers_total_form = context_data["passengers_total_form"]
        passengers_by_country_formset = context_data["passengers_by_country_formset"]
        self.assertFalse(passengers_total_form.is_valid())
        self.assertTrue(passengers_by_country_formset.is_valid())

    def test_total_number_of_passengers_wrong_input(self):
        request = self._post_formset(
            {"number_of_passengers": 40},
            {"number_of_passengers": "hello"},
            total_number_of_passengers=100,
        )
        response = self.instance.post(request)
        self.assertIsInstance(response, HttpResponseBadRequest)


class TestEnvironmentalTaxCreateView(TestCruiseTaxFormSetView):
    view_class = EnvironmentalTaxCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create an existing `Disembarkment` object (which is updated during the
        # test.)
        cls._disembarkment_site_1 = DisembarkmentSite.objects.first()
        cls._disembarkment_site_2 = DisembarkmentSite.objects.all()[1]
        cls._existing_disembarkment = Disembarkment.objects.create(
            cruise_tax_form=cls.cruise_tax_draft_form,
            disembarkment_site=cls._disembarkment_site_1,
            number_of_passengers=10,
        )

    def test_permissions_checked(self):
        self._assert_response(self.shipping_agent_user.username, HttpResponse)
        self._assert_response(self.unprivileged_user.username, HttpResponseForbidden)

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self._get(self.shipping_agent_user)
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {
                    "disembarkment_site": ds.pk,
                    "number_of_passengers": (
                        0
                        if ds != self._existing_disembarkment.disembarkment_site
                        else self._existing_disembarkment.number_of_passengers
                    ),
                    "pk": (
                        None
                        if ds != self._existing_disembarkment.disembarkment_site
                        else self._existing_disembarkment.pk
                    ),
                }
                for ds in DisembarkmentSite.objects.all()
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("disembarkment_formset")

    def test_form_valid_sends_email_to_agent(self):
        self._post_formset(
            # Add new entry for Australia (index 0)
            {"number_of_passengers": 42},
            # Add new (empty) entry for Austria (index 1)
            {"number_of_passengers": 0},
            # Update existing entry for Belgium (index 2)
            {"number_of_passengers": 42},
            user=self.ship_user,
            # Submit correct number of total passengers
            total_number_of_passengers=2 * 42,
        )
        with patch.object(
            self.instance, "handle_notification_mail"
        ) as mock_handle_notification_mail:
            # Act: trigger DB insert logic
            self.instance.form_valid(self.instance.get_form())
            # Assert: verify that we call the `_send_email` method as expected
            mock_handle_notification_mail.assert_called_once_with(
                OnSendToAgentMail,
                self.instance._cruise_tax_form,
            )

    def test_form_valid_creates_objects(self):
        # Arrange
        self._post_formset(
            # Update existing entry for first disembarkment site (index 0)
            {"number_of_passengers": 42},
            # Add new entry for next disembarkment site (index 1)
            {"number_of_passengers": 42},
            # Submit cruise tax form for review
            status=Status.NEW.value,
        )
        with patch.object(
            self.instance, "handle_notification_mail"
        ) as mock_handle_notification_mail:
            # Act: trigger DB insert logic
            self.instance.form_valid(self.instance.get_form())
            # Assert: verify that the specified `Disembarkment` objects are
            # created.
            self.assertQuerySetEqual(
                self.cruise_tax_draft_form.disembarkment_set.values(
                    "cruise_tax_form",
                    "disembarkment_site",
                    "number_of_passengers",
                ).order_by("disembarkment_site__pk"),
                [
                    {
                        "cruise_tax_form": self.cruise_tax_draft_form.pk,
                        "disembarkment_site": ds.pk,
                        "number_of_passengers": 42,
                    }
                    for ds in [
                        self._disembarkment_site_1,
                        self._disembarkment_site_2,
                    ]
                ],
            )
            # Assert: verify that we call the `_send_email` method as expected
            self.assertEqual(mock_handle_notification_mail.call_count, 2)

    def test_form_valid_checks_cruise_tax_form_on_submit(self):
        """If user clicks "Submit for review", the `CruiseTaxForm` created in "step 1"
        must be validated before it can be submitted. Otherwise, the user must be
        informed of the validation errors and sent back to "step 1."
        """
        # Arrange: set up view to process an invalid `CruiseTaxForm` instance.
        self.instance._cruise_tax_form.gross_tonnage = None
        # Arrange: user clicks "Submit" (rather than "Save as draft")
        self._post_formset(status=Status.NEW.value)
        # Act
        with patch("havneafgifter.views.messages.error") as mock_messages_error:
            response = self.instance.form_valid(self.instance.get_form())
            # Assert: an error message is displayed
            mock_messages_error.assert_called_once()
            # Assert: we receive the expected redirect back to "step 1" as the cruise
            # tax form is not valid.
            self.assertIsInstance(response, HttpResponseRedirect)
            self.assertEqual(
                response.url,
                "%s?status=NEW"
                % reverse(
                    "havneafgifter:draft_edit",
                    kwargs={"pk": self.instance._cruise_tax_form.pk},
                ),
            )


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
            datetime_of_arrival=datetime(2024, 7, 1, 0, 0, 0),
            datetime_of_departure=datetime(2024, 7, 15, 0, 0, 0),
            gross_tonnage=1000,
            vessel_type=ShipType.CRUISE,
            harbour_tax=Decimal("40000.00"),
            pax_tax=Decimal("3000.00"),
            disembarkment_tax=Decimal("20000.00"),
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form2,
            number_of_passengers=1,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaq"),
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
        )
        Disembarkment.objects.create(
            cruise_tax_form=cls.form3,
            number_of_passengers=2,
            disembarkment_site=DisembarkmentSite.objects.get(name="Qaanaq"),
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
        self.assertEqual(len(rows), 3)
        self.assertDictEqual(
            rows[0].record,
            {
                "id": self.form1.id,
                "port_of_call": "Aasiaat",
                "vessel_type": "Freighter",
                "municipality": None,
                "site": None,
                "disembarkment_tax_sum": Decimal("0.00"),
                "harbour_tax_sum": self.form1.harbour_tax,
                "count": 1,
                "status": Status.APPROVED.label,
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "id": self.form2.id,
                "port_of_call": "Aasiaat",
                "vessel_type": "Cruise ship",
                "municipality": "Avannaata",
                "site": "Qaanaq",
                "disembarkment_tax_sum": self.form2.disembarkment_tax,
                "harbour_tax_sum": self.form2.harbour_tax,
                "count": 1,
                "status": Status.APPROVED.label,
            },
        )
        self.assertDictEqual(
            rows[2].record,
            {
                "id": self.form3.id,
                "port_of_call": "Ilulissat",
                "vessel_type": "Cruise ship",
                "municipality": "Avannaata",
                "site": "Qaanaq",
                "disembarkment_tax_sum": self.form3.disembarkment_tax,
                "harbour_tax_sum": self.form3.harbour_tax,
                "count": 1,
                "status": Status.REJECTED.label,
            },
        )

    def test_filter_arrival(self):
        rows = self.get_rows(arrival_gt=datetime(2025, 1, 1, 0, 0, 0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].record["id"], self.form3.id)

        rows = self.get_rows(arrival_gt=datetime(2024, 6, 1, 0, 0, 0))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)
        self.assertEqual(rows[2].record["id"], self.form3.id)

        rows = self.get_rows(
            arrival_gt=datetime(2024, 6, 1, 0, 0, 0),
            arrival_lt=datetime(2024, 7, 5, 0, 0, 0),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)

        rows = self.get_rows(
            arrival_gt=datetime(2024, 6, 1, 0, 0, 0),
            arrival_lt=datetime(2024, 6, 15, 0, 0, 0),
        )
        self.assertEqual(len(rows), 0)

    def test_filter_departure(self):
        rows = self.get_rows(departure_gt=datetime(2025, 1, 1, 0, 0, 0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].record["id"], self.form3.id)

        rows = self.get_rows(departure_gt=datetime(2024, 7, 1, 0, 0, 0))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)
        self.assertEqual(rows[2].record["id"], self.form3.id)

        rows = self.get_rows(
            departure_gt=datetime(2024, 6, 1, 0, 0, 0),
            departure_lt=datetime(2024, 7, 25, 0, 0, 0),
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].record["id"], self.form1.id)
        self.assertEqual(rows[1].record["id"], self.form2.id)

        rows = self.get_rows(
            departure_gt=datetime(2024, 6, 1, 0, 0, 0),
            departure_lt=datetime(2024, 6, 15, 0, 0, 0),
        )
        self.assertEqual(len(rows), 0)

    def test_filter_municipality(self):
        rows = self.get_rows(municipality=960)
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "municipality": "Avannaata",
                "disembarkment_tax_sum": self.form2.disembarkment_tax
                + self.form3.disembarkment_tax,
                "harbour_tax_sum": self.form2.harbour_tax + self.form3.harbour_tax,
                "count": 2,
            },
        )

    def test_filter_vessel_type(self):
        rows = self.get_rows(vessel_type="CRUISE")
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_type": "Cruise ship",
                "disembarkment_tax_sum": self.form2.disembarkment_tax
                + self.form3.disembarkment_tax,
                "harbour_tax_sum": self.form2.harbour_tax + self.form3.harbour_tax,
                "count": 2,
            },
        )

        rows = self.get_rows(vessel_type="FREIGHTER")
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "vessel_type": "Freighter",
                "disembarkment_tax_sum": Decimal(0),
                "harbour_tax_sum": self.form1.harbour_tax,
                "count": 1,
            },
        )

        rows = self.get_rows(vessel_type="FISHER")
        self.assertEqual(len(rows), 0)

    def test_filter_site(self):
        rows = self.get_rows(site=DisembarkmentSite.objects.get(name="Qaanaq").pk)
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "site": "Qaanaq",
                "disembarkment_tax_sum": self.form2.disembarkment_tax
                + self.form3.disembarkment_tax,
                "harbour_tax_sum": self.form2.harbour_tax + self.form3.harbour_tax,
                "count": 2,
            },
        )

        rows = self.get_rows(site=DisembarkmentSite.objects.get(name="Qeqertat").pk)
        self.assertEqual(len(rows), 0)

    def test_filter_port(self):
        ports = Port.objects.all().order_by("name")
        port1 = ports[0]
        port2 = ports[1]
        rows = self.get_rows(port_of_call=port1.pk)
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "port_of_call": port1.name,
                "disembarkment_tax_sum": self.form2.disembarkment_tax,
                "harbour_tax_sum": self.form1.harbour_tax + self.form2.harbour_tax,
                "count": 2,
            },
        )

        rows = self.get_rows(port_of_call=[port1.pk, port2.pk])
        self.assertEqual(len(rows), 2)
        self.assertDictEqual(
            rows[0].record,
            {
                "port_of_call": port2.name,
                "disembarkment_tax_sum": self.form3.disembarkment_tax,
                "harbour_tax_sum": self.form3.harbour_tax,
                "count": 1,
            },
        )
        self.assertDictEqual(
            rows[1].record,
            {
                "port_of_call": port1.name,
                "disembarkment_tax_sum": self.form2.disembarkment_tax,
                "harbour_tax_sum": self.form1.harbour_tax + self.form2.harbour_tax,
                "count": 2,
            },
        )

    def test_filter_status(self):
        rows = self.get_rows(status=Status.APPROVED)
        self.assertEqual(len(rows), 1)
        self.assertDictEqual(
            rows[0].record,
            {
                "disembarkment_tax_sum": self.form2.disembarkment_tax,
                "harbour_tax_sum": self.form1.harbour_tax + self.form2.harbour_tax,
                "count": 2,
                "status": Status.APPROVED.label,
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

    def test_redirect_from_non_draft_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self._get_update_view_url(self.harbor_dues_form.pk))
        self._assert_redirects_to_receipt(response, self.harbor_dues_form.pk)

    def test_redirect_from_nonexistent_form(self):
        self.client.force_login(self.user)
        nonexistent_id = 987654321987
        response = self.client.get(self._get_update_view_url(nonexistent_id))
        self._assert_redirects_to_receipt(response, nonexistent_id)

    def test_update_cruise_tax_form(self):
        """It should be possible to edit an existing cruise tax form"""
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Act
        response = self.client.post(
            self._get_update_view_url(self.cruise_tax_draft_form.pk),
            {
                "status": Status.DRAFT.value,
                "vessel_type": ShipType.CRUISE.value,
                "no_port_of_call": True,
                "vessel_name": "Peder Dingo",
            },
        )
        # Assert
        cruise_tax_form = CruiseTaxForm.objects.get(pk=self.cruise_tax_draft_form.pk)
        self.assertEqual(cruise_tax_form.status, Status.DRAFT)
        self.assertEqual(cruise_tax_form.vessel_name, "Peder Dingo")
        self._assert_redirects_to_next_step(response, self.cruise_tax_draft_form.pk)

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
        response = self.client.post(
            self._get_update_view_url(self.harbor_dues_form.pk),
            {
                "status": Status.DRAFT.value,
                "vessel_type": ShipType.CRUISE.value,
                "no_port_of_call": True,
                "vessel_name": "Peder Dingo",
            },
        )
        # Assert
        new_cruise_tax_form = CruiseTaxForm.objects.get(pk=self.harbor_dues_form.pk)
        self.assertEqual(new_cruise_tax_form.status, Status.DRAFT)
        self.assertEqual(new_cruise_tax_form.vessel_name, "Peder Dingo")
        self._assert_redirects_to_next_step(response, new_cruise_tax_form.pk)

    def test_get_renders_form_errors(self):
        # Arrange
        self.client.force_login(self.shipping_agent_user)
        # Arrange: introduce missing/invalid data
        self.cruise_tax_form.gross_tonnage = None
        self.cruise_tax_form.save(update_fields=("gross_tonnage",))
        # Act: perform GET request
        response = self.client.get(
            self._get_update_view_url(self.cruise_tax_form.pk, status=Status.NEW.value)
        )
        # Assert: check that form error(s) are displayed (even before form is POSTed)
        self.assertSetEqual(
            set(response.context["form"].errors.keys()),
            {"gross_tonnage"},
        )

    def test_get_desired_status_handles_invalid_value(self):
        instance = HarborDuesFormUpdateView()
        instance.setup(self.request_factory.get("", {"status": "INVALID"}))
        self.assertEqual(instance._get_desired_status(), Status.DRAFT)

    def _get_update_view_url(self, pk: int, **query) -> str:
        return reverse("havneafgifter:draft_edit", kwargs={"pk": pk}) + (
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

        print(response.status_code)

        # make sure we get an error message
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn("Du har ikke rettighed til at se denne side.", soup.get_text())


class TestLandingModalOkView(HarborDuesFormTestMixin, TestCase):
    def test_post(self):
        self.client.force_login(self.port_user)
        response = self.client.post(reverse("havneafgifter:landing_modal_ok"))
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.client.session.get("harbor_user_modal"))
