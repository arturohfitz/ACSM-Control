from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Client,
    ConceptLabor,
    ConceptMaterial,
    ConstructionConcept,
    ExpectedMaterialItem,
    ExpectedMaterialList,
    HouseModel,
    HouseModelConcept,
    LaborRate,
    Material,
    MaterialReception,
    MaterialReceptionItem,
    Project,
    ProjectHouseModel,
    ProjectMaterialPrice,
    ProjectWarehouse,
    Quote,
    User,
    WarehouseStock,
)
from app.seed import seed_admin
from app.services.quote_calculator import create_project_quote


OWNER_COMPANY_NAME = "ACSM S.A de C.V."


CLIENTS = [
    {
        "name": "Desarrolladora Bosque Claro",
        "legal_name": "Desarrolladora Bosque Claro S.A. de C.V.",
        "contact_name": "Laura Méndez",
        "contact_email": "operaciones@bosqueclaro.mx",
        "contact_phone": "555-0101",
        "notes": "Demo: desarrolladora con casas de 1 planta y 2 habitaciones.",
        "model": "Modelo Nido 64",
        "projects": [
            ("Privada Encinos", 30, "Querétaro, Qro."),
            ("Villas del Roble", 50, "El Marqués, Qro."),
        ],
    },
    {
        "name": "Desarrolladora Valle Norte",
        "legal_name": "Valle Norte Desarrollos S.A. de C.V.",
        "contact_name": "Andrés Salgado",
        "contact_email": "proyectos@vallenorte.mx",
        "contact_phone": "555-0202",
        "notes": "Demo: desarrolladora con casas de 2 plantas y 3 habitaciones.",
        "model": "Modelo Doble 100",
        "projects": [
            ("Paseo Cumbre", 30, "Apodaca, N.L."),
            ("Cerrada Los Olivos", 50, "San Nicolás, N.L."),
        ],
    },
    {
        "name": "Desarrolladora Altura Residencial",
        "legal_name": "Altura Residencial S.A. de C.V.",
        "contact_name": "Mariana Cárdenas",
        "contact_email": "abasto@alturaresidencial.mx",
        "contact_phone": "555-0303",
        "notes": "Demo: casas de 2 plantas y 3 habitaciones, 50% más grandes.",
        "model": "Modelo Magna 150",
        "projects": [
            ("Altozano Plus", 30, "Mérida, Yuc."),
            ("Mirador Premium", 50, "Conkal, Yuc."),
        ],
    },
]


HOUSE_MODELS = [
    {
        "name": "Modelo Nido 64",
        "description": "Casa demo de 1 planta con 2 habitaciones.",
        "construction_m2": Decimal("64.00"),
        "levels": 1,
        "bedrooms": 2,
        "bathrooms": Decimal("1.00"),
        "estimated_cost_per_unit": Decimal("420000.00"),
        "estimated_price_per_unit": Decimal("520000.00"),
    },
    {
        "name": "Modelo Doble 100",
        "description": "Casa demo de 2 plantas con 3 habitaciones.",
        "construction_m2": Decimal("100.00"),
        "levels": 2,
        "bedrooms": 3,
        "bathrooms": Decimal("2.50"),
        "estimated_cost_per_unit": Decimal("680000.00"),
        "estimated_price_per_unit": Decimal("840000.00"),
    },
    {
        "name": "Modelo Magna 150",
        "description": "Casa demo de 2 plantas con 3 habitaciones y mayor metraje.",
        "construction_m2": Decimal("150.00"),
        "levels": 2,
        "bedrooms": 3,
        "bathrooms": Decimal("3.00"),
        "estimated_cost_per_unit": Decimal("1010000.00"),
        "estimated_price_per_unit": Decimal("1260000.00"),
    },
]


PROJECT_PRICE_FACTORS = {
    "Modelo Nido 64": Decimal("0.9800"),
    "Modelo Doble 100": Decimal("1.0300"),
    "Modelo Magna 150": Decimal("1.0800"),
}

DEVELOPER_SUPPLIED_MATERIALS = {
    "Concreto premezclado",
    "Varilla 1/2",
}


MATERIALS = [
    ("Cemento gris 50kg", "saco", "185.0000", "Cementos Demo"),
    ("Block 12x20x40", "pieza", "18.5000", "Blockera Regional"),
    ("Varilla 3/8", "pieza", "145.0000", "Aceros Demo"),
    ("Varilla 1/2", "pieza", "220.0000", "Aceros Demo"),
    ("Arena", "m3", "420.0000", "Agregados Demo"),
    ("Grava", "m3", "480.0000", "Agregados Demo"),
    ("Concreto premezclado", "m3", "2450.0000", "Concretos Demo"),
    ("Tubería PVC sanitaria", "m", "95.0000", "Plomería Demo"),
    ("Tubería CPVC hidráulica", "m", "115.0000", "Plomería Demo"),
    ("Cable THW", "m", "16.5000", "Eléctricos Demo"),
    ("Centro de carga", "pieza", "950.0000", "Eléctricos Demo"),
    ("Yeso", "saco", "145.0000", "Acabados Demo"),
    ("Pintura vinílica", "litro", "78.0000", "Pinturas Demo"),
    ("Loseta cerámica", "m2", "185.0000", "Pisos Demo"),
    ("Puerta interior", "pieza", "1450.0000", "Carpintería Demo"),
    ("Ventana aluminio", "pieza", "2250.0000", "Aluminios Demo"),
]


LABOR_RATES = [
    ("Cuadrilla cimentación", "jornal", "1850.0000"),
    ("Albañilería muros", "jornal", "1600.0000"),
    ("Colado losa", "jornal", "1900.0000"),
    ("Instalación hidráulica", "jornal", "1750.0000"),
    ("Instalación sanitaria", "jornal", "1700.0000"),
    ("Instalación eléctrica", "jornal", "1650.0000"),
    ("Aplanado y yeso", "jornal", "1500.0000"),
    ("Pintura", "jornal", "1350.0000"),
    ("Pisos", "jornal", "1450.0000"),
    ("Carpintería / puertas", "jornal", "1550.0000"),
]


CONCEPTS = [
    {
        "code": "CIM-001",
        "name": "Cimentación",
        "unit": "m2",
        "waste": "0.0300",
        "indirect": "0.0800",
        "materials": {
            "Cemento gris 50kg": "0.1800",
            "Varilla 3/8": "0.0800",
            "Arena": "0.0350",
            "Grava": "0.0300",
            "Concreto premezclado": "0.0600",
        },
        "labor": {"Cuadrilla cimentación": "0.0800"},
        "model_quantity_per_m2": "0.3200",
    },
    {
        "code": "EST-001",
        "name": "Muros de block",
        "unit": "m2",
        "waste": "0.0500",
        "indirect": "0.0700",
        "materials": {"Block 12x20x40": "12.5000", "Cemento gris 50kg": "0.0600", "Arena": "0.0200"},
        "labor": {"Albañilería muros": "0.0600"},
        "model_quantity_per_m2": "1.6500",
    },
    {
        "code": "EST-002",
        "name": "Losa / entrepiso",
        "unit": "m2",
        "waste": "0.0300",
        "indirect": "0.0800",
        "materials": {"Concreto premezclado": "0.1200", "Varilla 1/2": "0.0900"},
        "labor": {"Colado losa": "0.0700"},
        "model_quantity_per_m2": "0.8500",
    },
    {
        "code": "INS-001",
        "name": "Instalación hidráulica",
        "unit": "salida",
        "waste": "0.0300",
        "indirect": "0.0600",
        "materials": {"Tubería CPVC hidráulica": "6.0000"},
        "labor": {"Instalación hidráulica": "0.3500"},
        "model_quantity_per_m2": "0.0700",
    },
    {
        "code": "INS-002",
        "name": "Instalación sanitaria",
        "unit": "salida",
        "waste": "0.0300",
        "indirect": "0.0600",
        "materials": {"Tubería PVC sanitaria": "5.5000"},
        "labor": {"Instalación sanitaria": "0.3200"},
        "model_quantity_per_m2": "0.0600",
    },
    {
        "code": "INS-003",
        "name": "Instalación eléctrica",
        "unit": "salida",
        "waste": "0.0200",
        "indirect": "0.0600",
        "materials": {"Cable THW": "12.0000", "Centro de carga": "0.0800"},
        "labor": {"Instalación eléctrica": "0.3000"},
        "model_quantity_per_m2": "0.1200",
    },
    {
        "code": "ACA-001",
        "name": "Aplanados y yeso",
        "unit": "m2",
        "waste": "0.0400",
        "indirect": "0.0600",
        "materials": {"Yeso": "0.1800"},
        "labor": {"Aplanado y yeso": "0.0500"},
        "model_quantity_per_m2": "2.2500",
    },
    {
        "code": "ACA-002",
        "name": "Pintura",
        "unit": "m2",
        "waste": "0.0500",
        "indirect": "0.0500",
        "materials": {"Pintura vinílica": "0.1800"},
        "labor": {"Pintura": "0.0300"},
        "model_quantity_per_m2": "2.0000",
    },
    {
        "code": "ACA-003",
        "name": "Pisos",
        "unit": "m2",
        "waste": "0.0500",
        "indirect": "0.0500",
        "materials": {"Loseta cerámica": "1.0500"},
        "labor": {"Pisos": "0.0500"},
        "model_quantity_per_m2": "0.9500",
    },
    {
        "code": "CAR-001",
        "name": "Puertas y ventanas",
        "unit": "lote",
        "waste": "0.0100",
        "indirect": "0.0500",
        "materials": {"Puerta interior": "5.0000", "Ventana aluminio": "4.0000"},
        "labor": {"Carpintería / puertas": "1.2000"},
        "model_quantity_per_m2": "0.0100",
    },
]


def decimal(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value))


def get_one(db: Session, model: type, **filters: Any):
    statement = select(model)
    for field, value in filters.items():
        statement = statement.where(getattr(model, field) == value)
    return db.scalar(statement)


def item_status(expected: Decimal, received: Decimal, has_issue: bool = False) -> str:
    if has_issue:
        return "with_issue"
    if received <= 0:
        return "pending"
    if received < expected:
        return "partial"
    if received == expected:
        return "complete"
    return "over_received"


def upsert_materials(db: Session, company_id: int) -> dict[str, Material]:
    materials: dict[str, Material] = {}
    for name, unit, price, supplier in MATERIALS:
        material = get_one(db, Material, company_id=company_id, name=name)
        if material is None:
            material = Material(
                company_id=company_id,
                name=name,
                unit=unit,
                current_unit_price=decimal(price),
                supplier_name=supplier,
                last_price_update=date.today(),
                is_active=True,
            )
            db.add(material)
            db.flush()
        else:
            material.unit = unit
            material.current_unit_price = decimal(price)
            material.supplier_name = supplier
            material.is_active = True
        materials[name] = material
    return materials


def upsert_labor_rates(db: Session, company_id: int) -> dict[str, LaborRate]:
    labor_rates: dict[str, LaborRate] = {}
    for name, unit, unit_cost in LABOR_RATES:
        labor_rate = get_one(db, LaborRate, company_id=company_id, name=name)
        if labor_rate is None:
            labor_rate = LaborRate(
                company_id=company_id,
                name=name,
                unit=unit,
                unit_cost=decimal(unit_cost),
                is_active=True,
            )
            db.add(labor_rate)
            db.flush()
        else:
            labor_rate.unit = unit
            labor_rate.unit_cost = decimal(unit_cost)
            labor_rate.is_active = True
        labor_rates[name] = labor_rate
    return labor_rates


def upsert_concepts(
    db: Session,
    company_id: int,
    materials: dict[str, Material],
    labor_rates: dict[str, LaborRate],
) -> dict[str, ConstructionConcept]:
    concepts: dict[str, ConstructionConcept] = {}
    for index, data in enumerate(CONCEPTS, start=1):
        concept = get_one(db, ConstructionConcept, company_id=company_id, code=data["code"])
        if concept is None:
            concept = ConstructionConcept(
                company_id=company_id,
                code=data["code"],
                name=data["name"],
                unit=data["unit"],
                description=f"Concepto demo {data['code']}",
                default_waste_percent=decimal(data["waste"]),
                default_indirect_percent=decimal(data["indirect"]),
            )
            db.add(concept)
            db.flush()
        else:
            concept.name = data["name"]
            concept.unit = data["unit"]
            concept.default_waste_percent = decimal(data["waste"])
            concept.default_indirect_percent = decimal(data["indirect"])

        for material_name, quantity in data["materials"].items():
            material = materials[material_name]
            concept_material = get_one(
                db,
                ConceptMaterial,
                construction_concept_id=concept.id,
                material_id=material.id,
            )
            if concept_material is None:
                db.add(
                    ConceptMaterial(
                        construction_concept_id=concept.id,
                        material_id=material.id,
                        quantity_per_unit=decimal(quantity),
                    )
                )
            else:
                concept_material.quantity_per_unit = decimal(quantity)

        for labor_name, quantity in data["labor"].items():
            labor_rate = labor_rates[labor_name]
            concept_labor = get_one(
                db,
                ConceptLabor,
                construction_concept_id=concept.id,
                labor_rate_id=labor_rate.id,
            )
            if concept_labor is None:
                db.add(
                    ConceptLabor(
                        construction_concept_id=concept.id,
                        labor_rate_id=labor_rate.id,
                        quantity_per_unit=decimal(quantity),
                    )
                )
            else:
                concept_labor.quantity_per_unit = decimal(quantity)

        concepts[data["code"]] = concept
        concept._demo_sort_order = index
        concept._demo_model_quantity_per_m2 = decimal(data["model_quantity_per_m2"])
    db.flush()
    return concepts


def upsert_house_models(
    db: Session,
    company_id: int,
    concepts: dict[str, ConstructionConcept],
    clients: dict[str, Client],
) -> dict[str, HouseModel]:
    house_models: dict[str, HouseModel] = {}
    client_by_model = {client_data["model"]: clients[client_data["name"]] for client_data in CLIENTS}
    for data in HOUSE_MODELS:
        client = client_by_model[data["name"]]
        house_model = get_one(db, HouseModel, company_id=company_id, name=data["name"])
        if house_model is None:
            house_model = HouseModel(
                company_id=company_id,
                client_id=client.id,
                name=data["name"],
                description=data["description"],
                construction_m2=data["construction_m2"],
                levels=data["levels"],
                bedrooms=data["bedrooms"],
                bathrooms=data["bathrooms"],
                base_notes="Modelo demo conectado a conceptos de obra.",
            )
            db.add(house_model)
            db.flush()
        else:
            house_model.client_id = client.id
            house_model.description = data["description"]
            house_model.construction_m2 = data["construction_m2"]
            house_model.levels = data["levels"]
            house_model.bedrooms = data["bedrooms"]
            house_model.bathrooms = data["bathrooms"]

        for concept in concepts.values():
            model_concept = get_one(
                db,
                HouseModelConcept,
                house_model_id=house_model.id,
                construction_concept_id=concept.id,
            )
            quantity_value = concept._demo_model_quantity_per_m2
            sort_order = concept._demo_sort_order
            if model_concept is None:
                db.add(
                    HouseModelConcept(
                        house_model_id=house_model.id,
                        construction_concept_id=concept.id,
                        quantity_formula_type="per_m2",
                        quantity_value=quantity_value,
                        sort_order=sort_order,
                    )
                )
            else:
                model_concept.quantity_formula_type = "per_m2"
                model_concept.quantity_value = quantity_value
                model_concept.sort_order = sort_order

        house_models[data["name"]] = house_model
    db.flush()
    return house_models


def upsert_clients(db: Session, company_id: int) -> dict[str, Client]:
    clients: dict[str, Client] = {}
    for client_data in CLIENTS:
        client = get_one(db, Client, company_id=company_id, name=client_data["name"])
        if client is None:
            client = Client(
                company_id=company_id,
                name=client_data["name"],
                legal_name=client_data["legal_name"],
                contact_name=client_data["contact_name"],
                contact_email=client_data["contact_email"],
                contact_phone=client_data["contact_phone"],
                notes=client_data["notes"],
            )
            db.add(client)
            db.flush()
        else:
            client.legal_name = client_data["legal_name"]
            client.contact_name = client_data["contact_name"]
            client.contact_email = client_data["contact_email"]
            client.contact_phone = client_data["contact_phone"]
            client.notes = client_data["notes"]
        clients[client_data["name"]] = client
    db.flush()
    return clients


def upsert_clients_projects(
    db: Session,
    company_id: int,
    clients: dict[str, Client],
    house_models: dict[str, HouseModel],
) -> list[Project]:
    projects: list[Project] = []
    model_data_by_name = {item["name"]: item for item in HOUSE_MODELS}
    for client_data in CLIENTS:
        client = clients[client_data["name"]]
        house_model = house_models[client_data["model"]]
        model_data = model_data_by_name[client_data["model"]]
        for project_name, house_count, location in client_data["projects"]:
            project = get_one(db, Project, company_id=company_id, client_id=client.id, name=project_name)
            if project is None:
                project = Project(
                    company_id=company_id,
                    client_id=client.id,
                    name=project_name,
                    description=f"Desarrollo demo de {house_count} casas.",
                    location=location,
                    status="draft",
                    start_date=date(2026, 6, 1),
                    estimated_end_date=date(2027, 3, 31),
                )
                db.add(project)
                db.flush()
            else:
                project.description = f"Desarrollo demo de {house_count} casas."
                project.location = location

            assignment = get_one(
                db,
                ProjectHouseModel,
                project_id=project.id,
                house_model_id=house_model.id,
            )
            total_cost = model_data["estimated_cost_per_unit"] * decimal(house_count)
            total_price = model_data["estimated_price_per_unit"] * decimal(house_count)
            if assignment is None:
                assignment = ProjectHouseModel(
                    project_id=project.id,
                    house_model_id=house_model.id,
                    quantity=decimal(house_count),
                    estimated_cost_per_unit=model_data["estimated_cost_per_unit"],
                    estimated_price_per_unit=model_data["estimated_price_per_unit"],
                    total_estimated_cost=total_cost,
                    total_estimated_price=total_price,
                )
                db.add(assignment)
            else:
                assignment.quantity = decimal(house_count)
                assignment.estimated_cost_per_unit = model_data["estimated_cost_per_unit"]
                assignment.estimated_price_per_unit = model_data["estimated_price_per_unit"]
                assignment.total_estimated_cost = total_cost
                assignment.total_estimated_price = total_price
            projects.append(project)
    db.flush()
    return projects


def upsert_project_material_prices(
    db: Session,
    company_id: int,
    projects: list[Project],
) -> None:
    for project in projects:
        for assignment in project.project_house_models:
            house_model = assignment.house_model
            price_factor = PROJECT_PRICE_FACTORS.get(house_model.name, Decimal("1.0000"))
            used_materials: dict[int, Material] = {}
            for model_concept in house_model.model_concepts:
                concept = model_concept.construction_concept
                for concept_material in concept.concept_materials:
                    used_materials[concept_material.material.id] = concept_material.material

            for material in used_materials.values():
                supplied_by_developer = material.name in DEVELOPER_SUPPLIED_MATERIALS
                project_price = get_one(
                    db,
                    ProjectMaterialPrice,
                    company_id=company_id,
                    project_id=project.id,
                    house_model_id=house_model.id,
                    material_id=material.id,
                )
                unit_price = material.current_unit_price * price_factor
                if project_price is None:
                    project_price = ProjectMaterialPrice(
                        company_id=company_id,
                        project_id=project.id,
                        house_model_id=house_model.id,
                        material_id=material.id,
                        unit=material.unit,
                    )
                    db.add(project_price)
                project_price.unit = material.unit
                project_price.unit_price = unit_price
                project_price.supply_source = "developer" if supplied_by_developer else "constructor"
                project_price.supplier_name = (
                    "Material suministrado por desarrolladora"
                    if supplied_by_developer
                    else material.supplier_name
                )
                project_price.include_in_quote = not supplied_by_developer
                project_price.source_document_name = f"Tabulador {project.name}.pdf"
                project_price.effective_date = date(2026, 5, 18)
                project_price.notes = (
                    "Demo: material documentado en tabulador, no se cobra en cotizacion."
                    if supplied_by_developer
                    else "Demo: precio unitario especifico del desarrollo."
                )
                project_price.is_active = True
    db.flush()


def create_quotes_if_missing(db: Session, projects: list[Project], admin_user: User) -> None:
    db.commit()
    for project in projects:
        existing_quote = db.scalar(select(Quote.id).where(Quote.project_id == project.id))
        if existing_quote is None:
            create_project_quote(
                db=db,
                project_id=project.id,
                created_by=admin_user.id,
                notes="Cotización demo generada desde seed_demo.",
                profit_percent=Decimal("0.1500"),
            )


def expected_materials_for_project(project: Project, house_count: Decimal) -> dict[str, Decimal]:
    multiplier = house_count / Decimal("30")
    if "Nido" in project.project_house_models[0].house_model.name:
        base = {
            "Cemento gris 50kg": Decimal("900"),
            "Block 12x20x40": Decimal("18000"),
            "Varilla 3/8": Decimal("1200"),
            "Arena": Decimal("180"),
            "Grava": Decimal("150"),
            "Pintura vinílica": Decimal("900"),
            "Loseta cerámica": Decimal("1920"),
        }
    elif "Magna" in project.project_house_models[0].house_model.name:
        base = {
            "Cemento gris 50kg": Decimal("2100"),
            "Block 12x20x40": Decimal("42000"),
            "Varilla 3/8": Decimal("2500"),
            "Varilla 1/2": Decimal("1800"),
            "Arena": Decimal("390"),
            "Grava": Decimal("330"),
            "Concreto premezclado": Decimal("270"),
            "Pintura vinílica": Decimal("2200"),
            "Loseta cerámica": Decimal("4500"),
        }
    else:
        base = {
            "Cemento gris 50kg": Decimal("1450"),
            "Block 12x20x40": Decimal("29000"),
            "Varilla 3/8": Decimal("1800"),
            "Varilla 1/2": Decimal("1100"),
            "Arena": Decimal("265"),
            "Grava": Decimal("225"),
            "Concreto premezclado": Decimal("180"),
            "Pintura vinílica": Decimal("1500"),
            "Loseta cerámica": Decimal("3000"),
        }
    return {name: quantity * multiplier for name, quantity in base.items()}


def upsert_inventory_demo(
    db: Session,
    company_id: int,
    projects: list[Project],
    materials: dict[str, Material],
) -> None:
    for project in projects:
        house_count = project.project_house_models[0].quantity
        warehouse_name = f"Bodega {project.name}"
        warehouse = get_one(db, ProjectWarehouse, company_id=company_id, project_id=project.id, name=warehouse_name)
        if warehouse is None:
            warehouse = ProjectWarehouse(
                company_id=company_id,
                project_id=project.id,
                name=warehouse_name,
                location=project.location,
                notes="Bodega demo creada para recepciones parciales.",
                is_active=True,
            )
            db.add(warehouse)
            db.flush()

        list_name = f"Lista PDF Inicial - {project.name}"
        expected_list = get_one(
            db,
            ExpectedMaterialList,
            company_id=company_id,
            project_id=project.id,
            name=list_name,
        )
        if expected_list is None:
            expected_list = ExpectedMaterialList(
                company_id=company_id,
                project_id=project.id,
                warehouse_id=warehouse.id,
                name=list_name,
                source_document_name=f"{project.name.lower().replace(' ', '-')}-materiales.pdf",
                source_notes="Lista demo enviada por la desarrolladora.",
                status="open",
            )
            db.add(expected_list)
            db.flush()

        expected_by_material = expected_materials_for_project(project, house_count)
        expected_items: dict[str, ExpectedMaterialItem] = {}
        for material_name, expected_quantity in expected_by_material.items():
            material = materials[material_name]
            expected_item = get_one(
                db,
                ExpectedMaterialItem,
                expected_list_id=expected_list.id,
                material_id=material.id,
            )
            if expected_item is None:
                expected_item = ExpectedMaterialItem(
                    company_id=company_id,
                    expected_list_id=expected_list.id,
                    material_id=material.id,
                    description=material.name,
                    unit=material.unit,
                    expected_quantity=expected_quantity,
                    received_quantity=Decimal("0"),
                    status="pending",
                )
                db.add(expected_item)
                db.flush()
            else:
                expected_item.expected_quantity = expected_quantity
                expected_item.description = material.name
                expected_item.unit = material.unit
            expected_items[material_name] = expected_item

        if db.scalar(select(MaterialReception.id).where(MaterialReception.expected_list_id == expected_list.id)) is None:
            create_demo_receptions(db, company_id, project, warehouse, expected_list, expected_items)


def create_demo_receptions(
    db: Session,
    company_id: int,
    project: Project,
    warehouse: ProjectWarehouse,
    expected_list: ExpectedMaterialList,
    expected_items: dict[str, ExpectedMaterialItem],
) -> None:
    reception_sets = [
        ("ENT-001", date(2026, 6, 5), Decimal("0.35"), "Primera entrega parcial."),
        ("ENT-002", date(2026, 6, 12), Decimal("0.40"), "Segunda entrega; algunos materiales siguen pendientes."),
        ("ENT-003", date(2026, 6, 20), Decimal("0.20"), "Tercera entrega con faltantes registrados."),
    ]
    material_names = list(expected_items)
    for reference, received_at, factor, notes in reception_sets:
        reception = MaterialReception(
            company_id=company_id,
            project_id=project.id,
            warehouse_id=warehouse.id,
            expected_list_id=expected_list.id,
            received_at=received_at,
            delivery_reference=reference,
            delivered_by="Desarrolladora",
            received_by="Encargado de bodega demo",
            notes=notes,
            status="closed",
        )
        db.add(reception)
        db.flush()

        for material_index, material_name in enumerate(material_names):
            if reference == "ENT-003" and material_index % 3 == 0:
                continue
            expected_item = expected_items[material_name]
            received_quantity = (expected_item.expected_quantity * factor).quantize(Decimal("0.0001"))
            condition_status = "incomplete" if reference == "ENT-003" and material_index % 2 == 0 else "ok"
            db.add(
                MaterialReceptionItem(
                    reception_id=reception.id,
                    expected_item_id=expected_item.id,
                    material_id=expected_item.material_id,
                    description=expected_item.description,
                    unit=expected_item.unit,
                    received_quantity=received_quantity,
                    condition_status=condition_status,
                    notes="Cotejado contra lista PDF demo." if condition_status == "ok" else "Queda faltante por completar.",
                )
            )
            expected_item.received_quantity += received_quantity
            expected_item.status = item_status(
                expected_item.expected_quantity,
                expected_item.received_quantity,
                has_issue=condition_status != "ok",
            )
            stock_item = get_one(
                db,
                WarehouseStock,
                warehouse_id=warehouse.id,
                expected_item_id=expected_item.id,
            )
            if stock_item is None:
                stock_item = WarehouseStock(
                    company_id=company_id,
                    warehouse_id=warehouse.id,
                    expected_item_id=expected_item.id,
                    material_id=expected_item.material_id,
                    description=expected_item.description,
                    unit=expected_item.unit,
                    quantity_on_hand=Decimal("0"),
                )
                db.add(stock_item)
            stock_item.quantity_on_hand += received_quantity


def seed_demo(db: Session) -> None:
    admin_user = seed_admin(db)
    company_id = admin_user.company_id
    if company_id is None:
        raise RuntimeError("El usuario administrador no tiene empresa asignada")

    materials = upsert_materials(db, company_id)
    labor_rates = upsert_labor_rates(db, company_id)
    concepts = upsert_concepts(db, company_id, materials, labor_rates)
    clients = upsert_clients(db, company_id)
    house_models = upsert_house_models(db, company_id, concepts, clients)
    projects = upsert_clients_projects(db, company_id, clients, house_models)
    upsert_project_material_prices(db, company_id, projects)
    db.commit()

    create_quotes_if_missing(db, projects, admin_user)

    projects = list(
        db.scalars(
            select(Project).where(Project.company_id == company_id, Project.name.in_([name for client in CLIENTS for name, _, _ in client["projects"]]))
        ).all()
    )
    # Force-load project model assignments for inventory sizing while the session is open.
    for project in projects:
        _ = project.project_house_models[0].house_model.name
    upsert_inventory_demo(db, company_id, projects, materials)
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_demo(db)
        print("Datos demo listos: 3 clientes, 6 desarrollos, 3 modelos, cotizaciones e inventario.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
