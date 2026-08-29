from __future__ import annotations

import os
from contextlib import asynccontextmanager
from enum import Enum
from typing import Iterator
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from infrai_storage import InfraiError, InfraiStorageClient


class AssetKind(str, Enum):
    MAINTENANCE_REQUEST = "maintenance_request"
    TENANT_DOCUMENT = "tenant_document"
    INSPECTION_REMINDER = "inspection_reminder"


class UploadIntentRequest(BaseModel):
    property_id: UUID
    record_id: UUID
    asset_kind: AssetKind
    filename: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    content_type: str


class UploadIntentResponse(BaseModel):
    upload_url: str
    method: str
    object_key: str
    expires_seconds: int
    max_bytes: int


class UploadPolicy(BaseModel):
    prefix: str
    content_types: frozenset[str]
    max_bytes: int


POLICIES = {
    AssetKind.MAINTENANCE_REQUEST: UploadPolicy(
        prefix="maintenance", content_types=frozenset({"image/jpeg", "image/png"}), max_bytes=10_000_000
    ),
    AssetKind.TENANT_DOCUMENT: UploadPolicy(
        prefix="tenant-documents", content_types=frozenset({"application/pdf"}), max_bytes=15_000_000
    ),
    AssetKind.INSPECTION_REMINDER: UploadPolicy(
        prefix="inspection-reminders",
        content_types=frozenset({"image/jpeg", "image/png", "application/pdf"}),
        max_bytes=8_000_000,
    ),
}

BUCKET = os.environ.get("INFRAI_ASSET_BUCKET", "property-assets")
PRESIGN_TTL_SECONDS = 600


def upload_policy(request: UploadIntentRequest) -> tuple[str, UploadPolicy]:
    policy = POLICIES[request.asset_kind]
    if request.content_type not in policy.content_types:
        raise HTTPException(status_code=422, detail="content type is not allowed for this asset kind")
    object_key = f"properties/{request.property_id}/{policy.prefix}/{request.record_id}/{request.filename}"
    return object_key, policy


def get_storage(request: Request) -> InfraiStorageClient:
    return request.app.state.storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> Iterator[None]:
    storage = InfraiStorageClient.from_environment()
    storage.require_bucket(BUCKET)
    app.state.storage = storage
    try:
        yield
    finally:
        storage.close()


app = FastAPI(title="Property asset upload service", lifespan=lifespan)


@app.post("/upload-intents", response_model=UploadIntentResponse)
def create_upload_intent(
    request: UploadIntentRequest,
    storage: InfraiStorageClient = Depends(get_storage),
) -> UploadIntentResponse:
    object_key, policy = upload_policy(request)
    idempotency_key = f"{request.asset_kind.value}:{request.record_id}:{request.filename}"
    try:
        signed = storage.presign_put(
            BUCKET,
            object_key,
            content_type=request.content_type,
            max_bytes=policy.max_bytes,
            expires_seconds=PRESIGN_TTL_SECONDS,
            idempotency_key=idempotency_key,
        )
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=caller_status, detail=error.detail) from error
    return UploadIntentResponse(
        upload_url=signed.url,
        method=signed.method,
        object_key=object_key,
        expires_seconds=signed.expires_seconds,
        max_bytes=policy.max_bytes,
    )
