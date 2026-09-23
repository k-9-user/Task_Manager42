import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 5


def send_mail(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("SMTP_HOST is empty; mail %r not sent", subject)
        return

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Could not send mail %r", subject)
