"""Complete deterministic Ask My Documents application workflow."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.application.documents import (
    chunk_text,
    extract_text,
    remove_untrusted_instruction_chunks,
    validate_document,
)
from app.application.errors import (
    AllowanceExceeded,
    AuthorizationError,
    NotReadyError,
    PreparationError,
    ShareAccessError,
    ValidationError,
)
from app.config import Settings
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
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    assess_readiness,
    transition_project,
)
from app.ports import (
    AuthPort,
    ClockPort,
    EmbeddingPort,
    GenerationPort,
    IdPort,
    M0RepositoryPort,
    StoragePort,
)
from app.ports.contracts import Citation, GenerationRequest, RetrievedContext

_STOPWORDS = {
    "a",
    "about",
    "and",
    "are",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "the",
    "to",
    "what",
    "when",
}


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: tuple[Citation, ...]
    abstained: bool
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ShareReceipt:
    publication_id: str
    token: str


@dataclass(frozen=True, slots=True)
class PublishedAssistant:
    publication_id: str
    project_id: str
    project_name: str
    visibility: PublicationVisibility
    source_names: tuple[str, ...]


class M0Service:
    """Application boundary enforcing authentication, authorization, and domain rules."""

    def __init__(
        self,
        *,
        settings: Settings,
        auth: AuthPort,
        clock: ClockPort,
        ids: IdPort,
        generation: GenerationPort,
        embedding: EmbeddingPort,
        repository: M0RepositoryPort,
        storage: StoragePort,
    ) -> None:
        self.settings = settings
        self.auth = auth
        self.clock = clock
        self.ids = ids
        self.generation = generation
        self.embedding = embedding
        self.repository = repository
        self.storage = storage

    def resolve_workspace(self) -> Workspace:
        user = self.auth.current_user()
        if not user.active:
            raise AuthorizationError("Your Aqlio access is not active.")
        self.repository.save_user(user)
        existing = self.repository.get_workspace_for_user(user.id)
        if existing:
            return existing
        workspace = Workspace(self.ids.new_id(), user.id, f"{user.display_name}'s Workspace")
        member = WorkspaceMember(workspace.id, user.id, WorkspaceRole.OWNER)
        self.repository.save_workspace(workspace, member)
        self._audit(workspace.id, None, "WORKSPACE_CREATED", "SUCCEEDED")
        return workspace

    def create_project(self, name: str, description: str = "") -> Project:
        user = self.auth.current_user()
        workspace = self.resolve_workspace()
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValidationError("Give your project a name to continue.")
        if len(clean_name) > 100:
            raise ValidationError("Use a project name with 100 characters or fewer.")
        now = self.clock.now()
        project = Project(
            id=self.ids.new_id(),
            workspace_id=workspace.id,
            owner_user_id=user.id,
            name=clean_name,
            description=" ".join(description.split())[:500],
            created_at=now,
            updated_at=now,
            metadata={"template": "ASK_MY_DOCUMENTS"},
        )
        self.repository.save_project(project)
        self._lifecycle(project.id, "PROJECT_CREATED", {"template": "ASK_MY_DOCUMENTS"})
        self._audit(workspace.id, project.id, "PROJECT_CREATED", "SUCCEEDED")
        return project

    def list_my_projects(self) -> list[Project]:
        user = self.auth.current_user()
        self.resolve_workspace()
        return self.repository.list_projects_for_user(user.id)

    def get_my_project(self, project_id: str) -> Project:
        return self._authorized_project(project_id)

    def list_documents(self, project_id: str) -> list[Asset]:
        project = self._authorized_project(project_id)
        return self.repository.list_assets(project.id)

    def upload_document(self, project_id: str, filename: str, content: bytes) -> Asset:
        project = self._authorized_project(project_id)
        assets = self.repository.list_assets(project.id)
        checksum = hashlib.sha256(content).hexdigest()
        duplicate = self.repository.find_asset_by_checksum(project.id, checksum)
        if duplicate:
            return duplicate
        if len(assets) >= self.settings.max_files_per_project:
            raise ValidationError("This project already has the maximum number of documents.")
        display_name, media_type = validate_document(
            filename=filename,
            content=content,
            allowed_types=self.settings.allowed_file_types,
            max_size_bytes=self.settings.max_file_size_mb * 1024 * 1024,
        )
        if sum(asset.size_bytes for asset in assets) + len(content) > (
            self.settings.max_project_storage_mb * 1024 * 1024
        ):
            raise ValidationError("These documents exceed this project's storage allowance.")
        safe_name = f"{self.ids.new_id()}.{display_name.rsplit('.', 1)[-1].lower()}"
        storage_key = self.storage.put(
            workspace_id=project.workspace_id,
            project_id=project.id,
            content=content,
        )
        asset = Asset(
            id=self.ids.new_id(),
            workspace_id=project.workspace_id,
            project_id=project.id,
            original_name=display_name,
            safe_name=safe_name,
            media_type=media_type,
            size_bytes=len(content),
            checksum=checksum,
            storage_key=storage_key,
            created_at=self.clock.now(),
        )
        self.repository.save_asset(asset)
        project.valid_document_count += 1
        if project.status == ProjectStatus.DRAFT:
            transition_project(project, ProjectStatus.DOCUMENTS_ADDED)
        project.updated_at = self.clock.now()
        self.repository.save_project(project)
        self._lifecycle(project.id, "DOCUMENT_UPLOADED", {"asset_id": asset.id})
        return asset

    def prepare_document(self, project_id: str, asset_id: str) -> Asset:
        project = self._authorized_project(project_id)
        asset = self._authorized_asset(project, asset_id)
        if asset.status == AssetStatus.READY:
            return asset
        asset.status = AssetStatus.PREPARING
        asset.participant_message = "Preparing"
        self.repository.save_asset(asset)
        self._lifecycle(project.id, "DOCUMENT_PREPARATION_STARTED", {"asset_id": asset.id})
        try:
            content = self.storage.get(
                workspace_id=project.workspace_id,
                project_id=project.id,
                storage_key=asset.storage_key,
            )
            normalized = extract_text(asset.original_name, content)
            asset.normalized_text = normalized
            asset.status = AssetStatus.READY
            asset.participant_message = "Ready"
            self.repository.save_asset(asset)
            self._rebuild_project_version(project)
            project = self._authorized_project(project.id)
            project.prepared_document_count = sum(
                item.status == AssetStatus.READY for item in self.repository.list_assets(project.id)
            )
            project.has_blocking_preparation_error = False
            if project.status == ProjectStatus.DOCUMENTS_ADDED:
                transition_project(project, ProjectStatus.PREPARED)
            project.updated_at = self.clock.now()
            self.repository.save_project(project)
            self._lifecycle(project.id, "DOCUMENT_PREPARED", {"asset_id": asset.id})
            return asset
        except PreparationError as exc:
            asset.status = AssetStatus.FAILED
            asset.participant_message = str(exc)
            self.repository.save_asset(asset)
            project.has_blocking_preparation_error = True
            self.repository.save_project(project)
            self._lifecycle(project.id, "DOCUMENT_PREPARATION_FAILED", {"asset_id": asset.id})
            raise

    def ask_question(self, project_id: str, question: str, *, guided: bool = False) -> Answer:
        project = self._authorized_project(project_id)
        user = self.auth.current_user()
        clean_question = " ".join(question.split())
        if not clean_question:
            raise ValidationError("Enter a question to test your assistant.")
        if project.current_version_id is None or project.prepared_document_count < 1:
            raise NotReadyError("Prepare at least one document before testing your assistant.")
        correlation_id = self.ids.new_id()
        if (
            self.repository.usage_count_for_user(user.id)
            >= self.settings.daily_ai_request_allowance
        ):
            self._usage(project, correlation_id, "REJECTED")
            raise AllowanceExceeded(
                "You've reached your Aqlio AI usage allowance. Please try again after it resets."
            )
        contexts = self._retrieve(project, clean_question)
        response = self.generation.generate(GenerationRequest(clean_question, contexts))
        self._usage(project, correlation_id, "SUCCEEDED")
        if guided and not response.abstained:
            test = GuidedTest(
                id=self.ids.new_id(),
                project_id=project.id,
                project_version_id=project.current_version_id,
                user_id=user.id,
                question_summary=hashlib.sha256(clean_question.encode()).hexdigest()[:12],
                cited_asset_ids=tuple(context.document_id for context in contexts),
                completed_at=self.clock.now(),
            )
            self.repository.save_guided_test(test)
            project.guided_test_count += 1
            if project.status == ProjectStatus.PREPARED:
                transition_project(project, ProjectStatus.TESTED)
            self.repository.save_project(project)
            self._lifecycle(project.id, "TEST_COMPLETED", {"test_id": test.id})
        return Answer(response.answer, response.citations, response.abstained, correlation_id)

    def confirm_readiness(self, project_id: str) -> Project:
        project = self._authorized_project(project_id)
        project.readiness_confirmed = True
        result = assess_readiness(project)
        if not result.ready:
            project.readiness_confirmed = False
            raise NotReadyError("Complete the readiness steps before deploying your assistant.")
        if project.status == ProjectStatus.TESTED:
            transition_project(project, ProjectStatus.READY)
        self.repository.save_project(project)
        self._lifecycle(project.id, "READINESS_CONFIRMED", {})
        return project

    def readiness(self, project_id: str) -> tuple[bool, tuple[str, ...]]:
        result = assess_readiness(self._authorized_project(project_id))
        return result.ready, result.missing

    def deploy(self, project_id: str, *, idempotency_key: str) -> Publication:
        project = self._authorized_project(project_id)
        existing = self.repository.get_publication_for_idempotency(idempotency_key)
        if existing:
            if existing.owner_user_id != self.auth.current_user().id:
                raise AuthorizationError("You do not have permission to deploy this project.")
            return existing
        if project.status != ProjectStatus.READY or not assess_readiness(project).ready:
            raise NotReadyError("Complete the readiness steps before deploying your assistant.")
        if project.current_version_id is None:
            raise NotReadyError("Prepare your documents before deploying your assistant.")
        version = self.repository.get_version(project.current_version_id)
        if version is None:
            raise NotReadyError("Prepare your documents again before deploying.")
        chunks = self.repository.list_chunks(project.id, version.id)
        publication = Publication(
            id=self.ids.new_id(),
            workspace_id=project.workspace_id,
            project_id=project.id,
            project_version_id=version.id,
            owner_user_id=project.owner_user_id,
            project_name=project.name,
            created_at=self.clock.now(),
            assistant_config=version.assistant_config,
            asset_ids=version.asset_ids,
            chunks=tuple(
                PublishedChunk(chunk.asset_id, chunk.source_name, chunk.position, chunk.text)
                for chunk in chunks
            ),
        )
        self.repository.save_publication(publication)
        self.repository.save_share_link(ShareLink(publication.id))
        self.repository.bind_publication_idempotency(idempotency_key, publication.id)
        transition_project(project, ProjectStatus.DEPLOYED)
        self.repository.save_project(project)
        self._lifecycle(project.id, "PUBLICATION_CREATED", {"publication_id": publication.id})
        self._audit(project.workspace_id, project.id, "PUBLICATION_CREATED", "SUCCEEDED")
        return publication

    def open_private(self, publication_id: str) -> PublishedAssistant:
        publication = self.repository.get_publication(publication_id)
        if publication is None or publication.owner_user_id != self.auth.current_user().id:
            raise AuthorizationError("You do not have permission to open this assistant.")
        return self._publication_view(publication, PublicationVisibility.PRIVATE)

    def enable_link_sharing(self, publication_id: str) -> ShareReceipt:
        publication = self._owned_publication(publication_id)
        link = self.repository.get_share_link(publication.id) or ShareLink(publication.id)
        if link.visibility == PublicationVisibility.LINK_ONLY and link.token_hash:
            raise ValidationError(
                "Sharing is already enabled. Stop sharing before creating a new link."
            )
        token = hashlib.sha256(f"{publication.id}:{self.ids.new_id()}".encode()).hexdigest()
        link.token_hash = self._token_hash(token)
        link.visibility = PublicationVisibility.LINK_ONLY
        link.enabled_at = self.clock.now()
        link.revoked_at = None
        self.repository.save_share_link(link)
        self._lifecycle(publication.project_id, "SHARING_ENABLED", {})
        self._audit(
            publication.workspace_id, publication.project_id, "SHARING_ENABLED", "SUCCEEDED"
        )
        return ShareReceipt(publication.id, token)

    def open_shared(self, token: str) -> PublishedAssistant:
        link = self.repository.find_share_link_by_hash(self._token_hash(token))
        if link is None or link.visibility != PublicationVisibility.LINK_ONLY:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        publication = self.repository.get_publication(link.publication_id)
        if publication is None:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        return self._publication_view(publication, link.visibility)

    def revoke_sharing(self, publication_id: str) -> None:
        publication = self._owned_publication(publication_id)
        link = self.repository.get_share_link(publication.id)
        if link is None or link.visibility == PublicationVisibility.REVOKED:
            return
        link.visibility = PublicationVisibility.REVOKED
        link.revoked_at = self.clock.now()
        self.repository.save_share_link(link)
        self._lifecycle(publication.project_id, "SHARING_REVOKED", {})
        self._audit(
            publication.workspace_id, publication.project_id, "SHARING_REVOKED", "SUCCEEDED"
        )

    def _authorized_project(self, project_id: str) -> Project:
        user = self.auth.current_user()
        project = self.repository.get_project(project_id)
        if (
            project is None
            or project.owner_user_id != user.id
            or not self.repository.is_workspace_member(project.workspace_id, user.id)
        ):
            raise AuthorizationError("You do not have permission to access this project.")
        return project

    def _authorized_asset(self, project: Project, asset_id: str) -> Asset:
        asset = self.repository.get_asset(asset_id)
        if (
            asset is None
            or asset.project_id != project.id
            or asset.workspace_id != project.workspace_id
        ):
            raise AuthorizationError("You do not have permission to access this document.")
        return asset

    def _owned_publication(self, publication_id: str) -> Publication:
        publication = self.repository.get_publication(publication_id)
        user = self.auth.current_user()
        if publication is None or publication.owner_user_id != user.id:
            raise AuthorizationError("You do not have permission to manage this assistant.")
        if not self.repository.is_workspace_member(publication.workspace_id, user.id):
            raise AuthorizationError("You do not have permission to manage this assistant.")
        return publication

    def _rebuild_project_version(self, project: Project) -> ProjectVersion:
        ready_assets = [
            asset
            for asset in self.repository.list_assets(project.id)
            if asset.status == AssetStatus.READY
        ]
        version = ProjectVersion(
            id=self.ids.new_id(),
            workspace_id=project.workspace_id,
            project_id=project.id,
            number=self.repository.version_count(project.id) + 1,
            asset_ids=tuple(asset.id for asset in ready_assets),
            assistant_config={"template": "ASK_MY_DOCUMENTS", "policy": "GROUNDED_OR_ABSTAIN"},
            created_at=self.clock.now(),
        )
        self.repository.save_version(version)
        for asset in ready_assets:
            raw_chunks = chunk_text(asset.normalized_text or "")
            vectors = self.embedding.embed(raw_chunks)
            chunks = [
                DocumentChunk(
                    id=self.ids.new_id(),
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    project_version_id=version.id,
                    asset_id=asset.id,
                    source_name=asset.original_name,
                    position=index + 1,
                    text=text,
                    embedding=tuple(vector),
                )
                for index, (text, vector) in enumerate(zip(raw_chunks, vectors, strict=True))
            ]
            self.repository.replace_chunks(asset.id, chunks)
        project.current_version_id = version.id
        self.repository.save_project(project)
        return version

    def _retrieve(self, project: Project, question: str) -> list[RetrievedContext]:
        if project.current_version_id is None:
            return []
        query_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", question.lower())
            if len(term) > 2 and term not in _STOPWORDS
        }
        candidates = self.repository.list_chunks(project.id, project.current_version_id)
        safe_texts = set(remove_untrusted_instruction_chunks([chunk.text for chunk in candidates]))
        scored: list[tuple[int, DocumentChunk]] = []
        for chunk in candidates:
            if chunk.text not in safe_texts:
                continue
            chunk_terms = set(re.findall(r"[a-z0-9]+", chunk.text.lower()))
            score = len(query_terms & chunk_terms)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].source_name, item[1].position))
        return [
            RetrievedContext(chunk.asset_id, chunk.source_name, chunk.id, chunk.text)
            for _score, chunk in scored[:3]
        ]

    def _publication_view(
        self, publication: Publication, visibility: PublicationVisibility
    ) -> PublishedAssistant:
        return PublishedAssistant(
            publication.id,
            publication.project_id,
            publication.project_name,
            visibility,
            tuple(dict.fromkeys(chunk.source_name for chunk in publication.chunks)),
        )

    def _usage(self, project: Project, correlation_id: str, status: str) -> None:
        user = self.auth.current_user()
        self.repository.save_usage(
            UsageEvent(
                id=self.ids.new_id(),
                user_id=user.id,
                workspace_id=project.workspace_id,
                project_id=project.id,
                operation="TEST_ASSISTANT",
                provider="aqlio-fake",
                model="deterministic-grounded-v1",
                occurred_at=self.clock.now(),
                status=status,
                request_units=1,
                estimated_cost=0.0,
                correlation_id=correlation_id,
            )
        )

    def _lifecycle(self, project_id: str, event_type: str, metadata: dict[str, str]) -> None:
        self.repository.save_lifecycle(
            LifecycleEvent(
                self.ids.new_id(),
                project_id,
                self.auth.current_user().id,
                event_type,
                self.clock.now(),
                metadata,
            )
        )

    def _audit(self, workspace_id: str, project_id: str | None, action: str, outcome: str) -> None:
        self.repository.save_audit(
            AuditEvent(
                self.ids.new_id(),
                self.auth.current_user().id,
                workspace_id,
                project_id,
                action,
                self.clock.now(),
                outcome,
            )
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
