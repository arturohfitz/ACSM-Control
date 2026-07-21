from sqlalchemy import text
from sqlalchemy.orm import Session


def _delete_company_rows(db: Session, company_id: int, *table_names: str) -> None:
    for table_name in table_names:
        db.execute(
            text(f"DELETE FROM {table_name} WHERE company_id = :company_id"),
            {"company_id": company_id},
        )


def _delete_related(db: Session, company_id: int, statement: str) -> None:
    db.execute(text(statement), {"company_id": company_id})


def cleanup_company_data(db: Session, company_id: int) -> None:
    """Remove one test tenant without touching operational tenants."""
    db.rollback()
    _delete_company_rows(
        db,
        company_id,
        "inventory_movements",
        "notifications",
        "audit_events",
        "email_outbox_messages",
        "supplier_payments",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM supplier_invoice_items WHERE supplier_invoice_id IN "
        "(SELECT id FROM supplier_invoices WHERE company_id = :company_id)",
    )
    _delete_company_rows(db, company_id, "supplier_invoice_documents")
    _delete_related(
        db,
        company_id,
        "DELETE FROM material_reception_items WHERE reception_id IN "
        "(SELECT id FROM material_receptions WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "material_receptions",
        "warehouse_stock",
        "expected_material_items",
        "expected_material_lists",
        "supplier_invoices",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM purchase_order_items WHERE purchase_order_id IN "
        "(SELECT id FROM purchase_orders WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "purchase_orders",
        "supplier_quote_approvals",
        "supplier_quote_uploads",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM supplier_quote_items WHERE supplier_quote_id IN "
        "(SELECT id FROM supplier_quotes WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM material_requisition_items WHERE requisition_id IN "
        "(SELECT id FROM material_requisitions WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "supplier_quotes",
        "supplier_rfq_exception_requests",
        "material_requisitions",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM supplier_rfq_suppliers WHERE rfq_id IN "
        "(SELECT id FROM supplier_rfqs WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM supplier_rfq_items WHERE rfq_id IN "
        "(SELECT id FROM supplier_rfqs WHERE company_id = :company_id)",
    )
    _delete_company_rows(db, company_id, "supplier_rfqs")
    _delete_related(
        db,
        company_id,
        "DELETE FROM quote_items WHERE quote_id IN "
        "(SELECT id FROM quotes WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "quotes",
        "project_material_prices",
        "project_warehouses",
        "project_material_budget_baselines",
        "house_model_budget_activities",
        "house_model_material_requirements",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM project_house_models WHERE project_id IN "
        "(SELECT id FROM projects WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM house_model_concepts WHERE house_model_id IN "
        "(SELECT id FROM house_models WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM concept_labor WHERE construction_concept_id IN "
        "(SELECT id FROM construction_concepts WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM concept_materials WHERE construction_concept_id IN "
        "(SELECT id FROM construction_concepts WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM supplier_agreement_items WHERE agreement_id IN "
        "(SELECT id FROM supplier_agreements WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "house_model_documents",
        "construction_concepts",
        "labor_rates",
        "material_unit_conversions",
        "materials",
        "supplier_agreements",
        "suppliers",
        "house_models",
        "projects",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM role_permissions WHERE role_id IN "
        "(SELECT id FROM roles WHERE company_id = :company_id)",
    )
    _delete_related(
        db,
        company_id,
        "DELETE FROM user_roles WHERE user_id IN "
        "(SELECT id FROM users WHERE company_id = :company_id) "
        "OR role_id IN (SELECT id FROM roles WHERE company_id = :company_id)",
    )
    _delete_company_rows(
        db,
        company_id,
        "user_client_access",
        "clients",
        "system_email_settings",
        "system_notification_settings",
        "roles",
        "users",
    )
    db.execute(text("DELETE FROM companies WHERE id = :company_id"), {"company_id": company_id})
    db.commit()
