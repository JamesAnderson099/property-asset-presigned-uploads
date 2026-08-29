import json

import httpx
import pytest

from infrai_storage import InfraiError, InfraiStorageClient


def test_require_bucket_does_not_create_a_missing_bucket() -> None:
    captured: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            404,
            json={"ok": False, "error": {"code": "NOT_FOUND", "message": "missing"}},
        )

    client = InfraiStorageClient("test-key", transport=httpx.MockTransport(respond))
    with pytest.raises(InfraiError):
        client.require_bucket("property-assets")
    client.close()

    assert [(request.method, request.url.path) for request in captured] == [
        ("GET", "/v1/storage/bucket/get/property-assets")
    ]


def test_presign_put_places_identity_in_path_and_policy_in_body() -> None:
    captured: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"ok": True, "data": {"url": "https://upload.example/signed"}})

    client = InfraiStorageClient("test-key", transport=httpx.MockTransport(respond))
    signed = client.presign_put(
        "property-assets",
        "properties/p-1/maintenance/r-1/leak.jpg",
        content_type="image/jpeg",
        max_bytes=10_000_000,
        expires_seconds=600,
        idempotency_key="maintenance_request:r-1:leak.jpg",
    )
    client.close()

    assert captured[0].method == "POST"
    assert captured[0].url.path == (
        "/v1/storage/object/presign/property-assets/"
        "properties%2Fp-1%2Fmaintenance%2Fr-1%2Fleak.jpg"
    )
    assert json.loads(captured[0].content) == {
        "op": "put",
        "expires_seconds": 600,
        "content_type": "image/jpeg",
        "max_bytes": 10_000_000,
        "idempotency_key": "maintenance_request:r-1:leak.jpg",
    }
    assert signed.method == "PUT"
