import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.inventory import create_reception
from app.api.v1.endpoints.purchasing import (
    approve_supplier_quote,
    create_supplier_quote,
    create_supplier_rfq,
    create_supplier_invoice,
    create_supplier_payment,
    list_supplier_quote_approvals,
    request_supplier_rfq_approval,
    supplier_rfq_comparison,
    validate_supplier_invoice,
)
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import (
    Client,
    Company,
    Project,
    ProjectWarehouse,
    PurchaseOrder,
    Supplier,
    SupplierInvoice,
    SupplierRFQ,
    User,
)
from app.schemas.inventory import MaterialReceptionCreate, MaterialReceptionItemCreate
from app.schemas.purchasing import (
    SupplierInvoiceCreate,
    SupplierPaymentCreate,
    SupplierQuoteCreate,
    SupplierQuoteItemCreate,
    SupplierRFQApprovalRequest,
    SupplierRFQCreate,
    SupplierRFQItemCreate,
)


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requiere RUN_DB_TESTS=1")
class PurchasingFlowDBTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.suffix = uuid4().hex[:10]
        self.company = Company(
            name=f"Constructora CI {self.suffix}",
            legal_name=f"Constructora CI {self.suffix} SA de CV",
            contact_email=f"ci-{self.suffix}@example.com",
            license_status="active",
        )
        self.db.add(self.company)
        self.db.flush()
        self.user = User(
            company_id=self.company.id,
            full_name="Comprador CI",
            email=f"comprador-{self.suffix}@example.com",
            password_hash=get_password_hash("Admin12345!"),
            is_active=True,
            is_master_admin=False,
        )
        self.client = Client(
            company_id=self.company.id,
            name=f"Desarrolladora CI {self.suffix}",
            contact_email=f"desarrolladora-{self.suffix}@example.com",
        )
        self.db.add_all([self.user, self.client])
        self.db.flush()
        self.project = Project(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Proyecto CI {self.suffix}",
            status="draft",
        )
        self.db.add(self.project)
        self.db.flush()
        self.warehouse = ProjectWarehouse(
            company_id=self.company.id,
            project_id=self.project.id,
            name=f"Bodega CI {self.suffix}",
            location="Patio de pruebas",
            is_active=True,
        )
        self.db.add(self.warehouse)
        self.db.flush()
        self.suppliers = [
            Supplier(
                company_id=self.company.id,
                name=f"Proveedor CI {index} {self.suffix}",
                contact_name=f"Contacto {index}",
                contact_email=f"proveedor{index}-{self.suffix}@example.com",
                payment_terms_days=30,
                average_delivery_days=5 + index,
                material_categories="Acero, concreto",
                status="active",
            )
            for index in range(1, 4)
        ]
        self.db.add_all(self.suppliers)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_rfq_quote_comparison_and_approval_request(self) -> None:
        rfq_payload = SupplierRFQCreate(
            project_id=self.project.id,
            title=f"Compra acero CI {self.suffix}",
            required_by=date.today() + timedelta(days=10),
            response_deadline=date.today() + timedelta(days=5),
            supplier_ids=[supplier.id for supplier in self.suppliers],
            items=[
                SupplierRFQItemCreate(
                    source_code="AC-001",
                    description="Varilla corrugada 3/8",
                    unit="pieza",
                    quantity=Decimal("100"),
                ),
                SupplierRFQItemCreate(
                    source_code="CN-001",
                    description="Concreto premezclado",
                    unit="m3",
                    quantity=Decimal("10"),
                ),
            ],
        )

        rfq = create_supplier_rfq(rfq_payload, BackgroundTasks(), self.db, self.user)
        persisted_rfq = self.db.get(SupplierRFQ, rfq.id)
        self.assertIsNotNone(persisted_rfq)
        self.assertEqual(persisted_rfq.status, "sent")
        self.assertEqual(len(rfq.items), 2)
        self.assertEqual(len(rfq.supplier_links), 3)

        price_sets = [
            (Decimal("20"), Decimal("1500")),
            (Decimal("22"), Decimal("1700")),
            (Decimal("19"), Decimal("1600")),
        ]
        for supplier, (steel_price, concrete_price) in zip(self.suppliers, price_sets, strict=True):
            quote_payload = SupplierQuoteCreate(
                supplier_id=supplier.id,
                quote_number=f"COT-{supplier.id}-{self.suffix}",
                delivery_days=supplier.average_delivery_days,
                payment_terms_days=supplier.payment_terms_days,
                items=[
                    SupplierQuoteItemCreate(
                        rfq_item_id=rfq.items[0].id,
                        unit_price=steel_price,
                    ),
                    SupplierQuoteItemCreate(
                        rfq_item_id=rfq.items[1].id,
                        unit_price=concrete_price,
                    ),
                ],
            )
            create_supplier_quote(rfq.id, quote_payload, self.db, self.user)

        comparison = supplier_rfq_comparison(rfq.id, self.db, self.user)
        self.assertEqual(len(comparison), 3)
        self.assertTrue(all(row.complete_items == row.total_items == 2 for row in comparison))
        self.assertEqual([row.subtotal for row in comparison], sorted(row.subtotal for row in comparison))

        approval = request_supplier_rfq_approval(
            rfq.id,
            SupplierRFQApprovalRequest(request_notes="Comparativo completo validado en CI"),
            self.db,
            self.user,
        )
        self.assertEqual(approval.status, "requested")
        self.assertEqual(approval.supplier_quote_id, comparison[0].supplier_quote_id)
        self.assertEqual(approval.rfq.status, "approval_pending")

        pending = list_supplier_quote_approvals("requested", 0, 20, self.db, self.user)
        self.assertIn(approval.id, {item.id for item in pending})

    def test_purchase_order_reception_invoice_and_payment_controls(self) -> None:
        rfq = create_supplier_rfq(
            SupplierRFQCreate(
                project_id=self.project.id,
                warehouse_id=self.warehouse.id,
                title=f"Flujo OC inventario pago {self.suffix}",
                required_by=date.today() + timedelta(days=10),
                response_deadline=date.today() + timedelta(days=5),
                supplier_ids=[supplier.id for supplier in self.suppliers],
                items=[
                    SupplierRFQItemCreate(
                        source_code="BLK-001",
                        description="Block 12x20x40",
                        unit="pieza",
                        quantity=Decimal("100"),
                    ),
                    SupplierRFQItemCreate(
                        source_code="ARE-001",
                        description="Arena",
                        unit="m3",
                        quantity=Decimal("20"),
                    ),
                ],
            ),
            BackgroundTasks(),
            self.db,
            self.user,
        )

        quote_ids: list[int] = []
        for index, supplier in enumerate(self.suppliers, start=1):
            quote = create_supplier_quote(
                rfq.id,
                SupplierQuoteCreate(
                    supplier_id=supplier.id,
                    quote_number=f"COT-OC-{index}-{self.suffix}",
                    delivery_days=supplier.average_delivery_days,
                    payment_terms_days=supplier.payment_terms_days,
                    items=[
                        SupplierQuoteItemCreate(
                            rfq_item_id=rfq.items[0].id,
                            unit_price=Decimal(10 + index),
                        ),
                        SupplierQuoteItemCreate(
                            rfq_item_id=rfq.items[1].id,
                            unit_price=Decimal(100 + index),
                        ),
                    ],
                ),
                self.db,
                self.user,
            )
            quote_ids.append(quote.id)

        request_supplier_rfq_approval(
            rfq.id,
            SupplierRFQApprovalRequest(request_notes="Comparativo completo para prueba de OC"),
            self.db,
            self.user,
        )

        selected_quote_id = quote_ids[-1]
        approval_result = approve_supplier_quote(selected_quote_id, self.db, self.user)
        purchase_order = approval_result["purchase_order"]
        expected_list = approval_result["expected_list"]

        self.assertEqual(purchase_order.supplier_quote_id, selected_quote_id)
        self.assertEqual(purchase_order.status, "issued")
        self.assertEqual(expected_list.purchase_order_id, purchase_order.id)
        self.assertEqual(len(expected_list.items), 2)

        purchase_order = self._get_purchase_order(purchase_order.id)
        first_item, second_item = purchase_order.items
        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"PARCIAL-{self.suffix}",
                received_by="Almacen CI",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_list.items[0].id,
                        received_quantity=first_item.quantity_ordered / Decimal("2"),
                    )
                ],
            ),
            self.db,
            self.user,
        )

        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "partially_received")
        self.assertEqual(purchase_order.items[0].status, "partial")
        self.assertEqual(purchase_order.items[1].status, "pending")

        invoice = create_supplier_invoice(
            SupplierInvoiceCreate(
                purchase_order_id=purchase_order.id,
                invoice_number=f"FAC-BLOQ-{self.suffix}",
                invoice_date=date.today(),
                total=purchase_order.subtotal,
            ),
            self.db,
            self.user,
        )
        self.assertEqual(invoice.status, "blocked")

        with self.assertRaises(HTTPException) as blocked_payment:
            create_supplier_payment(
                SupplierPaymentCreate(
                    supplier_invoice_id=invoice.id,
                    amount=invoice.total,
                    scheduled_date=date.today() + timedelta(days=30),
                ),
                self.db,
                self.user,
            )
        self.assertEqual(blocked_payment.exception.status_code, 400)
        self.assertEqual(blocked_payment.exception.detail, "La factura no esta aprobada para pago")

        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"FINAL-{self.suffix}",
                received_by="Almacen CI",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_list.items[0].id,
                        received_quantity=purchase_order.items[0].quantity_ordered
                        - purchase_order.items[0].received_quantity,
                    ),
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_list.items[1].id,
                        received_quantity=second_item.quantity_ordered,
                    ),
                ],
            ),
            self.db,
            self.user,
        )

        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "received")
        self.assertTrue(all(item.status == "complete" for item in purchase_order.items))

        validation = validate_supplier_invoice(invoice.id, self.db, self.user)
        self.assertEqual(validation.status, "approved_for_payment")
        self.assertEqual(validation.pending_items, 0)

        invoice = self.db.get(SupplierInvoice, invoice.id)
        assert invoice is not None
        payment = create_supplier_payment(
            SupplierPaymentCreate(
                supplier_invoice_id=invoice.id,
                amount=invoice.total,
                scheduled_date=date.today() + timedelta(days=30),
                reference=f"PAGO-{self.suffix}",
            ),
            self.db,
            self.user,
        )
        self.assertEqual(payment.status, "scheduled")
        self.db.refresh(invoice)
        self.assertEqual(invoice.status, "scheduled")

    def _get_purchase_order(self, purchase_order_id: int) -> PurchaseOrder:
        purchase_order = self.db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == purchase_order_id)
            .options(selectinload(PurchaseOrder.items))
        )
        assert purchase_order is not None
        return purchase_order


if __name__ == "__main__":
    unittest.main()
