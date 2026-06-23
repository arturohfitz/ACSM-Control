from collections.abc import Iterable
from email.message import EmailMessage
from html import escape
import smtplib

from app.models import PurchaseOrder, SupplierRFQ, SystemEmailSettings
from app.services.secrets import decrypt_secret


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
    smtp_password = decrypt_secret(settings.smtp_password)
    if not smtp_password:
        raise EmailConfigurationError("Falta contrasena SMTP")
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
            server.login(settings.smtp_username, smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as server:
        if settings.smtp_use_tls:
            server.starttls()
        server.login(settings.smtp_username, smtp_password)
        server.send_message(message)


def rfq_email_content(rfq: SupplierRFQ, portal_url: str | None = None) -> tuple[str, str, str]:
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
    if portal_url:
        lines.extend(
            [
                "",
                "Para cargar su cotizacion, ingrese a la siguiente liga segura:",
                portal_url,
                "",
                "Esta liga es unica para su empresa. No la comparta con terceros.",
            ]
        )
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
    portal_block = ""
    if portal_url:
        safe_url = escape(portal_url)
        portal_block = f"""
        <div style="margin: 20px 0; padding: 16px; border:1px solid #b7d8f4; border-radius: 12px; background:#eef8ff;">
          <p style="margin:0 0 12px;">Puede cargar su cotizacion PDF o Excel en la siguiente liga segura:</p>
          <a href="{safe_url}" style="display:inline-block; padding:12px 16px; border-radius:10px; background:#006da8; color:white; text-decoration:none; font-weight:700;">Cargar cotizacion</a>
          <p style="margin:12px 0 0; color:#53657d; font-size:12px;">Esta liga es unica para su empresa. No la comparta con terceros.</p>
        </div>
        """
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
      {portal_block}
      <p style="margin-top: 18px;">Gracias.</p>
    </div>
    """
    return subject, text_body, html_body


def _decimal_text(value) -> str:
    return f"{value.normalize():f}".rstrip("0").rstrip(".")


def _money_text(value) -> str:
    return f"${value:,.2f}"


def purchase_order_email_content(purchase_order: PurchaseOrder) -> tuple[str, str, str]:
    supplier_name = purchase_order.supplier.name if purchase_order.supplier else "Proveedor"
    project_name = purchase_order.project.name if purchase_order.project else "Sin desarrollo"
    issued_at = purchase_order.issued_at.isoformat() if purchase_order.issued_at else "Sin fecha"
    expected_delivery = (
        purchase_order.expected_delivery_date.isoformat()
        if purchase_order.expected_delivery_date
        else "Por confirmar"
    )
    subject = f"Orden de compra {purchase_order.po_number} - {supplier_name}"

    lines = [
        "Buen dia,",
        "",
        "Compartimos la orden de compra autorizada para su atencion.",
        "",
        f"Orden de compra: {purchase_order.po_number}",
        f"Proveedor: {supplier_name}",
        f"Desarrollo: {project_name}",
        f"Fecha de emision: {issued_at}",
        f"Entrega esperada: {expected_delivery}",
        f"Dias de credito/pago: {purchase_order.payment_terms_days}",
        f"Subtotal: {_money_text(purchase_order.subtotal)}",
        "",
        "Partidas:",
    ]
    for item in purchase_order.items:
        quantity = _decimal_text(item.quantity_ordered)
        lines.append(
            "- "
            f"{item.description} | {quantity} {item.unit} | "
            f"PU {_money_text(item.unit_price)} | Total {_money_text(item.line_total)}"
        )
    if purchase_order.notes:
        lines.extend(["", f"Notas: {purchase_order.notes}"])
    lines.extend(["", "Favor de confirmar recepcion de esta orden de compra.", "", "Gracias."])
    text_body = "\n".join(lines)

    rows = "".join(
        "<tr>"
        f"<td style=\"padding:8px; border:1px solid #cbdced;\">{escape(item.description)}</td>"
        f"<td style=\"padding:8px; border:1px solid #cbdced;\">{escape(item.unit)}</td>"
        f"<td style=\"padding:8px; border:1px solid #cbdced;\">{escape(_decimal_text(item.quantity_ordered))}</td>"
        f"<td style=\"padding:8px; border:1px solid #cbdced;\">{escape(_money_text(item.unit_price))}</td>"
        f"<td style=\"padding:8px; border:1px solid #cbdced;\">{escape(_money_text(item.line_total))}</td>"
        "</tr>"
        for item in purchase_order.items
    )
    notes_block = ""
    if purchase_order.notes:
        notes_block = f"""
        <div style="margin-top:16px; padding:12px; border-radius:10px; background:#eef8ff; border:1px solid #b7d8f4;">
          <strong>Notas</strong><br>{escape(purchase_order.notes)}
        </div>
        """
    html_body = f"""
    <div style="font-family: Arial, sans-serif; color: #172033; line-height: 1.45;">
      <h2 style="margin: 0 0 12px;">Orden de compra {escape(purchase_order.po_number)}</h2>
      <p>Buen dia, compartimos la orden de compra autorizada para su atencion.</p>
      <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
        <tbody>
          <tr><td style="font-weight:700; padding:4px 0;">Proveedor</td><td>{escape(supplier_name)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Desarrollo</td><td>{escape(project_name)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Fecha de emision</td><td>{escape(issued_at)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Entrega esperada</td><td>{escape(expected_delivery)}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Dias de credito/pago</td><td>{purchase_order.payment_terms_days}</td></tr>
          <tr><td style="font-weight:700; padding:4px 0;">Subtotal</td><td>{escape(_money_text(purchase_order.subtotal))}</td></tr>
        </tbody>
      </table>
      <table style="border-collapse: collapse; width: 100%;">
        <thead>
          <tr style="background: #eaf3fb;">
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Material</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Unidad</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Cantidad</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Precio unitario</th>
            <th style="text-align:left; padding:8px; border:1px solid #cbdced;">Total</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {notes_block}
      <p style="margin-top: 18px;">Favor de confirmar recepcion de esta orden de compra.</p>
      <p>Gracias.</p>
    </div>
    """
    return subject, text_body, html_body
