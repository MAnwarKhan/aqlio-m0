import io
import json
import zipfile

import pytest

from app.adapters import DeterministicIdFactory
from app.application.errors import AuthorizationError, NotReadyError
from app.domain import User
from tests.helpers import build_service, prepare_project


def approve_current(service, project_id: str):
    answer = service.ask_question(project_id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project_id, answer.correlation_id)
    return service.approve_working_version(project_id)


def package_files(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_unapproved_working_version_cannot_be_exported() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)

    with pytest.raises(NotReadyError, match="Approve the current"):
        service.generate_application_export(project_id)


def test_export_matches_exact_approved_version_and_excludes_private_or_platform_data() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    service.apply_ui_improvement(
        project_id,
        "Use a table and compact source display.",
        title="Approved Policy Helper",
        instructions="Ask a policy question.",
        question_position="top",
        response_layout="table",
        citation_presentation="compact",
        display_density="detailed",
    )
    approved = approve_current(service, project_id)
    package = service.generate_application_export(project_id)
    files = package_files(service.download_application_export(package.id).content)
    manifest = json.loads(files["AQLIO_EXPORT_MANIFEST.json"])
    config = json.loads(files["application_config.json"])
    combined = b"\n".join(files.values())

    assert package.approved_snapshot_id == approved.id
    assert package.project_version_id == approved.specification.project_version_id
    assert manifest["Approved Version"] == approved.id
    assert manifest["Project Version"] == approved.specification.project_version_id
    assert config["title"] == "Approved Policy Helper"
    assert config["instructions"] == "Ask a policy question."
    assert config["ui"]["response_layout"] == "table"
    assert config["ui"]["citation_presentation"] == "compact"
    assert "document_asset_ids" not in config
    assert approved.specification.document_asset_ids[0].encode() not in combined
    assert b"app.application" not in combined
    assert b"OperationsService" not in combined
    assert set(files) == {
        ".env.example",
        ".python-version",
        "AQLIO_EXPORT_MANIFEST.json",
        "README.md",
        "app.py",
        "application_config.json",
        "deployment/RAILWAY.md",
        "railpack.json",
        "requirements.txt",
        "requirements-test.txt",
        "runtime.py",
        "tests/test_package.py",
    }
    env = files[".env.example"].decode()
    assert "OPENAI_API_KEY=\n" in env
    assert "DATABASE_URL" not in env
    assert "source documents" in str(manifest["Excluded Private Data"])
    assert files[".python-version"] == b"3.12\n"
    railpack = json.loads(files["railpack.json"])
    assert railpack["deploy"]["startCommand"].endswith("--server.port $PORT")
    guide = files["deployment/RAILWAY.md"].decode()
    assert "APPLICATION_AI_MODE=fake" in guide
    assert "`/_stcore/health`" in guide
    assert "do not survive a restart" in guide
    assert "three short questions" in guide
    runtime = files["runtime.py"].decode()
    assert "Retrieval evidence is not itself the answer" in runtime
    assert "deterministic_answer(question, evidence)" in runtime
    assert "This .txt file contains RTF formatting" in runtime
    assert "cited_evidence_ids" in runtime
    assert "invalid grounded response" in runtime


def test_existing_export_is_immutable_and_new_approval_creates_separate_export() -> None:
    service = build_service()
    project_id, _ = prepare_project(service)
    first_approval = approve_current(service, project_id)
    first = service.generate_application_export(project_id)
    first_bytes = service.download_application_export(first.id).content

    service.apply_improvement(project_id, "Give more detailed answers", response_style="detailed")
    with pytest.raises(NotReadyError):
        service.generate_application_export(project_id)
    second_approval = approve_current(service, project_id)
    second = service.generate_application_export(project_id)

    assert first.id != second.id
    assert first.approved_snapshot_id == first_approval.id
    assert second.approved_snapshot_id == second_approval.id
    assert first.export_version == 1 and second.export_version == 2
    assert service.download_application_export(first.id).content == first_bytes


def test_export_download_enforces_owner_and_excludes_other_user_content() -> None:
    owner = build_service()
    project_id, _ = prepare_project(owner)
    approve_current(owner, project_id)
    package = owner.generate_application_export(project_id)
    other = build_service(
        user=User("other-user", "other@example.com", "Other"),
        repository=owner.repository,
        storage=owner.storage,  # type: ignore[arg-type]
        ids=DeterministicIdFactory("other"),
    )
    other_project = other.create_project("OTHER_USER_PRIVATE_MARKER")
    other.add_and_prepare_document(
        other_project.id, "other-private.txt", b"OTHER_USER_SECRET_CONTENT"
    )

    with pytest.raises(AuthorizationError):
        other.download_application_export(package.id)
    content = owner.download_application_export(package.id).content
    assert b"OTHER_USER_PRIVATE_MARKER" not in content
    assert b"OTHER_USER_SECRET_CONTENT" not in content
