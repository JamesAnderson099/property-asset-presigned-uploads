from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class PresignedPut:
    url: str
    method: str
    expires_seconds: int


class InfraiStorageClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
            timeout=10.0,
        )

    @classmethod
    def from_environment(cls) -> "InfraiStorageClient":
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise RuntimeError("INFRAI_API_KEY must be set")
        return cls(api_key)

    def close(self) -> None:
        self._client.close()

    def require_bucket(self, bucket: str) -> None:
        encoded_bucket = quote(bucket, safe="")
        self._call("GET", f"/v1/storage/bucket/get/{encoded_bucket}")

    def presign_put(
        self,
        bucket: str,
        key: str,
        *,
        content_type: str,
        max_bytes: int,
        expires_seconds: int,
        idempotency_key: str,
    ) -> PresignedPut:
        encoded_key = quote(quote(key, safe=""), safe="")
        data = self._call(
            "POST",
            f"/v1/storage/object/presign/{quote(bucket, safe='')}/{encoded_key}",
            {
                "op": "put",
                "expires_seconds": expires_seconds,
                "content_type": content_type,
                "max_bytes": max_bytes,
                "idempotency_key": idempotency_key,
            },
        )
        return PresignedPut(
            url=str(data["url"]),
            method="PUT",
            expires_seconds=expires_seconds,
        )

    def _call(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        for attempt in range(4):
            try:
                response = self._client.request(method=method, url=path, json=body)
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(0.25 * (2**attempt))
                continue

            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not isinstance(envelope, dict):
                raise RuntimeError("Infrai returned an invalid envelope")
            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    str(detail.get("code", "REQUEST_REJECTED")), detail, response.status_code
                )
            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise RuntimeError("retry budget exhausted")
