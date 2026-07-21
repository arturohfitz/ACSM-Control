import asyncio
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.inventory import (
    create_quick_inventory_document,
    create_reception,
    list_inventory_inbound_cases,
    project_model_material_control,
)
from app.api.v1.endpoints.purchasing import (
    approve_supplier_quote,
    approve_supplier_agreement,
    create_supplier_agreement,
    create_supplier_quote,
    create_supplier_rfq,
    create_purchase_order_from_approved_quote,
    create_supplier_invoice,
    create_supplier_payment,
    list_purchase_cases,
    list_supplier_agreement_approvals,
    list_supplier_quote_approvals,
    register_supplier_invoice,
    request_supplier_rfq_approval,
    send_purchase_order,
    supplier_rfq_comparison,
    update_purchase_order_billing_mode,
    validate_supplier_invoice,
)
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models import (
    AuditEvent,
    Client,
    Company,
    ExpectedMaterialItem,
    ExpectedMaterialList,
    HouseModel,
    HouseModelDocument,
    HouseModelMaterialRequirement,
    InventoryMovement,
    Material,
    Project,
    ProjectHouseModel,
    ProjectWarehouse,
    PurchaseOrder,
    SupplierInvoiceItem,
    Supplier,
    SupplierInvoice,
    SupplierRFQ,
    User,
    WarehouseStock,
)
from app.schemas.inventory import (
    MaterialReceptionCreate,
    MaterialReceptionItemCreate,
    QuickInventoryDocumentCreate,
    QuickInventoryLine,
)
from app.schemas.purchasing import (
    PurchaseOrderBillingModeUpdate,
    SupplierAgreementCreate,
    SupplierInvoiceCreate,
    SupplierInvoiceItemCreate,
    SupplierPaymentCreate,
    SupplierQuoteCreate,
    SupplierQuoteItemCreate,
    SupplierRFQApprovalRequest,
    SupplierRFQCreate,
    SupplierRFQExceptionDecision,
    SupplierRFQItemCreate,
)
from app.services.project_financials import (
    approve_project_material_budget,
    project_financial_progress,
)
from tests.db_cleanup import cleanup_company_data


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
        cleanup_company_data(self.db, self.company.id)
        self.db.close()

    def test_inventory_document_requires_explicit_warehouse_selection(self) -> None:
        warehouse_count = self.db.scalar(
            select(func.count(ProjectWarehouse.id)).where(
                ProjectWarehouse.project_id == self.project.id
            )
        )

        with self.assertRaises(HTTPException) as missing_warehouse:
            create_quick_inventory_document(
                self.project.id,
                QuickInventoryDocumentCreate(
                    warehouse_id=None,
                    name=f"Documento sin bodega {self.suffix}",
                    items=[
                        QuickInventoryLine(
                            description="Material sin asignacion automatica",
                            unit="PZA",
                            expected_quantity=Decimal("1"),
                        )
                    ],
                ),
                self.db,
                self.user,
            )

        self.assertEqual(missing_warehouse.exception.status_code, 400)
        self.assertEqual(
            missing_warehouse.exception.detail,
            "Debes crear y seleccionar una bodega antes de registrar material",
        )
        self.assertEqual(
            self.db.scalar(
                select(func.count(ProjectWarehouse.id)).where(
                    ProjectWarehouse.project_id == self.project.id
                )
            ),
            warehouse_count,
        )

    def test_model_material_control_tracks_partial_inventory_receipts(self) -> None:
        house_model = HouseModel(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Modelo inventario {self.suffix}",
            construction_m2=Decimal("61.91"),
        )
        self.db.add(house_model)
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.project.id,
                house_model_id=house_model.id,
                quantity=Decimal("2"),
            )
        )
        document = HouseModelDocument(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=house_model.id,
            document_type="explosion",
            file_name=f"explosion-{self.suffix}.xlsx",
            file_hash=f"hash-{self.suffix}",
            status="integrated",
            total_items=1,
        )
        self.db.add(document)
        self.db.flush()
        requirement = HouseModelMaterialRequirement(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=house_model.id,
            document_id=document.id,
            source_code="CEM-001",
            description="Cemento normal gris",
            unit="TON",
            quantity_per_house=Decimal("10"),
            validation_status="validated",
        )
        self.db.add(requirement)
        self.db.flush()
        expected_list = ExpectedMaterialList(
            company_id=self.company.id,
            project_id=self.project.id,
            warehouse_id=self.warehouse.id,
            name=f"Recepcion parcial {self.suffix}",
            status="open",
        )
        self.db.add(expected_list)
        self.db.flush()
        expected_item = ExpectedMaterialItem(
            company_id=self.company.id,
            expected_list_id=expected_list.id,
            house_model_id=house_model.id,
            house_model_material_requirement_id=requirement.id,
            source_code=requirement.source_code,
            description=requirement.description,
            unit=requirement.unit,
            expected_quantity=Decimal("20"),
            received_quantity=Decimal("0"),
            status="pending",
        )
        self.db.add(expected_item)
        self.db.commit()

        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_item.id,
                        received_quantity=Decimal("5"),
                    )
                ],
            ),
            self.db,
            self.user,
        )

        control = project_model_material_control(self.project.id, self.db, self.user)
        self.assertEqual(len(control), 1)
        row = control[0]
        self.assertEqual(row["required_quantity"], Decimal("20"))
        self.assertEqual(row["received_quantity"], Decimal("5"))
        self.assertEqual(row["pending_quantity"], Decimal("15"))
        self.assertEqual(row["received_percent"], Decimal("25.00"))
        self.assertEqual(row["status"], "partial")

    def test_project_material_budget_freezes_the_approved_explosion(self) -> None:
        house_model = HouseModel(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Modelo presupuesto {self.suffix}",
            construction_m2=Decimal("61.91"),
        )
        material = Material(
            company_id=self.company.id,
            supplier_id=self.suppliers[0].id,
            name=f"Cemento presupuesto {self.suffix}",
            unit="SACO",
            current_unit_price=Decimal("10"),
            is_active=True,
        )
        self.db.add_all([house_model, material])
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.project.id,
                house_model_id=house_model.id,
                quantity=Decimal("2"),
            )
        )
        document = HouseModelDocument(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=house_model.id,
            document_type="explosion",
            file_name=f"presupuesto-{self.suffix}.xlsx",
            file_hash=f"presupuesto-{self.suffix}",
            status="integrated",
            total_items=1,
            total_amount=Decimal("100"),
        )
        self.db.add(document)
        self.db.flush()
        self.db.add(
            HouseModelMaterialRequirement(
                company_id=self.company.id,
                client_id=self.client.id,
                house_model_id=house_model.id,
                document_id=document.id,
                material_id=material.id,
                source_code="CEM-PRES-001",
                description="Cemento normal gris",
                unit="SACO",
                quantity_per_house=Decimal("10"),
                unit_cost_reference=Decimal("10"),
                total_cost_reference=Decimal("100"),
                validation_status="validated",
            )
        )
        self.db.commit()

        baseline = approve_project_material_budget(
            self.db,
            project=self.project,
            approved_by=self.user.id,
            notes="Linea base de integracion",
        )
        self.db.commit()
        self.assertEqual(baseline.total_amount, Decimal("200.00"))

        self.db.expire_all()
        progress = project_financial_progress(
            self.db,
            company_id=self.company.id,
            project_id=self.project.id,
        )
        project_row = next(
            row for row in progress["projects"] if row["project_id"] == self.project.id
        )
        self.assertEqual(project_row["budget_amount"], Decimal("200.00"))
        self.assertEqual(project_row["houses_count"], Decimal("2"))
        self.assertEqual(len(progress["materials"]), 1)
        self.assertEqual(progress["materials"][0]["budget_quantity"], Decimal("20.0000"))
        self.assertEqual(progress["materials"][0]["budget_amount"], Decimal("200.00"))

    def test_damaged_material_is_reported_but_does_not_increase_inventory(self) -> None:
        house_model = HouseModel(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Modelo danado {self.suffix}",
            construction_m2=Decimal("50"),
        )
        self.db.add(house_model)
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.project.id,
                house_model_id=house_model.id,
                quantity=Decimal("1"),
            )
        )
        document = HouseModelDocument(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=house_model.id,
            document_type="explosion",
            file_name=f"danado-{self.suffix}.xlsx",
            file_hash=f"danado-{self.suffix}",
            status="integrated",
            total_items=1,
        )
        self.db.add(document)
        self.db.flush()
        requirement = HouseModelMaterialRequirement(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=house_model.id,
            document_id=document.id,
            source_code="CEM-DANADO",
            description="Cemento con incidencia",
            unit="SACO",
            quantity_per_house=Decimal("10"),
            validation_status="validated",
        )
        self.db.add(requirement)
        self.db.flush()
        expected_list = ExpectedMaterialList(
            company_id=self.company.id,
            project_id=self.project.id,
            warehouse_id=self.warehouse.id,
            name=f"Entrega con incidencia {self.suffix}",
            status="open",
        )
        self.db.add(expected_list)
        self.db.flush()
        expected_item = ExpectedMaterialItem(
            company_id=self.company.id,
            expected_list_id=expected_list.id,
            house_model_id=house_model.id,
            house_model_material_requirement_id=requirement.id,
            source_code=requirement.source_code,
            description=requirement.description,
            unit=requirement.unit,
            expected_quantity=Decimal("10"),
            received_quantity=Decimal("0"),
            status="pending",
        )
        self.db.add(expected_item)
        self.db.commit()

        reception = create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"DANADO-{self.suffix}",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_item.id,
                        received_quantity=Decimal("4"),
                        accepted_quantity=Decimal("0"),
                        rejected_quantity=Decimal("4"),
                        condition_status="damaged",
                    )
                ],
            ),
            self.db,
            self.user,
        )

        self.db.refresh(expected_item)
        self.assertEqual(reception.status, "with_issue")
        self.assertEqual(expected_item.received_quantity, Decimal("0"))
        self.assertEqual(expected_item.status, "with_issue")
        self.assertIsNone(
            self.db.scalar(
                select(WarehouseStock).where(WarehouseStock.expected_item_id == expected_item.id)
            )
        )
        self.assertIsNone(
            self.db.scalar(
                select(InventoryMovement).where(
                    InventoryMovement.reception_item_id == reception.items[0].id
                )
            )
        )
        control = project_model_material_control(self.project.id, self.db, self.user)
        row = next(
            item
            for item in control
            if item["house_model_material_requirement_id"] == requirement.id
        )
        self.assertEqual(row["received_quantity"], Decimal("0"))

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
        self.assertEqual(approval_result.status, "approved")
        self.assertEqual(approval_result.rfq.status, "approved_for_order")
        purchase_case = next(item for item in list_purchase_cases(db=self.db, current_user=self.user) if item.rfq_id == rfq.id)
        self.assertEqual(purchase_case.current_stage, "order")
        self.assertIsNone(purchase_case.purchase_order_id)

        purchase_order = create_purchase_order_from_approved_quote(rfq.id, self.db, self.user)
        self.assertEqual(purchase_order.status, "issued")
        self.assertIsNone(
            self.db.scalar(
                select(ExpectedMaterialList).where(
                    ExpectedMaterialList.purchase_order_id == purchase_order.id
                )
            )
        )
        purchase_case = next(item for item in list_purchase_cases(db=self.db, current_user=self.user) if item.rfq_id == rfq.id)
        self.assertEqual(purchase_case.current_stage, "order")
        self.assertEqual(purchase_case.purchase_order_status, "issued")
        purchase_order = send_purchase_order(
            purchase_order.id,
            BackgroundTasks(),
            self.db,
            self.user,
        )
        expected_list = self.db.scalar(
            select(ExpectedMaterialList)
            .where(ExpectedMaterialList.purchase_order_id == purchase_order.id)
            .options(selectinload(ExpectedMaterialList.items))
        )
        assert expected_list is not None

        self.assertEqual(purchase_order.supplier_quote_id, selected_quote_id)
        self.assertEqual(purchase_order.status, "sent")
        self.assertEqual(expected_list.purchase_order_id, purchase_order.id)
        self.assertEqual(len(expected_list.items), 2)
        inbound_case = next(
            item
            for item in list_inventory_inbound_cases(db=self.db, current_user=self.user)
            if item["purchase_order_id"] == purchase_order.id
        )
        self.assertEqual(inbound_case["stage"], "awaiting")
        self.assertIn(f"project_id={self.project.id}", inbound_case["next_action_url"])
        self.assertIn(f"purchase_order_id={purchase_order.id}", inbound_case["next_action_url"])
        self.assertIn(f"warehouse_id={self.warehouse.id}", inbound_case["next_action_url"])
        purchase_case = next(item for item in list_purchase_cases(db=self.db, current_user=self.user) if item.rfq_id == rfq.id)
        self.assertEqual(purchase_case.current_stage, "receiving")
        self.assertEqual(purchase_case.purchase_order_status, "sent")

        purchase_order = self._get_purchase_order(purchase_order.id)
        first_item, second_item = purchase_order.items
        first_expected_item = next(
            item for item in expected_list.items if item.purchase_order_item_id == first_item.id
        )
        second_expected_item = next(
            item for item in expected_list.items if item.purchase_order_item_id == second_item.id
        )
        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"PARCIAL-{self.suffix}",
                received_by="Almacen CI",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=first_expected_item.id,
                        received_quantity=first_item.quantity_ordered / Decimal("2"),
                    )
                ],
            ),
            self.db,
            self.user,
        )

        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "partially_received")
        item_statuses = {item.id: item.status for item in purchase_order.items}
        self.assertEqual(item_statuses[first_item.id], "partial")
        self.assertEqual(item_statuses[second_item.id], "pending")

        invoice = self._create_validated_invoice(
            SupplierInvoiceCreate(
                purchase_order_id=purchase_order.id,
                invoice_number=f"FAC-BLOQ-{self.suffix}",
                invoice_date=date.today(),
                total=purchase_order.subtotal,
            )
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
                        expected_item_id=first_expected_item.id,
                        received_quantity=first_item.quantity_ordered
                        - first_item.received_quantity,
                    ),
                    MaterialReceptionItemCreate(
                        expected_item_id=second_expected_item.id,
                        received_quantity=second_item.quantity_ordered,
                    ),
                ],
            ),
            self.db,
            self.user,
        )

        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "factured")
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
        self._assert_core_audit_events()

    def _get_purchase_order(self, purchase_order_id: int) -> PurchaseOrder:
        purchase_order = self.db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == purchase_order_id)
            .options(selectinload(PurchaseOrder.items))
        )
        assert purchase_order is not None
        return purchase_order

    def _create_validated_invoice(self, payload: SupplierInvoiceCreate) -> SupplierInvoice:
        invoice = create_supplier_invoice(payload, self.db, self.user)
        invoice = self.db.get(SupplierInvoice, invoice.id)
        assert invoice is not None
        invoice.fiscal_status = "legacy_validated"
        invoice.fiscal_validation_message = "Factura historica validada por prueba de integracion."
        invoice.status = "received"
        self.db.commit()
        validate_supplier_invoice(invoice.id, self.db, self.user)
        validated = self.db.scalar(
            select(SupplierInvoice)
            .where(SupplierInvoice.id == invoice.id)
            .options(
                selectinload(SupplierInvoice.items),
                selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items),
            )
        )
        assert validated is not None
        return validated

    def _assert_core_audit_events(self) -> None:
        events = list(
            self.db.scalars(
                select(AuditEvent).where(AuditEvent.company_id == self.company.id)
            ).all()
        )
        event_keys = {(event.module, event.action, event.entity_type) for event in events}
        self.assertIn(("compras", "create", "SupplierRFQ"), event_keys)
        self.assertIn(("compras", "create", "SupplierQuote"), event_keys)
        self.assertIn(("compras", "request_approval", "SupplierRFQ"), event_keys)
        self.assertIn(("ordenes_compra", "create", "PurchaseOrder"), event_keys)
        self.assertIn(("inventario", "receive", "MaterialReception"), event_keys)
        self.assertIn(("facturas_proveedor", "create", "SupplierInvoice"), event_keys)
        self.assertIn(("facturas_proveedor", "validate", "SupplierInvoice"), event_keys)
        self.assertIn(("pagos_proveedores", "schedule", "SupplierPayment"), event_keys)

    def test_purchase_order_partial_billing_and_payments(self) -> None:
        rfq = create_supplier_rfq(
            SupplierRFQCreate(
                project_id=self.project.id,
                warehouse_id=self.warehouse.id,
                title=f"Flujo OC parcial {self.suffix}",
                required_by=date.today() + timedelta(days=10),
                response_deadline=date.today() + timedelta(days=5),
                supplier_ids=[supplier.id for supplier in self.suppliers],
                items=[
                    SupplierRFQItemCreate(
                        source_code="MOR-001",
                        description="Mortero en saco",
                        unit="saco",
                        quantity=Decimal("100"),
                    ),
                ],
            ),
            BackgroundTasks(),
            self.db,
            self.user,
        )
        quote = None
        for index, supplier in enumerate(self.suppliers, start=1):
            created_quote = create_supplier_quote(
                rfq.id,
                SupplierQuoteCreate(
                    supplier_id=supplier.id,
                    quote_number=f"COT-PARCIAL-{index}-{self.suffix}",
                    delivery_days=supplier.average_delivery_days,
                    payment_terms_days=supplier.payment_terms_days,
                    items=[
                        SupplierQuoteItemCreate(
                            rfq_item_id=rfq.items[0].id,
                            unit_price=Decimal("25") + Decimal(index - 1),
                        ),
                    ],
                ),
                self.db,
                self.user,
            )
            if index == 1:
                quote = created_quote
        assert quote is not None
        request_supplier_rfq_approval(
            rfq.id,
            SupplierRFQApprovalRequest(request_notes="Comparativo completo para pagos parciales"),
            self.db,
            self.user,
        )
        approval_result = approve_supplier_quote(quote.id, self.db, self.user)
        self.assertEqual(approval_result.rfq.status, "approved_for_order")
        purchase_order = create_purchase_order_from_approved_quote(rfq.id, self.db, self.user)
        purchase_order = send_purchase_order(
            purchase_order.id,
            BackgroundTasks(),
            self.db,
            self.user,
        )
        expected_list = self.db.scalar(
            select(ExpectedMaterialList)
            .where(ExpectedMaterialList.purchase_order_id == purchase_order.id)
            .options(selectinload(ExpectedMaterialList.items))
        )
        assert expected_list is not None

        purchase_order = update_purchase_order_billing_mode(
            purchase_order.id,
            PurchaseOrderBillingModeUpdate(billing_mode="partial"),
            self.db,
            self.user,
        )
        self.assertEqual(purchase_order.billing_mode, "partial")

        purchase_order = self._get_purchase_order(purchase_order.id)
        po_item = purchase_order.items[0]
        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"ENTREGA-50-{self.suffix}",
                received_by="Almacen CI",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_list.items[0].id,
                        received_quantity=Decimal("50"),
                    )
                ],
            ),
            self.db,
            self.user,
        )

        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "partially_received")
        invoice_payload = SupplierInvoiceCreate(
            purchase_order_id=purchase_order.id,
            invoice_number=f"FAC-PARCIAL-1-{self.suffix}",
            invoice_date=date.today(),
            subtotal=Decimal("1250.00"),
            total=Decimal("1250.00"),
            items=[
                SupplierInvoiceItemCreate(
                    purchase_order_item_id=po_item.id,
                    quantity=Decimal("50"),
                    unit_price=Decimal("25"),
                )
            ],
        )
        supplier = self.db.get(Supplier, purchase_order.supplier_id)
        assert supplier is not None
        supplier.tax_id = "AAA010101AAA"
        self.company.tax_id = "BBB010101BBB"
        self.db.commit()
        cfdi = f'''<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
    Serie="CI" Folio="{self.suffix}" Fecha="{date.today().isoformat()}T10:30:00"
    SubTotal="1250.00" Moneda="MXN" Total="1250.00" MetodoPago="PUE" FormaPago="03">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor CI" />
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Constructora CI" />
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        UUID="{str(uuid4()).upper()}" />
  </cfdi:Complemento>
</cfdi:Comprobante>'''.encode()
        original_upload_dir = settings.supplier_invoice_upload_dir
        with TemporaryDirectory() as upload_dir:
            settings.supplier_invoice_upload_dir = upload_dir
            try:
                first_invoice = asyncio.run(
                    register_supplier_invoice(
                        payload_json=invoice_payload.model_dump_json(),
                        pdf_file=None,
                        xml_file=UploadFile(file=BytesIO(cfdi), filename="factura-ci.xml"),
                        db=self.db,
                        current_user=self.user,
                    )
                )
            finally:
                settings.supplier_invoice_upload_dir = original_upload_dir
        self.assertEqual(first_invoice.fiscal_status, "valid")
        self.assertEqual(len(first_invoice.documents), 1)
        validate_supplier_invoice(first_invoice.id, self.db, self.user)
        first_invoice = self.db.scalar(
            select(SupplierInvoice)
            .where(SupplierInvoice.id == first_invoice.id)
            .options(
                selectinload(SupplierInvoice.items),
                selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.items),
            )
        )
        assert first_invoice is not None
        self.assertEqual(first_invoice.status, "approved_for_payment")
        self.assertEqual(first_invoice.purchase_order.status, "partially_received")

        blocked_invoice = self._create_validated_invoice(
            SupplierInvoiceCreate(
                purchase_order_id=purchase_order.id,
                invoice_number=f"FAC-EXCESO-{self.suffix}",
                invoice_date=date.today(),
                total=Decimal("25.00"),
                items=[
                    SupplierInvoiceItemCreate(
                        purchase_order_item_id=po_item.id,
                        quantity=Decimal("1"),
                        unit_price=Decimal("25"),
                    )
                ],
            )
        )
        self.assertEqual(blocked_invoice.status, "blocked")

        first_payment = create_supplier_payment(
            SupplierPaymentCreate(
                supplier_invoice_id=first_invoice.id,
                amount=Decimal("625.00"),
                scheduled_date=date.today(),
                paid_at=date.today(),
                status="paid",
                reference=f"PAGO-PARCIAL-1A-{self.suffix}",
            ),
            self.db,
            self.user,
        )
        self.assertEqual(first_payment.status, "paid")
        self.db.refresh(first_invoice)
        self.assertEqual(first_invoice.status, "scheduled")
        second_payment = create_supplier_payment(
            SupplierPaymentCreate(
                supplier_invoice_id=first_invoice.id,
                amount=Decimal("625.00"),
                scheduled_date=date.today(),
                paid_at=date.today(),
                status="paid",
                reference=f"PAGO-PARCIAL-1B-{self.suffix}",
            ),
            self.db,
            self.user,
        )
        self.assertEqual(second_payment.status, "paid")
        self.db.refresh(first_invoice)
        self.assertEqual(first_invoice.status, "paid")
        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "partially_received")

        create_reception(
            self.project.id,
            MaterialReceptionCreate(
                warehouse_id=self.warehouse.id,
                expected_list_id=expected_list.id,
                delivery_reference=f"ENTREGA-100-{self.suffix}",
                received_by="Almacen CI",
                items=[
                    MaterialReceptionItemCreate(
                        expected_item_id=expected_list.items[0].id,
                        received_quantity=Decimal("50"),
                    )
                ],
            ),
            self.db,
            self.user,
        )
        blocked_invoice = self.db.get(SupplierInvoice, blocked_invoice.id)
        assert blocked_invoice is not None
        self.assertEqual(blocked_invoice.status, "approved_for_payment")
        create_supplier_payment(
            SupplierPaymentCreate(
                supplier_invoice_id=blocked_invoice.id,
                amount=blocked_invoice.total,
                scheduled_date=date.today(),
                paid_at=date.today(),
                status="paid",
                reference=f"PAGO-EXCESO-{self.suffix}",
            ),
            self.db,
            self.user,
        )
        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "received")

        with self.assertRaises(HTTPException) as overbilled:
            create_supplier_invoice(
                SupplierInvoiceCreate(
                    purchase_order_id=purchase_order.id,
                    invoice_number=f"FAC-EXCESO-IMPORTE-{self.suffix}",
                    invoice_date=date.today(),
                    total=Decimal("1274.00"),
                    items=[
                        SupplierInvoiceItemCreate(
                            purchase_order_item_id=po_item.id,
                            quantity=Decimal("49"),
                            unit_price=Decimal("26"),
                        )
                    ],
                ),
                self.db,
                self.user,
            )
        self.assertEqual(overbilled.exception.status_code, 400)
        self.assertIn("supera la orden de compra", overbilled.exception.detail)

        second_invoice = self._create_validated_invoice(
            SupplierInvoiceCreate(
                purchase_order_id=purchase_order.id,
                invoice_number=f"FAC-PARCIAL-2-{self.suffix}",
                invoice_date=date.today(),
                total=Decimal("1225.00"),
                items=[
                    SupplierInvoiceItemCreate(
                        purchase_order_item_id=po_item.id,
                        quantity=Decimal("49"),
                        unit_price=Decimal("25"),
                    )
                ],
            )
        )
        self.assertEqual(second_invoice.status, "approved_for_payment")
        create_supplier_payment(
            SupplierPaymentCreate(
                supplier_invoice_id=second_invoice.id,
                amount=second_invoice.total,
                scheduled_date=date.today(),
                paid_at=date.today(),
                status="paid",
                reference=f"PAGO-PARCIAL-2-{self.suffix}",
            ),
            self.db,
            self.user,
        )
        purchase_order = self._get_purchase_order(purchase_order.id)
        self.assertEqual(purchase_order.status, "closed")

        paid_quantity = self.db.scalar(
            select(func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0))
            .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceItem.supplier_invoice_id)
            .where(
                SupplierInvoiceItem.purchase_order_item_id == po_item.id,
                SupplierInvoice.status == "paid",
            )
        )
        self.assertEqual(paid_quantity, Decimal("100"))

    def test_supplier_agreement_requires_admin_approval_before_use(self) -> None:
        house_model = HouseModel(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Modelo convenio {self.suffix}",
            construction_m2=Decimal("61.91"),
        )
        self.db.add(house_model)
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.project.id,
                house_model_id=house_model.id,
                quantity=Decimal("10"),
            )
        )
        self.db.commit()

        agreement = create_supplier_agreement(
            SupplierAgreementCreate(
                supplier_id=self.suppliers[0].id,
                client_id=self.client.id,
                house_model_id=house_model.id,
                name=f"Convenio pendiente {self.suffix}",
                request_notes="Proveedor autorizado por direccion comercial.",
            ),
            self.db,
            self.user,
        )
        self.assertEqual(agreement.approval_status, "requested")

        self.user.is_master_admin = True
        pending = list_supplier_agreement_approvals("requested", 0, 20, self.db, self.user)
        self.user.is_master_admin = False
        self.assertIn(agreement.id, {item.id for item in pending})

        self.user.is_master_admin = True
        with self.assertRaises(HTTPException) as not_authorized:
            create_supplier_rfq(
                SupplierRFQCreate(
                    project_id=self.project.id,
                    warehouse_id=self.warehouse.id,
                    title=f"Solicitud convenio pendiente {self.suffix}",
                    required_by=date.today() + timedelta(days=5),
                    response_deadline=date.today() + timedelta(days=2),
                    supplier_ids=[self.suppliers[0].id],
                    supplier_agreement_id=agreement.id,
                    items=[
                        SupplierRFQItemCreate(
                            source_code="COV-001",
                            description="Material por convenio",
                            unit="pieza",
                            quantity=Decimal("10"),
                        )
                    ],
                ),
                BackgroundTasks(),
                self.db,
                self.user,
            )
        self.user.is_master_admin = False
        self.assertEqual(not_authorized.exception.status_code, 400)
        self.assertEqual(
            not_authorized.exception.detail,
            "El convenio esta pendiente de autorizacion administrativa",
        )

        approved = approve_supplier_agreement(
            agreement.id,
            SupplierRFQExceptionDecision(decision_notes="Autorizado por administracion."),
            self.db,
            self.user,
        )
        self.assertEqual(approved.approval_status, "approved")

        self.user.is_master_admin = True
        rfq = create_supplier_rfq(
            SupplierRFQCreate(
                project_id=self.project.id,
                warehouse_id=self.warehouse.id,
                title=f"Solicitud convenio aprobado {self.suffix}",
                required_by=date.today() + timedelta(days=5),
                response_deadline=date.today() + timedelta(days=2),
                supplier_ids=[self.suppliers[0].id],
                supplier_agreement_id=agreement.id,
                items=[
                    SupplierRFQItemCreate(
                        source_code="COV-001",
                        description="Material por convenio",
                        unit="pieza",
                        quantity=Decimal("10"),
                    )
                ],
            ),
            BackgroundTasks(),
            self.db,
            self.user,
        )
        self.user.is_master_admin = False
        self.assertEqual(rfq.request_type, "agreement")


if __name__ == "__main__":
    unittest.main()
