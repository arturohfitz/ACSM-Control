from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit_events,
    auth,
    clients,
    companies,
    construction_concepts,
    house_models,
    inventory,
    materials,
    material_requisitions,
    notifications,
    permissions,
    projects,
    purchasing,
    roles,
    settings,
    supplier_portal,
    users,
)


api_router = APIRouter()
api_router.include_router(audit_events.router, prefix="/events", tags=["events"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["permissions"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(house_models.router, prefix="/house-models", tags=["house-models"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(
    material_requisitions.router,
    prefix="/material-requisitions",
    tags=["material-requisitions"],
)
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    construction_concepts.router,
    prefix="/construction-concepts",
    tags=["construction-concepts"],
)
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(supplier_portal.router, prefix="/supplier-portal", tags=["supplier-portal"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
