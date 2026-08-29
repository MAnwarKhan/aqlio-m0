"""Private local and S3-compatible StoragePort implementations."""

from __future__ import annotations

import secrets
from pathlib import Path, PurePosixPath
from typing import Any


class StorageAdapterError(RuntimeError):
    """Normalized private-storage failure without credential details."""


def _new_key(workspace_id: str, project_id: str) -> str:
    return f"{workspace_id}/{project_id}/{secrets.token_hex(24)}"


def _validate_key(workspace_id: str, project_id: str, storage_key: str) -> None:
    path = PurePosixPath(storage_key)
    expected = (workspace_id, project_id)
    if path.is_absolute() or ".." in path.parts or tuple(path.parts[:2]) != expected:
        raise StorageAdapterError("The requested document is not available.")


class LocalPrivateStorage:
    """Development storage rooted in one explicit private directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, *, workspace_id: str, project_id: str, content: bytes) -> str:
        key = _new_key(workspace_id, project_id)
        target = self._target(workspace_id, project_id, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def get(self, *, workspace_id: str, project_id: str, storage_key: str) -> bytes:
        try:
            return self._target(workspace_id, project_id, storage_key).read_bytes()
        except OSError as exc:
            raise StorageAdapterError("The requested document is not available.") from exc

    def delete(self, *, workspace_id: str, project_id: str, storage_key: str) -> None:
        target = self._target(workspace_id, project_id, storage_key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageAdapterError("The document could not be removed safely.") from exc

    def _target(self, workspace_id: str, project_id: str, storage_key: str) -> Path:
        _validate_key(workspace_id, project_id, storage_key)
        target = (self._root / storage_key).resolve()
        if self._root not in target.parents:
            raise StorageAdapterError("The requested document is not available.")
        return target


class S3CompatiblePrivateStorage:
    """Private S3-compatible adapter; the injected client is easy to fake in CI."""

    def __init__(self, client: Any, bucket: str) -> None:
        if not bucket:
            raise ValueError("A private storage bucket is required.")
        self._client = client
        self._bucket = bucket

    def put(self, *, workspace_id: str, project_id: str, content: bytes) -> str:
        key = _new_key(workspace_id, project_id)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content,
                ServerSideEncryption="AES256",
            )
        except Exception as exc:
            raise StorageAdapterError("The document could not be stored safely.") from exc
        return key

    def get(self, *, workspace_id: str, project_id: str, storage_key: str) -> bytes:
        _validate_key(workspace_id, project_id, storage_key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=storage_key)
            return bytes(response["Body"].read())
        except Exception as exc:
            raise StorageAdapterError("The requested document is not available.") from exc

    def delete(self, *, workspace_id: str, project_id: str, storage_key: str) -> None:
        _validate_key(workspace_id, project_id, storage_key)
        try:
            self._client.delete_object(Bucket=self._bucket, Key=storage_key)
        except Exception as exc:
            raise StorageAdapterError("The document could not be removed safely.") from exc
