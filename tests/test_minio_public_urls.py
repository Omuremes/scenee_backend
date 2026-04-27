from app.core import minio as minio_module


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
