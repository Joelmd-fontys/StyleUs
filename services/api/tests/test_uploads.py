from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DEFAULT_USER_ID, get_db
from app.core.config import get_settings
from app.main import create_app
from app.models.wardrobe import WardrobeItem
from app.utils import storage as storage_utils


class FakeStorageAdapter:
    def __init__(self) -> None:
        self.created_uploads: list[str] = []
        self.uploaded_objects: dict[str, bytes] = {}
        self.deleted_objects: list[str] = []
        self.downloaded_path: str | None = None
        self.info_by_path: dict[str, dict[str, object]] = {}
        self.file_by_path: dict[str, storage_utils.DownloadedObject] = {}

    def create_signed_upload_target(self, object_path: str) -> storage_utils.SignedUploadTarget:
        self.created_uploads.append(object_path)
        return storage_utils.SignedUploadTarget(
            bucket="wardrobe-images",
            object_path=object_path,
            upload_url=f"https://storage.example/upload/{object_path}",
            token="signed-upload-token",
        )

    def get_object_info(self, object_path: str) -> dict[str, object]:
        return self.info_by_path[object_path]

    def download_object(self, object_path: str) -> storage_utils.DownloadedObject:
        self.downloaded_path = object_path
        return self.file_by_path[object_path]

    def upload_bytes(
        self,
        object_path: str,
        *,
        data: bytes,
        content_type: str,
        upsert: bool = True,
    ) -> None:
        _ = content_type, upsert
        self.uploaded_objects[object_path] = data

    def delete_objects(self, object_paths: list[str]) -> None:
        self.deleted_objects.extend(object_paths)

    def create_signed_urls(self, object_paths: list[str]) -> dict[str, str]:
        return {
            path: f"https://signed.example/{path.replace('/', '%2F')}"
            for path in object_paths
        }


def _make_sample_image_bytes(color: tuple[int, int, int] = (200, 40, 40)) -> bytes:
    image = Image.new("RGB", (64, 48), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_client(db_session: Session) -> TestClient:
    application = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db
    return TestClient(application)


def test_presign_creates_item_and_returns_signed_upload_target(
    db_session: Session,
    monkeypatch,
) -> None:
    fake_storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: fake_storage)
    get_settings.cache_clear()

    with _build_client(db_session) as client:
        response = client.post(
            "/items/presign",
            json={"contentType": "image/jpeg", "fileName": "test.jpg", "fileSize": 1024},
        )

    assert response.status_code == 200
    payload = response.json()
    item_id = uuid.UUID(payload["itemId"])

    assert payload["uploadUrl"] == (
        f"https://storage.example/upload/users/{DEFAULT_USER_ID}/{item_id}/source/test.jpg"
    )
    assert payload["uploadToken"] == "signed-upload-token"
    assert payload["bucket"] == "wardrobe-images"
    assert payload["objectKey"] == f"users/{DEFAULT_USER_ID}/{item_id}/source/test.jpg"
    assert fake_storage.created_uploads == [payload["objectKey"]]

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    inserted = db_session.execute(stmt).scalar_one()
    assert inserted.image_url is None
    assert inserted.image_object_path is None
    assert inserted.user_id == DEFAULT_USER_ID


def test_presign_rejects_oversized_upload(db_session: Session, monkeypatch) -> None:
    fake_storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: fake_storage)
    get_settings.cache_clear()

    with _build_client(db_session) as client:
        response = client.post(
            "/items/presign",
            json={"contentType": "image/jpeg", "fileName": "big.jpg", "fileSize": 99_999_999},
        )

    assert response.status_code == 400
    assert fake_storage.created_uploads == []


def test_complete_upload_persists_object_paths_and_returns_signed_urls(
    db_session: Session,
    monkeypatch,
) -> None:
    fake_storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: fake_storage)
    get_settings.cache_clear()

    source_bytes = _make_sample_image_bytes()

    with _build_client(db_session) as client:
        presign = client.post(
            "/items/presign",
            json={"contentType": "image/png", "fileName": "look.png", "fileSize": len(source_bytes)},
        )
        assert presign.status_code == 200

        payload = presign.json()
        item_id = uuid.UUID(payload["itemId"])
        object_key = payload["objectKey"]

        fake_storage.info_by_path[object_key] = {
            "name": object_key,
            "metadata": {"mimetype": "image/png", "size": len(source_bytes)},
            "size": len(source_bytes),
        }
        fake_storage.file_by_path[object_key] = storage_utils.DownloadedObject(
            object_path=object_key,
            data=source_bytes,
            content_type="image/png",
            size=len(source_bytes),
        )

        complete = client.post(
            f"/items/{item_id}/complete-upload",
            json={"objectKey": object_key, "fileName": "look.png"},
        )

        assert complete.status_code == 200
        body = complete.json()
        expected_prefix = f"users/{DEFAULT_USER_ID}/{item_id}"

        assert body["imageUrl"] == f"https://signed.example/{expected_prefix}%2Forig.jpg"
        assert body["mediumUrl"] == f"https://signed.example/{expected_prefix}%2Fmedium.jpg"
        assert body["thumbUrl"] == f"https://signed.example/{expected_prefix}%2Fthumb.jpg"

        metadata = body["imageMetadata"]
        assert metadata["width"] == 64
        assert metadata["height"] == 48
        assert metadata["mimeType"] == "image/jpeg"

        assert fake_storage.downloaded_path == object_key
        assert fake_storage.deleted_objects == [object_key]
        assert f"{expected_prefix}/orig.jpg" in fake_storage.uploaded_objects
        assert f"{expected_prefix}/medium.jpg" in fake_storage.uploaded_objects
        assert f"{expected_prefix}/thumb.jpg" in fake_storage.uploaded_objects

        detail = client.get(f"/items/{item_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["imageUrl"] == body["imageUrl"]

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    stored = db_session.execute(stmt).scalar_one()
    assert stored.image_object_path == f"{expected_prefix}/orig.jpg"
    assert stored.image_medium_object_path == f"{expected_prefix}/medium.jpg"
    assert stored.image_thumb_object_path == f"{expected_prefix}/thumb.jpg"
    assert stored.image_url is None


def test_legacy_binary_upload_sink_is_gone(db_session: Session) -> None:
    with _build_client(db_session) as client:
        response = client.put(
            f"/items/uploads/{uuid.uuid4()}",
            data=b"image",
            headers={"Content-Type": "image/jpeg"},
        )

    assert response.status_code == 410
