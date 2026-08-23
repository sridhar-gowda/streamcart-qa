"""Artifact stores — where screenshots, page sources and logs go.

The local store is the default and is what CI uploads as a job artifact. Remote
stores exist for retention beyond the CI provider's limits and for linking
evidence from the TMS; they are pluggable so a team can add its own object
store or artifact repository without touching the framework.

Keys follow one scheme everywhere: ``<nodeid-safe>/<file>`` inside a run,
prefixed with ``<team>/<env>/<platform>/<run-id>/`` on shared remote storage so
any artifact is findable by who ran it, against what, where, and when.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from streamcart.core.config import Settings
from streamcart.core.errors import ConfigurationError


class ArtifactStore(Protocol):
    name: str

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Store ``data`` under ``key`` and return where it can be reached (path or URL)."""
        ...


class LocalArtifactStore:
    """Files under the run directory; returns paths relative to it (so the HTML report links work)."""

    name = "local"

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.relative_to(self.root).as_posix()


class S3ArtifactStore:
    """Amazon S3 / MinIO. **Stub**: the upload call is real, the client import is lazy."""

    name = "s3"

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigurationError("artifacts.store=s3 needs boto3: pip install boto3") from exc
        full_key = f"{self.prefix}/{key}" if self.prefix else key
        boto3.client("s3").put_object(Bucket=self.bucket, Key=full_key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{full_key}"


class AzureBlobArtifactStore:
    """Azure Blob Storage. **Stub**: uses ``DefaultAzureCredential`` when the SDK is present."""

    name = "azure"

    def __init__(self, container: str, account_url: str | None = None) -> None:
        self.container = container
        self.account_url = account_url

    def put(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]
            from azure.storage.blob import BlobServiceClient, ContentSettings  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ConfigurationError("artifacts.store=azure needs azure-storage-blob and azure-identity") from exc
        if not self.account_url:
            raise ConfigurationError("artifacts.azure account_url is not configured")
        client = BlobServiceClient(self.account_url, credential=DefaultAzureCredential())
        blob = client.get_blob_client(container=self.container, blob=key)
        blob.upload_blob(data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
        return str(blob.url)


def remote_prefix(settings: Settings) -> str:
    return f"{settings.team}/{settings.env}/{settings.platform.name}/{settings.run_id}"


def artifact_store_for(settings: Settings, run_dir: Path) -> ArtifactStore:
    kind = settings.artifacts.store
    if kind == "local":
        return LocalArtifactStore(run_dir / "artifacts")
    if kind == "s3":
        if not settings.artifacts.s3_bucket:
            raise ConfigurationError("artifacts.store=s3 needs artifacts.s3_bucket")
        return S3ArtifactStore(
            settings.artifacts.s3_bucket, f"{settings.artifacts.s3_prefix}/{remote_prefix(settings)}"
        )
    if kind == "azure":
        if not settings.artifacts.azure_container:
            raise ConfigurationError("artifacts.store=azure needs artifacts.azure_container")
        return AzureBlobArtifactStore(settings.artifacts.azure_container)
    raise ConfigurationError(f"Unknown artifact store '{kind}'")
