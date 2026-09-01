from dataclasses import replace

import pytest

from app.adapters import (
    DeterministicDevelopmentAuth,
    FakeClock,
    InMemoryM0Repository,
    InMemoryRateLimiter,
    StreamlitOIDCAuth,
)
from app.application import OperationsService
from app.application.errors import AuthorizationError, RateLimitExceeded
from app.config import Settings
from app.domain import User
from app.ports import AuthenticationRequired
from tests.helpers import build_service, fixture_bytes


def test_oidc_requires_verified_claims_and_maps_a_stable_identity() -> None:
    with pytest.raises(AuthenticationRequired):
        StreamlitOIDCAuth(lambda: {}).current_user()

    claims = {"sub": "google-123", "email": "ADMIN@example.com", "email_verified": True}
    auth = StreamlitOIDCAuth(lambda: claims, admin_emails=frozenset({"admin@example.com"}))
    first = auth.current_user()
    second = auth.current_user()

    assert first.id == second.id
    assert first.email == "admin@example.com"
    assert first.is_admin
    assert first.identity_provider == "google"


def test_persisted_inactive_user_cannot_regain_access() -> None:
    repository = InMemoryM0Repository()
    identity = User("user-1", "person@example.com", "Person")
    repository.save_user(replace(identity, active=False))
    service = build_service(user=identity, repository=repository)

    with pytest.raises(AuthorizationError):
        service.resolve_workspace()


def test_operations_are_server_side_admin_only() -> None:
    repository = InMemoryM0Repository()
    clock = FakeClock()
    regular = User("regular", "regular@example.com", "Regular")
    repository.save_user(regular)
    with pytest.raises(AuthorizationError):
        OperationsService(DeterministicDevelopmentAuth(regular), repository, clock).snapshot()

    admin = User("admin", "admin@example.com", "Admin", is_admin=True)
    repository.save_user(admin)
    snapshot = OperationsService(DeterministicDevelopmentAuth(admin), repository, clock).snapshot()
    assert snapshot.user_count == 2


def test_upload_rate_limit_is_enforced() -> None:
    settings = replace(Settings.from_env(), upload_rate_limit=1)
    service = build_service()
    service.settings = settings
    service.rate_limiter = InMemoryRateLimiter(service.clock)
    project = service.create_project("Rate limited")
    content = fixture_bytes("employee_handbook.txt")

    service.upload_document(project.id, "first.txt", content)
    with pytest.raises(RateLimitExceeded):
        service.upload_document(project.id, "second.txt", content)
