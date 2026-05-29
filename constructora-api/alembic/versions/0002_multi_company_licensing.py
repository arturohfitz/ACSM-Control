"""multi company licensing

Revision ID: 0002_multi_company_licensing
Revises: 0001_initial
Create Date: 2026-05-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_multi_company_licensing"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("tax_id", sa.String(length=80), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=80), nullable=True),
        sa.Column("plan_name", sa.String(length=80), nullable=False, server_default="standard"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("license_status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("license_starts_at", sa.Date(), nullable=True),
        sa.Column("license_expires_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.execute(
        """
        INSERT INTO companies
            (name, legal_name, plan_name, max_users, license_status, notes)
        VALUES
            ('ACSM S.A de C.V.', 'ACSM S.A de C.V.', 'owner', 999, 'active',
             'Empresa propietaria del sistema ACSM Control')
        """
    )

    op.add_column("users", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_company_id"), "users", ["company_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_users_company_id_companies"), "users", "companies", ["company_id"], ["id"]
    )
    op.execute(
        """
        UPDATE users
        SET company_id = (SELECT id FROM companies WHERE name = 'ACSM S.A de C.V.' LIMIT 1)
        WHERE company_id IS NULL
        """
    )

    for table_name in (
        "clients",
        "projects",
        "house_models",
        "materials",
        "labor_rates",
        "construction_concepts",
        "quotes",
    ):
        op.add_column(table_name, sa.Column("company_id", sa.Integer(), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_company_id"), table_name, ["company_id"], unique=False)
        op.create_foreign_key(
            op.f(f"fk_{table_name}_company_id_companies"),
            table_name,
            "companies",
            ["company_id"],
            ["id"],
        )
        op.execute(
            f"""
            UPDATE {table_name}
            SET company_id = (SELECT id FROM companies WHERE name = 'ACSM S.A de C.V.' LIMIT 1)
            WHERE company_id IS NULL
            """
        )

    op.drop_constraint(
        op.f("uq_construction_concepts_code"),
        "construction_concepts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_construction_concepts_company_code",
        "construction_concepts",
        ["company_id", "code"],
    )

    for table_name in (
        "clients",
        "projects",
        "house_models",
        "materials",
        "labor_rates",
        "construction_concepts",
        "quotes",
    ):
        op.alter_column(table_name, "company_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "uq_construction_concepts_company_code",
        "construction_concepts",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_construction_concepts_code"), "construction_concepts", ["code"]
    )

    for table_name in reversed(
        (
            "clients",
            "projects",
            "house_models",
            "materials",
            "labor_rates",
            "construction_concepts",
            "quotes",
        )
    ):
        op.drop_constraint(op.f(f"fk_{table_name}_company_id_companies"), table_name, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table_name}_company_id"), table_name=table_name)
        op.drop_column(table_name, "company_id")

    op.drop_constraint(op.f("fk_users_company_id_companies"), "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_company_id"), table_name="users")
    op.drop_column("users", "company_id")
    op.drop_table("companies")
