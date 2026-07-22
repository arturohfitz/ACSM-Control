import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import (
    Client,
    Company,
    Notification,
    Project,
    PurchaseOrder,
    PurchaseOrderItem,
    Role,
    Supplier,
    SupplierInvoice,
    User,
    UserRole,
)
from app.services.notifications import notify_permission, sync_purchase_order_invoice_readiness
from app.services.permissions import ensure_default_permissions, permission_code, set_role_permissions
from tests.db_cleanup import cleanup_company_data


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requiere RUN_DB_TESTS=1")
class NotificationWorkflowDBTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid4().hex[:10]
        self.permissions = {
            permission_code(permission.module, permission.action): permission
            for permission in ensure_default_permissions(self.db)
        }
        self.company = Company(
            name=f"Notificaciones CI {self.suffix}",
            legal_name=f"Notificaciones CI {self.suffix} SA de CV",
            contact_email=f"notificaciones-{self.suffix}@example.com",
            license_status="active",
        )
        self.db.add(self.company)
        self.db.flush()
        self.master = self._create_user("Maestro CI", is_master_admin=True)
        self.client = Client(
            company_id=self.company.id,
            name=f"Cliente CI {self.suffix}",
        )
        self.db.add(self.client)
        self.db.flush()
        self.project = Project(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Proyecto CI {self.suffix}",
            status="active",
        )
        self.supplier = Supplier(
            company_id=self.company.id,
            name=f"Proveedor CI {self.suffix}",
            status="active",
        )
        self.db.add_all([self.project, self.supplier])
        self.db.commit()

    def tearDown(self) -> None:
        cleanup_company_data(self.db, self.company.id)
        self.db.close()

    def _create_user(
        self,
        name: str,
        *,
        permissions: list[str] | None = None,
        is_master_admin: bool = False,
    ) -> User:
        user = User(
            company_id=self.company.id,
            full_name=f"{name} {self.suffix}",
            email=f"{name.lower().replace(' ', '-')}-{self.suffix}@example.com",
            password_hash=get_password_hash("Admin12345!"),
            is_active=True,
            is_master_admin=is_master_admin,
        )
        self.db.add(user)
        self.db.flush()
        if permissions:
            role = Role(
                company_id=self.company.id,
                name=f"Rol {name} {self.suffix}",
                description="Rol de prueba de notificaciones",
                is_system_role=False,
            )
            self.db.add(role)
            self.db.flush()
            set_role_permissions(
                self.db,
                role.id,
                [self.permissions[code].id for code in permissions],
            )
            self.db.add(UserRole(user_id=user.id, role_id=role.id))
        self.db.flush()
        return user

    def _purchase_order(
        self,
        *,
        suffix: str,
        billing_mode: str,
        ordered: Decimal,
        received: Decimal,
    ) -> PurchaseOrder:
        order = PurchaseOrder(
            company_id=self.company.id,
            project_id=self.project.id,
            supplier_id=self.supplier.id,
            po_number=f"OC-NOT-{suffix}-{self.suffix}",
            status="received" if received >= ordered else "partially_received",
            billing_mode=billing_mode,
            issued_at=date.today(),
            payment_terms_days=30,
            subtotal=Decimal("100.00"),
        )
        order.items.append(
            PurchaseOrderItem(
                description="Material de prueba",
                unit="PZA",
                quantity_ordered=ordered,
                unit_price=Decimal("10.00"),
                line_total=Decimal("100.00"),
                received_quantity=received,
                status="complete" if received >= ordered else "partial",
            )
        )
        self.db.add(order)
        self.db.flush()
        return order

    def test_permission_notification_falls_back_to_master_admin(self) -> None:
        delivered = notify_permission(
            self.db,
            company_id=self.company.id,
            module="supplier_quotes",
            action="approve",
            notification_type="approval_test",
            title="Aprobacion pendiente",
            body="Prueba de destinatario de respaldo.",
            source_module="compras",
            entity_type="Project",
            entity_id=self.project.id,
            project_id=self.project.id,
        )
        self.db.commit()

        self.assertEqual(delivered, 1)
        notification = self.db.scalar(
            select(Notification).where(Notification.notification_type == "approval_test")
        )
        self.assertIsNotNone(notification)
        assert notification is not None
        self.assertEqual(notification.user_id, self.master.id)
        self.assertEqual(
            notification.event_metadata["notification_routing"]["fallback"],
            "master_admin",
        )

    def test_full_receipt_notifies_invoice_entry_and_invoice_resolves_it(self) -> None:
        invoice_user = self._create_user(
            "Facturas CI",
            permissions=["supplier_invoices:upload", "notifications:view"],
        )
        order = self._purchase_order(
            suffix="TOTAL",
            billing_mode="single",
            ordered=Decimal("10"),
            received=Decimal("10"),
        )
        sync_purchase_order_invoice_readiness(self.db, purchase_order=order)
        self.db.commit()

        notification = self.db.scalar(
            select(Notification).where(
                Notification.user_id == invoice_user.id,
                Notification.notification_type == "purchase_order_ready_for_invoice",
                Notification.entity_id == str(order.id),
            )
        )
        self.assertIsNotNone(notification)
        assert notification is not None
        self.assertEqual(notification.status, "unread")

        invoice = SupplierInvoice(
            company_id=self.company.id,
            supplier_id=self.supplier.id,
            purchase_order_id=order.id,
            invoice_number=f"FAC-NOT-{self.suffix}",
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal("100.00"),
            total=Decimal("116.00"),
            currency="MXN",
            status="document_pending",
            fiscal_status="pending",
        )
        self.db.add(invoice)
        self.db.flush()
        sync_purchase_order_invoice_readiness(self.db, purchase_order=order)
        self.db.commit()
        self.db.refresh(notification)

        self.assertEqual(notification.status, "resolved")

    def test_partial_billing_notifies_received_uninvoiced_material(self) -> None:
        invoice_user = self._create_user(
            "Facturas Parciales CI",
            permissions=["supplier_invoices:upload", "notifications:view"],
        )
        order = self._purchase_order(
            suffix="PARCIAL",
            billing_mode="partial",
            ordered=Decimal("10"),
            received=Decimal("5"),
        )
        sync_purchase_order_invoice_readiness(self.db, purchase_order=order)
        self.db.commit()

        notification = self.db.scalar(
            select(Notification).where(
                Notification.user_id == invoice_user.id,
                Notification.notification_type == "purchase_order_partial_ready_for_invoice",
                Notification.entity_id == str(order.id),
            )
        )
        self.assertIsNotNone(notification)


if __name__ == "__main__":
    unittest.main()
