from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal


# Datos transaccionales y catalogos de operacion. Se conservan empresas,
# usuarios, roles, permisos y configuracion del sistema.
TABLES_TO_CLEAR = (
    "notifications",
    "audit_events",
    "email_outbox_messages",
    "supplier_payments",
    "supplier_invoices",
    "material_reception_items",
    "material_receptions",
    "warehouse_stock",
    "expected_material_items",
    "expected_material_lists",
    "purchase_order_items",
    "purchase_orders",
    "supplier_quote_approvals",
    "supplier_quote_items",
    "supplier_quotes",
    "supplier_rfq_suppliers",
    "supplier_rfq_items",
    "supplier_rfq_exception_requests",
    "supplier_rfqs",
    "quote_items",
    "quotes",
    "project_material_prices",
    "project_house_models",
    "project_warehouses",
    "house_model_budget_activities",
    "house_model_material_requirements",
    "house_model_documents",
    "house_model_concepts",
    "concept_labor",
    "concept_materials",
    "construction_concepts",
    "labor_rates",
    "materials",
    "suppliers",
    "house_models",
    "projects",
    "clients",
)

PRESERVED_TABLES = (
    "companies",
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "user_roles",
    "system_email_settings",
)

STORAGE_DIRS_TO_CLEAR = ("house_model_documents",)


def _count_rows(table_names: tuple[str, ...]) -> dict[str, int]:
    with SessionLocal() as db:
        return {
            table_name: int(
                db.execute(text(f"select count(*) from {table_name}")).scalar_one()
            )
            for table_name in table_names
        }


def _clear_tables() -> None:
    table_list = ", ".join(TABLES_TO_CLEAR)
    with SessionLocal() as db:
        db.execute(text(f"truncate table {table_list} restart identity cascade"))
        db.commit()


def _clear_storage() -> list[str]:
    storage_root = Path(__file__).resolve().parents[1] / "storage"
    removed: list[str] = []
    for dirname in STORAGE_DIRS_TO_CLEAR:
        target = storage_root / dirname
        if not target.exists():
            continue
        shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        removed.append(str(target))
    return removed


def _print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for table_name, count in counts.items():
        if count:
            print(f"- {table_name}: {count}")
    if not any(counts.values()):
        print("- Sin registros operativos.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Limpia datos operativos/demo sin borrar usuarios, roles ni configuracion."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Ejecuta la limpieza. Sin esta bandera solo muestra el diagnostico.",
    )
    parser.add_argument(
        "--files",
        action="store_true",
        help="Tambien elimina archivos operativos subidos en constructora-api/storage.",
    )
    args = parser.parse_args()

    try:
        before_counts = _count_rows(TABLES_TO_CLEAR)
    except SQLAlchemyError as exc:
        raise SystemExit(f"No fue posible leer la base de datos: {exc}") from exc

    _print_counts("Registros que se limpiaran:", before_counts)
    print("\nSe conservaran:")
    for table_name in PRESERVED_TABLES:
        print(f"- {table_name}")

    if not args.yes:
        print("\nModo diagnostico. Ejecuta con --yes para borrar los datos listados.")
        return

    try:
        _clear_tables()
    except SQLAlchemyError as exc:
        raise SystemExit(f"No fue posible limpiar la base de datos: {exc}") from exc

    removed_dirs: list[str] = []
    if args.files:
        removed_dirs = _clear_storage()

    after_counts = _count_rows(TABLES_TO_CLEAR)
    _print_counts("\nRegistros despues de limpiar:", after_counts)

    if removed_dirs:
        print("\nArchivos operativos limpiados:")
        for dirname in removed_dirs:
            print(f"- {dirname}")

    print("\nLimpieza operativa completada.")


if __name__ == "__main__":
    main()
