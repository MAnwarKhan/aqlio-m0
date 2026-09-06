from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.domain import (
    ApplicationSpecification,
    ApplicationType,
    ApprovedVersionSnapshot,
    ExportPackage,
    ExportPackageStatus,
    VersionApprovalState,
)


def test_approved_snapshot_and_export_record_are_version_specific_and_immutable() -> None:
    specification = ApplicationSpecification(
        project_id="project-1",
        project_version_id="version-4",
        application_type=ApplicationType.ASK_MY_DOCUMENTS,
        name="Policy helper",
        description="Answers questions from approved policies.",
        behavior_config={"response_style": "balanced"},
        ui_config={"result_layout": "prose"},
        document_asset_ids=("document-1",),
        approval_state=VersionApprovalState.APPROVED,
    )
    snapshot = ApprovedVersionSnapshot(
        id="approval-1",
        owner_user_id="user-1",
        workspace_id="workspace-1",
        specification=specification,
        approved_at=datetime(2026, 9, 5, tzinfo=UTC),
    )
    package = ExportPackage(
        id="export-1",
        approved_snapshot_id=snapshot.id,
        owner_user_id="user-1",
        workspace_id="workspace-1",
        project_id=specification.project_id,
        project_version_id=specification.project_version_id,
        export_version=1,
        status=ExportPackageStatus.REQUESTED,
        storage_key="private-key",
        filename="policy-helper-v4-export-1.zip",
        sha256="0" * 64,
        created_at=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert package.project_version_id == "version-4"
    with pytest.raises(TypeError):
        specification.behavior_config["response_style"] = "detailed"  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        package.status = ExportPackageStatus.READY  # type: ignore[misc]
