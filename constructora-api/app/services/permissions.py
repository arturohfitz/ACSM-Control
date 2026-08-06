from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission, Role, RolePermission, User, UserRole


DEFAULT_PERMISSIONS: list[tuple[str, str, str]] = [
    ("executive_dashboard", "view", "Ver control ejecutivo de la constructora"),
    ("executive_dashboard", "export", "Exportar indicadores ejecutivos"),
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
    ("inventory_reception_history", "view", "Ver historial de recepciones de material"),
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
    ("project_financials", "view", "Ver avance financiero de materiales por desarrollo"),
    ("project_material_budgets", "approve", "Aprobar linea base del presupuesto de materiales"),
    ("financial_reconciliations", "view", "Ver conciliaciones financieras"),
    ("financial_reconciliations", "request", "Solicitar correcciones financieras"),
    ("financial_reconciliations", "approve", "Aprobar y aplicar correcciones financieras"),
]

TENANT_ADMIN_EXCLUDED_PERMISSIONS: set[str] = {
    "settings:view",
    "settings:edit",
    "settings:test_email",
}

DEFAULT_TENANT_ROLE_TEMPLATES: list[tuple[str, str, set[str]]] = [
    (
        "Administrador",
        "Acceso total a la operacion de la constructora, sin ajustes globales del sistema",
        {"*:*"},
    ),
    (
        "Obra",
        "Operacion de obra: consulta catalogos y envia requerimientos de material a Compras",
        {
            "clients:view",
            "projects:view",
            "house_models:view",
            "materials:view",
            "materials:create",
            "construction_concepts:view",
            "construction_concepts:create",
            "material_requisitions:view",
            "material_requisitions:create",
            "suppliers:view",
            "notifications:view",
        },
    ),
    (
        "Inventarios",
        "Recepcion de material, control de avance, faltantes y existencias de bodega",
        {
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
            "inventory_reception_history:view",
            "inventory_progress:view",
            "inventory_missing:view",
            "inventory_stock:view",
            "suppliers:view",
            "purchase_orders:view",
            "notifications:view",
        },
    ),
    (
        "Compras",
        "Gestion de proveedores, convenios, solicitudes de cotizacion y ordenes de compra",
        {
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
            "supplier_invoices:view",
            "supplier_invoices:upload",
            "notifications:view",
        },
    ),
    (
        "Cuentas por pagar",
        "Revision fiscal de facturas, programacion y registro de pagos a proveedores",
        {
            "projects:view",
            "suppliers:view",
            "purchase_orders:view",
            "supplier_invoices:view",
            "supplier_invoices:upload",
            "supplier_invoices:validate",
            "supplier_payments:view",
            "supplier_payments:schedule",
            "supplier_payments:pay",
            "project_financials:view",
            "financial_reconciliations:view",
            "financial_reconciliations:request",
            "notifications:view",
        },
    ),
    (
        "Direccion",
        "Consulta ejecutiva del portafolio, aprobaciones y avance financiero de proyectos",
        {
            "executive_dashboard:view",
            "executive_dashboard:export",
            "clients:view",
            "projects:view",
            "house_models:view",
            "materials:view",
            "material_requisitions:view",
            "supplier_rfq:view",
            "supplier_quotes:view",
            "purchase_approvals:view",
            "purchase_orders:view",
            "inventory_reception_history:view",
            "inventory_progress:view",
            "inventory_missing:view",
            "inventory_stock:view",
            "supplier_invoices:view",
            "supplier_payments:view",
            "project_financials:view",
            "financial_reconciliations:view",
            "notifications:view",
        },
    ),
]


def permission_code(module: str, action: str) -> str:
    return f"{module}:{action}"


def get_user_permission_codes(user: User) -> set[str]:
    if user.is_master_admin:
        return {"*:*"}
    codes: set[str] = set()
    for role in user.roles:
        for permission in role.permissions:
            codes.add(permission_code(permission.module, permission.action))
    return codes


def user_has_permission(user: User, module: str, action: str) -> bool:
    if user.is_master_admin:
        return True
    return permission_code(module, action) in get_user_permission_codes(user)


def ensure_default_permissions(db: Session) -> list[Permission]:
    existing = {
        (permission.module, permission.action): permission
        for permission in db.scalars(select(Permission)).all()
    }
    permissions: list[Permission] = []
    for module, action, description in DEFAULT_PERMISSIONS:
        permission = existing.get((module, action))
        if permission is None:
            permission = Permission(module=module, action=action, description=description)
            db.add(permission)
        permissions.append(permission)
    db.flush()
    return permissions


def tenant_permission_ids(
    permissions: list[Permission],
    requested_codes: set[str],
) -> list[int]:
    permission_by_code = {
        permission_code(permission.module, permission.action): permission
        for permission in permissions
    }
    if "*:*" in requested_codes:
        codes = set(permission_by_code) - TENANT_ADMIN_EXCLUDED_PERMISSIONS
    else:
        codes = requested_codes - TENANT_ADMIN_EXCLUDED_PERMISSIONS
    return [
        permission_by_code[code].id
        for code in sorted(codes)
        if code in permission_by_code
    ]


def ensure_default_company_roles(db: Session, company_id: int) -> list[Role]:
    permissions = ensure_default_permissions(db)
    roles: list[Role] = []
    for name, description, requested_codes in DEFAULT_TENANT_ROLE_TEMPLATES:
        role = db.scalar(
            select(Role).where(
                Role.company_id == company_id,
                Role.name == name,
                Role.is_system_role.is_(False),
            )
        )
        if role is None:
            role = Role(
                company_id=company_id,
                name=name,
                description=description,
                is_system_role=False,
            )
            db.add(role)
            db.flush()
        set_role_permissions(
            db,
            role.id,
            tenant_permission_ids(permissions, requested_codes),
        )
        roles.append(role)
    db.flush()
    return roles


def set_role_permissions(db: Session, role_id: int, permission_ids: list[int]) -> None:
    current = db.scalars(
        select(RolePermission).where(RolePermission.role_id == role_id)
    ).all()
    current_by_permission = {item.permission_id: item for item in current}
    desired = set(permission_ids)

    for permission_id, item in current_by_permission.items():
        if permission_id not in desired:
            db.delete(item)

    for permission_id in desired:
        if permission_id not in current_by_permission:
            db.add(RolePermission(role_id=role_id, permission_id=permission_id))


def set_user_roles(db: Session, user_id: int, role_ids: list[int]) -> None:
    current = db.scalars(select(UserRole).where(UserRole.user_id == user_id)).all()
    current_by_role = {item.role_id: item for item in current}
    desired = set(role_ids)

    for role_id, item in current_by_role.items():
        if role_id not in desired:
            db.delete(item)

    for role_id in desired:
        if role_id not in current_by_role:
            db.add(UserRole(user_id=user_id, role_id=role_id))


def ensure_roles_assignable(
    db: Session,
    role_ids: list[int],
    current_user: User,
    target_company_id: int | None,
    allow_system_roles: bool = False,
) -> None:
    desired = set(role_ids)
    if not desired:
        return

    roles = db.scalars(select(Role).where(Role.id.in_(desired))).all()
    if len(roles) != len(desired):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uno o mas roles no existen",
        )

    for role in roles:
        is_global_role = role.is_system_role or role.company_id is None
        if is_global_role:
            if not (current_user.is_master_admin and allow_system_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No se pueden asignar roles de sistema",
                )
            continue

        if role.company_id != target_company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden asignar roles de otra empresa",
            )
