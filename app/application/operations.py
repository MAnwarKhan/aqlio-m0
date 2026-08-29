"""Minimal protected operational queries for the M0 pilot."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.errors import AuthorizationError, ValidationError
from app.ports import AuthPort, ClockPort, M0RepositoryPort


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    user_count: int
    project_count: int
    failed_preparation_count: int
    usage_event_count: int
    failed_ai_run_count: int
    shared_count: int
    revoked_count: int
    provider_status: str


class OperationsService:
    def __init__(self, auth: AuthPort, repository: M0RepositoryPort, clock: ClockPort) -> None:
        self._auth = auth
        self._repository = repository
        self._clock = clock

    def snapshot(self) -> OperationsSnapshot:
        self._require_admin()
        usage = self._repository.list_usage_events()
        links = self._repository.list_share_links()
        return OperationsSnapshot(
            user_count=len(self._repository.list_users()),
            project_count=len(self._repository.list_all_projects()),
            failed_preparation_count=len(self._repository.list_failed_assets()),
            usage_event_count=len(usage),
            failed_ai_run_count=sum(event.status == "FAILED" for event in usage),
            shared_count=sum(link.visibility.value == "LINK_ONLY" for link in links),
            revoked_count=sum(link.visibility.value == "REVOKED" for link in links),
            provider_status="Deterministic mode",
        )

    def set_allowance(self, user_id: str, daily_limit: int) -> None:
        self._require_admin()
        if daily_limit <= 0:
            raise ValidationError("Allowance must be greater than zero.")
        with self._repository.transaction():
            if self._repository.get_user(user_id) is None:
                raise ValidationError("User was not found.")
            self._repository.set_daily_allowance(user_id, daily_limit, self._clock.now())

    def _require_admin(self) -> None:
        identity = self._auth.current_user()
        user = self._repository.get_user(identity.id)
        if user is None or not user.active or not user.is_admin:
            raise AuthorizationError("You do not have permission to view operations.")
