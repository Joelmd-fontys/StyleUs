from __future__ import annotations

import uuid

from sqlalchemy import select

from app.api.deps import DEFAULT_USER_ID
from app.models.wardrobe import WardrobeItem


class DummyS3Client:
    def __init__(self, expected_bucket: str):
        self.expected_bucket = expected_bucket
        self.called_with: dict[str, str] | None = None

    def generate_presigned_url(self, ClientMethod: str, Params: dict, ExpiresIn: int) -> str:
        assert ClientMethod == "put_object"
        assert Params["Bucket"] == self.expected_bucket
        self.called_with = {
            "key": Params["Key"],
            "content_type": Params["ContentType"],
            "expires": ExpiresIn,
        }
        return "https://example.com/upload"


def test_presign_creates_item_and_returns_url(client, db_session, monkeypatch):
    from app.utils import s3

    dummy_client = DummyS3Client(expected_bucket="test-bucket")
    monkeypatch.setattr(s3, "get_s3_client", lambda region: dummy_client)

    response = client.post(
        "/items/presign",
        json={"contentType": "image/jpeg", "fileName": "test.jpg"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploadUrl"] == "https://example.com/upload"
    item_id = uuid.UUID(payload["itemId"])

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    inserted = db_session.execute(stmt).scalar_one()
    assert inserted.image_url is None
    assert inserted.user_id == DEFAULT_USER_ID
    assert dummy_client.called_with is not None
    assert dummy_client.called_with["content_type"] == "image/jpeg"
