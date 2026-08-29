from uuid import UUID

import pytest
from fastapi import HTTPException

from asset_upload_service import AssetKind, UploadIntentRequest, upload_policy


PROPERTY_ID = UUID("2f4b2e95-3468-4e98-a38a-9f668f301902")
RECORD_ID = UUID("5d555ac0-a02d-4300-bce8-5d70dc7cc90c")


def test_tenant_document_gets_private_domain_key_and_pdf_limit() -> None:
    request = UploadIntentRequest(
        property_id=PROPERTY_ID,
        record_id=RECORD_ID,
        asset_kind=AssetKind.TENANT_DOCUMENT,
        filename="lease-2026.pdf",
        content_type="application/pdf",
    )

    key, policy = upload_policy(request)

    assert key == (
        "properties/2f4b2e95-3468-4e98-a38a-9f668f301902/tenant-documents/"
        "5d555ac0-a02d-4300-bce8-5d70dc7cc90c/lease-2026.pdf"
    )
    assert policy.max_bytes == 15_000_000


def test_tenant_document_rejects_image_content() -> None:
    request = UploadIntentRequest(
        property_id=PROPERTY_ID,
        record_id=RECORD_ID,
        asset_kind=AssetKind.TENANT_DOCUMENT,
        filename="lease.png",
        content_type="image/png",
    )

    with pytest.raises(HTTPException) as rejected:
        upload_policy(request)

    assert rejected.value.status_code == 422
