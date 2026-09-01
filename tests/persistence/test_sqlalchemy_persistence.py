from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
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
    first.ask_question(project.id, "When is annual leave available?", guided=True)
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
    service.improve_application(project.id, "Shorter answers", answer_length="short")
    question = "When is annual leave available?"
    service.ask_question(project.id, question, guided=True)
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
        "policy": "GROUNDED_OR_ABSTAIN",
        "answer_length": "short",
        "improvement_request": "Shorter answers",
    }
    assert restarted.repository.get_publication(publication.id).assistant_config == (
        publication.assistant_config
    )
    before = restarted.ask_shared(receipt.token, question)
    restarted.improve_application(project.id, "Standard answers", answer_length="standard")
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
