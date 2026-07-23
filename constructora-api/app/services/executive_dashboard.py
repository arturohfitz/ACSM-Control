from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    MaterialRequisition,
    PurchaseOrder,
    SupplierInvoice,
    SupplierPayment,
    SupplierQuoteApproval,
    SupplierRFQ,
    SupplierRFQExceptionRequest,
)
from app.services.project_financials import project_financial_progress


ZERO = Decimal("0")


def _count(db: Session, model: type, *conditions) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def _project_scope(model: type, company_id: int, project_ids: list[int]):
    return (
        getattr(model, "company_id") == company_id,
        getattr(model, "project_id").in_(project_ids),
    )


def executive_dashboard(
    db: Session,
    *,
    company_id: int,
    project_id: int | None,
    allowed_client_ids: list[int] | None = None,
) -> dict:
    financial = project_financial_progress(
        db,
        company_id=company_id,
        project_id=project_id,
        allowed_client_ids=allowed_client_ids,
    )
    all_projects = financial["projects"]
    visible_projects = (
        [row for row in all_projects if row["project_id"] == project_id]
        if project_id is not None
        else all_projects
    )
    project_ids = [row["project_id"] for row in visible_projects]
    today = date.today()

    if project_ids:
        requisition_scope = _project_scope(MaterialRequisition, company_id, project_ids)
        rfq_scope = _project_scope(SupplierRFQ, company_id, project_ids)
        order_scope = _project_scope(PurchaseOrder, company_id, project_ids)
        invoice_project_scope = (
            SupplierInvoice.company_id == company_id,
            SupplierInvoice.purchase_order_id.in_(
                select(PurchaseOrder.id).where(*order_scope)
            ),
        )
        payment_project_scope = (
            SupplierPayment.company_id == company_id,
            SupplierPayment.supplier_invoice_id.in_(
                select(SupplierInvoice.id).where(*invoice_project_scope)
            ),
        )

        requisitions = _count(
            db,
            MaterialRequisition,
            *requisition_scope,
            MaterialRequisition.status.in_({"submitted", "in_review", "approved"}),
            MaterialRequisition.converted_rfq_id.is_(None),
        )
        requisitions_attention = _count(
            db,
            MaterialRequisition,
            *requisition_scope,
            MaterialRequisition.status.in_({"submitted", "in_review", "approved"}),
            MaterialRequisition.converted_rfq_id.is_(None),
            MaterialRequisition.required_date.is_not(None),
            MaterialRequisition.required_date < today,
        )
        quotations = _count(
            db,
            SupplierRFQ,
            *rfq_scope,
            SupplierRFQ.status.in_({"draft", "sent", "email_error", "partially_quoted", "quoted"}),
        )
        quotations_attention = _count(
            db,
            SupplierRFQ,
            *rfq_scope,
            (
                (SupplierRFQ.status == "email_error")
                | (
                    SupplierRFQ.response_deadline.is_not(None)
                    & (SupplierRFQ.response_deadline < today)
                    & SupplierRFQ.status.in_({"sent", "partially_quoted"})
                )
            ),
        )
        approvals = _count(
            db,
            SupplierQuoteApproval,
            SupplierQuoteApproval.company_id == company_id,
            SupplierQuoteApproval.rfq_id.in_(
                select(SupplierRFQ.id).where(*rfq_scope)
            ),
            SupplierQuoteApproval.status == "requested",
        ) + _count(
            db,
            SupplierRFQExceptionRequest,
            *_project_scope(SupplierRFQExceptionRequest, company_id, project_ids),
            SupplierRFQExceptionRequest.status == "requested",
        )
        orders_to_send = _count(
            db,
            PurchaseOrder,
            *order_scope,
            PurchaseOrder.status == "issued",
        )
        receiving = _count(
            db,
            PurchaseOrder,
            *order_scope,
            PurchaseOrder.status.in_({"sent", "partially_received"}),
        )
        receiving_attention = _count(
            db,
            PurchaseOrder,
            *order_scope,
            PurchaseOrder.status.in_({"sent", "partially_received"}),
            PurchaseOrder.expected_delivery_date.is_not(None),
            PurchaseOrder.expected_delivery_date < today,
        )
        invoices = _count(
            db,
            SupplierInvoice,
            *invoice_project_scope,
            SupplierInvoice.status.in_(
                {"document_pending", "fiscal_review", "received", "blocked"}
            ),
        )
        invoices_attention = _count(
            db,
            SupplierInvoice,
            *invoice_project_scope,
            SupplierInvoice.status.in_({"fiscal_review", "blocked"}),
        )
        payments = _count(
            db,
            SupplierPayment,
            *payment_project_scope,
            SupplierPayment.status == "scheduled",
        )
        payments_attention = _count(
            db,
            SupplierPayment,
            *payment_project_scope,
            SupplierPayment.status == "scheduled",
            SupplierPayment.scheduled_date.is_not(None),
            SupplierPayment.scheduled_date <= today,
        )
    else:
        requisitions = requisitions_attention = 0
        quotations = quotations_attention = 0
        approvals = orders_to_send = 0
        receiving = receiving_attention = 0
        invoices = invoices_attention = 0
        payments = payments_attention = 0

    flow = [
        {
            "key": "requisitions",
            "label": "Requerimientos",
            "count": requisitions,
            "attention_count": requisitions_attention,
            "description": "Solicitudes de Obra pendientes de tomar",
            "action_url": "/purchasing",
        },
        {
            "key": "quotes",
            "label": "Cotizaciones",
            "count": quotations,
            "attention_count": quotations_attention,
            "description": "Solicitudes esperando propuestas o captura",
            "action_url": "/purchasing/operations",
        },
        {
            "key": "approvals",
            "label": "Aprobaciones",
            "count": approvals,
            "attention_count": approvals,
            "description": "Decisiones pendientes de gerencia",
            "action_url": "/purchasing/approvals",
        },
        {
            "key": "orders",
            "label": "Ordenes",
            "count": orders_to_send,
            "attention_count": orders_to_send,
            "description": "Ordenes aprobadas pendientes de envio",
            "action_url": "/purchasing/orders",
        },
        {
            "key": "receiving",
            "label": "Recepciones",
            "count": receiving,
            "attention_count": receiving_attention,
            "description": "Ordenes con material pendiente de recibir",
            "action_url": "/inventory",
        },
        {
            "key": "invoices",
            "label": "Facturas",
            "count": invoices,
            "attention_count": invoices_attention,
            "description": "Documentos pendientes de validar",
            "action_url": "/supplier-payments?view=invoices",
        },
        {
            "key": "payments",
            "label": "Pagos",
            "count": payments,
            "attention_count": payments_attention,
            "description": "Pagos programados pendientes de ejecutar",
            "action_url": "/supplier-payments?view=payments",
        },
    ]

    project_rows: list[dict] = []
    alerts: list[dict] = []
    for row in visible_projects:
        if row["integrity_issues"] or row["over_budget_amount"] > ZERO:
            health = "critical"
            health_label = "Requiere conciliacion"
            next_action_label = "Revisar conciliacion"
            next_action_url = "/supplier-payments?view=reconciliations"
        elif row["baseline_id"] is None:
            health = "attention"
            health_label = "Sin presupuesto base"
            next_action_label = "Aprobar linea base"
            next_action_url = f"/dashboard/projects/{row['project_id']}?focus=baseline"
        elif row["received_amount"] > row["invoiced_amount"]:
            health = "attention"
            health_label = "Factura pendiente"
            next_action_label = "Revisar facturas"
            next_action_url = (
                f"/supplier-payments?view=invoices&project_id={row['project_id']}"
            )
        elif row["invoiced_amount"] > row["paid_amount"]:
            health = "attention"
            health_label = "Pago pendiente"
            next_action_label = "Revisar pagos"
            next_action_url = (
                f"/supplier-payments?view=payments&project_id={row['project_id']}"
            )
        elif row["committed_amount"] > row["received_amount"]:
            health = "attention"
            health_label = "Material por recibir"
            next_action_label = "Revisar recepciones"
            next_action_url = f"/inventory?project_id={row['project_id']}"
        else:
            health = "healthy"
            health_label = "En control"
            next_action_label = "Abrir proyecto"
            next_action_url = f"/dashboard/projects/{row['project_id']}"

        project_rows.append(
            {
                **row,
                "health": health,
                "health_label": health_label,
                "next_action_label": next_action_label,
                "next_action_url": next_action_url,
            }
        )

        if row["baseline_id"] is None:
            alerts.append(
                {
                    "key": f"baseline-{row['project_id']}",
                    "project_id": row["project_id"],
                    "project_name": row["project_name"],
                    "title": "Proyecto sin linea base de materiales",
                    "detail": "El presupuesto no puede compararse hasta aprobar su linea base.",
                    "priority": "high",
                    "action_label": "Revisar presupuesto",
                    "action_url": f"/dashboard/projects/{row['project_id']}?focus=baseline",
                }
            )
        if row["over_budget_amount"] > ZERO:
            alerts.append(
                {
                    "key": f"budget-{row['project_id']}",
                    "project_id": row["project_id"],
                    "project_name": row["project_name"],
                    "title": "Compromiso superior al presupuesto",
                    "detail": f"Excedente comprometido: ${row['over_budget_amount']:,.2f}.",
                    "priority": "critical",
                    "action_label": "Ver detalle",
                    "action_url": f"/dashboard/projects/{row['project_id']}",
                }
            )
        if row["received_amount"] > row["invoiced_amount"]:
            difference = row["received_amount"] - row["invoiced_amount"]
            alerts.append(
                {
                    "key": f"invoice-gap-{row['project_id']}",
                    "project_id": row["project_id"],
                    "project_name": row["project_name"],
                    "title": "Material recibido pendiente de factura",
                    "detail": f"Importe recibido sin facturar: ${difference:,.2f}.",
                    "priority": "high",
                    "action_label": "Revisar facturas",
                    "action_url": (
                        f"/supplier-payments?view=invoices&project_id={row['project_id']}"
                    ),
                }
            )
        if row["invoiced_amount"] > row["paid_amount"]:
            difference = row["invoiced_amount"] - row["paid_amount"]
            alerts.append(
                {
                    "key": f"payment-gap-{row['project_id']}",
                    "project_id": row["project_id"],
                    "project_name": row["project_name"],
                    "title": "Factura pendiente de pago",
                    "detail": f"Importe facturado sin pagar: ${difference:,.2f}.",
                    "priority": "normal",
                    "action_label": "Revisar pagos",
                    "action_url": (
                        f"/supplier-payments?view=payments&project_id={row['project_id']}"
                    ),
                }
            )
        for index, issue in enumerate(row["integrity_issues"][:2]):
            alerts.append(
                {
                    "key": f"integrity-{row['project_id']}-{index}",
                    "project_id": row["project_id"],
                    "project_name": row["project_name"],
                    "title": "Dato financiero por conciliar",
                    "detail": issue,
                    "priority": "critical",
                    "action_label": "Abrir conciliaciones",
                    "action_url": "/supplier-payments?view=reconciliations",
                }
            )

    priority_order = {"critical": 0, "high": 1, "normal": 2}
    alerts.sort(key=lambda item: priority_order.get(item["priority"], 3))
    attention_projects = sum(1 for row in project_rows if row["health"] != "healthy")
    invoice_gap_projects = sum(
        1 for row in visible_projects if row["received_amount"] > row["invoiced_amount"]
    )
    payment_gap_projects = sum(
        1 for row in visible_projects if row["invoiced_amount"] > row["paid_amount"]
    )
    for stage in flow:
        if stage["key"] == "invoices":
            stage["count"] = max(stage["count"], invoice_gap_projects)
            stage["attention_count"] = max(
                stage["attention_count"], invoice_gap_projects
            )
        elif stage["key"] == "payments":
            stage["count"] = max(stage["count"], payment_gap_projects)
            stage["attention_count"] = max(
                stage["attention_count"], payment_gap_projects
            )

    def total(key: str) -> Decimal:
        return sum((Decimal(row[key]) for row in visible_projects), ZERO)

    totals = {
        "project_count": len(project_rows),
        "active_project_count": len(project_rows),
        "attention_project_count": attention_projects,
        "houses_count": total("houses_count"),
        "budget_amount": total("budget_amount"),
        "committed_amount": total("committed_amount"),
        "received_amount": total("received_amount"),
        "invoiced_amount": total("invoiced_amount"),
        "paid_amount": total("paid_amount"),
        "available_amount": total("available_amount"),
        "over_budget_amount": total("over_budget_amount"),
        "purchase_orders_count": sum(row["purchase_orders_count"] for row in visible_projects),
        "invoices_count": sum(row["invoices_count"] for row in visible_projects),
        "payments_count": sum(row["payments_count"] for row in visible_projects),
    }
    return {
        "generated_at": datetime.now(timezone.utc),
        "selected_project_id": project_id,
        "totals": totals,
        "flow": flow,
        "alerts": alerts[:12],
        "projects": project_rows,
        "materials": financial["materials"] if project_id is not None else [],
    }
