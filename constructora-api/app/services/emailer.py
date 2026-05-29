from collections.abc import Iterable
from email.message import EmailMessage
from html import escape
import smtplib

from app.models import SupplierRFQ, SystemEmailSettings


class EmailConfigurationError(RuntimeError):
    pass


def _require_config(settings: SystemEmailSettings) -> None:
    if not settings.is_active:
        raise EmailConfigurationError("La configuracion de correo esta desactivada")
    if not settings.smtp_host or not settings.smtp_port:
        raise EmailConfigurationError("Falta servidor SMTP")
    if not settings.smtp_username or not settings.smtp_password:
        raise EmailConfigurationError("Falta usuario o contrasena SMTP")
    if not settings.sender_email:
        raise EmailConfigurationError("Falta correo remitente")


def send_email(
    settings: SystemEmailSettings,
    recipients: Iterable[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    _require_config(settings)
    clean_recipients = [recipient.strip() for recipient in recipients if recipient and recipient.strip()]
    if not clean_recipients:
        raise EmailConfigurationError("No hay destinatarios validos")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.sender_name} <{settings.sender_email}>"
    message["To"] = ", ".join(clean_recipients)
    if settings.reply_to_email:
        message["Reply-To"] = settings.reply_to_email
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=25) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def rfq_email_content(rfq: SupplierRFQ) -> tuple[str, str, str]:
    subject = f"Solicitud de cotizacion {rfq.rfq_number} - {rfq.title}"
    required_by = rfq.required_by.isoformat() if rfq.required_by else "Sin fecha definida"
    deadline = rfq.response_deadline.isoformat() if rfq.response_deadline else "Sin fecha definida"

    lines = [
        "Buen dia,",
        "",
        "Solicitamos su cotizacion para los siguientes materiales:",
        "",
        f"Solicitud: {rfq.rfq_number}",
        f"Nombre: {rfq.title}",
        f"Fecha requerida: {required_by}",
        f"Limite de respuesta: {deadline}",
        "",
        "Materiales:",
    ]
    for item in rfq.items:
        quantity = f"{item.quantity.normalize():f}".rstrip("0").rstrip(".")
        lines.append(f"- {item.description} | {quantity} {item.unit} | {item.notes or 'Sin notas'}")
    lines.extend(["", "Gracias."])
    text_body = "\n".join(lines)

    rows = "".join(
        "<tr>"
        f"<td>{escape(item.description)}</td>"
        f"<td>{escape(str(item.unit))}</td>"
        f"<td>{escape(f'{item.quantity.normalize():f}'.rstrip('0').rstrip('.'))}</td>"
        f"<td>{escape(item.notes or '')}</td>"
        "</tr>"
        for item in rfq.items
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; color: #172033; line-height: 1.45;">
      <h2 style="margin: 0 0 12px;">Solicitud de cotizacion {escape(rfq.rfq_number)}</h2>
      <p>Buen dia, solicitamos su cotizacion para los siguientes materiales.</p>
      <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
        <tbody>
          <tr><td style="font-weight:700; padding:4px 0;">Nombre</td><td>{escape(rfq.title)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Fecha requerida</td><td>{escape(required_by)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Limite de respuesta</td><td>{escape(deadline)}</td></tr>
        </tbody>
      </table>
      <table style="border-collapse: collapse; width: 100%;">
        <thead>
          <tr style="background: #eaf3fb;">
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Material</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Unidad</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Cantidad</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Notas</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="margin-top: 18px;">Gracias.</p>
    </div>
    """
    return subject, text_body, html_body
