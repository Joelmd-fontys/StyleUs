from __future__ import annotations

import uuid

from sqlalchemy import select

from app.api.deps import DEFAULT_USER_ID
from app.models.user import User
from app.models.wardrobe import ItemTag, WardrobeItem


def seed_items(db_session):
    user = db_session.get(User, DEFAULT_USER_ID)
    if not user:
        user = User(id=DEFAULT_USER_ID, email="user@example.com")
        db_session.add(user)

    first = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="top",
        color="red",
        brand="Nike",
    )
    first.tags = [ItemTag(tag="sport"), ItemTag(tag="running")]

    second = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="bottom",
        color="blue",
        brand="Levis",
    )
    second.tags = [ItemTag(tag="denim"), ItemTag(tag="casual")]

    db_session.add_all([first, second])
    db_session.commit()

    return first, second


def test_list_items_with_filters(client, db_session):
    seed_items(db_session)

    response = client.get("/items", params={"category": "top", "q": "sport"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    item = data[0]
    assert item["category"] == "top"
    assert any(tag == "sport" for tag in item["tags"])


def test_patch_updates_item_and_tags(client, db_session):
    item, _ = seed_items(db_session)

    payload = {
        "brand": "Uniqlo",
        "color": "green",
        "tags": ["minimal", "casual"],
    }

    response = client.patch(f"/items/{item.id}", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["brand"] == "Uniqlo"
    assert body["color"] == "green"
    assert set(body["tags"]) == {"minimal", "casual"}

    stmt = select(ItemTag).where(ItemTag.item_id == item.id)
    tags = {tag.tag for tag in db_session.execute(stmt).scalars().all()}
    assert tags == {"minimal", "casual"}
