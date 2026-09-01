"""Explicit lifecycle and readiness rules."""

from dataclasses import dataclass

from app.domain.models import Project, ProjectStatus


class InvalidTransition(ValueError):
    """Raised when a project lifecycle transition violates domain rules."""


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    ready: bool
    missing: tuple[str, ...]


_ALLOWED_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    ProjectStatus.DRAFT: frozenset({ProjectStatus.DOCUMENTS_ADDED, ProjectStatus.ARCHIVED}),
    ProjectStatus.DOCUMENTS_ADDED: frozenset({ProjectStatus.PREPARED, ProjectStatus.ARCHIVED}),
    ProjectStatus.PREPARED: frozenset(
        {ProjectStatus.DOCUMENTS_ADDED, ProjectStatus.TESTED, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.TESTED: frozenset(
        {ProjectStatus.PREPARED, ProjectStatus.READY, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.READY: frozenset(
        {
            ProjectStatus.TESTED,
            ProjectStatus.PREPARED,
            ProjectStatus.DEPLOYED,
            ProjectStatus.ARCHIVED,
        }
    ),
    ProjectStatus.DEPLOYED: frozenset({ProjectStatus.PREPARED, ProjectStatus.ARCHIVED}),
    ProjectStatus.ARCHIVED: frozenset({ProjectStatus.DRAFT}),
}


def assess_readiness(project: Project) -> ReadinessResult:
    missing: list[str] = []
    if project.valid_document_count < 1:
        missing.append("Add at least one valid document.")
    if project.prepared_document_count < 1:
        missing.append("Wait for at least one document to finish preparing.")
    if project.guided_test_count < 1:
        missing.append("Complete at least one guided test.")
    if project.has_blocking_preparation_error:
        missing.append("Resolve the document preparation issue.")
    if not project.readiness_confirmed:
        missing.append("Confirm that the application is ready to publish.")
    return ReadinessResult(ready=not missing, missing=tuple(missing))


def transition_project(project: Project, target: ProjectStatus) -> None:
    if target == project.status:
        return
    if target not in _ALLOWED_TRANSITIONS[project.status]:
        raise InvalidTransition(f"Cannot move project from {project.status} to {target}.")
    if target == ProjectStatus.READY and not assess_readiness(project).ready:
        raise InvalidTransition("Project is not ready to publish.")
    project.status = target
