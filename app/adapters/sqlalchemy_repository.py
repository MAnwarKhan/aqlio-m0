"""SQLAlchemy implementation of the Phase 2 repository contract."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.domain import (
    Asset,
    AssetStatus,
    AuditEvent,
    DocumentChunk,
    GuidedTest,
    LifecycleEvent,
    Project,
    ProjectStatus,
    ProjectVersion,
    Publication,
    PublicationVisibility,
    PublishedChunk,
    ShareLink,
    UsageEvent,
    User,
    Workspace,
    WorkspaceMember,
)
from app.infrastructure.db_models import (
    AssetRow,
    AuditEventRow,
    DocumentChunkRow,
    GuidedTestRow,
    LifecycleEventRow,
    ProjectRow,
    ProjectVersionAssetRow,
    ProjectVersionRow,
    PublicationAssetRow,
    PublicationChunkRow,
    PublicationRow,
    ShareLinkRow,
    UsageAllowanceRow,
    UsageEventRow,
    UserRow,
    WorkspaceMemberRow,
    WorkspaceRow,
)


class SQLAlchemyM0Repository:
    """Durable repository with optional multi-method application transactions."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory
        self._active: ContextVar[Session | None] = ContextVar("aqlio_session", default=None)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._active.get() is not None:
            yield
            return
        with self._factory() as session:
            token = self._active.set(session)
            try:
                with session.begin():
                    yield
            finally:
                self._active.reset(token)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        active = self._active.get()
        if active is not None:
            yield active
            return
        with self._factory() as session:
            yield session

    def _finish(self, session: Session) -> None:
        if self._active.get() is None:
            session.commit()
        else:
            session.flush()

    def save_user(self, user: User) -> None:
        with self._session() as session:
            existing = session.get(UserRow, user.id)
            now = datetime.now(UTC)
            if existing:
                existing.email = user.email
                existing.display_name = user.display_name
                existing.identity_provider = user.identity_provider
                existing.identity_subject = user.identity_subject
                existing.is_admin = existing.is_admin or user.is_admin
                existing.updated_at = now
            else:
                session.add(
                    UserRow(
                        id=user.id,
                        email=user.email,
                        display_name=user.display_name,
                        active=user.active,
                        is_admin=user.is_admin,
                        identity_provider=user.identity_provider,
                        identity_subject=user.identity_subject,
                        created_at=now,
                        updated_at=now,
                    )
                )
            self._finish(session)

    def get_user(self, user_id: str) -> User | None:
        with self._session() as session:
            row = session.get(UserRow, user_id)
            return self._user(row) if row else None

    def get_workspace_for_user(self, user_id: str) -> Workspace | None:
        with self._session() as session:
            row = session.execute(
                select(WorkspaceRow)
                .join(WorkspaceMemberRow, WorkspaceMemberRow.workspace_id == WorkspaceRow.id)
                .where(WorkspaceMemberRow.user_id == user_id)
            ).scalar_one_or_none()
            return Workspace(row.id, row.owner_user_id, row.name) if row else None

    def save_workspace(self, workspace: Workspace, member: WorkspaceMember) -> None:
        with self._session() as session:
            if session.get(WorkspaceRow, workspace.id) is None:
                session.add(
                    WorkspaceRow(
                        id=workspace.id,
                        owner_user_id=workspace.owner_user_id,
                        name=workspace.name,
                        created_at=datetime.now(UTC),
                    )
                )
            session.merge(
                WorkspaceMemberRow(
                    workspace_id=member.workspace_id,
                    user_id=member.user_id,
                    role=member.role.value,
                    created_at=datetime.now(UTC),
                )
            )
            self._finish(session)

    def is_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        with self._session() as session:
            return session.get(WorkspaceMemberRow, (workspace_id, user_id)) is not None

    def save_project(self, project: Project) -> None:
        with self._session() as session:
            session.merge(
                ProjectRow(
                    id=project.id,
                    workspace_id=project.workspace_id,
                    owner_user_id=project.owner_user_id,
                    name=project.name,
                    description=project.description,
                    journey_metadata=dict(project.metadata),
                    status=project.status.value,
                    valid_document_count=project.valid_document_count,
                    prepared_document_count=project.prepared_document_count,
                    guided_test_count=project.guided_test_count,
                    has_blocking_preparation_error=project.has_blocking_preparation_error,
                    readiness_confirmed=project.readiness_confirmed,
                    current_version_id=project.current_version_id,
                    template=project.metadata.get("template", "ASK_MY_DOCUMENTS"),
                    archived_at=None,
                    created_at=project.created_at or datetime.now(UTC),
                    updated_at=project.updated_at or datetime.now(UTC),
                )
            )
            self._finish(session)

    def get_project(self, project_id: str) -> Project | None:
        with self._session() as session:
            row = session.get(ProjectRow, project_id)
            return self._project(row) if row else None

    def list_projects_for_user(self, user_id: str) -> list[Project]:
        with self._session() as session:
            rows = session.scalars(
                select(ProjectRow).where(ProjectRow.owner_user_id == user_id)
            ).all()
            return [self._project(row) for row in rows]

    def save_asset(self, asset: Asset) -> None:
        with self._session() as session:
            session.merge(
                AssetRow(
                    id=asset.id,
                    workspace_id=asset.workspace_id,
                    project_id=asset.project_id,
                    original_name=asset.original_name,
                    safe_name=asset.safe_name,
                    media_type=asset.media_type,
                    size_bytes=asset.size_bytes,
                    checksum=asset.checksum,
                    storage_key=asset.storage_key,
                    status=asset.status.value,
                    participant_message=asset.participant_message,
                    normalized_text=asset.normalized_text,
                    created_at=asset.created_at or datetime.now(UTC),
                )
            )
            self._finish(session)

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._session() as session:
            row = session.get(AssetRow, asset_id)
            return self._asset(row) if row else None

    def list_assets(self, project_id: str) -> list[Asset]:
        with self._session() as session:
            rows = session.scalars(select(AssetRow).where(AssetRow.project_id == project_id)).all()
            return [self._asset(row) for row in rows]

    def find_asset_by_checksum(self, project_id: str, checksum: str) -> Asset | None:
        with self._session() as session:
            row = session.execute(
                select(AssetRow).where(
                    AssetRow.project_id == project_id, AssetRow.checksum == checksum
                )
            ).scalar_one_or_none()
            return self._asset(row) if row else None

    def save_version(self, version: ProjectVersion) -> None:
        with self._session() as session:
            session.merge(
                ProjectVersionRow(
                    id=version.id,
                    workspace_id=version.workspace_id,
                    project_id=version.project_id,
                    number=version.number,
                    template=version.assistant_config.get("template", "ASK_MY_DOCUMENTS"),
                    policy=version.assistant_config.get("policy", "GROUNDED_OR_ABSTAIN"),
                    assistant_config=dict(version.assistant_config),
                    created_at=version.created_at,
                )
            )
            session.execute(
                delete(ProjectVersionAssetRow).where(
                    ProjectVersionAssetRow.project_version_id == version.id
                )
            )
            session.add_all(
                [
                    ProjectVersionAssetRow(project_version_id=version.id, asset_id=asset_id)
                    for asset_id in version.asset_ids
                ]
            )
            self._finish(session)

    def get_version(self, version_id: str) -> ProjectVersion | None:
        with self._session() as session:
            row = session.get(ProjectVersionRow, version_id)
            if row is None:
                return None
            assets = tuple(
                session.scalars(
                    select(ProjectVersionAssetRow.asset_id).where(
                        ProjectVersionAssetRow.project_version_id == version_id
                    )
                ).all()
            )
            return ProjectVersion(
                row.id,
                row.workspace_id,
                row.project_id,
                row.number,
                assets,
                {"template": row.template, "policy": row.policy, **row.assistant_config},
                row.created_at,
            )

    def version_count(self, project_id: str) -> int:
        with self._session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(ProjectVersionRow)
                    .where(ProjectVersionRow.project_id == project_id)
                )
                or 0
            )

    def replace_chunks(self, asset_id: str, chunks: Sequence[DocumentChunk]) -> None:
        with self._session() as session:
            session.execute(delete(DocumentChunkRow).where(DocumentChunkRow.asset_id == asset_id))
            session.add_all(
                [
                    DocumentChunkRow(
                        id=chunk.id,
                        workspace_id=chunk.workspace_id,
                        project_id=chunk.project_id,
                        project_version_id=chunk.project_version_id,
                        asset_id=chunk.asset_id,
                        source_name=chunk.source_name,
                        position=chunk.position,
                        text=chunk.text,
                        embedding_bytes=json.dumps(chunk.embedding).encode(),
                    )
                    for chunk in chunks
                ]
            )
            self._finish(session)

    def list_chunks(self, project_id: str, version_id: str) -> list[DocumentChunk]:
        with self._session() as session:
            rows = session.scalars(
                select(DocumentChunkRow).where(
                    DocumentChunkRow.project_id == project_id,
                    DocumentChunkRow.project_version_id == version_id,
                )
            ).all()
            return [
                DocumentChunk(
                    row.id,
                    row.workspace_id,
                    row.project_id,
                    row.project_version_id,
                    row.asset_id,
                    row.source_name,
                    row.position,
                    row.text,
                    tuple(json.loads(row.embedding_bytes.decode())),
                )
                for row in rows
            ]

    def save_guided_test(self, test: GuidedTest) -> None:
        with self._session() as session:
            session.add(
                GuidedTestRow(
                    id=test.id,
                    project_id=test.project_id,
                    project_version_id=test.project_version_id,
                    user_id=test.user_id,
                    question_summary=test.question_summary,
                    cited_asset_ids=",".join(test.cited_asset_ids),
                    completed_at=test.completed_at,
                )
            )
            self._finish(session)

    def save_usage(self, event: UsageEvent) -> None:
        with self._session() as session:
            session.add(
                UsageEventRow(
                    id=event.id,
                    user_id=event.user_id,
                    workspace_id=event.workspace_id,
                    project_id=event.project_id,
                    operation=event.operation,
                    provider=event.provider,
                    model=event.model,
                    occurred_at=event.occurred_at,
                    status=event.status,
                    request_units=event.request_units,
                    estimated_cost=event.estimated_cost,
                    correlation_id=event.correlation_id,
                    output_units=event.output_units,
                    latency_ms=event.latency_ms,
                    retry_count=event.retry_count,
                    error_category=event.error_category,
                    cost_is_estimated=event.cost_is_estimated,
                )
            )
            self._finish(session)

    def usage_count_for_user(self, user_id: str) -> int:
        with self._session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(UsageEventRow)
                    .where(UsageEventRow.user_id == user_id, UsageEventRow.status == "SUCCEEDED")
                )
                or 0
            )

    def get_daily_allowance(self, user_id: str) -> int | None:
        with self._session() as session:
            row = session.get(UsageAllowanceRow, user_id)
            return row.daily_request_limit if row else None

    def set_daily_allowance(self, user_id: str, limit: int, updated_at: datetime) -> None:
        with self._session() as session:
            session.merge(
                UsageAllowanceRow(user_id=user_id, daily_request_limit=limit, updated_at=updated_at)
            )
            self._finish(session)

    def save_lifecycle(self, event: LifecycleEvent) -> None:
        metadata = event.safe_metadata
        with self._session() as session:
            session.add(
                LifecycleEventRow(
                    id=event.id,
                    project_id=event.project_id,
                    user_id=event.user_id,
                    event_type=event.event_type,
                    occurred_at=event.occurred_at,
                    asset_id=metadata.get("asset_id"),
                    publication_id=metadata.get("publication_id"),
                )
            )
            self._finish(session)

    def save_audit(self, event: AuditEvent) -> None:
        with self._session() as session:
            session.add(
                AuditEventRow(
                    id=event.id,
                    actor_user_id=event.actor_user_id,
                    workspace_id=event.workspace_id,
                    project_id=event.project_id,
                    action=event.action,
                    occurred_at=event.occurred_at,
                    outcome=event.outcome,
                )
            )
            self._finish(session)

    def save_publication(self, publication: Publication) -> None:
        with self._session() as session:
            session.add(
                PublicationRow(
                    id=publication.id,
                    workspace_id=publication.workspace_id,
                    project_id=publication.project_id,
                    project_version_id=publication.project_version_id,
                    owner_user_id=publication.owner_user_id,
                    project_name=publication.project_name,
                    template=publication.assistant_config.get("template", "ASK_MY_DOCUMENTS"),
                    policy=publication.assistant_config.get("policy", "GROUNDED_OR_ABSTAIN"),
                    assistant_config=dict(publication.assistant_config),
                    created_at=publication.created_at,
                    idempotency_key=f"pending:{publication.id}",
                )
            )
            session.add_all(
                [
                    PublicationAssetRow(publication_id=publication.id, asset_id=asset_id)
                    for asset_id in publication.asset_ids
                ]
            )
            session.add_all(
                [
                    PublicationChunkRow(
                        publication_id=publication.id,
                        asset_id=chunk.asset_id,
                        source_name=chunk.source_name,
                        position=chunk.position,
                        text=chunk.text,
                    )
                    for chunk in publication.chunks
                ]
            )
            self._finish(session)

    def get_publication(self, publication_id: str) -> Publication | None:
        with self._session() as session:
            row = session.get(PublicationRow, publication_id)
            return self._publication(session, row) if row else None

    def get_publication_for_idempotency(self, key: str) -> Publication | None:
        with self._session() as session:
            row = session.execute(
                select(PublicationRow).where(PublicationRow.idempotency_key == key)
            ).scalar_one_or_none()
            return self._publication(session, row) if row else None

    def bind_publication_idempotency(self, key: str, publication_id: str) -> None:
        with self._session() as session:
            row = session.get(PublicationRow, publication_id)
            if row:
                row.idempotency_key = key
            self._finish(session)

    def save_share_link(self, link: ShareLink) -> None:
        with self._session() as session:
            session.merge(
                ShareLinkRow(
                    publication_id=link.publication_id,
                    token_hash=link.token_hash,
                    visibility=link.visibility.value,
                    enabled_at=link.enabled_at,
                    revoked_at=link.revoked_at,
                )
            )
            self._finish(session)

    def get_share_link(self, publication_id: str) -> ShareLink | None:
        with self._session() as session:
            row = session.get(ShareLinkRow, publication_id)
            return self._share(row) if row else None

    def find_share_link_by_hash(self, token_hash: str) -> ShareLink | None:
        with self._session() as session:
            row = session.execute(
                select(ShareLinkRow).where(ShareLinkRow.token_hash == token_hash)
            ).scalar_one_or_none()
            return self._share(row) if row else None

    def list_users(self) -> list[User]:
        with self._session() as session:
            return [self._user(row) for row in session.scalars(select(UserRow)).all()]

    def list_all_projects(self) -> list[Project]:
        with self._session() as session:
            return [self._project(row) for row in session.scalars(select(ProjectRow)).all()]

    def list_failed_assets(self) -> list[Asset]:
        with self._session() as session:
            rows = session.scalars(select(AssetRow).where(AssetRow.status == "FAILED")).all()
            return [self._asset(row) for row in rows]

    def list_usage_events(self) -> list[UsageEvent]:
        with self._session() as session:
            return [self._usage(row) for row in session.scalars(select(UsageEventRow)).all()]

    def list_share_links(self) -> list[ShareLink]:
        with self._session() as session:
            return [self._share(row) for row in session.scalars(select(ShareLinkRow)).all()]

    def list_lifecycle_events(self) -> list[LifecycleEvent]:
        with self._session() as session:
            rows = session.scalars(select(LifecycleEventRow)).all()
            return [
                LifecycleEvent(
                    row.id,
                    row.project_id,
                    row.user_id,
                    row.event_type,
                    row.occurred_at,
                    {
                        key: value
                        for key, value in {
                            "asset_id": row.asset_id,
                            "publication_id": row.publication_id,
                        }.items()
                        if value
                    },
                )
                for row in rows
            ]

    def list_audit_events(self) -> list[AuditEvent]:
        with self._session() as session:
            rows = session.scalars(select(AuditEventRow)).all()
            return [
                AuditEvent(
                    row.id,
                    row.actor_user_id,
                    row.workspace_id,
                    row.project_id,
                    row.action,
                    row.occurred_at,
                    row.outcome,
                )
                for row in rows
            ]

    @staticmethod
    def _user(row: UserRow) -> User:
        return User(
            row.id,
            row.email,
            row.display_name,
            row.active,
            row.is_admin,
            row.identity_provider,
            row.identity_subject,
        )

    @staticmethod
    def _project(row: ProjectRow) -> Project:
        return Project(
            id=row.id,
            workspace_id=row.workspace_id,
            owner_user_id=row.owner_user_id,
            name=row.name,
            status=ProjectStatus(row.status),
            valid_document_count=row.valid_document_count,
            prepared_document_count=row.prepared_document_count,
            guided_test_count=row.guided_test_count,
            has_blocking_preparation_error=row.has_blocking_preparation_error,
            readiness_confirmed=row.readiness_confirmed,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata={**row.journey_metadata, "template": row.template},
            description=row.description,
            current_version_id=row.current_version_id,
        )

    @staticmethod
    def _asset(row: AssetRow) -> Asset:
        return Asset(
            row.id,
            row.workspace_id,
            row.project_id,
            row.original_name,
            row.safe_name,
            row.media_type,
            row.size_bytes,
            row.checksum,
            row.storage_key,
            AssetStatus(row.status),
            row.participant_message,
            row.normalized_text,
            row.created_at,
        )

    def _publication(self, session: Session, row: PublicationRow) -> Publication:
        assets = tuple(
            session.scalars(
                select(PublicationAssetRow.asset_id).where(
                    PublicationAssetRow.publication_id == row.id
                )
            ).all()
        )
        chunks = tuple(
            PublishedChunk(chunk.asset_id, chunk.source_name, chunk.position, chunk.text)
            for chunk in session.scalars(
                select(PublicationChunkRow).where(PublicationChunkRow.publication_id == row.id)
            ).all()
        )
        return Publication(
            row.id,
            row.workspace_id,
            row.project_id,
            row.project_version_id,
            row.owner_user_id,
            row.project_name,
            row.created_at,
            {"template": row.template, "policy": row.policy, **row.assistant_config},
            assets,
            chunks,
        )

    @staticmethod
    def _share(row: ShareLinkRow) -> ShareLink:
        return ShareLink(
            row.publication_id,
            row.token_hash,
            PublicationVisibility(row.visibility),
            row.enabled_at,
            row.revoked_at,
        )

    @staticmethod
    def _usage(row: UsageEventRow) -> UsageEvent:
        return UsageEvent(
            row.id,
            row.user_id,
            row.workspace_id,
            row.project_id,
            row.operation,
            row.provider,
            row.model,
            row.occurred_at,
            row.status,
            row.request_units,
            row.estimated_cost,
            row.correlation_id,
            row.output_units,
            row.latency_ms,
            row.retry_count,
            row.error_category,
            row.cost_is_estimated,
        )
