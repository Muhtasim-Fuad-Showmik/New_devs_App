from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

from sqlalchemy import text

from app.core.database_pool import db_pool

async def calculate_monthly_revenue(property_id: str, month: int, year: int, db_session=None) -> Decimal:
    """
    Calculates revenue for a specific month.
    """

    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)
        
    print(f"DEBUG: Querying revenue for {property_id} from {start_date} to {end_date}")

    # SQL Simulation (This would be executed against the actual DB)
    query = """
        SELECT SUM(total_amount) as total
        FROM reservations
        WHERE property_id = $1
        AND tenant_id = $2
        AND check_in_date >= $3
        AND check_in_date < $4
    """
    
    # In production this query executes against a database session.
    # result = await db.fetch_val(query, property_id, tenant_id, start_date, end_date)
    # return result or Decimal('0')
    
    return Decimal('0') # Placeholder for now until DB connection is finalized

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from the database for one tenant's property.
    Database failures propagate to the caller
    """
    # Reuse the single shared pool instead of building a new one per request.
    if not db_pool.session_factory:
        await db_pool.initialize()

    query = text("""
        SELECT
            COALESCE(SUM(total_amount), 0) AS total_revenue,
            COUNT(*) AS reservation_count,
            MIN(currency) AS currency
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
    """)

    async with db_pool.get_session() as session:
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
        })
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
