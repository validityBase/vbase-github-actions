"""Minimal S3-compatible object storage client for backup uploads."""

from __future__ import annotations

import hashlib
import hmac
import http.client
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ALGORITHM = "AWS4-HMAC-SHA256"
SERVICE = "s3"


class ObjectStorageClient:
    """Uploads files to one S3-compatible object storage bucket."""

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        endpoint_url: str,
        region: str,
    ) -> None:
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url.rstrip("/")
        self.region = region

    def upload_files(self, uploads: list[tuple[Path, str]]) -> None:
        for local_path, remote_name in uploads:
            self.upload_file(local_path, remote_name)

    def upload_file(
        self,
        local_path: Path,
        remote_name: str,
        payload_hash: str | None = None,
    ) -> None:
        endpoint = urllib.parse.urlsplit(self.endpoint_url)
        if endpoint.scheme not in {"http", "https"} or not endpoint.netloc:
            raise ValueError(
                "OBJECT_STORAGE_ENDPOINT_URL must be an http(s) URL with a host."
            )
        if endpoint.username or endpoint.password:
            raise ValueError("OBJECT_STORAGE_ENDPOINT_URL must not include credentials.")
        if endpoint.path.rstrip("/"):
            raise ValueError("OBJECT_STORAGE_ENDPOINT_URL must not include a path.")
        if endpoint.query or endpoint.fragment:
            raise ValueError(
                "OBJECT_STORAGE_ENDPOINT_URL must not include a query or fragment."
            )

        canonical_uri = self._canonical_uri(remote_name)
        target = self._request_target(endpoint, canonical_uri)
        size = local_path.stat().st_size
        payload_hash = payload_hash or self._sha256_file(local_path)
        request_time = datetime.now(timezone.utc)
        headers = self._signed_headers(
            host=endpoint.netloc,
            canonical_uri=canonical_uri,
            payload_hash=payload_hash,
            request_time=request_time,
        )

        print(
            f"Uploading {local_path} to object storage "
            f"{self.bucket_name}/{remote_name}"
        )
        connection_cls = (
            http.client.HTTPSConnection
            if endpoint.scheme == "https"
            else http.client.HTTPConnection
        )
        connection = connection_cls(endpoint.netloc, timeout=300)
        try:
            connection.putrequest("PUT", target, skip_host=True)
            for name, value in headers.items():
                connection.putheader(name, value)
            connection.putheader("Content-Type", "application/octet-stream")
            connection.putheader("Content-Length", str(size))
            connection.endheaders()

            with local_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    connection.send(chunk)

            response = connection.getresponse()
            response_body = response.read().decode("utf-8", errors="replace")
            if response.status not in {200, 201, 204}:
                raise RuntimeError(
                    f"Object storage upload failed for {remote_name}: "
                    f"HTTP {response.status}: {response_body}"
                )
        finally:
            connection.close()

    def _canonical_uri(self, remote_name: str) -> str:
        key_path = urllib.parse.quote(remote_name, safe="/~")
        bucket = urllib.parse.quote(self.bucket_name, safe="")
        return f"/{bucket}/{key_path}"

    @staticmethod
    def _request_target(
        endpoint: urllib.parse.SplitResult,
        canonical_uri: str,
    ) -> str:
        base_path = endpoint.path.rstrip("/")
        return f"{base_path}{canonical_uri}" if base_path else canonical_uri

    def _signed_headers(
        self,
        *,
        host: str,
        canonical_uri: str,
        payload_hash: str,
        request_time: datetime,
    ) -> dict[str, str]:
        amz_date = request_time.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = request_time.strftime("%Y%m%d")
        credential_scope = f"{date_stamp}/{self.region}/{SERVICE}/aws4_request"
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                "PUT",
                canonical_uri,
                "",
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        string_to_sign = "\n".join(
            [
                ALGORITHM,
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            f"{ALGORITHM} "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        return {
            "Authorization": authorization,
            "Host": host,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
        }

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = self._sign(
            ("AWS4" + self.secret_access_key).encode("utf-8"),
            date_stamp,
        )
        region_key = self._sign(date_key, self.region)
        service_key = self._sign(region_key, SERVICE)
        return self._sign(service_key, "aws4_request")

    @staticmethod
    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
