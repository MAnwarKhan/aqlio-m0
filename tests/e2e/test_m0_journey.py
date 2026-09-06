from app.domain import ProjectStatus, PublicationVisibility
from tests.helpers import build_service, fixture_bytes


def test_complete_deterministic_participant_journey() -> None:
    service = build_service()
    user = service.auth.current_user()
    workspace = service.resolve_workspace()
    project = service.create_project("Employee Handbook Assistant")
    asset = service.upload_document(
        project.id, "employee_handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    service.prepare_document(project.id, asset.id)

    grounded = service.ask_question(project.id, "When is annual leave available?", guided=True)
    unsupported = service.ask_question(project.id, "What food is served on Friday?")
    service.confirm_test_success(project.id, grounded.correlation_id)
    service.confirm_readiness(project.id)
    publication = service.deploy(project.id, idempotency_key="journey-deploy")
    private = service.open_private(publication.id)
    receipt = service.enable_link_sharing(publication.id)
    shared = service.open_shared(receipt.token)
    service.revoke_sharing(publication.id)

    assert workspace.owner_user_id == user.id
    assert grounded.citations and not grounded.abstained
    assert unsupported.abstained
    assert service.get_my_project(project.id).status is ProjectStatus.DEPLOYED
    assert private.publication_id == publication.id
    assert shared.visibility is PublicationVisibility.LINK_ONLY
    assert {event.event_type for event in service.repository.lifecycle_events} >= {
        "PROJECT_CREATED",
        "DOCUMENT_UPLOADED",
        "DOCUMENT_PREPARATION_STARTED",
        "DOCUMENT_PREPARED",
        "TEST_CONFIRMED",
        "READINESS_CONFIRMED",
        "PUBLICATION_CREATED",
        "SHARING_ENABLED",
        "SHARING_REVOKED",
    }
