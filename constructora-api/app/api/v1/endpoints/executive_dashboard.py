from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.executive_dashboard import ExecutiveDashboardResponse
from app.services.executive_dashboard import executive_dashboard
from app.services.tenancy import (
    allowed_client_ids,
    ensure_project_access,
    get_user_company_id,
)


router = APIRouter()


@router.get("", response_model=ExecutiveDashboardResponse)
def get_executive_dashboard(
    project_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("executive_dashboard", "view")),
) -> dict:
    if project_id is not None:
        ensure_project_access(db, current_user, project_id)
    return executive_dashboard(
        db,
        company_id=get_user_company_id(current_user),
        project_id=project_id,
        allowed_client_ids=allowed_client_ids(db, current_user),
    )
