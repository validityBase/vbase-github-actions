"""Minimal Backblaze B2 Native API client for backup uploads."""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

B2_API_VERSION = "v4"
AUTH_URL = f"https://api.backblazeb2.com/b2api/{B2_API_VERSION}/b2_authorize_account"


class B2Client:
    """Uploads files to a single Backblaze B2 bucket."""

    def __init__(self, key_id: str, application_key: str, bucket_name: str) -> None:
        self.bucket_name = bucket_name
        auth = self._authorize(key_id, application_key)
        storage_api = auth["apiInfo"]["storageApi"]
        self.api_url = storage_api["apiUrl"]
        self.auth_token = auth["authorizationToken"]
        self.account_id = auth["accountId"]
        self.bucket_id = self._resolve_bucket_id(storage_api)

    def upload_files(self, uploads: list[tuple[Path, str]]) -> None:
        for local_path, remote_name in uploads:
            self.upload_file(local_path, remote_name)

    def upload_file(self, local_path: Path, remote_name: str) -> None:
        upload_auth = self._request_json(
            f"{self.api_url}/b2api/{B2_API_VERSION}/b2_get_upload_url",
            token=self.auth_token,
            body={"bucketId": self.bucket_id},
        )
        upload_url = upload_auth["uploadUrl"]
        upload_token = upload_auth["authorizationToken"]

        parsed = urllib.parse.urlsplit(upload_url)
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        encoded_remote_name = urllib.parse.quote(remote_name, safe="/")
        size = local_path.stat().st_size
        sha1 = self._sha1_file(local_path)

        print(f"Uploading {local_path} to b2://{self.bucket_name}/{remote_name}")
        connection = http.client.HTTPSConnection(parsed.netloc, timeout=300)
        try:
            connection.putrequest("POST", target)
            connection.putheader("Authorization", upload_token)
            connection.putheader("X-Bz-File-Name", encoded_remote_name)
            connection.putheader("Content-Type", "application/octet-stream")
            connection.putheader("Content-Length", str(size))
            connection.putheader("X-Bz-Content-Sha1", sha1)
            connection.endheaders()

            with local_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    connection.send(chunk)

            response = connection.getresponse()
            response_body = response.read().decode("utf-8", errors="replace")
            if response.status != 200:
                print(
                    f"[ERROR] B2 upload failed for {remote_name}: "
                    f"HTTP {response.status}: {response_body}",
                    file=sys.stderr,
                )
                sys.exit(1)
        finally:
            connection.close()

    def _authorize(self, key_id: str, application_key: str) -> dict[str, Any]:
        basic_auth = base64.b64encode(
            f"{key_id}:{application_key}".encode("utf-8")
        ).decode("ascii")
        return self._request_json(AUTH_URL, basic_auth=basic_auth)

    def _resolve_bucket_id(self, storage_api: dict[str, Any]) -> str:
        for bucket in storage_api.get("allowed", {}).get("buckets") or []:
            if bucket.get("name") == self.bucket_name:
                bucket_id = bucket.get("id") or bucket.get("bucketId")
                if bucket_id:
                    return bucket_id
                raise ValueError(
                    f"B2 authorize response did not include an id for bucket: "
                    f"{self.bucket_name}"
                )

        buckets = self._request_json(
            f"{self.api_url}/b2api/{B2_API_VERSION}/b2_list_buckets",
            token=self.auth_token,
            body={"accountId": self.account_id, "bucketName": self.bucket_name},
        ).get("buckets", [])
        if not buckets:
            print(
                f"[ERROR] B2 bucket not found or not accessible: {self.bucket_name}",
                file=sys.stderr,
            )
            sys.exit(1)
        return buckets[0]["bucketId"]

    @staticmethod
    def _request_json(
        url: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        basic_auth: str | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = token
        if basic_auth:
            headers["Authorization"] = f"Basic {basic_auth}"
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            print(
                f"[ERROR] B2 API {url} -> HTTP {exc.code}: {response_body}",
                file=sys.stderr,
            )
            sys.exit(1)
        except urllib.error.URLError as exc:
            print(f"[ERROR] B2 API request failed: {exc.reason}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def _sha1_file(path: Path) -> str:
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
