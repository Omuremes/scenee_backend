import pytest
from httpx import AsyncClient
from uuid import uuid4
from datetime import datetime, timedelta
from app.main import app
from app.core.database import get_db
from app.models import Event, EventSession, EventCategory
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_get_upcoming_events_filtering(db_session: AsyncSession):
    # 1. Create a category
    category = EventCategory(name="Music", slug="music")
    db_session.add(category)
    await db_session.flush()

    # 2. Create an event that should match
    event_match = Event(
        title="The Weeknd Live",
        description="Great concert",
        type="concerts",
        city="Bishkek",
        category_id=category.id,
        is_active=True
    )
    db_session.add(event_match)
    await db_session.flush()

    # 3. Add an upcoming session
    session_upcoming = EventSession(
        event_id=event_match.id,
        starts_at=datetime.utcnow() + timedelta(days=1),
        base_price=1000.0,
        pricing_type="fixed"
    )
    db_session.add(session_upcoming)

    # 4. Create an event that should NOT match (past session)
    event_past = Event(
        title="The Weeknd Past",
        description="Old concert",
        type="concerts",
        city="Bishkek",
        category_id=category.id,
        is_active=True
    )
    db_session.add(event_past)
    await db_session.flush()

    session_past = EventSession(
        event_id=event_past.id,
        starts_at=datetime.utcnow() - timedelta(days=1),
        base_price=1000.0,
        pricing_type="fixed"
    )
    db_session.add(session_past)

    # 5. Create an event in a different city
    event_city = Event(
        title="The Weeknd Osh",
        description="Concert in Osh",
        type="concerts",
        city="Osh",
        category_id=category.id,
        is_active=True
    )
    db_session.add(event_city)
    await db_session.flush()

    session_osh = EventSession(
        event_id=event_city.id,
        starts_at=datetime.utcnow() + timedelta(days=1),
        base_price=1000.0,
        pricing_type="fixed"
    )
    db_session.add(session_osh)

    await db_session.commit()

    # Test the API
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Search with city and query
        response = await client.get("/v1/events/?city=Bishkek&query=The Week")
        assert response.status_code == 200
        data = response.json()
        
        # We expect only "The Weeknd Live"
        assert len(data) == 1
        assert data[0]["title"] == "The Weeknd Live"
        assert data[0]["city"] == "Bishkek"

        # Search without query
        response = await client.get("/v1/events/?city=Bishkek")
        assert len(response.json()) == 1

        # Search with wrong query
        response = await client.get("/v1/events/?city=Bishkek&query=None")
        assert len(response.json()) == 0
