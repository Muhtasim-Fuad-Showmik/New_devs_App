from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional

from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.database_pool import db_pool

def month_bounds_utc(timezone_name: str, month: int, year: int):
    """
    Half-open [start, end) of a calendar month as seen in the property's own
    timezone, converted to UTC so it can be compared with TIMESTAMPTZ values.
    """
    tz = ZoneInfo(timezone_name)
    start_local = datetime(year, month, 1, tzinfo=tz)
    if month < 12:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def calculate_monthly_revenue(
    property_id: str, tenant_id: str, month: int, year: int, timezone_name: str = "UTC"
) -> Decimal:
    """
    Calculates revenue for one calendar month of the property's local time.
    """
    summary = await calculate_total_revenue(property_id, tenant_id, month, year, timezone_name)
    return Decimal(summary["total"])


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    timezone_name: str = "UTC",
) -> Dict[str, Any]:
    """
    Aggregates revenue from the database for one tenant's property.
    All-time by default, or for one calendar month in the property's timezone.
    Database failures propagate to the caller: we never return made-up figures.
    """
    # Reuse the single shared pool instead of building a new one per request.
    if not db_pool.session_factory:
        await db_pool.initialize()

    params: Dict[str, Any] = {"property_id": property_id, "tenant_id": tenant_id}
    date_filter = ""
    if month is not None and year is not None:
        start_utc, end_utc = month_bounds_utc(timezone_name, month, year)
        date_filter = "AND check_in_date >= :start_date AND check_in_date < :end_date"
        params["start_date"] = start_utc
        params["end_date"] = end_utc

    query = text(f"""
        SELECT
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COUNT(*) AS reservation_count,
            MIN(currency) AS currency
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
        {date_filter}
    """)

    async with db_pool.get_session() as session:
        result = await session.execute(query, params)
        row = result.fetchone()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(Decimal(str(row.total_revenue))),
        "currency": row.currency or "USD",
        "count": row.reservation_count,
    }


async def get_property(property_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """Return the property only if it belongs to the tenant, else None."""
    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        result = await session.execute(
            text("""
                SELECT id, name, timezone
                FROM properties
                WHERE id = :property_id AND tenant_id = :tenant_id
            """),
            {"property_id": property_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()

    if not row:
        return None
    return {"id": row.id, "name": row.name, "timezone": row.timezone}


async def list_properties(tenant_id: str) -> List[Dict[str, Any]]:
    """All properties owned by the tenant."""
    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        result = await session.execute(
            text("""
                SELECT id, name, timezone
                FROM properties
                WHERE tenant_id = :tenant_id
                ORDER BY id
            """),
            {"tenant_id": tenant_id},
        )
        rows = result.fetchall()

    return [{"id": r.id, "name": r.name, "timezone": r.timezone} for r in rows]
