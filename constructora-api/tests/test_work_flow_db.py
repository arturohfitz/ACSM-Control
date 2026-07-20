import os
import unittest
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.construction_concepts import create_model_concept_catalog
from app.api.v1.endpoints.material_requisitions import (
    create_material_requisition,
    list_available_materials,
    start_material_requisition_review,
)
from app.core.security import get_password_hash
from app.db.session import engine
from app.models import (
    Client,
    Company,
    HouseModel,
    HouseModelDocument,
    HouseModelMaterialRequirement,
    Material,
    MaterialUnitConversion,
    Project,
    ProjectHouseModel,
    User,
)
from app.schemas.business import ConstructionConceptModelCatalogCreate
from app.schemas.material_requisition import (
    MaterialRequisitionCreate,
    MaterialRequisitionItemCreate,
)


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "requiere RUN_DB_TESTS=1")
class WorkFlowDBTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection)
        suffix = uuid4().hex[:10]
        self.company = Company(
            name=f"Obra CI {suffix}",
            legal_name=f"Obra CI {suffix} SA de CV",
            license_status="active",
        )
        self.db.add(self.company)
        self.db.flush()
        self.user = User(
            company_id=self.company.id,
            full_name="Arquitecto CI",
            email=f"obra-{suffix}@example.com",
            password_hash=get_password_hash("Admin12345!"),
            is_active=True,
            is_master_admin=False,
        )
        self.reviewer = User(
            company_id=self.company.id,
            full_name="Compras CI",
            email=f"compras-{suffix}@example.com",
            password_hash=get_password_hash("Admin12345!"),
            is_active=True,
            is_master_admin=False,
        )
        self.client = Client(company_id=self.company.id, name=f"Inmobiliaria {suffix}")
        self.db.add_all([self.user, self.reviewer, self.client])
        self.db.flush()
        self.project = Project(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Desarrollo {suffix}",
            status="active",
        )
        self.model = HouseModel(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Modelo {suffix}",
            construction_m2=Decimal("60"),
        )
        self.db.add_all([self.project, self.model])
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.project.id,
                house_model_id=self.model.id,
                quantity=Decimal("10"),
            )
        )
        self.other_project = Project(
            company_id=self.company.id,
            client_id=self.client.id,
            name=f"Otro desarrollo {suffix}",
            status="active",
        )
        self.db.add(self.other_project)
        self.db.flush()
        self.db.add(
            ProjectHouseModel(
                project_id=self.other_project.id,
                house_model_id=self.model.id,
                quantity=Decimal("10"),
            )
        )
        self.material = Material(
            company_id=self.company.id,
            name=f"Cemento {suffix}",
            unit="TON",
            current_unit_price=Decimal("1000"),
            is_active=True,
        )
        self.document = HouseModelDocument(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=self.model.id,
            document_type="explosion",
            file_name=f"explosion-{suffix}.xlsx",
            file_hash=f"explosion-{suffix}",
            status="integrated",
            total_items=1,
        )
        self.db.add_all([self.material, self.document])
        self.db.flush()
        self.requirement = HouseModelMaterialRequirement(
            company_id=self.company.id,
            client_id=self.client.id,
            house_model_id=self.model.id,
            document_id=self.document.id,
            material_id=self.material.id,
            source_code="CEM-001",
            description=self.material.name,
            unit="TON",
            quantity_per_house=Decimal("1"),
            validation_status="validated",
        )
        self.db.add_all(
            [
                self.requirement,
                MaterialUnitConversion(
                    company_id=self.company.id,
                    material_id=self.material.id,
                    from_unit="BULTO",
                    to_unit="TON",
                    factor_to_base=Decimal("0.05"),
                    is_active=True,
                ),
            ]
        )
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_requisition_tracks_conversion_available_balance_and_review(self) -> None:
        requisition = create_material_requisition(
            MaterialRequisitionCreate(
                project_id=self.project.id,
                house_model_id=self.model.id,
                title="Cemento para dos viviendas",
                items=[
                    MaterialRequisitionItemCreate(
                        house_model_material_requirement_id=self.requirement.id,
                        requested_quantity=Decimal("20"),
                        requested_unit="BULTO",
                        coverage_houses=Decimal("2"),
                    )
                ],
            ),
            self.db,
            self.user,
        )
        self.assertEqual(requisition.items[0].requested_base_quantity, Decimal("1.0000"))
        self.assertEqual(requisition.items[0].unit_conversion_factor, Decimal("0.05000000"))

        available = list_available_materials(
            project_id=self.project.id,
            house_model_id=self.model.id,
            q=None,
            limit=500,
            db=self.db,
            current_user=self.user,
        )
        self.assertEqual(available[0].total_required, Decimal("10"))
        self.assertEqual(available[0].already_requested, Decimal("1.0000"))
        self.assertEqual(available[0].available_to_request, Decimal("9.0000"))

        other_project_available = list_available_materials(
            project_id=self.other_project.id,
            house_model_id=self.model.id,
            q=None,
            limit=500,
            db=self.db,
            current_user=self.user,
        )
        self.assertEqual(other_project_available[0].already_requested, Decimal("0"))
        self.assertEqual(other_project_available[0].available_to_request, Decimal("10"))

        reviewed = start_material_requisition_review(
            requisition.id,
            self.db,
            self.reviewer,
        )
        self.assertEqual(reviewed.status, "in_review")
        self.assertEqual(reviewed.reviewed_by_user_id, self.reviewer.id)

        with self.assertRaises(HTTPException) as error:
            create_material_requisition(
                MaterialRequisitionCreate(
                    project_id=self.project.id,
                    house_model_id=self.model.id,
                    title="Solicitud excesiva",
                    items=[
                        MaterialRequisitionItemCreate(
                            house_model_material_requirement_id=self.requirement.id,
                            requested_quantity=Decimal("181"),
                            requested_unit="BULTO",
                        )
                    ],
                ),
                self.db,
                self.user,
            )
        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("supera lo disponible", str(error.exception.detail))

    def test_manual_concept_is_linked_to_selected_model(self) -> None:
        created = create_model_concept_catalog(
            ConstructionConceptModelCatalogCreate(
                project_id=self.project.id,
                house_model_id=self.model.id,
                code=f"CON-{uuid4().hex[:8]}",
                name="Trazo manual",
                unit="M2",
                quantity_per_house=Decimal("60"),
                unit_price_reference=Decimal("25"),
            ),
            self.db,
            self.user,
        )
        self.assertEqual(created.project_id, self.project.id)
        self.assertEqual(created.house_model_id, self.model.id)
        self.assertTrue(created.is_linked)
        self.assertEqual(created.total_required, Decimal("600"))
