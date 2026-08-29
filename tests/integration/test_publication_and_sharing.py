import pytest

from app.application.errors import NotReadyError, ShareAccessError
from app.domain import PublicationVisibility
from tests.helpers import build_service, deploy_project, fixture_bytes


def test_deploy_is_rejected_until_domain_readiness_passes() -> None:
    service = build_service()
    project = service.create_project("Not Ready")

    with pytest.raises(NotReadyError, match="readiness"):
        service.deploy(project.id, idempotency_key="too-early")


def test_publication_is_private_immutable_and_deploy_is_idempotent() -> None:
    service = build_service()
    project_id, publication_id = deploy_project(service)
    publication = service.repository.get_publication(publication_id)
    assert publication is not None

    project = service.get_my_project(project_id)
    project.name = "Changed Draft Name"
    service.repository.save_project(project)
    repeated = service.deploy(project_id, idempotency_key=f"deploy-{project_id}")

    assert repeated.id == publication.id
    assert publication.project_name == "Handbook Assistant"
    assert publication.assistant_config["policy"] == "GROUNDED_OR_ABSTAIN"
    assert (
        service.repository.get_share_link(publication_id).visibility
        is PublicationVisibility.PRIVATE
    )


def test_clean_session_link_access_and_revocation() -> None:
    service = build_service()
    _project_id, publication_id = deploy_project(service)

    with pytest.raises(ShareAccessError):
        service.open_shared("not-a-valid-token")

    receipt = service.enable_link_sharing(publication_id)
    shared = service.open_shared(receipt.token)
    service.revoke_sharing(publication_id)
    service.revoke_sharing(publication_id)

    assert shared.publication_id == publication_id
    assert shared.visibility is PublicationVisibility.LINK_ONLY
    with pytest.raises(ShareAccessError, match="no longer available"):
        service.open_shared(receipt.token)


def test_shared_queries_use_the_immutable_publication_snapshot() -> None:
    service = build_service()
    project_id, publication_id = deploy_project(service)
    receipt = service.enable_link_sharing(publication_id)

    before = service.ask_shared(receipt.token, "When is annual leave available?")
    added = service.upload_document(
        project_id, "benefits_guide.txt", fixture_bytes("benefits_guide.txt")
    )
    service.prepare_document(project_id, added.id)
    after = service.ask_shared(receipt.token, "When is annual leave available?")

    assert before.text == after.text
    assert before.citations == after.citations
    assert all(citation.document_name == "employee_handbook.txt" for citation in after.citations)
