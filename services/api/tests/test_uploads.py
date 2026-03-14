from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import color
from app.ai import tasks as ai_tasks
from app.ai.pipeline import PipelineResult
from app.api.deps import DEFAULT_USER_ID, get_current_user_id, get_db
from app.core.config import get_settings
from app.main import create_app
from app.models.ai_job import AIJob
from app.models.wardrobe import WardrobeItem
from app.services import uploads as uploads_service
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
        self.file_by_path[object_path] = storage_utils.DownloadedObject(
            object_path=object_path,
            data=data,
            content_type=content_type,
            size=len(data),
        )
        self.info_by_path[object_path] = {
            "name": object_path,
            "metadata": {"mimetype": content_type, "size": len(data)},
            "size": len(data),
        }

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


def _mock_pipeline_result() -> PipelineResult:
    return PipelineResult(
        colors=color.ColorResult(
            primary_color="Camel",
            secondary_color="Tan",
            confidence=0.88,
            secondary_confidence=0.71,
        ),
        clip={
            "category": "outerwear",
            "category_confidence": 0.91,
            "materials": [("wool", 0.83)],
            "style_tags": [("heritage", 0.79)],
            "subcategory": "coat",
            "subcategory_confidence": 0.8,
            "scores": {
                "category": {"outerwear": 0.91},
                "materials": {"wool": 0.83},
                "style_tags": {"heritage": 0.79},
                "subcategory": {"coat": 0.8},
            },
        },
        cached=False,
    )


def _build_client(db_session: Session) -> TestClient:
    application = create_app(start_worker=False)

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


def test_presign_preflight_returns_cors_headers_without_auth_or_body_logic(
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("CORS_ORIGINS", "https://style-us.vercel.app")
    monkeypatch.delenv("LOCAL_AUTH_BYPASS", raising=False)
    get_settings.cache_clear()

    application = create_app(start_worker=False)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def fail_on_auth():
        raise AssertionError("Auth dependency should not run for CORS preflight")

    def fail_on_presign(*args, **kwargs):
        raise AssertionError("Presign handler should not run for CORS preflight")

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user_id] = fail_on_auth
    monkeypatch.setattr(uploads_service, "create_presigned_upload", fail_on_presign)

    with TestClient(application) as client:
        response = client.options(
            "/items/presign",
            headers={
                "Origin": "https://style-us.vercel.app",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type,x-client-info",
            },
        )

    application.dependency_overrides.pop(get_db, None)
    application.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://style-us.vercel.app"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert (
        response.headers["access-control-allow-headers"]
        == "authorization,content-type,x-client-info"
    )


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
            json={
                "contentType": "image/png",
                "fileName": "look.png",
                "fileSize": len(source_bytes),
            },
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

        encoded_prefix = expected_prefix.replace("/", "%2F")
        assert body["imageUrl"] == f"https://signed.example/{encoded_prefix}%2Forig.jpg"
        assert body["mediumUrl"] == f"https://signed.example/{encoded_prefix}%2Fmedium.jpg"
        assert body["thumbUrl"] == f"https://signed.example/{encoded_prefix}%2Fthumb.jpg"
        assert body["aiJob"]["status"] == "pending"
        assert body["aiJob"]["pending"] is True
        assert body["ai"] is None

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
    job = db_session.execute(select(AIJob).where(AIJob.item_id == item_id)).scalar_one()
    assert job.status == "pending"
    assert job.attempts == 0


def test_complete_upload_runs_inline_heuristic_when_classifier_disabled(
    db_session: Session,
    monkeypatch,
) -> None:
    fake_storage = FakeStorageAdapter()
    monkeypatch.setattr(storage_utils, "get_storage_adapter", lambda settings: fake_storage)
    monkeypatch.setenv("AI_ENABLE_CLASSIFIER", "false")
    monkeypatch.setattr(ai_tasks.pipeline, "run", lambda path: _mock_pipeline_result())
    get_settings.cache_clear()

    source_bytes = _make_sample_image_bytes()

    with _build_client(db_session) as client:
        presign = client.post(
            "/items/presign",
            json={
                "contentType": "image/png",
                "fileName": "look.png",
                "fileSize": len(source_bytes),
            },
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
        assert body["aiJob"] is None
        assert body["ai"]["category"] == "outerwear"
        assert body["ai"]["subcategory"] == "coat"
        assert body["primaryColor"] == "Camel"
        assert body["secondaryColor"] == "Tan"

        preview = client.get(f"/items/{item_id}/ai-preview")
        assert preview.status_code == 200
        preview_body = preview.json()
        assert preview_body["pending"] is False
        assert preview_body["category"] == "outerwear"
        assert preview_body["subcategory"] == "coat"

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    stored = db_session.execute(stmt).scalar_one()
    assert stored.category == "outerwear"
    assert stored.subcategory == "coat"
    assert stored.primary_color == "Camel"
    assert stored.secondary_color == "Tan"
    assert (
        db_session.execute(select(AIJob).where(AIJob.item_id == item_id)).scalar_one_or_none()
        is None
    )
    get_settings.cache_clear()


def test_legacy_binary_upload_sink_is_gone(db_session: Session) -> None:
    with _build_client(db_session) as client:
        response = client.put(
            f"/items/uploads/{uuid.uuid4()}",
            data=b"image",
            headers={"Content-Type": "image/jpeg"},
        )

    assert response.status_code == 410
