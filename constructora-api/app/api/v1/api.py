from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit_events,
    auth,
    clients,
    companies,
    construction_concepts,
    house_models,
    inventory,
    labor_rates,
    materials,
    notifications,
    permissions,
    project_material_prices,
    projects,
    purchasing,
    quotes,
    roles,
    settings,
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
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(
    project_material_prices.router,
    prefix="/project-material-prices",
    tags=["project-material-prices"],
)
api_router.include_router(labor_rates.router, prefix="/labor-rates", tags=["labor-rates"])
api_router.include_router(
    construction_concepts.router,
    prefix="/construction-concepts",
    tags=["construction-concepts"],
)
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(purchasing.router, prefix="/purchasing", tags=["purchasing"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
