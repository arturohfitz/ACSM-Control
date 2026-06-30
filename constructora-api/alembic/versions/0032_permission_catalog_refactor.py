"""permission catalog refactor

Revision ID: 0032_permission_catalog_refactor
Revises: 0031_mr_requested_unit
Create Date: 2026-06-30 09:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_permission_catalog_refactor"
down_revision = "0031_mr_requested_unit"
branch_labels = None
depends_on = None


ACTIVE_PERMISSIONS: list[tuple[str, str, str]] = [
    ("projects", "view", "Ver proyectos"),
    ("projects", "create", "Crear proyectos"),
    ("projects", "edit", "Editar proyectos"),
    ("projects", "delete", "Eliminar proyectos"),
    ("materials", "view", "Ver materiales"),
    ("materials", "create", "Crear materiales"),
    ("materials", "edit", "Editar materiales"),
    ("materials", "delete", "Eliminar materiales"),
    ("material_requisitions", "view", "Ver requerimientos de material de obra"),
    ("material_requisitions", "create", "Crear requerimientos de material de obra"),
    ("material_requisitions", "review", "Revisar requerimientos de material de obra"),
    ("material_requisitions", "convert_to_rfq", "Convertir requerimientos de obra a solicitud de cotizacion"),
    ("users", "view", "Ver usuarios"),
    ("users", "create", "Crear usuarios"),
    ("users", "edit", "Editar usuarios"),
    ("users", "delete", "Eliminar usuarios"),
    ("roles", "view", "Ver roles"),
    ("roles", "create", "Crear roles"),
    ("roles", "edit", "Editar roles"),
    ("roles", "delete", "Eliminar roles"),
    ("settings", "view", "Ver configuracion"),
    ("settings", "edit", "Editar configuracion"),
    ("settings", "test_email", "Probar configuracion de correo"),
    ("events", "view", "Ver bitacora de eventos"),
    ("notifications", "view", "Ver notificaciones"),
    ("companies", "view", "Ver empresas"),
    ("clients", "view", "Ver clientes"),
    ("clients", "create", "Crear clientes"),
    ("clients", "edit", "Editar clientes"),
    ("clients", "delete", "Eliminar clientes"),
    ("house_models", "view", "Ver modelos de casa"),
    ("house_models", "create", "Crear modelos de casa"),
    ("house_models", "edit", "Editar modelos de casa"),
    ("house_models", "delete", "Eliminar modelos de casa"),
    ("construction_concepts", "view", "Ver conceptos de obra"),
    ("construction_concepts", "create", "Crear conceptos de obra"),
    ("construction_concepts", "edit", "Editar conceptos de obra"),
    ("construction_concepts", "delete", "Eliminar conceptos de obra"),
    ("inventory", "view", "Ver inventario"),
    ("inventory", "create", "Crear bodegas y listas de material"),
    ("inventory", "edit", "Editar inventario"),
    ("inventory", "delete", "Eliminar inventario"),
    ("inventory_receiving", "view", "Ver recepcion de materiales"),
    ("inventory_receiving", "receive", "Registrar recepciones de material"),
    ("inventory_progress", "view", "Ver control de avance por modelo"),
    ("inventory_missing", "view", "Ver faltantes de material"),
    ("inventory_stock", "view", "Ver existencias de bodega"),
    ("suppliers", "view", "Ver proveedores"),
    ("suppliers", "create", "Crear proveedores"),
    ("suppliers", "edit", "Editar proveedores"),
    ("suppliers", "delete", "Eliminar proveedores"),
    ("supplier_agreements", "view", "Ver convenios de proveedores"),
    ("supplier_agreements", "create", "Crear convenios de proveedores"),
    ("supplier_agreements", "edit", "Editar convenios de proveedores"),
    ("supplier_agreements", "delete", "Eliminar convenios de proveedores"),
    ("supplier_agreements", "use", "Crear solicitudes directas por convenio"),
    ("supplier_agreements", "approve", "Aprobar o rechazar convenios de proveedores"),
    ("supplier_rfq", "view", "Ver solicitudes a proveedores"),
    ("supplier_rfq", "create", "Crear solicitudes a proveedores"),
    ("supplier_rfq", "edit", "Editar solicitudes a proveedores"),
    ("supplier_rfq", "send", "Enviar solicitudes a proveedores"),
    ("supplier_quotes", "view", "Ver cotizaciones de proveedores"),
    ("supplier_quotes", "create", "Capturar cotizaciones de proveedores"),
    ("supplier_quotes", "edit", "Editar cotizaciones de proveedores"),
    ("supplier_quotes", "compare", "Comparar cotizaciones de proveedores"),
    ("supplier_quotes", "request_approval", "Solicitar aprobacion de cotizaciones de proveedores"),
    ("supplier_quotes", "approve", "Aprobar o rechazar cotizaciones de proveedores"),
    ("purchase_approvals", "view", "Ver aprobaciones de compras"),
    ("purchase_orders", "view", "Ver ordenes de compra"),
    ("purchase_orders", "send", "Enviar orden de compra"),
    ("supplier_invoices", "view", "Ver facturas de proveedor"),
    ("supplier_invoices", "upload", "Cargar facturas de proveedor"),
    ("supplier_invoices", "validate", "Validar facturas contra recepcion"),
    ("supplier_payments", "view", "Ver pagos a proveedores"),
    ("supplier_payments", "schedule", "Programar pagos a proveedores"),
    ("supplier_payments", "pay", "Registrar pago a proveedor"),
]

OBSOLETE_PERMISSION_CODES = {
    "quotes:view",
    "quotes:create",
    "quotes:edit",
    "quotes:approve",
    "quotes:view_costs",
    "quotes:view_profit",
    "labor:view",
    "labor:create",
    "labor:edit",
    "labor:delete",
    "material_requisitions:edit",
    "material_requisitions:cancel",
    "companies:create",
    "companies:edit",
    "companies:delete",
    "inventory:receive",
    "supplier_rfq:cancel",
    "purchase_orders:approve",
    "purchase_orders:cancel",
    "supplier_invoices:reject",
}

TENANT_ADMIN_EXCLUDED_CODES = {
    "settings:view",
    "settings:edit",
    "settings:test_email",
}

ROLE_TEMPLATES: dict[str, set[str]] = {
    "Administrador": {"*:*"},
    "Obra": {
        "clients:view",
        "projects:view",
        "house_models:view",
        "materials:view",
        "construction_concepts:view",
        "material_requisitions:view",
        "material_requisitions:create",
        "notifications:view",
    },
    "Inventarios": {
        "clients:view",
        "projects:view",
        "house_models:view",
        "materials:view",
        "material_requisitions:view",
        "inventory:view",
        "inventory:create",
        "inventory:edit",
        "inventory_receiving:view",
        "inventory_receiving:receive",
        "inventory_progress:view",
        "inventory_missing:view",
        "inventory_stock:view",
        "suppliers:view",
        "purchase_orders:view",
        "supplier_invoices:view",
        "supplier_invoices:upload",
        "supplier_invoices:validate",
        "notifications:view",
    },
    "Compras": {
        "clients:view",
        "projects:view",
        "house_models:view",
        "materials:view",
        "materials:create",
        "materials:edit",
        "material_requisitions:view",
        "material_requisitions:review",
        "material_requisitions:convert_to_rfq",
        "inventory:view",
        "suppliers:view",
        "suppliers:create",
        "suppliers:edit",
        "supplier_agreements:view",
        "supplier_agreements:create",
        "supplier_agreements:edit",
        "supplier_agreements:use",
        "supplier_rfq:view",
        "supplier_rfq:create",
        "supplier_rfq:edit",
        "supplier_rfq:send",
        "supplier_quotes:view",
        "supplier_quotes:create",
        "supplier_quotes:edit",
        "supplier_quotes:compare",
        "supplier_quotes:request_approval",
        "purchase_orders:view",
        "purchase_orders:send",
        "notifications:view",
    },
}


def _code(module: str, action: str) -> str:
    return f"{module}:{action}"


def _permission_ids(conn, codes: set[str]) -> list[int]:
    if not codes:
        return []
    rows = conn.execute(
        sa.text(
            """
            SELECT id, module, action
            FROM permissions
            WHERE (module || ':' || action) = ANY(:codes)
            """
        ),
        {"codes": list(codes)},
    ).mappings()
    return [row["id"] for row in rows]


def _replace_role_permissions(conn, role_id: int, permission_ids: list[int]) -> None:
    conn.execute(sa.text("DELETE FROM role_permissions WHERE role_id = :role_id"), {"role_id": role_id})
    if not permission_ids:
        return
    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT :role_id, permission_id
            FROM unnest(:permission_ids) AS permission_id
            """
        ),
        {"role_id": role_id, "permission_ids": permission_ids},
    )


def upgrade() -> None:
    conn = op.get_bind()

    for module, action, description in ACTIVE_PERMISSIONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO permissions (module, action, description)
                VALUES (:module, :action, :description)
                ON CONFLICT (module, action)
                DO UPDATE SET description = EXCLUDED.description
                """
            ),
            {"module": module, "action": action, "description": description},
        )

    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions rp
            USING permissions p
            WHERE rp.permission_id = p.id
              AND (p.module || ':' || p.action) = ANY(:codes)
            """
        ),
        {"codes": list(OBSOLETE_PERMISSION_CODES)},
    )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE (module || ':' || action) = ANY(:codes)"),
        {"codes": list(OBSOLETE_PERMISSION_CODES)},
    )

    active_codes = {_code(module, action) for module, action, _description in ACTIVE_PERMISSIONS}
    role_rows = conn.execute(
        sa.text(
            """
            SELECT id, name, company_id, is_system_role
            FROM roles
            WHERE name = 'master_admin'
               OR name = ANY(:role_names)
            """
        ),
        {"role_names": list(ROLE_TEMPLATES)},
    ).mappings()

    for role in role_rows:
        if role["name"] == "master_admin":
            selected_codes = active_codes
        else:
            requested = ROLE_TEMPLATES.get(role["name"], set())
            if "*:*" in requested:
                selected_codes = active_codes - TENANT_ADMIN_EXCLUDED_CODES
            else:
                selected_codes = requested
        _replace_role_permissions(conn, role["id"], _permission_ids(conn, selected_codes))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions rp
            USING permissions p
            WHERE rp.permission_id = p.id
              AND p.module IN (
                'inventory_receiving',
                'inventory_progress',
                'inventory_missing',
                'inventory_stock',
                'purchase_approvals'
              )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE module IN (
                'inventory_receiving',
                'inventory_progress',
                'inventory_missing',
                'inventory_stock',
                'purchase_approvals'
            )
            """
        )
    )
