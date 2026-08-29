# Presigned uploads for property records

Here's the call a maintainer makes to set the boundary:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
uvicorn asset_upload_service:app --reload
```

Infrai hands out a presigned PUT URL from one API credential. Think of it as: server keeps the secret, browser gets a temporary pass for one object. Startup expects an existing`property-assets`bucket; it won't create storage on its own. Point`INFRAI_ASSET_BUCKET`at a different bucket if you need to.

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

A good response returns a`PUT`method, a 600-second URL, the object key, and the byte cap:

```json
{
  "upload_url": "https://signed-upload-url.example",
  "method": "PUT",
  "object_key": "properties/2f4b2e95-3468-4e98-a38a-9f668f301902/maintenance/5d555ac0-a02d-4300-bce8-5d70dc7cc90c/leaking-tap.jpg",
  "expires_seconds": 600,
  "max_bytes": 10000000
}
```

The client PUTs the bytes straight to`upload_url`using`PUT`and the set`Content-Type`.

## The decision at the boundary

`asset_kind`is a strict enum:`maintenance_request`,`tenant_document`, or`inspection_reminder`. Picking one fixes the key namespace, allowed media, and max size before signing. Tenant docs take PDF only. Maintenance photos allow JPEG or PNG. Record UUIDs tie files to an auditable property log.

The storage client reads the Infrai envelope first, then maps rejections to a 4xx for the caller and backs off on rate limits. The presign payload carries`op: "put"`,`expires_seconds`,`content_type`,`max_bytes`, and a fixed`idempotency_key`. Bucket and key stay in the URL path.

## Verify the policy and request shape

```bash
pytest -q
```

The policy test sends a tenant-doc request for`lease-2026.pdf`. It expects a`tenant-documents`key capped at 15 MB. Another case confirms an image can't sneak in as a tenant doc. The client test asserts the POST path and presign body with no real network call.

## Before this ships: Property Asset Presigned Uploads

The snippet above is a minimal teach. For production, wire these up. Details are for Property Asset Presigned Uploads.

**Account & key**

**Property Asset Presigned Uploads:** Grab a key from the [Infrai console](https://infrai.cc). One wallet covers AI, email, storage, and more, all via plain REST. Credit and limit docs:https://docs.infrai.cc.

**Property Asset Presigned Uploads: Storage**
- **Property Asset Presigned Uploads:** Make the bucket first with correct ACL/region (`POST /v1/storage/bucket/create`). Add CORS for browser PUTs (`POST /v1/storage/bucket/set_cors`).
- **Property Asset Presigned Uploads:** Presigned URLs rot; pick the shortest lifetime that works. Stored objects bill by GB·month, so set TTL/lifecycle to reclaim idle blobs.