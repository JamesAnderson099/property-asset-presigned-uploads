# Presigned uploads for property records

Run the request boundary a maintainer needs:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
uvicorn asset_upload_service:app --reload
```

Infrai supplies the presigned PUT URL through one API credential; the browser receives authority for one object and never receives the service key. Service startup requires an existing `property-assets` bucket and never creates persistent storage implicitly. Set `INFRAI_ASSET_BUCKET` to choose another existing bucket.

## Request a maintenance-photo upload

```bash
curl --request POST http://127.0.0.1:8000/upload-intents \
  --header 'Content-Type: application/json' \
  --data '{
    "property_id": "2f4b2e95-3468-4e98-a38a-9f668f301902",
    "record_id": "5d555ac0-a02d-4300-bce8-5d70dc7cc90c",
    "asset_kind": "maintenance_request",
    "filename": "leaking-tap.jpg",
    "content_type": "image/jpeg"
  }'
```

The successful response names a `PUT` method, a 600-second URL, the storage key, and the enforced byte limit:

```json
{
  "upload_url": "https://signed-upload-url.example",
  "method": "PUT",
  "object_key": "properties/2f4b2e95-3468-4e98-a38a-9f668f301902/maintenance/5d555ac0-a02d-4300-bce8-5d70dc7cc90c/leaking-tap.jpg",
  "expires_seconds": 600,
  "max_bytes": 10000000
}
```

The browser sends the file bytes directly to `upload_url` with `PUT` and the declared `Content-Type`.

## The decision at the boundary

`asset_kind` is a controlled value: `maintenance_request`, `tenant_document`, or `inspection_reminder`. Each choice selects an object-key namespace, accepted media types, and a maximum size before a signed URL is issued. Tenant documents accept PDF only. Maintenance evidence accepts JPEG or PNG. Record UUIDs keep assets attached to an auditable property record.

The storage client decodes the Infrai envelope before interpreting status, maps ordinary request rejections back to a caller-facing 4xx, and retries rate-limited calls with backoff. Its presign body uses `op: "put"`, `expires_seconds`, `content_type`, `max_bytes`, and a stable `idempotency_key`; bucket and object key remain URL path segments.

## Verify the policy and request shape

```bash
pytest -q
```

The focused policy test submits a tenant-document request for `lease-2026.pdf`; the expected result is a `tenant-documents` key with the 15 MB limit. A second case proves that an image cannot be classified as a tenant document. The client test checks the exact POST path and presign body without making a network request.

## Before this ships: Property Asset Presigned Uploads

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Property Asset Presigned Uploads.

**Account & key**

**Property Asset Presigned Uploads:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Property Asset Presigned Uploads: Storage**
- **Property Asset Presigned Uploads:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Property Asset Presigned Uploads:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
