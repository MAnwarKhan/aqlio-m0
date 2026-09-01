from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.adapters import LocalPrivateStorage, S3CompatiblePrivateStorage, StorageAdapterError


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def get_object(self, **kwargs):  # type: ignore[no-untyped-def]
        return {"Body": io.BytesIO(self.objects[(kwargs["Bucket"], kwargs["Key"])])}

    def delete_object(self, **kwargs):  # type: ignore[no-untyped-def]
        self.objects.pop((kwargs["Bucket"], kwargs["Key"]), None)


def exercise_storage(storage) -> None:  # type: ignore[no-untyped-def]
    first = storage.put(workspace_id="workspace-a", project_id="project-a", content=b"one")
    second = storage.put(workspace_id="workspace-a", project_id="project-a", content=b"two")
    assert first != second
    assert (
        storage.get(workspace_id="workspace-a", project_id="project-a", storage_key=first) == b"one"
    )
    with pytest.raises(StorageAdapterError):
        storage.get(workspace_id="workspace-a", project_id="project-b", storage_key=first)
    with pytest.raises(StorageAdapterError):
        storage.get(workspace_id="workspace-a", project_id="project-a", storage_key="../escape")
    storage.delete(workspace_id="workspace-a", project_id="project-a", storage_key=first)


def test_local_private_storage(tmp_path: Path) -> None:
    exercise_storage(LocalPrivateStorage(tmp_path))


def test_s3_compatible_private_storage() -> None:
    exercise_storage(S3CompatiblePrivateStorage(FakeS3Client(), "private-bucket"))
