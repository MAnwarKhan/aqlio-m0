from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.adapters import (
    DeterministicDevelopmentAuth,
    FakeClock,
    FakeEmbeddingAdapter,
    FakeGenerationAdapter,
    LocalPrivateStorage,
    SQLAlchemyM0Repository,
    UUIDIdFactory,
)
from app.application import M0Service
from app.application.eligibility_advisor import AdvisorInput
from app.application.errors import AuthorizationError, ShareAccessError
from app.config import Settings
from app.domain import PublicationVisibility, UsageEvent, User
from app.infrastructure.database import create_database_engine, create_session_factory
from tests.helpers import fixture_bytes


def migrate(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def service_for(database_url: str, storage_root: Path, user: User | None = None) -> M0Service:
    engine = create_database_engine(database_url)
    repository = SQLAlchemyM0Repository(create_session_factory(engine))
    return M0Service(
        settings=Settings.from_env(),
        auth=DeterministicDevelopmentAuth(user),
        clock=FakeClock(),
        ids=UUIDIdFactory(),
        generation=FakeGenerationAdapter(),
        embedding=FakeEmbeddingAdapter(),
        repository=repository,
        storage=LocalPrivateStorage(storage_root),
    )


def test_migration_and_complete_state_survive_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'aqlio.db'}"
    storage_root = tmp_path / "private"
    migrate(database_url, monkeypatch)
    first = service_for(database_url, storage_root)
    workspace = first.resolve_workspace()
    project = first.create_project("Durable Handbook")
    asset = first.upload_document(
        project.id, "employee_handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    first.prepare_document(project.id, asset.id)
    answer = first.ask_question(project.id, "When is annual leave available?", guided=True)
    first.confirm_test_success(project.id, answer.correlation_id)
    first.confirm_readiness(project.id)
    publication = first.deploy(project.id, idempotency_key="durable-deploy")
    receipt = first.enable_link_sharing(publication.id)
    first.repository.set_daily_allowance(first.auth.current_user().id, 7, first.clock.now())
    first.repository.save_usage(
        UsageEvent(
            "managed-usage",
            first.auth.current_user().id,
            workspace.id,
            project.id,
            "TEST_ASSISTANT",
            "openai",
            "configured-model",
            first.clock.now(),
            "FAILED",
            11,
            0.002,
            "managed-correlation",
            output_units=3,
            latency_ms=50,
            retry_count=2,
            error_category="TIMEOUT",
        )
    )

    restarted = service_for(database_url, storage_root)

    assert restarted.resolve_workspace().id == workspace.id
    assert restarted.get_my_project(project.id).current_version_id is not None
    assert restarted.list_documents(project.id)[0].normalized_text
    assert restarted.repository.get_daily_allowance(restarted.auth.current_user().id) == 7
    assert restarted.repository.list_usage_events()
    managed = next(
        event for event in restarted.repository.list_usage_events() if event.id == "managed-usage"
    )
    assert (managed.output_units, managed.retry_count, managed.error_category) == (
        3,
        2,
        "TIMEOUT",
    )
    assert restarted.repository.list_lifecycle_events()
    assert restarted.repository.list_audit_events()
    assert restarted.open_private(publication.id).project_name == "Durable Handbook"
    assert restarted.open_shared(receipt.token).visibility is PublicationVisibility.LINK_ONLY

    restarted.revoke_sharing(publication.id)
    after_revoke = service_for(database_url, storage_root)
    with pytest.raises(ShareAccessError):
        after_revoke.open_shared(receipt.token)


def test_unique_identity_transaction_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'rollback.db'}"
    migrate(database_url, monkeypatch)
    repository = SQLAlchemyM0Repository(
        create_session_factory(create_database_engine(database_url))
    )

    with pytest.raises(IntegrityError), repository.transaction():
        repository.save_user(User("one", "same@example.com", "One"))
        repository.save_user(User("two", "same@example.com", "Two"))

    assert repository.list_users() == []


def test_sqlalchemy_repository_preserves_horizontal_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'isolation.db'}"
    storage_root = tmp_path / "private"
    migrate(database_url, monkeypatch)
    owner = service_for(database_url, storage_root, User("owner", "owner@example.com", "Owner"))
    outsider = service_for(
        database_url, storage_root, User("outsider", "outsider@example.com", "Outsider")
    )
    project = owner.create_project("Private project")
    asset = owner.upload_document(
        project.id, "employee_handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    owner.prepare_document(project.id, asset.id)

    with pytest.raises(AuthorizationError):
        outsider.get_my_project(project.id)
    with pytest.raises(AuthorizationError):
        outsider.list_documents(project.id)
    with pytest.raises(AuthorizationError):
        outsider.ask_question(project.id, "When is leave available?")
    with pytest.raises(AuthorizationError):
        outsider.deploy(project.id, idempotency_key="outsider")


def test_journey_and_version_configuration_survive_restart(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'journey.db'}"
    root = tmp_path / "private"
    migrate(url, monkeypatch)
    service = service_for(url, root)
    project = service.create_idea("Help employees understand policies")
    service.update_definition(
        project.id,
        {
            "problem": "Hard to find answers",
            "users": "Employees",
            "outcome": "Clear answers",
            "ai_role": "Explain documents",
            "information": "Handbooks",
        },
    )
    service.define_solution(project.id)
    service.evaluate_idea(project.id)
    service.add_and_prepare_document(
        project.id, "handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    service.apply_improvement(project.id, "Use direct wording", response_style="concise")
    question = "When is annual leave available?"
    answer = service.ask_question(project.id, question, guided=True)
    service.confirm_test_success(project.id, answer.correlation_id)
    approved = service.approve_working_version(project.id)
    exported = service.generate_application_export(project.id)
    exported_bytes = service.download_application_export(exported.id).content
    service.run_application(project.id, question)
    publication = service.publish_working_application(project.id)
    receipt = service.enable_link_sharing(publication.id)
    restarted = service_for(url, root)
    loaded = restarted.get_my_project(project.id)
    assert loaded.metadata["problem"] == "Hard to find answers"
    assert loaded.metadata["defined"] == "true"
    assert "Problem:" in loaded.metadata["idea_evaluation"]
    assert loaded.metadata["run_version_id"] == loaded.current_version_id
    assert loaded.metadata["publication_id"] == publication.id
    assert restarted.repository.get_version(loaded.current_version_id).assistant_config == {
        "template": "ASK_MY_DOCUMENTS",
        "behavioral_schema": "ask-my-documents.behavior.v1",
        "policy": "GROUNDED_OR_ABSTAIN",
        "spec_problem": "Hard to find answers",
        "spec_users": "Employees",
        "spec_outcome": "Clear answers",
        "response_style": "concise",
        "response_guidance": "Use direct wording",
        "improvement_request": "Use direct wording",
    }
    assert restarted.repository.get_publication(publication.id).assistant_config == (
        publication.assistant_config
    )
    assert restarted.get_approved_version(approved.id) == approved
    assert restarted.repository.get_export_package(exported.id) == exported
    assert restarted.download_application_export(exported.id).content == exported_bytes
    before = restarted.ask_shared(receipt.token, question)
    restarted.apply_improvement(project.id, "Use explanatory wording", response_style="balanced")
    assert restarted.ask_shared(receipt.token, question).text == before.text


def test_journey_migration_upgrades_existing_rows(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    migrate(url, monkeypatch)
    service = service_for(url, tmp_path / "private")
    project = service.create_project("Existing project")
    # Simulate the previous schema with real rows, then apply the additive migration.
    config = Config("alembic.ini")
    command.downgrade(config, "20260829_0002")
    command.upgrade(config, "head")
    loaded = service_for(url, tmp_path / "private").get_my_project(project.id)
    assert loaded.name == "Existing project"
    assert loaded.metadata == {"template": "ASK_MY_DOCUMENTS"}


def test_advisor_approval_and_validation_evidence_survive_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'advisor.db'}"
    root = tmp_path / "private"
    migrate(url, monkeypatch)
    first = service_for(url, root)
    project = first.create_advisor_project(
        name="Durable Synthetic Advisor",
        problem="Synthetic requirements are hard to compare.",
        users="People testing fictional admission scenarios.",
        outcome="Transparent deterministic results and next actions.",
    )
    first.build_advisor_working_version(project.id)
    first.evaluate_working_version(project.id)
    first.test_advisor(
        project.id,
        AdvisorInput(3.0, ("Algebra", "Academic Writing"), "Computing Foundations"),
    )
    first.confirm_advisor_test_success(project.id)
    approved = first.approve_working_version(project.id)
    assert approved.participant_validation is not None

    restarted = service_for(url, root)
    reconstructed = restarted.get_approved_version(approved.id)
    assert reconstructed == approved
    assert reconstructed.specification.behavioral_specification == (
        approved.specification.behavioral_specification
    )
    assert reconstructed.specification.evaluation_report == (
        approved.specification.evaluation_report
    )
    assert reconstructed.participant_validation == approved.participant_validation
    assert reconstructed.specification.application_type.value == (
        "ELIGIBILITY_RECOMMENDATION_ADVISOR"
    )

    restarted.apply_advisor_improvement(
        project.id,
        "Use a supportive recommendation style.",
        title="Changed Working Advisor",
        recommendation_style="supportive",
    )
    after_change = service_for(url, root).get_approved_version(approved.id)
    assert after_change == reconstructed
    assert after_change.specification.name == "Durable Synthetic Advisor"
    outsider = service_for(
        url, root, User("advisor-outsider", "advisor-outsider@example.com", "Outsider")
    )
    with pytest.raises(AuthorizationError):
        outsider.get_approved_version(approved.id)


def test_approved_reconstruction_fails_closed_for_unknown_or_mismatched_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'fail-closed.db'}"
    root = tmp_path / "private"
    migrate(url, monkeypatch)
    service = service_for(url, root)
    project = service.create_advisor_project(
        name="Schema Test Advisor",
        problem="Test schema dispatch.",
        users="Architecture testers.",
        outcome="Safe reconstruction.",
    )
    service.build_advisor_working_version(project.id)
    service.test_advisor(
        project.id,
        AdvisorInput(3.0, ("Algebra", "Academic Writing"), "Computing Foundations"),
    )
    service.confirm_advisor_test_success(project.id)
    approved = service.approve_working_version(project.id)
    engine = create_database_engine(url)

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE approved_versions SET behavioral_specification = "
                "json_set(behavioral_specification, '$.schema_version', :schema) WHERE id = :id"
            ),
            {"schema": "unknown.behavior.v99", "id": approved.id},
        )
    with pytest.raises(ValueError, match="Unsupported Behavioral Specification schema"):
        service_for(url, root).get_approved_version(approved.id)

    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE approved_versions SET behavioral_specification = "
                "json_set(behavioral_specification, '$.schema_version', :schema) WHERE id = :id"
            ),
            {"schema": "ask-my-documents.behavior.v1", "id": approved.id},
        )
    with pytest.raises(ValueError, match="does not match the persisted application type"):
        service_for(url, root).get_approved_version(approved.id)

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE approved_versions SET application_type = :kind WHERE id = :id"),
            {"kind": "UNKNOWN_APPLICATION", "id": approved.id},
        )
    with pytest.raises(ValueError, match="UNKNOWN_APPLICATION"):
        service_for(url, root).get_approved_version(approved.id)


def test_legacy_approval_without_snapshotted_validation_remains_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'legacy-approval.db'}"
    root = tmp_path / "private"
    migrate(url, monkeypatch)
    service = service_for(url, root)
    project = service.create_project("Legacy Approval")
    asset = service.upload_document(
        project.id, "employee_handbook.txt", fixture_bytes("employee_handbook.txt")
    )
    service.prepare_document(project.id, asset.id)
    answer = service.ask_question(project.id, "When is annual leave available?", guided=True)
    service.confirm_test_success(project.id, answer.correlation_id)
    approved = service.approve_working_version(project.id)

    with create_database_engine(url).begin() as connection:
        connection.execute(
            text("UPDATE approved_versions SET participant_validation = NULL WHERE id = :id"),
            {"id": approved.id},
        )
    reconstructed = service_for(url, root).get_approved_version(approved.id)
    assert reconstructed.specification == approved.specification
    assert reconstructed.approved_at == approved.approved_at
    assert reconstructed.participant_validation is None
