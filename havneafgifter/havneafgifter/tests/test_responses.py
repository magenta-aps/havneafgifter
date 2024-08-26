from django.test import RequestFactory, SimpleTestCase

from havneafgifter.responses import MessageTemplateMixin


class DerivedClass(MessageTemplateMixin):
    template_name = "foo"


class TestMessageTemplateMixin(SimpleTestCase):
    def test_context_data(self):
        request = RequestFactory().get("")
        instance = DerivedClass(request, "message")
        self.assertEqual(
            instance.context_data,
            {MessageTemplateMixin.message_context_var_name: "message"},
        )
