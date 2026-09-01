"""Participant projections of the domain lifecycle; no widget state is authoritative."""

from app.domain import Project, ProjectStatus


def project_status(project: Project) -> str:
    if project.status == ProjectStatus.ARCHIVED:
        return "Archived"
    if project.status == ProjectStatus.DEPLOYED:
        return "Published"
    if project.status == ProjectStatus.READY:
        return "Ready to Publish"
    if (
        project.current_version_id
        and project.metadata.get("run_version_id") == project.current_version_id
    ):
        return "Working"
    if project.prepared_document_count:
        return "Testing"
    if project.valid_document_count:
        return "Building"
    return "Defined" if project.metadata.get("defined") == "true" else "Idea"


def next_step(project: Project) -> str:
    if project.guided_test_count:
        return "run"
    if project.prepared_document_count:
        return "test"
    if project.valid_document_count or project.metadata.get("defined") == "true":
        return "build"
    return "define"
