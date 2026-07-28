"""Upload backup artifacts with AWS CLI against an S3-compatible endpoint."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path


class ObjectStorageUploader:
    """Small adapter around `aws s3 cp` with provider-neutral inputs."""

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
        self.endpoint_url = self._validate_endpoint_url(endpoint_url)
        self.region = region

        if not bucket_name or "/" in bucket_name:
            raise ValueError("OBJECT_STORAGE_BUCKET_NAME must be a bucket name.")
        if not region:
            raise ValueError("OBJECT_STORAGE_REGION is required.")

    def upload_file(self, local_path: Path, remote_name: str) -> None:
        remote_name = remote_name.strip("/")
        if not remote_name:
            raise ValueError("Object storage remote name must not be empty.")
        if not local_path.is_file():
            raise ValueError(f"Backup artifact does not exist: {local_path}")

        self._ensure_aws_cli()

        target = f"s3://{self.bucket_name}/{remote_name}"
        print(
            f"Uploading {local_path} to object storage "
            f"{self.bucket_name}/{remote_name}"
        )
        self._run_aws(
            "s3",
            "cp",
            str(local_path),
            target,
            "--endpoint-url",
            self.endpoint_url,
            "--region",
            self.region,
            "--only-show-errors",
        )

    @staticmethod
    def _validate_endpoint_url(endpoint_url: str) -> str:
        normalized_url = endpoint_url.rstrip("/")
        endpoint = urllib.parse.urlsplit(normalized_url)
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
        return normalized_url

    @staticmethod
    def _ensure_aws_cli() -> None:
        if shutil.which("aws"):
            return
        raise RuntimeError(
            "AWS CLI is required for S3-compatible backup uploads. "
            "GitHub-hosted ubuntu runners include it; self-hosted runners must "
            "install it before using repo-backup."
        )

    def _run_aws(self, *args: str) -> None:
        env = os.environ.copy()
        env.update(
            {
                "AWS_ACCESS_KEY_ID": self.access_key_id,
                "AWS_SECRET_ACCESS_KEY": self.secret_access_key,
                "AWS_DEFAULT_REGION": self.region,
                "AWS_EC2_METADATA_DISABLED": "true",
                "AWS_REQUEST_CHECKSUM_CALCULATION": "when_required",
                "AWS_RESPONSE_CHECKSUM_VALIDATION": "when_required",
            }
        )
        env.pop("AWS_SESSION_TOKEN", None)
        env.pop("AWS_SECURITY_TOKEN", None)
        try:
            completed = subprocess.run(
                ["aws", *args],
                check=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            output = self._redact_output((exc.stdout or "").strip())
            if output:
                print(output)
            raise

        output = self._redact_output(completed.stdout.strip())
        if output:
            print(output)

    def _redact_output(self, text: str) -> str:
        text = text.replace(self.access_key_id, "***")
        text = text.replace(self.secret_access_key, "***")
        return re.sub(r"(https?)://[^/@\s]+@", r"\1://***@", text)
