from app.core import minio as minio_module
from app.core.config import settings


def test_to_public_url_replaces_internal_minio_host(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", None)
    monkeypatch.setattr(minio_module.settings, "MINIO_SECURE", False)

    url = minio_module.to_public_url("http://minio:9000/cinescope-media/movies/poster.jpg")

    assert url == "http://localhost:9000/cinescope-media/movies/poster.jpg"


def test_build_public_object_url_uses_explicit_public_base_url(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150")

    url = minio_module.build_public_object_url("cinescope-media", "movies/poster.jpg")

    assert url == "http://192.168.68.150/cinescope-media/movies/poster.jpg"


def test_to_public_url_uses_explicit_public_base_url(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150")

    url = minio_module.to_public_url("http://minio:9000/cinescope-media/movies/poster.jpg")

    assert url == "http://192.168.68.150/cinescope-media/movies/poster.jpg"


def test_to_public_url_replaces_stale_public_minio_host(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_BUCKET_NAME", "cinescope-media")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.124:9000")

    url = minio_module.to_public_url("http://192.168.68.150:9000/cinescope-media/movies/poster.jpg")

    assert url == "http://192.168.68.124:9000/cinescope-media/movies/poster.jpg"


def test_ensure_bucket_applies_public_read_policy_for_media_bucket(monkeypatch):
    calls = {}

    class FakeMinioClient:
        def bucket_exists(self, bucket_name):
            calls["bucket_exists"] = bucket_name
            return True

        def set_bucket_policy(self, bucket_name, policy):
            calls["bucket_policy"] = (bucket_name, policy)

    monkeypatch.setattr(minio_module, "minio_client", FakeMinioClient())
    monkeypatch.setattr(settings, "MINIO_BUCKET_NAME", "cinescope-media")

    minio_module.ensure_bucket("cinescope-media")

    bucket_name, policy = calls["bucket_policy"]
    assert bucket_name == "cinescope-media"
    assert "arn:aws:s3:::cinescope-media/movies/posters/*" in policy
    assert "arn:aws:s3:::cinescope-media/episodes/*" not in policy


def test_presigned_url_is_signed_with_public_host(monkeypatch):
    captured = {}

    class FakeSigningClient:
        def __init__(self, endpoint, access_key, secret_key, secure):
            captured["endpoint"] = endpoint
            captured["secure"] = secure

        def presigned_get_object(self, bucket_name, object_name, expires):
            captured["bucket_name"] = bucket_name
            captured["object_name"] = object_name
            captured["expires"] = expires
            return f"http://{captured['endpoint']}/{bucket_name}/{object_name}?signed=true"

    monkeypatch.setattr(minio_module, "Minio", FakeSigningClient)
    monkeypatch.setattr(settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150:9000")

    url = minio_module.get_presigned_url_sync("cinescope-media", "episodes/demo.mp4")

    assert captured["endpoint"] == "192.168.68.150:9000"
    assert captured["secure"] is False
    assert url == "http://192.168.68.150:9000/cinescope-media/episodes/demo.mp4?signed=true"
