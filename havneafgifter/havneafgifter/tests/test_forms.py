import copy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib.auth.hashers import is_password_usable
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.forms.utils import ErrorList
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.forms import (
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersByCountryForm,
    PassengersTotalForm,
    SignupVesselForm,
)
from havneafgifter.models import (
    DisembarkmentSite,
    DisembarkmentTaxRate,
    Nationality,
    Port,
    PortAuthority,
    PortTaxRate,
    Status,
    TaxRates,
    Vessel,
)
from havneafgifter.tests.mixins import HarborDuesFormTestMixin


class TestSignupVesselForm(HarborDuesFormTestMixin, TestCase):
    def test_form_save_hashes_password(self):
        # Arrange
        instance = SignupVesselForm(data=self.ship_user_form_data)
        # Act
        user = instance.save()
        # Assert
        user.refresh_from_db()
        self.assertTrue(is_password_usable(user.password))

    def test_form_save_creates_vessel(self):
        # Arrange
        instance = SignupVesselForm(data=self.ship_user_form_data)
        # Act
        user = instance.save()
        # Assert
        self.assertIsInstance(user.vessel, Vessel)
        self.assertEqual(user.vessel.imo, user.username)


class TestHarborDuesFormForm(ParametrizedTestCase, HarborDuesFormTestMixin, TestCase):
    def test_clean_does_nothing_if_draft(self):
        data = copy.copy(self.harbor_dues_form_data)
        form = self._get_form_instance(data, status=Status.DRAFT)
        self.assertTrue(form.is_valid())
        self.assertDictEqual(
            {k: v for k, v in form.cleaned_data.items() if k != "no_port_of_call"},
            data,
        )
        self.assertEqual(
            form.user_visible_non_field_errors(),
            ErrorList(),  # empty error list
        )

    @parametrize(
        "changes",
        [
            (
                {
                    "datetime_of_arrival": datetime(2020, 1, 1, tzinfo=timezone.utc),
                    "datetime_of_departure": None,
                },
            ),
            (
                {
                    "datetime_of_arrival": None,
                    "datetime_of_departure": datetime(2020, 1, 1, tzinfo=timezone.utc),
                },
            ),
        ],
    )
    def test_error_on_arrival_but_no_departure(self, changes):
        data = copy.copy(self.harbor_dues_form_data)
        data.update(changes)
        self._assert_form_has_error(
            data, "port_of_call_requires_arrival_and_departure_dates"
        )

    def test_error_on_departure_before_arrival(self):
        data = copy.copy(self.harbor_dues_form_data)
        # Swap date of arrival with date of departure
        data["datetime_of_arrival"], data["datetime_of_departure"] = (
            data["datetime_of_departure"],
            data["datetime_of_arrival"],
        )
        self._assert_form_has_error(
            data, "datetime_of_departure_before_datetime_of_arrival"
        )

    @parametrize(
        "port_of_call,no_port_of_call,expected_error_code",
        [
            # Provide "port of call" and set "no port of call" to True
            (
                "Nordhavn",
                True,
                "port_of_call_chosen_but_no_port_of_call_is_true",
            ),
            # Provide no "port of call" and set "no port of call" to False
            (
                None,
                False,
                "port_of_call_is_empty_and_no_port_of_call_is_false",
            ),
        ],
    )
    def test_error_on_port_of_call_vs_no_port_of_call(
        self,
        port_of_call,
        no_port_of_call,
        expected_error_code,
    ):
        data = copy.copy(self.harbor_dues_form_data)
        data["port_of_call"] = (
            Port.objects.get(name=port_of_call) if port_of_call else None
        )
        data["no_port_of_call"] = no_port_of_call
        self._assert_form_has_error(data, expected_error_code)

    def test_error_on_no_port_of_call_if_non_cruise_ship(self):
        # In `self.harbor_dues_form_data`, `vessel_type` is already set to
        # `VesselType.FREIGHTER`.
        data = copy.copy(self.harbor_dues_form_data)
        # Try to submit a "no port of call" form for a non-cruise ship
        data["no_port_of_call"] = True
        data["port_of_call"] = None
        self._assert_form_has_error(
            data, "no_port_of_call_cannot_be_true_for_non_cruise_ships"
        )

    def test_form_clean_does_nothing_if_draft(self):
        data = copy.copy(self.harbor_dues_form_form_data)
        data["status"] = Status.DRAFT.value
        form = self._get_form_instance(data)
        self.assertTrue(form.is_valid())
        result = form.clean()
        self.assertEqual(data, result)

    def test_user_visible_non_field_errors(self):
        # Submit data that will lead to violating a database constraint
        data = copy.copy(self.harbor_dues_form_data)
        data["status"] = Status.NEW.value
        data["gross_tonnage"] = None
        form = self._get_form_instance(data)
        # We expect the `form.save(...)` to raise ValueError in this case
        try:
            form.save(commit=False)
        except ValueError:
            self.assertEqual(
                str(form.errors.get(NON_FIELD_ERRORS)[0]),
                "Gross tonnage cannot be empty",
            )
            self.assertEqual(
                form.user_visible_non_field_errors()[0],
                "Gross tonnage cannot be empty",
            )

    def test_get_vessel_info_for_ship_user(self):
        # If form is instantiated with a `User` that is a "ship user", the fields
        # `vessel_name`, `vessel_imo`, etc. are pre-filled using data from
        # `user.vessel`.
        form = HarborDuesFormForm(self.ship_user, data=self.harbor_dues_form_data)
        self._assert_form_field_initial(form, "vessel_name", self.ship_user_vessel.name)
        self._assert_form_field_initial(form, "vessel_imo", self.ship_user_vessel.imo)
        self._assert_form_field_initial(
            form, "vessel_owner", self.ship_user_vessel.owner
        )
        self._assert_form_field_initial(
            form, "vessel_master", self.ship_user_vessel.master
        )
        self._assert_form_field_initial(form, "vessel_type", self.ship_user_vessel.type)
        self._assert_form_field_initial(
            form, "gross_tonnage", self.ship_user_vessel.gross_tonnage
        )
        # If form is instantiated with a `User` that is a "ship user", the fields
        # `vessel_imo`, `vessel_type` and `gross_tonnage` are locked (= disabled.)
        self._assert_form_field_disabled(form, "vessel_imo")
        self._assert_form_field_disabled(form, "vessel_type")
        self._assert_form_field_disabled(form, "gross_tonnage")

    def test_ship_user_can_submit_without_agent(self):
        form_data = copy.copy(self.harbor_dues_form_data)
        form_data["status"] = Status.NEW.value
        del form_data["shipping_agent"]
        form = self._get_form_instance(form_data, status=Status.NEW)
        self.assertTrue(form.is_valid())

    def test_shipping_agent_field_is_locked_for_shipping_agents(self):
        # If form is instantiated with a `User` that is a "shipping agent user", the
        # field `shipping_agent` is locked, containing the `ShippingAgent` that the
        # `User` belongs to.
        form = HarborDuesFormForm(
            self.shipping_agent_user, data=self.harbor_dues_form_data
        )
        self.assertEqual(
            form.fields["shipping_agent"].initial,
            self.shipping_agent_user.shipping_agent,
        )
        self.assertTrue(form.fields["shipping_agent"].disabled)

    def _get_form_instance(self, data, status=Status.NEW):
        # We use `self.shipping_agent_user` here to get a "normal" user
        # (i.e., not a "ship user".)
        # We default to `status=Status.NEW` here to trigger most of the processing
        # in the `clean` method.
        return HarborDuesFormForm(
            self.shipping_agent_user,
            status=status,
            data=data,
        )

    def _assert_form_has_error(self, data, code):
        form = self._get_form_instance(data)
        # Trigger form validation
        form.is_valid()
        # Assert that our validation error is raised
        with self.assertRaises(ValidationError) as exc:
            form.clean()
            self.assertEqual(exc.code, code)
        # Assert that our validation error is user-visible
        self.assertFalse(
            form.user_visible_non_field_errors() == ErrorList()  # empty error list
        )

    def _assert_form_field_initial(self, form, field, value):
        self.assertEqual(form.fields[field].initial, value)

    def _assert_form_field_disabled(self, form, field):
        self.assertTrue(form.fields[field].disabled)


class TestPassengersByCountryForm(TestCase):
    def test_number_of_passengers_label(self):
        form = PassengersByCountryForm(initial={"nationality": Nationality.DENMARK})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            form.initial["nationality"].label,
        )


class TestDisembarkmentForm(HarborDuesFormTestMixin, TestCase):
    def test_disembarkment_site_initial(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertListEqual(
            form.fields["disembarkment_site"].choices,
            [(ds.pk, str(ds))],
        )

    def test_number_of_passengers_label(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            form.initial_disembarkment_site.name,
        )

    def test_number_of_passengers_label_outside_populated_areas(self):
        ds = DisembarkmentSite.objects.filter(is_outside_populated_areas=True).first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            ds._meta.get_field("is_outside_populated_areas").verbose_name,
        )

    def test_clean_disembarkment_site(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(
            initial={"disembarkment_site": ds.pk},
            data={"disembarkment_site": ds.pk, "number_of_passengers": 0},
        )
        # Trigger form validation
        form.is_valid()
        # Assert that our clean method returns model instance
        self.assertEqual(form.clean_disembarkment_site(), ds)

    def test_get_municipality_display(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(form.get_municipality_display(), ds.get_municipality_display())


class TestPassengersTotalForm(SimpleTestCase):
    def test_validate_total(self):
        instance = PassengersTotalForm(data={"total_number_of_passengers": "100"})
        instance.validate_total(101)
        self.assertEqual(len(instance.errors), 1)
        self.assertIn("total_number_of_passengers", instance.errors)


class TestBasePortTaxRateFormSet(HarborDuesFormTestMixin, TestCase):
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

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tax_authority_user)

    def test_clean(self):
        initial_object_count = DisembarkmentTaxRate.objects.count()

        # attempt to add an already existing disembarkment site rate
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )
        value_dict_to_post = {
            **original_response_dict,
            "disembarkment_tax_rates-TOTAL_FORMS": "6",
            "disembarkment_tax_rates-5-disembarkment_tax_rate": "2.00",
            "disembarkment_tax_rates-5-municipality": "955",
            "disembarkment_tax_rates-5-disembarkment_site": "175",
            "disembarkment_tax_rates-5-DELETE": "",
        }
        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )

        # ensure we're not getting a redirect
        self.assertEqual(post_request_response.status_code, 200)

        # ensure the expected error message is in the generated HTML
        soup = BeautifulSoup(post_request_response.content, "html.parser")
        self.assertIn('"955, Attu (Kujalleq)" er allerede i listen.', soup.get_text())

        # ensure nothing has been added to db
        self.assertEqual(initial_object_count, DisembarkmentTaxRate.objects.count())


class TestBaseDisembarkmentTaxRateFormSet(HarborDuesFormTestMixin, TestCase):
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

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tax_authority_user)

    def test_port_tax_rate_form_clean_round_gross_ton_up_to(self):
        # these are nested functions, so they can collapsed, for easier
        # navigation and reading them

        def attempt_single():
            orgiginal_object_count = PortTaxRate.objects.count()

            # attempt to create a port tax rate with a rounding value that's
            # not between gt_start and gt_end
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "11",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "100",
                "port_tax_rates-10-round_gross_ton_up_to": "200",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": "3",
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), orgiginal_object_count)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn("skal være mellem", soup.get_text())

        def attempt_multiple():
            orgiginal_object_count = PortTaxRate.objects.count()

            # attempt to create a port tax rate with a rounding value that's
            # not between gt_start and gt_end
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "12",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "100",
                "port_tax_rates-10-round_gross_ton_up_to": "200",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": "3",
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
                "port_tax_rates-11-gt_start": "100",
                "port_tax_rates-11-gt_end": "",
                "port_tax_rates-11-round_gross_ton_up_to": "80",
                "port_tax_rates-11-port_tax_rate": "42.00",
                "port_tax_rates-11-port": "3",
                "port_tax_rates-11-vessel_type": "FISHER",
                "port_tax_rates-11-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), orgiginal_object_count)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn("skal være mellem", soup.get_text())

        attempt_single()
        attempt_multiple()

    def test_port_tax_rate_form_check_for_tonnage_presences(self):
        # these are nested functions, so they can collapsed, for easier
        # navigation and reading them
        def attempt_single():
            orgiginal_object_count = PortTaxRate.objects.count()

            # attempt to create a singke "non-open ended" port tax rate
            # with gt_end of 10 not being None
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "11",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "100",
                "port_tax_rates-10-round_gross_ton_up_to": "80",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": self.port1.pk,
                "port_tax_rates-10-vessel_type": "FREIGHTER",
                "port_tax_rates-10-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn("For denne kombination", soup.get_text())

            # ensure nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), orgiginal_object_count)

        def attempt_multiple():
            orgiginal_object_count = PortTaxRate.objects.count()

            # attempt to create a "non-open ended" port tax rate over two objects
            # with gt_end of 11 not being None
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "12",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "100",
                "port_tax_rates-10-round_gross_ton_up_to": "80",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": self.port1.pk,
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
                "port_tax_rates-11-gt_start": "100",
                "port_tax_rates-11-gt_end": "200",
                "port_tax_rates-11-round_gross_ton_up_to": "80",
                "port_tax_rates-11-port_tax_rate": "42.00",
                "port_tax_rates-11-port": "3",
                "port_tax_rates-11-vessel_type": "FISHER",
                "port_tax_rates-11-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn("For denne kombination", soup.get_text())

            # ensure nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), orgiginal_object_count)

        attempt_single()
        attempt_multiple()

    def test_port_tax_rate_form_chek_for_tonnage_gap_or_overlap(self):
        # these are nested functions, so they can collapsed, for easier
        # navigation and reading them
        def attempt_acceptable():
            original_object_count = PortTaxRate.objects.count()

            # attempt to add two port tax rates with no overlapping or gapped tonnages
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "12",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "30000",
                "port_tax_rates-10-round_gross_ton_up_to": "80",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": "3",
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
                "port_tax_rates-11-gt_start": "30000",
                "port_tax_rates-11-gt_end": "",
                "port_tax_rates-11-round_gross_ton_up_to": "80",
                "port_tax_rates-11-port_tax_rate": "44.00",
                "port_tax_rates-11-port": "3",
                "port_tax_rates-11-vessel_type": "FISHER",
                "port_tax_rates-11-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 302)

            # ensure that two were added to db
            self.assertEqual(PortTaxRate.objects.count(), original_object_count + 2)

        def attempt_overlap():
            original_object_count = PortTaxRate.objects.count()

            # attempt to add two port tax rates with overlapping tonnages
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "12",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "40000",
                "port_tax_rates-10-round_gross_ton_up_to": "80",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": "3",
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
                "port_tax_rates-11-gt_start": "30000",
                "port_tax_rates-11-gt_end": "",
                "port_tax_rates-11-round_gross_ton_up_to": "80",
                "port_tax_rates-11-port_tax_rate": "44.00",
                "port_tax_rates-11-port": "3",
                "port_tax_rates-11-vessel_type": "FISHER",
                "port_tax_rates-11-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn("Der er overlap i brutto ton værdierne for", soup.get_text())

            # ensure that nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), original_object_count)

        def attempt_gapped():
            original_object_count = PortTaxRate.objects.count()

            # attempt to add two port tax rates with gapped tonnages
            original_response_dict = self.response_to_datafields_dict(
                self.client.get(self.edit_url).content.decode("utf-8")
            )
            value_dict_to_post = {
                **original_response_dict,
                "port_tax_rates-TOTAL_FORMS": "12",
                "port_tax_rates-10-gt_start": "0",
                "port_tax_rates-10-gt_end": "30000",
                "port_tax_rates-10-round_gross_ton_up_to": "80",
                "port_tax_rates-10-port_tax_rate": "42.00",
                "port_tax_rates-10-port": "3",
                "port_tax_rates-10-vessel_type": "FISHER",
                "port_tax_rates-10-DELETE": "",
                "port_tax_rates-11-gt_start": "40000",
                "port_tax_rates-11-gt_end": "",
                "port_tax_rates-11-round_gross_ton_up_to": "80",
                "port_tax_rates-11-port_tax_rate": "44.00",
                "port_tax_rates-11-port": "3",
                "port_tax_rates-11-vessel_type": "FISHER",
                "port_tax_rates-11-DELETE": "",
            }
            post_request_response = self.client.post(
                self.edit_url,
                data=value_dict_to_post,
            )

            # Check for redirect
            self.assertEqual(post_request_response.status_code, 200)

            # ensure the expected error message is in the generated HTML
            soup = BeautifulSoup(post_request_response.content, "html.parser")
            self.assertIn('Der er "hul" i brutto ton værdierne for', soup.get_text())

            # ensure that nothing was added to db
            self.assertEqual(PortTaxRate.objects.count(), original_object_count)

        attempt_acceptable()
        attempt_overlap()
        attempt_gapped()

    def test_port_tax_rate_form_check_for_duplicates(self):
        initial_object_count = PortTaxRate.objects.count()

        # attempt to add two port tax rates with the exact same values
        original_response_dict = self.response_to_datafields_dict(
            self.client.get(self.edit_url).content.decode("utf-8")
        )
        value_dict_to_post = {
            **original_response_dict,
            "port_tax_rates-TOTAL_FORMS": "12",
            "port_tax_rates-10-gt_start": "0",
            "port_tax_rates-10-gt_end": "",
            "port_tax_rates-10-round_gross_ton_up_to": "80",
            "port_tax_rates-10-port_tax_rate": "313373.00",
            "port_tax_rates-10-port": "3",
            "port_tax_rates-10-vessel_type": "FISHER",
            "port_tax_rates-10-DELETE": "",
            "port_tax_rates-11-gt_start": "0",
            "port_tax_rates-11-gt_end": "",
            "port_tax_rates-11-round_gross_ton_up_to": "80",
            "port_tax_rates-11-port_tax_rate": "313373.00",
            "port_tax_rates-11-port": "3",
            "port_tax_rates-11-vessel_type": "FISHER",
            "port_tax_rates-11-DELETE": "",
        }
        post_request_response = self.client.post(
            self.edit_url,
            data=value_dict_to_post,
        )

        # Check for redirect
        self.assertEqual(post_request_response.status_code, 200)

        # ensure the expected error message is in the generated HTML
        soup = BeautifulSoup(post_request_response.content, "html.parser")
        self.assertIn("eksisterer allerede.", soup.get_text())

        # ensure nothing was added to db
        self.assertEqual(PortTaxRate.objects.count(), initial_object_count)


class TestTaxRateForm(HarborDuesFormTestMixin, TestCase):
    """
    Ensure that TaxRates with start_date less than 1 week in advance
    can't be made or edited
    """

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

    def setUp(self):
        super().setUp()
        self.client.force_login(self.tax_authority_user)

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

    def test_write_tax_rate_deadline(self):
        original_object_count = TaxRates.objects.count()

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
        datetetime_string_two_days_in_the_future = (
            datetime.now(timezone.utc) + timedelta(days=2)
        ).strftime("%Y-%m-%d %H:%M:%S")
        data_dict_to_post = {
            key: value
            for key, value in original_response_dict.items()
            if not (number_pattern.match(key) or prefix_pattern.match(key))
        }
        data_dict_to_post["start_datetime"] = datetetime_string_two_days_in_the_future
        response = self.client.post(
            reverse("havneafgifter:tax_rate_clone", kwargs={"pk": self.tax_rate.pk}),
            data=data_dict_to_post,
        )

        # that should result in no redirect
        self.assertEqual(response.status_code, 200)

        # check that nothing was added to db
        self.assertEqual(original_object_count, TaxRates.objects.count())

        # ensure the expected error message is in the generated HTML
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertIn(
            "Der må ikke oprettes eller redigeres i afgifter, "
            "der bliver gyldige om mindre end 1 uge fra nu.",
            soup.get_text(),
        )
