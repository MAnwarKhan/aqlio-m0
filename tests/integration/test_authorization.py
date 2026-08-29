import pytest

from app.adapters import DeterministicIdFactory, InMemoryM0Repository, InMemoryStorageAdapter
from app.application.errors import AuthorizationError
from app.domain import User
from tests.helpers import build_service, deploy_project, fixture_bytes, prepare_project


def two_users():
    repository = InMemoryM0Repository()
    storage = InMemoryStorageAdapter()
    ids = DeterministicIdFactory()
    user_a = User("user-a", "a@example.com", "User A")
    user_b = User("user-b", "b@example.com", "User B")
    return (
        build_service(user=user_a, repository=repository, storage=storage, ids=ids),
        build_service(user=user_b, repository=repository, storage=storage, ids=ids),
    )


def test_user_cannot_read_upload_retrieve_or_publish_another_project() -> None:
    owner, outsider = two_users()
    project_id, _asset_id = prepare_project(owner)

    with pytest.raises(AuthorizationError):
        outsider.get_my_project(project_id)
    with pytest.raises(AuthorizationError):
        outsider.upload_document(project_id, "benefits.txt", fixture_bytes("benefits_guide.txt"))
    with pytest.raises(AuthorizationError):
        outsider.ask_question(project_id, "When is annual leave available?")
    with pytest.raises(AuthorizationError):
        outsider.deploy(project_id, idempotency_key="outsider")


def test_user_cannot_open_private_or_revoke_another_publication() -> None:
    owner, outsider = two_users()
    _project_id, publication_id = deploy_project(owner)

    with pytest.raises(AuthorizationError):
        outsider.open_private(publication_id)
    with pytest.raises(AuthorizationError):
        outsider.revoke_sharing(publication_id)
