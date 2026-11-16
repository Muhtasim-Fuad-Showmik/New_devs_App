import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import authenticate_request as get_current_user
from app.services.cache import get_revenue_summary
from app.services.reservations import get_property, list_properties

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_tenant(current_user) -> str:
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")
    return tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user=Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Properties owned by the caller tenant only."""
    tenant_id = _require_tenant(current_user)
    try:
        return await list_properties(tenant_id)
    except Exception:
        logger.exception("Failed to list properties for tenant %s", tenant_id)
        raise HTTPException(status_code=503, detail="Property data unavailable")


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = _require_tenant(current_user)

    try:
        # A property ID alone is not enough (prop-001 exists for several
        # tenants): it must belong to the tenant of the caller.
        if await get_property(property_id, tenant_id) is None:
            raise HTTPException(status_code=404, detail="Property not found")

        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Revenue lookup failed for %s (tenant %s)", property_id, tenant_id)
        raise HTTPException(status_code=503, detail="Revenue data unavailable")

    total_revenue_float = float(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
