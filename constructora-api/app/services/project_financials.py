from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    HouseModel,
    HouseModelDocument,
    HouseModelMaterialRequirement,
    Project,
    ProjectHouseModel,
    ProjectMaterialBudgetBaseline,
    ProjectMaterialBudgetItem,
    PurchaseOrder,
    PurchaseOrderItem,
    SupplierInvoice,
)


ZERO = Decimal("0")
CENT = Decimal("0.01")
FOUR = Decimal("0.0001")
PERCENT = Decimal("0.1")


def _money(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def _quantity(value: Decimal | int | None) -> Decimal:
    return Decimal(value or 0).quantize(FOUR, rounding=ROUND_HALF_UP)


def _percent(value: Decimal, budget: Decimal) -> Decimal:
    if budget <= ZERO:
        return ZERO
    return ((value / budget) * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)


def _invoice_net(invoice: SupplierInvoice) -> tuple[Decimal, str | None]:
    if invoice.subtotal is not None:
        return _money(invoice.subtotal), None
    if invoice.items:
        return _money(sum((item.line_total for item in invoice.items), ZERO)), None
    return _money(invoice.total), (
        f"Factura {invoice.invoice_number} no tiene subtotal; se uso el total fiscal como referencia."
    )


def _exchange(value: Decimal, invoice: SupplierInvoice) -> tuple[Decimal, str | None]:
    if invoice.currency.upper() == "MXN":
        return _money(value), None
    if invoice.exchange_rate is None:
        return _money(value), (
            f"Factura {invoice.invoice_number} esta en {invoice.currency} sin tipo de cambio."
        )
    return _money(value * invoice.exchange_rate), None


def approve_project_material_budget(
    db: Session,
    *,
    project: Project,
    approved_by: int,
    notes: str | None,
) -> ProjectMaterialBudgetBaseline:
    assignments = list(
        db.scalars(
            select(ProjectHouseModel)
            .where(ProjectHouseModel.project_id == project.id)
            .options(selectinload(ProjectHouseModel.house_model))
            .order_by(ProjectHouseModel.id)
        ).all()
    )
    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asigna al menos un modelo y su numero de viviendas antes de aprobar el presupuesto.",
        )

    source_rows: list[
        tuple[ProjectHouseModel, HouseModelDocument, HouseModelMaterialRequirement, Decimal, Decimal]
    ] = []
    errors: list[str] = []
    for assignment in assignments:
        document = db.scalar(
            select(HouseModelDocument)
            .where(
                HouseModelDocument.company_id == project.company_id,
                HouseModelDocument.house_model_id == assignment.house_model_id,
                HouseModelDocument.document_type == "explosion",
            )
            .order_by(HouseModelDocument.created_at.desc(), HouseModelDocument.id.desc())
            .limit(1)
        )
        if document is None:
            errors.append(f"{assignment.house_model.name}: falta la explosion de materiales.")
            continue
        requirements = list(
            db.scalars(
                select(HouseModelMaterialRequirement)
                .where(
                    HouseModelMaterialRequirement.document_id == document.id,
                    HouseModelMaterialRequirement.validation_status != "ignored",
                )
                .order_by(
                    HouseModelMaterialRequirement.sort_order,
                    HouseModelMaterialRequirement.id,
                )
            ).all()
        )
        if not requirements:
            errors.append(f"{assignment.house_model.name}: la explosion no tiene partidas integradas.")
            continue
        for requirement in requirements:
            if requirement.validation_status != "validated" or requirement.material_id is None:
                errors.append(
                    f"{assignment.house_model.name}: valida y vincula {requirement.description}."
                )
                continue
            quantity = Decimal(requirement.quantity_per_house or 0) * Decimal(assignment.quantity)
            unit_cost = requirement.unit_cost_reference
            if unit_cost is None and requirement.total_cost_reference is not None:
                per_house = Decimal(requirement.quantity_per_house or 0)
                if per_house > ZERO:
                    unit_cost = Decimal(requirement.total_cost_reference) / per_house
            if unit_cost is None:
                errors.append(
                    f"{assignment.house_model.name}: {requirement.description} no tiene costo unitario."
                )
                continue
            line_total = (
                Decimal(requirement.total_cost_reference) * Decimal(assignment.quantity)
                if requirement.total_cost_reference is not None
                else quantity * Decimal(unit_cost)
            )
            source_rows.append((assignment, document, requirement, unit_cost, line_total))

    if errors:
        detail = "No se puede aprobar la linea base: " + " ".join(errors[:8])
        if len(errors) > 8:
            detail += f" Hay {len(errors) - 8} observaciones adicionales."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    previous = list(
        db.scalars(
            select(ProjectMaterialBudgetBaseline).where(
                ProjectMaterialBudgetBaseline.project_id == project.id,
                ProjectMaterialBudgetBaseline.status == "approved",
            )
        ).all()
    )
    for baseline in previous:
        baseline.status = "superseded"
    revision = int(
        db.scalar(
            select(func.coalesce(func.max(ProjectMaterialBudgetBaseline.revision), 0)).where(
                ProjectMaterialBudgetBaseline.project_id == project.id
            )
        )
        or 0
    ) + 1
    total_amount = _money(sum((row[4] for row in source_rows), ZERO))
    baseline = ProjectMaterialBudgetBaseline(
        company_id=project.company_id,
        project_id=project.id,
        revision=revision,
        status="approved",
        currency="MXN",
        total_amount=total_amount,
        approved_at=datetime.now(timezone.utc),
        approved_by=approved_by,
        notes=notes,
    )
    db.add(baseline)
    db.flush()
    for assignment, document, requirement, unit_cost, line_total in source_rows:
        db.add(
            ProjectMaterialBudgetItem(
                baseline_id=baseline.id,
                house_model_id=assignment.house_model_id,
                source_document_id=document.id,
                material_requirement_id=requirement.id,
                material_id=requirement.material_id,
                source_code=requirement.source_code,
                description=requirement.description,
                unit=requirement.unit,
                houses_quantity=assignment.quantity,
                quantity_per_house=requirement.quantity_per_house,
                budget_quantity=_quantity(
                    Decimal(requirement.quantity_per_house) * Decimal(assignment.quantity)
                ),
                unit_cost=_quantity(unit_cost),
                line_total=_money(line_total),
            )
        )
    db.flush()
    return baseline


def project_financial_progress(
    db: Session,
    *,
    company_id: int,
    project_id: int | None,
    allowed_client_ids: list[int] | None = None,
) -> dict:
    project_statement = select(Project).where(Project.company_id == company_id)
    if allowed_client_ids is not None:
        project_statement = project_statement.where(Project.client_id.in_(allowed_client_ids))
    projects = list(
        db.scalars(
            project_statement.options(
                selectinload(Project.client),
                selectinload(Project.project_house_models),
                selectinload(Project.material_budget_baselines).selectinload(
                    ProjectMaterialBudgetBaseline.items
                ),
            )
            .execution_options(populate_existing=True)
            .order_by(Project.name)
        ).all()
    )
    project_ids = [project.id for project in projects]
    orders = (
        list(
            db.scalars(
                select(PurchaseOrder)
                .where(
                    PurchaseOrder.company_id == company_id,
                    PurchaseOrder.project_id.in_(project_ids),
                    PurchaseOrder.status != "cancelled",
                )
                .options(
                    selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.house_model),
                    selectinload(PurchaseOrder.invoices).selectinload(SupplierInvoice.items),
                    selectinload(PurchaseOrder.invoices).selectinload(SupplierInvoice.payments),
                )
                .execution_options(populate_existing=True)
            ).all()
        )
        if project_ids
        else []
    )
    orders_by_project: dict[int, list[PurchaseOrder]] = defaultdict(list)
    for order in orders:
        orders_by_project[order.project_id].append(order)

    project_rows: list[dict] = []
    material_rows: list[dict] = []
    for project in projects:
        approved_baselines = [
            baseline for baseline in project.material_budget_baselines if baseline.status == "approved"
        ]
        baseline = max(approved_baselines, key=lambda item: item.revision, default=None)
        budget = _money(baseline.total_amount if baseline else ZERO)
        project_orders = orders_by_project.get(project.id, [])
        committed = _money(sum((order.subtotal for order in project_orders), ZERO))
        received = _money(
            sum(
                (
                    min(Decimal(item.received_quantity), Decimal(item.quantity_ordered))
                    * Decimal(item.unit_price)
                    for order in project_orders
                    for item in order.items
                ),
                ZERO,
            )
        )
        invoiced = ZERO
        paid = ZERO
        invoice_count = 0
        payment_count = 0
        issues: list[str] = []
        order_invoice_totals: dict[int, Decimal] = defaultdict(lambda: ZERO)

        item_values: dict[int, dict[str, Decimal]] = defaultdict(
            lambda: {
                "ordered_quantity": ZERO,
                "received_quantity": ZERO,
                "committed_amount": ZERO,
                "received_amount": ZERO,
                "invoiced_amount": ZERO,
                "paid_amount": ZERO,
            }
        )
        requirement_to_baseline: dict[int, int] = {}
        model_material_to_baseline: dict[tuple[int | None, int | None], int] = {}
        if baseline:
            for item in baseline.items:
                if item.material_requirement_id:
                    requirement_to_baseline[item.material_requirement_id] = item.id
                model_material_to_baseline[(item.house_model_id, item.material_id)] = item.id

        def baseline_item_id(po_item: PurchaseOrderItem) -> int | None:
            if po_item.house_model_material_requirement_id:
                found = requirement_to_baseline.get(po_item.house_model_material_requirement_id)
                if found:
                    return found
            return model_material_to_baseline.get((po_item.house_model_id, po_item.material_id))

        for order in project_orders:
            po_items = {item.id: item for item in order.items}
            for po_item in order.items:
                target = baseline_item_id(po_item)
                if target is None:
                    continue
                item_values[target]["ordered_quantity"] += Decimal(po_item.quantity_ordered)
                item_values[target]["received_quantity"] += Decimal(po_item.received_quantity)
                item_values[target]["committed_amount"] += Decimal(po_item.line_total)
                item_values[target]["received_amount"] += (
                    min(Decimal(po_item.received_quantity), Decimal(po_item.quantity_ordered))
                    * Decimal(po_item.unit_price)
                )
            for invoice in order.invoices:
                if invoice.status in {"rejected", "cancelled"}:
                    continue
                invoice_count += 1
                net, issue = _invoice_net(invoice)
                net_mxn, exchange_issue = _exchange(net, invoice)
                if issue:
                    issues.append(issue)
                if exchange_issue:
                    issues.append(exchange_issue)
                invoiced += net_mxn
                order_invoice_totals[order.id] += net_mxn
                paid_fiscal = sum(
                    (Decimal(payment.amount) for payment in invoice.payments if payment.status == "paid"),
                    ZERO,
                )
                payment_count += sum(1 for payment in invoice.payments if payment.status == "paid")
                paid_net = ZERO
                if Decimal(invoice.total or 0) > ZERO:
                    paid_net = net * min(paid_fiscal / Decimal(invoice.total), Decimal("1"))
                paid_mxn, paid_exchange_issue = _exchange(paid_net, invoice)
                paid += paid_mxn
                if paid_exchange_issue and paid_exchange_issue not in issues:
                    issues.append(paid_exchange_issue)

                allocation: dict[int, Decimal] = defaultdict(lambda: ZERO)
                if invoice.items:
                    for invoice_item in invoice.items:
                        po_item = po_items.get(invoice_item.purchase_order_item_id)
                        if po_item is None:
                            continue
                        target = baseline_item_id(po_item)
                        if target is not None:
                            line_mxn, _ = _exchange(Decimal(invoice_item.line_total), invoice)
                            allocation[target] += line_mxn
                elif Decimal(order.subtotal or 0) > ZERO:
                    for po_item in order.items:
                        target = baseline_item_id(po_item)
                        if target is not None:
                            allocation[target] += net_mxn * (
                                Decimal(po_item.line_total) / Decimal(order.subtotal)
                            )
                allocated_total = sum(allocation.values(), ZERO)
                for target, amount in allocation.items():
                    item_values[target]["invoiced_amount"] += amount
                    if allocated_total > ZERO:
                        item_values[target]["paid_amount"] += paid_mxn * (amount / allocated_total)

        for order in project_orders:
            if order_invoice_totals[order.id] > Decimal(order.subtotal) + CENT:
                issues.append(
                    f"{order.po_number}: facturado neto {_money(order_invoice_totals[order.id])} "
                    f"supera la orden {_money(order.subtotal)}."
                )

        available = _money(budget - committed) if baseline else ZERO
        project_rows.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "client_name": project.client.name,
                "houses_count": sum(
                    (Decimal(item.quantity) for item in project.project_house_models), ZERO
                ),
                "models_count": len(project.project_house_models),
                "baseline_id": baseline.id if baseline else None,
                "baseline_revision": baseline.revision if baseline else None,
                "baseline_status": baseline.status if baseline else None,
                "baseline_approved_at": baseline.approved_at if baseline else None,
                "budget_amount": budget,
                "committed_amount": _money(committed),
                "received_amount": _money(received),
                "invoiced_amount": _money(invoiced),
                "paid_amount": _money(paid),
                "available_amount": max(available, ZERO),
                "over_budget_amount": abs(min(available, ZERO)) if baseline else ZERO,
                "committed_percent": _percent(committed, budget),
                "received_percent": _percent(received, budget),
                "invoiced_percent": _percent(invoiced, budget),
                "paid_percent": _percent(paid, budget),
                "purchase_orders_count": len(project_orders),
                "invoices_count": invoice_count,
                "payments_count": payment_count,
                "integrity_issues": list(dict.fromkeys(issues)),
            }
        )

        if project_id == project.id and baseline:
            model_names = {
                item.house_model_id: item.house_model.name
                for item in db.scalars(
                    select(ProjectMaterialBudgetItem)
                    .where(ProjectMaterialBudgetItem.baseline_id == baseline.id)
                    .options(selectinload(ProjectMaterialBudgetItem.house_model))
                ).all()
                if item.house_model is not None
            }
            for item in sorted(baseline.items, key=lambda row: (row.description, row.id)):
                values = item_values[item.id]
                committed_line = _money(values["committed_amount"])
                budget_line = _money(item.line_total)
                available_line = _money(budget_line - committed_line)
                if committed_line > budget_line:
                    line_status = "over_budget"
                elif _money(values["paid_amount"]) >= budget_line and budget_line > ZERO:
                    line_status = "paid"
                elif committed_line > ZERO:
                    line_status = "in_progress"
                else:
                    line_status = "pending"
                material_rows.append(
                    {
                        "baseline_item_id": item.id,
                        "house_model_id": item.house_model_id,
                        "house_model_name": model_names.get(item.house_model_id, "Modelo"),
                        "source_code": item.source_code,
                        "description": item.description,
                        "unit": item.unit,
                        "houses_quantity": item.houses_quantity,
                        "quantity_per_house": item.quantity_per_house,
                        "budget_quantity": item.budget_quantity,
                        "ordered_quantity": _quantity(values["ordered_quantity"]),
                        "received_quantity": _quantity(values["received_quantity"]),
                        "budget_amount": budget_line,
                        "committed_amount": committed_line,
                        "received_amount": _money(values["received_amount"]),
                        "invoiced_amount": _money(values["invoiced_amount"]),
                        "paid_amount": _money(values["paid_amount"]),
                        "available_amount": max(available_line, ZERO),
                        "committed_percent": _percent(committed_line, budget_line),
                        "paid_percent": _percent(_money(values["paid_amount"]), budget_line),
                        "status": line_status,
                    }
                )

    return {
        "projects": project_rows,
        "selected_project_id": project_id,
        "materials": material_rows,
    }
