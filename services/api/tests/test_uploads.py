from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DEFAULT_USER_ID, get_db
from app.core.config import get_settings
from app.main import create_app
from app.models.wardrobe import WardrobeItem
from app.utils import s3 as s3_utils


class DummyS3Client:
    def __init__(self, expected_bucket: str):
        self.expected_bucket = expected_bucket
        self.called_with: dict[str, str] | None = None

    def generate_presigned_url(
        self,
        *,
        ClientMethod: str,  # noqa: N803 - fixture emulates boto3 signature
        Params: dict,  # noqa: N803 - fixture emulates boto3 signature
        ExpiresIn: int,  # noqa: N803 - fixture emulates boto3 signature
    ) -> str:  # noqa: N803
        assert ClientMethod == "put_object"
        assert Params["Bucket"] == self.expected_bucket
        self.called_with = {
            "key": Params["Key"],
            "content_type": Params["ContentType"],
            "expires": ExpiresIn,
        }
        return "https://example.com/upload"


def _make_sample_image_bytes(color: tuple[int, int, int] = (200, 40, 40)) -> bytes:
    image = Image.new("RGB", (64, 48), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture()
def s3_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a TestClient configured for S3 upload mode."""

    monkeypatch.setenv("UPLOAD_MODE", "s3")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")
    get_settings.cache_clear()

    application = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db
    dummy_client = DummyS3Client(expected_bucket="test-bucket")
    monkeypatch.setattr(s3_utils, "get_s3_client", lambda region: dummy_client)
    return TestClient(application)


def test_presign_creates_item_and_returns_url(
    s3_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy_client = DummyS3Client(expected_bucket="test-bucket")
    monkeypatch.setattr(s3_utils, "get_s3_client", lambda region: dummy_client)

    response = s3_client.post(
        "/items/presign",
        json={"contentType": "image/jpeg", "fileName": "test.jpg"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["uploadUrl"] == "https://example.com/upload"
    assert payload["objectKey"].startswith("user/")
    item_id = uuid.UUID(payload["itemId"])

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    inserted = db_session.execute(stmt).scalar_one()
    assert inserted.image_url is None
    assert inserted.user_id == DEFAULT_USER_ID
    assert dummy_client.called_with is not None
    assert dummy_client.called_with["content_type"] == "image/jpeg"
    assert dummy_client.called_with["key"] == payload["objectKey"]


def test_complete_upload_constructs_public_url(
    s3_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    dummy_client = DummyS3Client(expected_bucket="test-bucket")
    monkeypatch.setattr(s3_utils, "get_s3_client", lambda region: dummy_client)

    sample_bytes = _make_sample_image_bytes()
    uploaded_objects: dict[str, bytes] = {}

    monkeypatch.setattr(
        s3_utils,
        "head_object",
        lambda **kwargs: {"ContentType": "image/png"},
    )
    monkeypatch.setattr(
        s3_utils,
        "download_object",
        lambda **kwargs: sample_bytes,
    )

    def _capture_upload(
        *,
        bucket: str,
        key: str,
        region: str,
        data: bytes,
        content_type: str,
    ) -> None:
        uploaded_objects[key] = data

    monkeypatch.setattr(s3_utils, "upload_bytes", _capture_upload)

    presign = s3_client.post(
        "/items/presign",
        json={"contentType": "image/png", "fileName": "look.png"},
    )
    assert presign.status_code == 200
    payload = presign.json()
    item_id = uuid.UUID(payload["itemId"])
    object_key = payload["objectKey"]

    complete = s3_client.post(
        f"/items/{item_id}/complete-upload",
        json={"objectKey": object_key, "fileName": "look.png"},
    )

    assert complete.status_code == 200
    body = complete.json()
    base_prefix, _sep, _ = object_key.rpartition("/")
    prefix = f"{base_prefix}/" if base_prefix else ""
    bucket_host = "https://test-bucket.s3.us-east-1.amazonaws.com"
    expected_url = f"{bucket_host}/{prefix}orig.jpg"
    assert body["imageUrl"] == expected_url
    assert body["thumbUrl"].endswith("thumb.jpg")
    assert body["mediumUrl"].endswith("medium.jpg")

    metadata = body["imageMetadata"]
    assert metadata["width"] == 64
    assert metadata["height"] == 48
    assert metadata["mimeType"] == "image/jpeg"

    assert f"{prefix}orig.jpg" in uploaded_objects
    assert f"{prefix}medium.jpg" in uploaded_objects
    assert f"{prefix}thumb.jpg" in uploaded_objects

    stmt = select(WardrobeItem).where(WardrobeItem.id == item_id)
    stored = db_session.execute(stmt).scalar_one()
    assert stored.image_url == expected_url


def test_local_upload_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("UPLOAD_MODE", "local")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_settings.cache_clear()

    application = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db

    with TestClient(application) as test_client:
        presign = test_client.post(
            "/items/presign",
            json={"contentType": "image/jpeg", "fileName": "camera.jpg"},
        )
        assert presign.status_code == 200
        presign_payload = presign.json()
        assert presign_payload["uploadUrl"].startswith("/items/uploads/")
        item_id = uuid.UUID(presign_payload["itemId"])

        local_bytes = _make_sample_image_bytes()
        upload = test_client.put(
            presign_payload["uploadUrl"],
            data=local_bytes,
            headers={
                "Content-Type": "image/jpeg",
                "X-File-Name": "camera.jpg",
            },
        )
        assert upload.status_code == 201
        saved_data = upload.json()
        saved_name = saved_data["fileName"]

        initial_path = Path(tmp_path) / str(item_id) / saved_name
        assert initial_path.exists()

        complete = test_client.post(
            f"/items/{item_id}/complete-upload",
            json={"fileName": "camera.jpg"},
        )
        assert complete.status_code == 200
        completed = complete.json()
        assert completed["imageUrl"].endswith("orig.jpg")
        assert completed["thumbUrl"].endswith("thumb.jpg")
        assert completed["mediumUrl"].endswith("medium.jpg")
        metadata = completed["imageMetadata"]
        assert metadata["width"] == 64
        assert metadata["height"] == 48
        assert metadata["mimeType"] == "image/jpeg"

        detail = test_client.get(f"/items/{item_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["imageUrl"] == completed["imageUrl"]

        media_response = test_client.get(detail_payload["imageUrl"])
        assert media_response.status_code == 200
        assert media_response.content.startswith(b"\xff\xd8\xff")

        item_dir = Path(tmp_path) / str(item_id)
        assert (item_dir / "orig.jpg").exists()
        assert (item_dir / "medium.jpg").exists()
        assert (item_dir / "thumb.jpg").exists()
        assert not initial_path.exists()

    # Ensure temporary media directory was written
    assert any(tmp_path.iterdir())
