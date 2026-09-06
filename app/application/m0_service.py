"""Complete deterministic Ask My Documents application workflow."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import wraps

from app.application.advisor_workflow import AdvisorWorkflowService
from app.application.documents import (
    chunk_text,
    extract_text,
    remove_untrusted_instruction_chunks,
    validate_document,
)
from app.application.eligibility_advisor import AdvisorInput, AdvisorResult
from app.application.errors import (
    AllowanceExceeded,
    AuthorizationError,
    NotReadyError,
    PreparationError,
    RateLimitExceeded,
    ShareAccessError,
    ValidationError,
)
from app.application.export_builder import build_export
from app.application.lifecycle_coordinator import LifecycleCoordinator
from app.application.specification_lifecycle import default_specification_registry
from app.config import Settings
from app.domain import (
    ApplicationSpecification,
    ApplicationType,
    ApprovedVersionSnapshot,
    Asset,
    AssetStatus,
    AuditEvent,
    DocumentChunk,
    EvaluationReport,
    ExportPackage,
    ExportPackageStatus,
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
    "all",
    "complete",
    "every",
    "list",
    "please",
    "with",
}

_COMPLETE_REQUEST_TERMS = {"all", "complete", "every", "list"}


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
class ImprovementProposal:
    request: str
    response_style: str
    summary: str
    supported: bool = True
    participant_message: str = ""


@dataclass(frozen=True, slots=True)
class UIImprovementProposal:
    request: str
    ui_config: dict[str, str]
    summary: str
    supported: bool = True
    participant_message: str = ""


@dataclass(frozen=True, slots=True)
class ShareReceipt:
    publication_id: str
    token: str


@dataclass(frozen=True, slots=True)
class ExportDownload:
    package: ExportPackage
    content: bytes


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
        self.specifications = default_specification_registry()
        self.lifecycle = LifecycleCoordinator(
            auth=auth,
            clock=clock,
            ids=ids,
            repository=repository,
            registry=self.specifications,
            authorized_project=self._authorized_project,
            lifecycle_event=self._lifecycle,
        )
        self.advisor = AdvisorWorkflowService(
            clock=clock,
            ids=ids,
            repository=repository,
            lifecycle=self.lifecycle,
            authorized_project=self._authorized_project,
            create_project=self.create_project,
            lifecycle_event=self._lifecycle,
            clean_text=self._journey_text,
        )

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
    def create_project(
        self,
        name: str,
        description: str = "",
        application_type: ApplicationType = ApplicationType.ASK_MY_DOCUMENTS,
    ) -> Project:
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
            metadata={"template": application_type.value},
        )
        self.repository.save_project(project)
        self._lifecycle(project.id, "PROJECT_CREATED", {"template": application_type.value})
        self._audit(workspace.id, project.id, "PROJECT_CREATED", "SUCCEEDED")
        return project

    @transactional
    def create_advisor_project(
        self, *, name: str, problem: str, users: str, outcome: str
    ) -> Project:
        return self.advisor.create(name=name, problem=problem, users=users, outcome=outcome)

    @transactional
    def build_advisor_working_version(self, project_id: str) -> ProjectVersion:
        return self.advisor.build(project_id)

    def list_my_projects(self) -> list[Project]:
        user = self.auth.current_user()
        self.resolve_workspace()
        return self.repository.list_projects_for_user(user.id)

    @transactional
    def create_idea(self, idea: str) -> Project:
        idea = self._journey_text(idea)
        if not idea:
            raise ValidationError("Describe your idea to continue.")
        project = self.create_project(" ".join(idea.split())[:80], idea[:500])
        project.metadata["idea"] = idea
        self.repository.save_project(project)
        return project

    @staticmethod
    def _journey_text(value: str) -> str:
        if len(value) > 2000:
            raise ValidationError("Keep each description to 2,000 characters or fewer.")
        return value.strip()

    @transactional
    def update_definition(self, project_id: str, fields: dict[str, str]) -> Project:
        project = self._authorized_project(project_id)
        allowed = {"idea", "problem", "users", "outcome", "ai_role", "information"}
        if not fields.keys() <= allowed:
            raise ValidationError("Use the solution definition fields provided.")
        cleaned = {key: self._journey_text(value) for key, value in fields.items()}
        if project.current_version_id and any(
            value != project.metadata.get(key, "") for key, value in cleaned.items()
        ):
            raise ValidationError(
                "This intent is already part of the Working Version. Use Improve to create a new "
                "versioned change."
            )
        if "idea" in cleaned and not cleaned["idea"]:
            raise ValidationError("Describe your idea to continue.")
        if cleaned.get("idea", project.metadata.get("idea")) != project.metadata.get("idea"):
            project.metadata.pop("idea_evaluation", None)
        project.metadata.update(cleaned)
        project.updated_at = self.clock.now()
        self.repository.save_project(project)
        return project

    @transactional
    def define_solution(self, project_id: str) -> Project:
        project = self._authorized_project(project_id)
        if not all(
            project.metadata.get(key)
            for key in ("idea", "problem", "users", "outcome", "ai_role", "information")
        ):
            raise ValidationError("Add a short description in each field before building.")
        project.metadata["defined"] = "true"
        self.repository.save_project(project)
        self._lifecycle(project.id, "SOLUTION_DEFINED", {})
        return project

    def evaluate_idea(self, project_id: str) -> str:
        project = self._authorized_project(project_id)
        idea = project.metadata.get("idea", "")
        if not idea:
            raise ValidationError("Describe your idea first.")
        self._limit(project.owner_user_id, "evaluate_idea", self.settings.ai_rate_limit)
        correlation_id = self.ids.new_id()
        if not self._has_allowance(project.owner_user_id):
            self._usage(project, correlation_id, "REJECTED", operation="EVALUATE_IDEA")
            raise AllowanceExceeded(
                "You've reached your Aqlio AI usage allowance. You can still continue."
            )
        try:
            response = self.generation.generate(GenerationRequest(idea, (), "idea_evaluation"))
        except ProviderCallError as exc:
            self._provider_failure(project, correlation_id, "EVALUATE_IDEA", exc)
            raise
        self._usage(
            project, correlation_id, "SUCCEEDED", operation="EVALUATE_IDEA", usage=response.usage
        )
        project.metadata["idea_evaluation"] = response.answer
        self.repository.save_project(project)
        return response.answer

    @transactional
    def propose_improvement(
        self, project_id: str, request: str, *, response_style: str
    ) -> ImprovementProposal:
        project = self._authorized_project(project_id)
        request = self._journey_text(request)
        if not request or response_style not in {"concise", "balanced", "detailed"}:
            raise ValidationError("Describe the change and choose a supported response style.")
        current = self.repository.get_version(project.current_version_id or "")
        if current is None or project.prepared_document_count < 1:
            raise NotReadyError("Add documents and test your application first.")
        supported = self._is_supported_response_improvement(request)
        if not supported:
            return ImprovementProposal(
                request,
                response_style,
                "This change is not supported in the current Ask My Documents version.",
                supported=False,
                participant_message=(
                    "Try an answer-focused change such as clearer wording, more detail, "
                    "a complete list, a summary, a comparison, or better source citations."
                ),
            )
        return ImprovementProposal(
            request,
            response_style,
            f"Use a {response_style} response style and apply this guidance: {request}",
        )

    @transactional
    def apply_improvement(
        self, project_id: str, request: str, *, response_style: str
    ) -> ProjectVersion:
        proposal = self.propose_improvement(project_id, request, response_style=response_style)
        if not proposal.supported:
            raise ValidationError(
                proposal.participant_message or "That improvement is not supported yet."
            )
        project = self._authorized_project(project_id)
        current = self.repository.get_version(project.current_version_id or "")
        if current is None:
            raise NotReadyError("Add documents and test your application first.")
        version = replace(
            current,
            id=self.ids.new_id(),
            number=self.repository.version_count(project.id) + 1,
            assistant_config={
                **current.assistant_config,
                "response_style": proposal.response_style,
                "response_guidance": proposal.request,
                "improvement_request": proposal.request,
            },
            created_at=self.clock.now(),
        )
        self.repository.save_version(version)
        chunks = self.repository.list_chunks(project.id, current.id)
        for asset_id in current.asset_ids:
            self.repository.replace_chunks(
                asset_id,
                [
                    replace(
                        chunk,
                        id=hashlib.sha256(f"{version.id}:{chunk.id}".encode()).hexdigest(),
                        project_version_id=version.id,
                    )
                    for chunk in chunks
                    if chunk.asset_id == asset_id
                ],
            )
        project.current_version_id = version.id
        self._invalidate_draft_test(project)
        self.repository.save_project(project)
        self._lifecycle(project.id, "DRAFT_IMPROVED", {"version_id": version.id})
        return version

    def improve_application(
        self, project_id: str, request: str, *, answer_length: str
    ) -> ProjectVersion:
        """Compatibility wrapper for callers created before adaptive response styles."""
        style = {"short": "concise", "standard": "balanced"}.get(answer_length)
        if style is None:
            raise ValidationError("Choose a supported response style.")
        return self.apply_improvement(project_id, request, response_style=style)

    def get_application_specification(self, project_id: str) -> ApplicationSpecification:
        return self.lifecycle.specification(project_id)

    @transactional
    def evaluate_working_version(self, project_id: str) -> EvaluationReport:
        return self.lifecycle.evaluate(project_id)

    @transactional
    def test_advisor(self, project_id: str, value: AdvisorInput) -> AdvisorResult:
        return self.advisor.test(project_id, value)

    def confirm_advisor_test_success(self, project_id: str) -> Project:
        return self.advisor.confirm_test(project_id)

    @transactional
    def apply_advisor_improvement(
        self,
        project_id: str,
        request: str,
        *,
        title: str | None = None,
        recommendation_style: str = "direct",
    ) -> ProjectVersion:
        return self.advisor.improve(
            project_id,
            request,
            title=title,
            recommendation_style=recommendation_style,
        )

    @transactional
    def improve_failed_evaluation(self, project_id: str) -> Project:
        return self.lifecycle.improve_failed_evaluation(project_id)

    @transactional
    def propose_ui_improvement(
        self,
        project_id: str,
        request: str,
        *,
        title: str,
        instructions: str,
        question_position: str,
        response_layout: str,
        citation_presentation: str,
        display_density: str,
    ) -> UIImprovementProposal:
        project = self._authorized_project(project_id)
        request = self._journey_text(request)
        title = self._journey_text(title)
        instructions = self._journey_text(instructions)
        if not request or not title or not instructions:
            raise ValidationError("Describe the change and provide a title and instructions.")
        if project.prepared_document_count < 1 or not project.current_version_id:
            raise NotReadyError("Build your Working Version before improving its experience.")
        choices = {
            "question_position": ({"top", "bottom"}, question_position),
            "response_layout": ({"prose", "list", "table"}, response_layout),
            "citation_presentation": ({"compact", "expanded"}, citation_presentation),
            "display_density": ({"concise", "balanced", "detailed"}, display_density),
        }
        if any(value not in allowed for allowed, value in choices.values()):
            raise ValidationError("Choose only the available look and experience options.")
        ui_config = {
            "title": title,
            "instructions": instructions,
            "question_position": question_position,
            "response_layout": response_layout,
            "citation_presentation": citation_presentation,
            "display_density": display_density,
        }
        if not self._is_supported_ui_improvement(request):
            return UIImprovementProposal(
                request,
                ui_config,
                "This look and experience change is not supported yet.",
                supported=False,
                participant_message=(
                    "You can change the title, instructions, question-box position, answer layout, "
                    "citation presentation, and display detail using the options shown."
                ),
            )
        return UIImprovementProposal(
            request,
            ui_config,
            (
                f"Show “{title}” with the selected instructions, place the question box at the "
                f"{question_position}, use a {response_layout} answer layout, show citations in "
                f"{citation_presentation} form, and use a {display_density} display."
            ),
        )

    @transactional
    def apply_ui_improvement(
        self,
        project_id: str,
        request: str,
        *,
        title: str,
        instructions: str,
        question_position: str,
        response_layout: str,
        citation_presentation: str,
        display_density: str,
    ) -> ProjectVersion:
        proposal = self.propose_ui_improvement(
            project_id,
            request,
            title=title,
            instructions=instructions,
            question_position=question_position,
            response_layout=response_layout,
            citation_presentation=citation_presentation,
            display_density=display_density,
        )
        if not proposal.supported:
            raise ValidationError(
                proposal.participant_message or "That look and experience change is not supported."
            )
        project = self._authorized_project(project_id)
        current = self.repository.get_version(project.current_version_id or "")
        if current is None:
            raise NotReadyError("Build your Working Version first.")
        version = replace(
            current,
            id=self.ids.new_id(),
            number=self.repository.version_count(project.id) + 1,
            assistant_config={
                **current.assistant_config,
                **{f"ui_{key}": value for key, value in proposal.ui_config.items()},
                "ui_improvement_request": proposal.request,
            },
            created_at=self.clock.now(),
        )
        self.repository.save_version(version)
        chunks = self.repository.list_chunks(project.id, current.id)
        for asset_id in current.asset_ids:
            self.repository.replace_chunks(
                asset_id,
                [
                    replace(
                        chunk,
                        id=hashlib.sha256(f"{version.id}:{chunk.id}".encode()).hexdigest(),
                        project_version_id=version.id,
                    )
                    for chunk in chunks
                    if chunk.asset_id == asset_id
                ],
            )
        project.current_version_id = version.id
        self._invalidate_draft_test(project)
        self.repository.save_project(project)
        self._lifecycle(project.id, "WORKING_VERSION_UI_IMPROVED", {"version_id": version.id})
        return version

    def run_application(self, project_id: str, question: str) -> Answer:
        project = self._authorized_project(project_id)
        if project.guided_test_count < 1 or project.has_blocking_preparation_error:
            raise NotReadyError("Test your current application successfully before running it.")
        answer = self.ask_question(project_id, question)
        if not answer.abstained:
            project.metadata["run_version_id"] = project.current_version_id or ""
            project.updated_at = self.clock.now()
            self.repository.save_project(project)
            self._lifecycle(
                project.id, "APPLICATION_RUN", {"version_id": project.current_version_id or ""}
            )
        return answer

    @transactional
    def publish_working_application(self, project_id: str) -> Publication:
        project = self._authorized_project(project_id)
        if not project.current_version_id or project.guided_test_count < 1:
            raise NotReadyError("Test your Working Version successfully before publishing it.")
        self.confirm_readiness(project_id)
        publication = self.deploy(
            project_id, idempotency_key=f"working-{project.id}-{project.current_version_id}"
        )
        project = self._authorized_project(project_id)
        project.metadata["publication_id"] = publication.id
        self.repository.save_project(project)
        return publication

    @transactional
    def approve_working_version(self, project_id: str) -> ApprovedVersionSnapshot:
        return self.lifecycle.approve(project_id)

    def get_approved_version(self, snapshot_id: str) -> ApprovedVersionSnapshot:
        snapshot = self.repository.get_approved_version(snapshot_id)
        if snapshot is None:
            raise AuthorizationError("That Approved Version is not available.")
        project = self._authorized_project(snapshot.specification.project_id)
        if (
            snapshot.owner_user_id != project.owner_user_id
            or snapshot.workspace_id != project.workspace_id
        ):
            raise AuthorizationError("That Approved Version is not available.")
        return snapshot

    def latest_approved_version(self, project_id: str) -> ApprovedVersionSnapshot | None:
        project = self._authorized_project(project_id)
        snapshots = self.repository.list_approved_versions(project.id)
        if not snapshots:
            return None

        def version_number(item: ApprovedVersionSnapshot) -> int:
            version = self.repository.get_version(item.specification.project_version_id)
            return version.number if version else -1

        return max(snapshots, key=version_number)

    @transactional
    def generate_application_export(self, project_id: str) -> ExportPackage:
        project = self._authorized_project(project_id)
        approved = self.latest_approved_version(project.id)
        if (
            approved is None
            or approved.specification.project_version_id != project.current_version_id
        ):
            raise NotReadyError(
                "Approve the current tested Working Version before getting its application code."
            )
        export_version = len(self.repository.list_export_packages(project.id)) + 1
        built = build_export(approved, export_version, self.clock.now())
        safe_name = re.sub(r"[^a-z0-9]+", "-", approved.specification.name.lower()).strip("-")
        filename = f"{safe_name or 'ask-my-documents'}-v{export_version}.zip"
        storage_key = self.storage.put(
            workspace_id=project.workspace_id,
            project_id=project.id,
            content=built.content,
        )
        package = ExportPackage(
            id=self.ids.new_id(),
            approved_snapshot_id=approved.id,
            owner_user_id=project.owner_user_id,
            workspace_id=project.workspace_id,
            project_id=project.id,
            project_version_id=approved.specification.project_version_id,
            export_version=export_version,
            status=ExportPackageStatus.READY,
            storage_key=storage_key,
            filename=filename,
            sha256=built.sha256,
            created_at=self.clock.now(),
        )
        self.repository.save_export_package(package)
        self._lifecycle(
            project.id,
            "APPLICATION_EXPORT_READY",
            {"version_id": package.project_version_id},
        )
        return package

    def download_application_export(self, package_id: str) -> ExportDownload:
        package = self.repository.get_export_package(package_id)
        if package is None:
            raise AuthorizationError("That application package is not available.")
        project = self._authorized_project(package.project_id)
        if (
            package.owner_user_id != project.owner_user_id
            or package.workspace_id != project.workspace_id
        ):
            raise AuthorizationError("That application package is not available.")
        content = self.storage.get(
            workspace_id=package.workspace_id,
            project_id=package.project_id,
            storage_key=package.storage_key,
        )
        if hashlib.sha256(content).hexdigest() != package.sha256:
            raise ValidationError(
                "The application package could not be verified. Generate it again."
            )
        return ExportDownload(package, content)

    def _invalidate_draft_test(self, project: Project) -> None:
        self.lifecycle.invalidate(project)

    @staticmethod
    def _application_type(project: Project) -> ApplicationType:
        return LifecycleCoordinator.application_type(project)

    @staticmethod
    def _require_document_project(project: Project) -> None:
        if LifecycleCoordinator.application_type(project) != ApplicationType.ASK_MY_DOCUMENTS:
            raise ValidationError("This action belongs to Ask My Documents.")

    def get_my_project(self, project_id: str) -> Project:
        return self._authorized_project(project_id)

    def list_documents(self, project_id: str) -> list[Asset]:
        project = self._authorized_project(project_id)
        return self.repository.list_assets(project.id)

    def latest_publication(self, project_id: str) -> Publication | None:
        project = self._authorized_project(project_id)
        # Existing publications predate journey metadata; their durable lifecycle evidence
        # keeps them discoverable without a data rewrite or changing the snapshot.
        events = [
            event
            for event in self.repository.list_lifecycle_events()
            if event.project_id == project.id and event.event_type == "PUBLICATION_CREATED"
        ]
        candidates: list[tuple[int, Publication]] = []
        for event in events:
            publication_id = event.safe_metadata.get("publication_id")
            if publication_id:
                publication = self._owned_publication(publication_id)
                version = self.repository.get_version(publication.project_version_id)
                if version:
                    candidates.append((version.number, publication))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    def add_and_prepare_document(self, project_id: str, filename: str, content: bytes) -> Asset:
        """Complete the participant's single Add Documents action."""

        asset = self.upload_document(project_id, filename, content)
        return self.prepare_document(project_id, asset.id)

    @transactional
    def upload_document(self, project_id: str, filename: str, content: bytes) -> Asset:
        project = self._authorized_project(project_id)
        self._require_document_project(project)
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

    def prepare_document(self, project_id: str, asset_id: str, *, refresh: bool = False) -> Asset:
        project = self._authorized_project(project_id)
        self._require_document_project(project)
        self._limit(project.owner_user_id, "prepare", self.settings.preparation_rate_limit)
        asset = self._authorized_asset(project, asset_id)
        if asset.status == AssetStatus.READY and not refresh:
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
            project.has_blocking_preparation_error = any(
                item.status == AssetStatus.FAILED
                for item in self.repository.list_assets(project.id)
            )
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
        self._require_document_project(project)
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
                version = self.repository.get_version(project.current_version_id)
                config = dict(version.assistant_config) if version is not None else {}
                legacy_style = "concise" if config.get("answer_length") == "short" else "balanced"
                response = self.generation.generate(
                    GenerationRequest(
                        clean_question,
                        contexts,
                        response_style=config.get("response_style", legacy_style),  # type: ignore[arg-type]
                        response_guidance=config.get("response_guidance", ""),
                        complete_answer_required=self._is_complete_request(clean_question),
                    )
                )
            except ProviderCallError as exc:
                self._provider_failure(project, correlation_id, "TEST_ASSISTANT", exc)
                raise
        self._usage(
            project,
            correlation_id,
            "ABSTAINED" if not contexts else "SUCCEEDED",
            usage=response.usage,
        )
        if guided:
            self._clear_pending_test(project)
            project.metadata["pending_test_correlation_id"] = correlation_id
            project.metadata["pending_test_version_id"] = project.current_version_id or ""
            project.metadata["pending_test_question_summary"] = hashlib.sha256(
                clean_question.encode()
            ).hexdigest()[:12]
            project.metadata["pending_test_asset_ids"] = ",".join(
                sorted({context.document_id for context in contexts})
            )
            project.metadata["pending_test_abstained"] = str(response.abstained).lower()
            self.repository.save_project(project)
        return Answer(response.answer, response.citations, response.abstained, correlation_id)

    @transactional
    def confirm_test_success(self, project_id: str, correlation_id: str) -> Project:
        return self.lifecycle.confirm_participant_validation(project_id, correlation_id)

    @transactional
    def record_test_feedback(self, project_id: str, correlation_id: str, feedback: str) -> Project:
        project = self._authorized_project(project_id)
        if project.metadata.get("pending_test_correlation_id") != correlation_id:
            raise ValidationError("Test the current Working Version before adding feedback.")
        feedback = self._journey_text(feedback)
        if not feedback:
            raise ValidationError("Describe what needs improvement.")
        project.metadata["improvement_feedback"] = feedback
        self._invalidate_draft_test(project)
        self.repository.save_project(project)
        self._lifecycle(project.id, "TEST_NEEDS_IMPROVEMENT", {})
        return project

    @staticmethod
    def _clear_pending_test(project: Project) -> None:
        LifecycleCoordinator.clear_pending_test(project)

    @transactional
    def confirm_readiness(self, project_id: str) -> Project:
        project = self._authorized_project(project_id)
        project.readiness_confirmed = True
        result = assess_readiness(project)
        if not result.ready:
            project.readiness_confirmed = False
            raise NotReadyError("Complete the readiness steps before publishing your application.")
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
            if (
                existing.owner_user_id != self.auth.current_user().id
                or existing.project_id != project.id
            ):
                raise AuthorizationError("You do not have permission to publish this project.")
            return existing
        if project.status != ProjectStatus.READY or not assess_readiness(project).ready:
            raise NotReadyError("Complete the readiness steps before publishing your application.")
        if project.current_version_id is None:
            raise NotReadyError("Prepare your documents before publishing your application.")
        version = self.repository.get_version(project.current_version_id)
        if version is None:
            raise NotReadyError("Prepare your documents again before publishing.")
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
            config = dict(publication.assistant_config)
            legacy_style = "concise" if config.get("answer_length") == "short" else "balanced"
            response = self.generation.generate(
                GenerationRequest(
                    clean_question,
                    contexts,
                    response_style=config.get("response_style", legacy_style),  # type: ignore[arg-type]
                    response_guidance=config.get("response_guidance", ""),
                    complete_answer_required=self._is_complete_request(clean_question),
                )
            )
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
        current = self.repository.get_version(project.current_version_id or "")
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
            assistant_config=dict(current.assistant_config)
            if current
            else {
                "template": "ASK_MY_DOCUMENTS",
                "behavioral_schema": "ask-my-documents.behavior.v1",
                "policy": "GROUNDED_OR_ABSTAIN",
                "spec_problem": project.metadata.get("problem", project.description),
                "spec_users": project.metadata.get("users", ""),
                "spec_outcome": project.metadata.get("outcome", ""),
            },
            created_at=self.clock.now(),
        )
        prepared_chunks: dict[str, list[DocumentChunk]] = {}
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
            prepared_chunks[asset.id] = chunks
        # Provider usage is already recorded; switch the draft only after all work succeeds.
        with self.repository.transaction():
            self.repository.save_version(version)
            for asset_id, chunks in prepared_chunks.items():
                self.repository.replace_chunks(asset_id, chunks)
            project.current_version_id = version.id
            self._invalidate_draft_test(project)
            self.repository.save_project(project)
        return version

    def _retrieve(self, project: Project, question: str) -> list[RetrievedContext]:
        if project.current_version_id is None:
            return []
        query_terms = self._question_terms(question)
        if not query_terms:
            return []
        candidates = self.repository.list_chunks(project.id, project.current_version_id)
        safe_texts = set(remove_untrusted_instruction_chunks([chunk.text for chunk in candidates]))
        scored: list[tuple[int, DocumentChunk]] = []
        for chunk in candidates:
            if chunk.text not in safe_texts:
                continue
            chunk_terms = self._normalized_terms(chunk.text)
            score = len(query_terms & chunk_terms)
            required = 1 if len(query_terms) == 1 else max(2, (len(query_terms) + 1) // 2)
            if score >= required:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].source_name, item[1].position))
        if self._is_complete_request(question) and scored:
            matched_assets = {chunk.asset_id for _score, chunk in scored}
            complete_chunks = sorted(
                (
                    chunk
                    for chunk in candidates
                    if chunk.asset_id in matched_assets and chunk.text in safe_texts
                ),
                key=lambda chunk: (chunk.source_name, chunk.position),
            )[:12]
            return [
                RetrievedContext(chunk.asset_id, chunk.source_name, chunk.id, chunk.text)
                for chunk in complete_chunks
            ]
        return [
            RetrievedContext(chunk.asset_id, chunk.source_name, chunk.id, chunk.text)
            for _score, chunk in scored[:3]
        ]

    def _retrieve_publication(
        self, publication: Publication, question: str
    ) -> list[RetrievedContext]:
        query_terms = self._question_terms(question)
        if not query_terms:
            return []
        safe_texts = set(
            remove_untrusted_instruction_chunks([chunk.text for chunk in publication.chunks])
        )
        scored = []
        for chunk in publication.chunks:
            if chunk.text not in safe_texts:
                continue
            score = len(query_terms & self._normalized_terms(chunk.text))
            required = 1 if len(query_terms) == 1 else max(2, (len(query_terms) + 1) // 2)
            if score >= required:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].source_name, item[1].position))
        if self._is_complete_request(question) and scored:
            matched_assets = {chunk.asset_id for _score, chunk in scored}
            selected = [
                chunk
                for chunk in publication.chunks
                if chunk.asset_id in matched_assets and chunk.text in safe_texts
            ][:12]
        else:
            selected = [chunk for _score, chunk in scored[:3]]
        return [
            RetrievedContext(
                chunk.asset_id,
                chunk.source_name,
                f"published:{chunk.asset_id}:{chunk.position}",
                chunk.text,
            )
            for chunk in selected
        ]

    @staticmethod
    def _normalized_terms(text: str) -> set[str]:
        terms: set[str] = set()
        for raw in re.findall(r"[a-z0-9]+", text.lower()):
            if len(raw) <= 2:
                continue
            term = raw[:-3] + "y" if raw.endswith("ies") and len(raw) > 4 else raw
            if term.endswith("s") and not term.endswith("ss") and len(term) > 4:
                term = term[:-1]
            if term.endswith("ed") and len(term) > 5:
                term = term[:-2]
                if term.endswith(("c", "g", "r", "s", "v", "z")):
                    term += "e"
            terms.add(term)
        return terms

    @classmethod
    def _question_terms(cls, question: str) -> set[str]:
        return {term for term in cls._normalized_terms(question) if term not in _STOPWORDS}

    @classmethod
    def _is_complete_request(cls, question: str) -> bool:
        return bool(cls._normalized_terms(question) & _COMPLETE_REQUEST_TERMS)

    @classmethod
    def _is_supported_response_improvement(cls, request: str) -> bool:
        request_terms = cls._normalized_terms(request)
        unsupported_terms = {
            "accounting",
            "action",
            "audio",
            "email",
            "integration",
            "send",
            "system",
            "tool",
            "voice",
            "workflow",
        }
        if request_terms & unsupported_terms:
            return False
        supported_terms = {
            "answer",
            "brief",
            "citation",
            "cite",
            "clear",
            "clearly",
            "compare",
            "comparison",
            "complete",
            "concise",
            "detail",
            "detailed",
            "explain",
            "explanatory",
            "list",
            "response",
            "short",
            "source",
            "summary",
            "summarize",
            "wording",
        }
        return bool(request_terms & supported_terms)

    @classmethod
    def _is_supported_ui_improvement(cls, request: str) -> bool:
        request_terms = cls._normalized_terms(request)
        unsupported_terms = {
            "animation",
            "audio",
            "code",
            "css",
            "html",
            "javascript",
            "plugin",
            "theme",
            "video",
            "voice",
        }
        supported_terms = {
            "answer",
            "box",
            "citation",
            "concise",
            "detail",
            "detailed",
            "display",
            "easier",
            "instruction",
            "layout",
            "list",
            "question",
            "response",
            "simple",
            "source",
            "table",
            "title",
        }
        return not bool(request_terms & unsupported_terms) and bool(request_terms & supported_terms)

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
