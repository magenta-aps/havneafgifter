import logging
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from django.core.files import File
from django.core.mail import EmailMessage
from django.db.models import Model
from django.templatetags.l10n import localize
from django.utils import translation
from django.utils.translation import gettext

from havneafgifter.models import CruiseTaxForm, HarborDuesForm, ShipType, User, UserType

logger = logging.getLogger(__name__)


@dataclass
class MailRecipient:
    name: str
    email: str
    object: Model | None


@dataclass
class SendResult:
    mail: "NotificationMail"
    succeeded: bool
    msg: EmailMessage


class NotificationMail:
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        self.form: HarborDuesForm | CruiseTaxForm = form
        self.recipients: list[MailRecipient] = []
        self.user: User | None = user

    def add_recipient(self, recipient: MailRecipient | None) -> None:
        if recipient is not None:
            self.recipients.append(recipient)
        return None

    def get_local_port_recipient(self) -> MailRecipient | None:
        if self.form.port_of_call and self.form.port_of_call.users.exists():
            port_user = self.form.port_of_call.users.all()[0]
            return MailRecipient(
                name=port_user.display_name, email=port_user.email, object=port_user
            )

        else:
            logger.info(
                "%r is not linked to a local port user, excluding from recipients",
            )
            return None

    def get_port_authority_recipient(self) -> MailRecipient | None:
        if (
            self.form.port_of_call
            and self.form.port_of_call.portauthority
            and self.form.port_of_call.portauthority.email
        ):
            return MailRecipient(
                name=self.form.port_of_call.portauthority.name,
                email=self.form.port_of_call.portauthority.email,
                object=self.form.port_of_call.portauthority,
            )
        elif (
            not self.form.has_port_of_call
            and settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL
        ):
            return MailRecipient(
                name=gettext("Authority for vessels without port of call"),
                email=settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL,
                object=None,
            )
        else:
            logger.info(
                "%r is not linked to a port authority, excluding from mail recipients",
                self,
            )
            return None

    def get_shipping_agent_recipient(self) -> MailRecipient | None:
        if self.form.shipping_agent and self.form.shipping_agent.email:
            return MailRecipient(
                name=self.form.shipping_agent.name,
                email=self.form.shipping_agent.email,
                object=self.form.shipping_agent,
            )
        logger.info(
            "%r is not linked to a shipping agent, excluding from mail recipients",
            self,
        )
        return None

    def get_ship_recipient(self) -> MailRecipient | None:
        # The contact email for a ship is through the associated user.
        # Ships with no associated users have no contact emails.
        if self.user and self.user.user_type == UserType.SHIP:
            vessel_contact: User | None = self.user
        else:
            vessel_imo = self.form.vessel_imo
            vessel_contact = User.objects.filter(username=vessel_imo).first()
        # If there is such a user, we've got it now.
        if vessel_contact:
            return MailRecipient(
                name=vessel_contact.display_name,
                email=vessel_contact.email,
                object=vessel_contact,
            )
        logger.info(
            "%r is not linked to a ship user, excluding from mail recipients",
            self,
        )
        return None

    def get_shipping_agent_or_ship_recipient(self) -> MailRecipient | None:
        if self.form.shipping_agent:
            return self.get_shipping_agent_recipient()
        else:
            # No agent - this form must have been submitted by a ship user
            return self.get_ship_recipient()

    def get_tax_authority_recipient(self) -> MailRecipient | None:
        if settings.EMAIL_ADDRESS_SKATTESTYRELSEN:
            return MailRecipient(
                name=gettext("Tax Authority"),
                email=settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
                object=None,
            )
        else:
            logger.info(
                "Skattestyrelsen email not configured, excluding from mail recipients",
            )
            return None

    def send_email(self) -> SendResult:
        logger.info("Sending email %r to %r", self.mail_subject, self.mail_recipients)
        msg = EmailMessage(
            self.mail_subject,
            self.mail_body,
            from_email=settings.EMAIL_SENDER,
            bcc=self.mail_recipients,
        )
        receipt = self.form.get_receipt()
        msg.attach(
            filename=self.form.get_pdf_filename(),
            content=receipt.pdf,
            mimetype="application/pdf",
        )
        result = msg.send(fail_silently=False)
        if result:
            self.form.pdf = File(
                BytesIO(receipt.pdf), name=self.form.get_pdf_filename()
            )
            self.form.save(update_fields=["pdf"])
        return SendResult(mail=self, succeeded=result == 1, msg=msg)

    @property
    def mail_recipients(self) -> list[str]:
        return [recipient.email for recipient in self.recipients]

    @property
    def mail_subject(self):
        return f"Talippoq: {self.form.pk:05} ({self.form.date})"

    @property
    def mail_body(self):
        raise NotImplementedError("must be implemented by subclass")

    @property
    def success_message(self) -> str:
        return gettext("An email was sent successfully")

    @property
    def error_message(self) -> str:
        return gettext("Error when sending email")


class OnSubmitForReviewMail(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        super().__init__(form, user)
        self.add_recipient(self.get_port_authority_recipient())
        self.add_recipient(self.get_local_port_recipient())
        self.add_recipient(self.get_shipping_agent_or_ship_recipient())
        self.add_recipient(self.get_tax_authority_recipient())

    @property
    def mail_body(self):
        # The mail body consists of the same text repeated in English, Greenlandic, and
        # Danish.
        # The text varies depending on whether the form concerns a cruise ship, or any
        # other type of vessel.
        result = []
        ship_name = self.form.vessel_name
        for lang_code, lang_name in settings.LANGUAGES:
            with translation.override(lang_code):
                context = {
                    "date": localize(self.form.date),
                    "submitter": (
                        self.form.shipping_agent.name
                        if self.form.shipping_agent
                        else ship_name or ""
                    ),
                }
                if self.form.vessel_type == ShipType.CRUISE:
                    text = (
                        gettext(
                            "%(submitter)s has %(date)s reported port taxes, cruise "
                            "passenger taxes, as well as environmental and "
                            "maintenance fees in relation to a ship's call "
                            "at a Greenlandic port. See further details in the "
                            "attached overview."
                        )
                        % context
                    )
                else:
                    text = (
                        gettext(
                            "%(submitter)s has %(date)s reported port taxes due to a "
                            "ship's call at a Greenlandic port. See further details "
                            "in the attached overview."
                        )
                        % context
                    )
                result.append(text)
        return "\n\n".join(result)

    @property
    def success_message(self) -> str:
        return gettext(
            "Thank you for submitting this form. "
            "Your harbour dues form has now been received by the port authority "
            "and the Greenlandic Tax Authority."
        )


class OnSubmitForReviewReceipt(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        super().__init__(form, user)
        self.add_recipient(self.get_shipping_agent_or_ship_recipient())

    @property
    def mail_body(self):
        # The mail body consists of the same text repeated in English, Greenlandic, and
        # Danish.
        result = []
        context = {
            "id": str(self.form.id),
            "name": self.form.vessel_name,
        }
        for lang_code, lang_name in settings.LANGUAGES:
            with translation.override(lang_code):
                text = (
                    gettext(
                        "Form %(id)s has been submitted for %(name)s and has been"
                        + " sent to the port authorities."
                    )
                    % context
                )
                result.append(text)
        return "\n\n".join(result)

    @property
    def success_message(self) -> str:
        return gettext("An email receipt was successfully sent.")


class OnRejectMail(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        super().__init__(form, user)
        self.add_recipient(self.get_shipping_agent_recipient())
        self.add_recipient(self.get_ship_recipient())
        self.add_recipient(self.get_port_authority_recipient())

    @property
    def mail_subject(self):
        return "Harbor dues form rejected in Talippoq"

    @property
    def mail_body(self):
        town = (
            self.form.port_of_call.portauthority.name
            if self.form.port_of_call
            else settings.APPROVER_NO_PORT_OF_CALL
        )
        context = {
            "town": town,
            "id": str(self.form.id),
        }
        return (
            gettext(
                "The port authority in %(town)s has rejected your harbor"
                + " dues form %(id)s."
                + "\n"
                + "Log on to Talippoq and edit your form as directed by the"
                + " port authority. If you have any questions concerning the"
                + " rejection you should contact the local port authority or the"
                + " Greenlandic Tax Authority at aka-talippoq@nanoq.gl."
            )
            % context
        )

    @property
    def success_message(self) -> str:
        return gettext("A rejection notification has been sent to the form submitter")


class OnRejectReceipt(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        super().__init__(form, user)
        self.add_recipient(self.get_port_authority_recipient())

    @property
    def mail_subject(self):
        return gettext("Rejected harbor dues form in Talippoq")

    @property
    def mail_body(self):
        context = {
            "id": str(self.form.id),
        }

        return gettext("Harbour dues form %(id)s has been rejected") % context

    @property
    def success_message(self) -> str:
        return gettext("A rejection receipt was sent to the port authority")


class OnSendToAgentMail(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        super().__init__(form, user)
        self.add_recipient(self.get_shipping_agent_recipient())

    @property
    def mail_body(self):
        context = {
            "submitter": self.user.email if self.user else "",
            "date": localize(self.form.date),
        }

        return (
            gettext(
                "%(submitter)s has %(date)s created a port tax form for you to complete"
            )
            % context
        )

    @property
    def success_message(self) -> str:
        return gettext("This form was successfully sent to your agent")
