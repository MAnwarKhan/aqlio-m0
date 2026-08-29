"""Core Aqlio M0 domain records without framework dependencies."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    DOCUMENTS_ADDED = "DOCUMENTS_ADDED"
    PREPARED = "PREPARED"
    TESTED = "TESTED"
    READY = "READY"
    DEPLOYED = "DEPLOYED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    display_name: str
    active: bool = True


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    owner_user_id: str
    name: str


@dataclass(slots=True)
class Project:
    id: str
    workspace_id: str
    owner_user_id: str
    name: str
    status: ProjectStatus = ProjectStatus.DRAFT
    valid_document_count: int = 0
    prepared_document_count: int = 0
    guided_test_count: int = 0
    has_blocking_preparation_error: bool = False
    readiness_confirmed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)
