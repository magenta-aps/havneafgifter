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


def get_tax_authority_recipient() -> MailRecipient | None:
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


class NotificationMail:
    def __init__(self, form: HarborDuesForm | CruiseTaxForm, user: User | None = None):
        self.form: HarborDuesForm | CruiseTaxForm = form
        self.recipients: list[MailRecipient] = []
        self.user: User | None = user

    def add_recipient(self, recipient: MailRecipient | None) -> None:
        if recipient is not None:
            self.recipients.append(recipient)
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
        self.add_recipient(self.get_shipping_agent_or_ship_recipient())
        self.add_recipient(get_tax_authority_recipient())

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


class OnNewUserMail(NotificationMail):
    def __init__(self, user: User):
        self.user = user
        self.recipients: list[MailRecipient] = []
        self.add_recipient(get_tax_authority_recipient())

    def send_email(self) -> SendResult:
        logger.info("Sending email %r to %r", self.mail_subject, self.mail_recipients)
        msg = EmailMessage(
            self.mail_subject,
            self.mail_body,
            from_email=settings.EMAIL_SENDER,
            bcc=self.mail_recipients,
        )
        result = msg.send(fail_silently=False)

        return SendResult(mail=self, succeeded=result == 1, msg=msg)

    @property
    def mail_body(self):
        return (
            f"Ny skibsbruger oprettet: {self.user.username}"
            + f" med email-adresse {self.user.email}"
        )

    @property
    def mail_subject(self):
        return f"Talippoq - ny bruger {self.user.username}"

    @property
    def success_message(self) -> str:
        return "The Greenlandic Tax Authority has been notified of the new vessel"
