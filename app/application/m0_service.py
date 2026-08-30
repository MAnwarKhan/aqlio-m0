"""Complete deterministic Ask My Documents application workflow."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

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
    RateLimitExceeded,
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
    RateLimitPort,
    StoragePort,
)
from app.ports.contracts import (
    Citation,
    GenerationRequest,
    GenerationResponse,
    ProviderCallError,
    ProviderUsage,
    RetrievedContext,
)

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


def transactional[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        service = args[0]
        if not isinstance(service, M0Service):
            raise TypeError("Transactional methods require M0Service.")
        with service.repository.transaction():
            return method(*args, **kwargs)

    return wrapped


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
        rate_limiter: RateLimitPort | None = None,
    ) -> None:
        self.settings = settings
        self.auth = auth
        self.clock = clock
        self.ids = ids
        self.generation = generation
        self.embedding = embedding
        self.repository = repository
        self.storage = storage
        self.rate_limiter = rate_limiter

    @transactional
    def resolve_workspace(self) -> Workspace:
        identity = self.auth.current_user()
        persisted = self.repository.get_user(identity.id)
        if persisted and not persisted.active:
            raise AuthorizationError("Your Aqlio access is not active.")
        user = persisted or identity
        self.repository.save_user(identity)
        if self.repository.get_daily_allowance(user.id) is None:
            self.repository.set_daily_allowance(
                user.id, self.settings.daily_ai_request_allowance, self.clock.now()
            )
        existing = self.repository.get_workspace_for_user(user.id)
        if existing:
            return existing
        workspace = Workspace(self.ids.new_id(), user.id, f"{user.display_name}'s Workspace")
        member = WorkspaceMember(workspace.id, user.id, WorkspaceRole.OWNER)
        self.repository.save_workspace(workspace, member)
        self._audit(workspace.id, None, "WORKSPACE_CREATED", "SUCCEEDED")
        return workspace

    @transactional
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

    def add_and_prepare_document(self, project_id: str, filename: str, content: bytes) -> Asset:
        """Complete the participant's single Add Documents action."""

        asset = self.upload_document(project_id, filename, content)
        return self.prepare_document(project_id, asset.id)

    @transactional
    def upload_document(self, project_id: str, filename: str, content: bytes) -> Asset:
        project = self._authorized_project(project_id)
        self._limit(project.owner_user_id, "upload", self.settings.upload_rate_limit)
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
        try:
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
        except Exception:
            self.storage.delete(
                workspace_id=project.workspace_id,
                project_id=project.id,
                storage_key=storage_key,
            )
            raise

    def prepare_document(self, project_id: str, asset_id: str) -> Asset:
        project = self._authorized_project(project_id)
        self._limit(project.owner_user_id, "prepare", self.settings.preparation_rate_limit)
        asset = self._authorized_asset(project, asset_id)
        if asset.status == AssetStatus.READY:
            return asset
        asset.status = AssetStatus.PREPARING
        asset.participant_message = "Preparing"
        self.repository.save_asset(asset)
        self._lifecycle(project.id, "DOCUMENT_PREPARATION_STARTED", {"asset_id": asset.id})
        try:
            try:
                content = self.storage.get(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    storage_key=asset.storage_key,
                )
            except Exception as exc:
                raise PreparationError(
                    "We couldn't access this document. Add it again and try again."
                ) from exc
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
        except (PreparationError, AllowanceExceeded) as exc:
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
        self._limit(user.id, "test_assistant", self.settings.ai_rate_limit)
        clean_question = " ".join(question.split())
        if not clean_question:
            raise ValidationError("Enter a question to test your assistant.")
        if project.current_version_id is None or project.prepared_document_count < 1:
            raise NotReadyError("Prepare at least one document before testing your assistant.")
        correlation_id = self.ids.new_id()
        if not self._has_allowance(user.id):
            self._usage(project, correlation_id, "REJECTED")
            raise AllowanceExceeded(
                "You've reached your Aqlio AI usage allowance. Please try again after it resets."
            )
        contexts = self._retrieve(project, clean_question)
        if not contexts:
            response = GenerationResponse(
                "I couldn't find enough information in your documents to answer that confidently.",
                (),
                True,
            )
        else:
            try:
                response = self.generation.generate(GenerationRequest(clean_question, contexts))
            except ProviderCallError as exc:
                self._provider_failure(project, correlation_id, "TEST_ASSISTANT", exc)
                raise
        self._usage(
            project,
            correlation_id,
            "ABSTAINED" if not contexts else "SUCCEEDED",
            usage=response.usage,
        )
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

    @transactional
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

    @transactional
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

    @transactional
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
        self._limit(
            self._token_hash(token), "shared_access", self.settings.shared_access_rate_limit
        )
        link = self.repository.find_share_link_by_hash(self._token_hash(token))
        if link is None or link.visibility != PublicationVisibility.LINK_ONLY:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        publication = self.repository.get_publication(link.publication_id)
        if publication is None:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        return self._publication_view(publication, link.visibility)

    def ask_shared(self, token: str, question: str) -> Answer:
        token_hash = self._token_hash(token)
        self._limit(token_hash, "shared_access", self.settings.shared_access_rate_limit)
        link = self.repository.find_share_link_by_hash(token_hash)
        if link is None or link.visibility != PublicationVisibility.LINK_ONLY:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        publication = self.repository.get_publication(link.publication_id)
        if publication is None:
            raise ShareAccessError("This assistant link is invalid or no longer available.")
        clean_question = " ".join(question.split())
        if not clean_question:
            raise ValidationError("Enter a question to ask this assistant.")
        correlation_id = self.ids.new_id()
        if not self._has_allowance(publication.owner_user_id):
            self._save_usage(
                publication.owner_user_id,
                publication.workspace_id,
                publication.project_id,
                correlation_id,
                "REJECTED",
                operation="SHARED_ASSISTANT",
            )
            raise AllowanceExceeded("This assistant is temporarily unavailable. Please try later.")
        contexts = self._retrieve_publication(publication, clean_question)
        if not contexts:
            return Answer(
                "I couldn't find enough information in the documents to answer that confidently.",
                (),
                True,
                correlation_id,
            )
        try:
            response = self.generation.generate(GenerationRequest(clean_question, contexts))
        except ProviderCallError as exc:
            self._save_provider_failure(
                publication.owner_user_id,
                publication.workspace_id,
                publication.project_id,
                correlation_id,
                "SHARED_ASSISTANT",
                exc,
            )
            raise
        self._save_usage(
            publication.owner_user_id,
            publication.workspace_id,
            publication.project_id,
            correlation_id,
            "SUCCEEDED",
            operation="SHARED_ASSISTANT",
            usage=response.usage,
        )
        return Answer(response.answer, response.citations, response.abstained, correlation_id)

    @transactional
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
            raw_chunks = chunk_text(
                asset.normalized_text or "", max_words=self.settings.chunk_max_words
            )
            correlation_id = self.ids.new_id()
            if self.settings.ai_mode == "managed" and not self._has_allowance(
                self.auth.current_user().id
            ):
                self._usage(project, correlation_id, "REJECTED", operation="EMBED_DOCUMENT")
                raise AllowanceExceeded(
                    "You've reached your Aqlio AI usage allowance. "
                    "Please try again after it resets."
                )
            try:
                embedding_response = self.embedding.embed(raw_chunks)
            except ProviderCallError as exc:
                self._provider_failure(project, correlation_id, "EMBED_DOCUMENT", exc)
                raise PreparationError(
                    "We couldn't prepare this document right now. Please try again."
                ) from exc
            vectors = embedding_response.vectors
            if embedding_response.usage is not None:
                self._usage(
                    project,
                    correlation_id,
                    "SUCCEEDED",
                    operation="EMBED_DOCUMENT",
                    usage=embedding_response.usage,
                )
            chunks = [
                DocumentChunk(
                    id=hashlib.sha256(
                        f"{version.id}:{asset.id}:{index}:{text}".encode()
                    ).hexdigest(),
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

    def _retrieve_publication(
        self, publication: Publication, question: str
    ) -> list[RetrievedContext]:
        query_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", question.lower())
            if len(term) > 2 and term not in _STOPWORDS
        }
        safe_texts = set(
            remove_untrusted_instruction_chunks([chunk.text for chunk in publication.chunks])
        )
        scored = []
        for chunk in publication.chunks:
            if chunk.text not in safe_texts:
                continue
            score = len(query_terms & set(re.findall(r"[a-z0-9]+", chunk.text.lower())))
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].source_name, item[1].position))
        return [
            RetrievedContext(
                chunk.asset_id,
                chunk.source_name,
                f"published:{chunk.asset_id}:{chunk.position}",
                chunk.text,
            )
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

    def _usage(
        self,
        project: Project,
        correlation_id: str,
        status: str,
        *,
        operation: str = "TEST_ASSISTANT",
        usage: ProviderUsage | None = None,
        error_category: str | None = None,
    ) -> None:
        user = self.auth.current_user()
        self._save_usage(
            user.id,
            project.workspace_id,
            project.id,
            correlation_id,
            status,
            operation=operation,
            usage=usage,
            error_category=error_category,
        )

    def _save_usage(
        self,
        user_id: str,
        workspace_id: str,
        project_id: str,
        correlation_id: str,
        status: str,
        *,
        operation: str,
        usage: ProviderUsage | None = None,
        error_category: str | None = None,
    ) -> None:
        self.repository.save_usage(
            UsageEvent(
                id=self.ids.new_id(),
                user_id=user_id,
                workspace_id=workspace_id,
                project_id=project_id,
                operation=operation,
                provider=usage.provider if usage else "aqlio-fake",
                model=usage.model if usage else "deterministic-grounded-v1",
                occurred_at=self.clock.now(),
                status=status,
                request_units=usage.input_units if usage else 1,
                estimated_cost=usage.estimated_cost if usage else 0.0,
                correlation_id=correlation_id,
                output_units=usage.output_units if usage else 0,
                latency_ms=usage.latency_ms if usage else 0,
                retry_count=usage.retry_count if usage else 0,
                error_category=error_category,
                cost_is_estimated=usage.cost_is_estimated if usage else True,
            )
        )

    def _provider_failure(
        self, project: Project, correlation_id: str, operation: str, error: ProviderCallError
    ) -> None:
        usage = ProviderUsage(
            provider=error.provider,
            model=error.model,
            latency_ms=error.latency_ms,
            retry_count=error.retry_count,
        )
        self._usage(
            project,
            correlation_id,
            "FAILED",
            operation=operation,
            usage=usage,
            error_category=error.category,
        )

    def _save_provider_failure(
        self,
        user_id: str,
        workspace_id: str,
        project_id: str,
        correlation_id: str,
        operation: str,
        error: ProviderCallError,
    ) -> None:
        self._save_usage(
            user_id,
            workspace_id,
            project_id,
            correlation_id,
            "FAILED",
            operation=operation,
            usage=ProviderUsage(
                provider=error.provider,
                model=error.model,
                latency_ms=error.latency_ms,
                retry_count=error.retry_count,
            ),
            error_category=error.category,
        )

    def _has_allowance(self, user_id: str) -> bool:
        allowance = self.repository.get_daily_allowance(user_id)
        effective_allowance = allowance or self.settings.daily_ai_request_allowance
        return self.repository.usage_count_for_user(user_id) < effective_allowance

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

    def _limit(self, subject: str, operation: str, limit: int) -> None:
        if self.rate_limiter and not self.rate_limiter.allow(
            subject=subject,
            operation=operation,
            limit=limit,
            window_seconds=self.settings.rate_limit_window_seconds,
        ):
            raise RateLimitExceeded("Please wait a moment before trying that again.")
