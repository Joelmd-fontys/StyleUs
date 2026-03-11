from __future__ import annotations

import uuid

from sqlalchemy import select

from app.api.deps import DEFAULT_USER_ID
from app.models.ai_job import AIJob
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
        subcategory="t-shirt",
        color="red",
        brand="Nike",
    )
    first.tags = [ItemTag(tag="sport"), ItemTag(tag="running")]

    second = WardrobeItem(
        id=uuid.uuid4(),
        user_id=DEFAULT_USER_ID,
        category="bottom",
        subcategory="jeans",
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
    assert item["subcategory"] == "t-shirt"
    assert item["ai"] is not None
    assert item["ai"]["subcategory"] == "t-shirt"
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


def test_delete_marks_item_and_hides_from_listing(client, db_session):
    item, other = seed_items(db_session)
    job = AIJob(item_id=item.id, status="pending", attempts=0)
    db_session.add(job)
    db_session.commit()

    response = client.delete(f"/items/{item.id}")
    assert response.status_code == 204

    db_session.expire_all()
    deleted = db_session.get(WardrobeItem, item.id)
    deleted_job = db_session.get(AIJob, job.id)
    assert deleted is not None and deleted.deleted_at is not None
    assert deleted_job is not None
    assert deleted_job.status == "failed"
    assert deleted_job.error_message == "Wardrobe item deleted before AI enrichment"

    list_response = client.get("/items")
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(other.id)

    detail_response = client.get(f"/items/{item.id}")
    assert detail_response.status_code == 404

    include_deleted = client.get("/items", params={"include_deleted": "true"})
    assert include_deleted.status_code == 200
    full_data = include_deleted.json()
    assert len(full_data) == 2
    assert any(entry["id"] == str(item.id) for entry in full_data)


def test_ai_preview_endpoint_returns_predictions(client, db_session):
    item, _ = seed_items(db_session)
    item.category = "uncategorized"
    item.subcategory = None
    item.primary_color = None
    item.secondary_color = None
    item.ai_confidence = None
    db_session.add(item)
    db_session.add(
        AIJob(
            item_id=item.id,
            status="completed",
            attempts=1,
            result_payload={
                "category": "top",
                "category_confidence": 0.82,
                "subcategory": "t-shirt",
                "subcategory_confidence": 0.71,
                "primary_color": "Camel",
                "primary_color_confidence": 0.69,
                "secondary_color": "Tan",
                "secondary_color_confidence": 0.52,
                "materials": ["cotton"],
                "style_tags": ["minimal"],
                "tags": ["minimal", "cotton"],
                "confidence": 0.82,
            },
        )
    )
    db_session.commit()

    response = client.get(f"/items/{item.id}/ai-preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "top"
    assert payload["subcategory"] == "t-shirt"
    assert payload["primaryColor"] == "Camel"
    assert payload["secondaryColor"] == "Tan"
    assert payload["materials"] == ["cotton"]
    assert payload["styleTags"] == ["minimal"]
    assert payload["tags"] == ["minimal", "cotton"]
    assert payload["confidence"] == 0.82
    assert payload["categoryConfidence"] == 0.82
    assert payload["subcategoryConfidence"] == 0.71
    assert payload["primaryColorConfidence"] == 0.69
    assert payload["secondaryColorConfidence"] == 0.52
    assert payload["pending"] is False
    assert payload["job"]["status"] == "completed"


def test_ai_preview_endpoint_reports_pending_job_without_running_pipeline(client, db_session):
    item, _ = seed_items(db_session)
    item.category = "uncategorized"
    item.subcategory = None
    item.ai_confidence = None
    db_session.add(item)
    db_session.add(AIJob(item_id=item.id, status="pending", attempts=0))
    db_session.commit()

    response = client.get(f"/items/{item.id}/ai-preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] is None
    assert payload["subcategory"] is None
    assert payload["pending"] is True
    assert payload["job"]["status"] == "pending"
    assert payload["job"]["attempts"] == 0
