"""Guided Phase 2 Streamlit journey."""

from __future__ import annotations

import streamlit as st

from app.application import M0Service, OperationsService, build_runtime_foundation
from app.application.errors import AqlioError, ShareAccessError
from app.config import Settings, SettingsError
from app.domain import AssetStatus, ProjectStatus
from app.ports import AuthenticationRequired, ProviderCallError


@st.cache_resource
def _service() -> M0Service:
    settings = Settings.from_env()

    def claims_loader():  # type: ignore[no-untyped-def]
        if not getattr(st.user, "is_logged_in", False):
            return {}
        return dict(st.user)

    foundation = build_runtime_foundation(settings, claims_loader=claims_loader)
    return M0Service(
        settings=foundation.settings,
        auth=foundation.auth,
        clock=foundation.clock,
        ids=foundation.ids,
        generation=foundation.generation,
        embedding=foundation.embedding,
        repository=foundation.state,
        storage=foundation.storage,
        rate_limiter=foundation.rate_limiter,
    )


def render_home() -> None:
    st.set_page_config(page_title="Aqlio", page_icon="✨", layout="centered")
    try:
        service = _service()
    except (SettingsError, ValueError):
        st.error("Aqlio could not start safely. Please contact support.")
        return
    share_token = st.query_params.get("share")
    if share_token:
        _render_shared(service, share_token)
        return
    if service.settings.auth_mode == "oidc" and not getattr(st.user, "is_logged_in", False):
        st.title("Welcome to Aqlio")
        st.write("Sign in to continue to your workspace.")
        if st.button("Sign in", type="primary"):
            st.login("google")
        return
    try:
        user = service.auth.current_user()
        workspace = service.resolve_workspace()
    except (AqlioError, AuthenticationRequired):
        st.error("Aqlio could not start safely. Please contact support.")
        return
    if st.query_params.get("operations") == "1":
        _render_operations(service)
        return
    st.title("Welcome to Aqlio")
    st.caption(workspace.name)
    st.write(f"Hello, {user.display_name}. Build a useful assistant from your documents.")
    projects = service.list_my_projects()
    if not projects:
        _render_create_project(service)
        return
    project_ids = {project.name: project.id for project in projects}
    selected_id = st.session_state.get("project_id")
    default_name = next(
        (name for name, project_id in project_ids.items() if project_id == selected_id),
        next(iter(project_ids)),
    )
    selected_name = st.selectbox(
        "My Projects", project_ids, index=list(project_ids).index(default_name)
    )
    project_id = project_ids[selected_name]
    st.session_state["project_id"] = project_id
    _render_project(service, project_id)


def _render_create_project(service: M0Service) -> None:
    st.subheader("Create your first project")
    with st.form("create-project"):
        name = st.text_input("Project name", placeholder="Employee Handbook Assistant")
        description = st.text_area("What should this assistant help with? (optional)")
        submitted = st.form_submit_button("Create Project", type="primary")
    if submitted:
        try:
            project = service.create_project(name, description)
            st.session_state["project_id"] = project.id
            st.rerun()
        except AqlioError as exc:
            st.error(str(exc))


def _render_project(service: M0Service, project_id: str) -> None:
    try:
        project = service.get_my_project(project_id)
    except AqlioError as exc:
        st.error(str(exc))
        return
    st.header(project.name)
    st.caption("Ask My Documents")
    st.write(project.description or "Add documents, test the answers, and deploy when ready.")
    _render_documents(service, project.id)
    _render_testing(service, project.id)
    _render_readiness(service, project.id)


def _render_documents(service: M0Service, project_id: str) -> None:
    st.subheader("1. Add Documents")
    uploads = st.file_uploader(
        "Add PDF, DOCX, or TXT documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
    )
    if st.button("Add Documents", disabled=not uploads):
        for upload in uploads or []:
            try:
                service.upload_document(project_id, upload.name, upload.getvalue())
                st.success(f"Added {upload.name}.")
            except (AqlioError, ProviderCallError) as exc:
                st.error(str(exc))
        st.rerun()
    documents = service.list_documents(project_id)
    for document in documents:
        status = {
            AssetStatus.UPLOADED: "Ready to prepare",
            AssetStatus.PREPARING: "Preparing",
            AssetStatus.READY: "Ready",
            AssetStatus.FAILED: "Unable to prepare",
        }[document.status]
        st.write(f"{document.original_name} — {status}")
        if document.participant_message and document.status == AssetStatus.FAILED:
            st.warning(document.participant_message)
        if document.status != AssetStatus.READY and st.button(
            "Prepare Document", key=f"prepare-{document.id}"
        ):
            try:
                service.prepare_document(project_id, document.id)
                st.success("Your document is ready.")
                st.rerun()
            except (AqlioError, ProviderCallError) as exc:
                st.error(str(exc))


def _render_testing(service: M0Service, project_id: str) -> None:
    st.subheader("2. Test Assistant")
    documents = service.list_documents(project_id)
    if not any(document.status == AssetStatus.READY for document in documents):
        st.info("Prepare at least one document before testing your assistant.")
        return
    with st.form("test-assistant"):
        question = st.text_input(
            "Ask a test question", placeholder="When can employees use annual leave?"
        )
        guided = st.checkbox("Count this as my guided test", value=True)
        ask = st.form_submit_button("Run Test", type="primary")
    if ask:
        try:
            st.session_state["last_answer"] = service.ask_question(
                project_id, question, guided=guided
            )
        except (AqlioError, ProviderCallError) as exc:
            st.error(str(exc))
    answer = st.session_state.get("last_answer")
    if not answer:
        return
    if answer.abstained:
        st.warning(
            "I couldn't find enough information in your documents to answer that confidently."
        )
    else:
        st.write(answer.text)
        st.markdown("**Sources**")
        for citation in answer.citations:
            st.write(f"- {citation.document_name} — source passage")


def _render_readiness(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    st.subheader("3. Ready to Deploy")
    checks = (
        (project.valid_document_count > 0, "Documents added"),
        (project.prepared_document_count > 0, "Documents prepared"),
        (project.guided_test_count > 0, "Assistant tested"),
        (not project.has_blocking_preparation_error, "No blocking document issues"),
    )
    for complete, label in checks:
        st.write(f"{'✓' if complete else '○'} {label}")
    confirmed = st.checkbox("I am ready to deploy this assistant")
    if st.button("Confirm Readiness", disabled=not confirmed):
        try:
            service.confirm_readiness(project_id)
            st.success("Your assistant is ready to deploy.")
            st.rerun()
        except AqlioError as exc:
            st.error(str(exc))
    project = service.get_my_project(project_id)
    if st.button("Deploy", type="primary", disabled=project.status != ProjectStatus.READY):
        try:
            publication = service.deploy(project_id, idempotency_key=f"ui-{project_id}")
            st.session_state["publication_id"] = publication.id
            st.success("Project successfully deployed.")
            st.rerun()
        except AqlioError as exc:
            st.error(str(exc))
    publication_id = st.session_state.get("publication_id")
    if publication_id:
        _render_publication(service, publication_id)


def _render_publication(service: M0Service, publication_id: str) -> None:
    st.subheader("4. My Assistant")
    if st.button("Open Assistant"):
        try:
            assistant = service.open_private(publication_id)
            st.success(f"{assistant.project_name} is running.")
        except AqlioError as exc:
            st.error(str(exc))
    if st.button("Share"):
        try:
            receipt = service.enable_link_sharing(publication_id)
            st.session_state["share_token"] = receipt.token
        except AqlioError as exc:
            st.error(str(exc))
    token = st.session_state.get("share_token")
    if token:
        st.info(f"Share path: ?share={token}")
        if st.button("Stop Sharing"):
            service.revoke_sharing(publication_id)
            st.session_state.pop("share_token", None)
            st.success("Sharing has stopped.")


def _render_shared(service: M0Service, token: str) -> None:
    st.title("My Assistant")
    try:
        assistant = service.open_shared(token)
    except ShareAccessError as exc:
        st.error(str(exc))
        return
    st.header(assistant.project_name)
    st.write("This assistant is available through a shared link.")
    st.caption("Sources included: " + ", ".join(assistant.source_names))
    with st.form("shared-question"):
        question = st.text_input("Ask a question")
        submitted = st.form_submit_button("Ask", type="primary")
    if submitted:
        try:
            answer = service.ask_shared(token, question)
            if answer.abstained:
                st.warning(
                    "I couldn't find enough information in the documents to answer that "
                    "confidently."
                )
            else:
                st.write(answer.text)
                st.markdown("**Sources**")
                for citation in answer.citations:
                    st.write(f"- {citation.document_name} — source passage")
        except (AqlioError, ProviderCallError) as exc:
            st.error(str(exc))


def _render_operations(service: M0Service) -> None:
    st.title("Aqlio Operations")
    operations = OperationsService(service.auth, service.repository, service.clock)
    try:
        snapshot = operations.snapshot()
    except AqlioError as exc:
        st.error(str(exc))
        return
    st.metric("Users", snapshot.user_count)
    st.metric("Projects", snapshot.project_count)
    st.metric("Failed document preparations", snapshot.failed_preparation_count)
    st.metric("Usage events", snapshot.usage_event_count)
    st.metric("Failed assistant runs", snapshot.failed_ai_run_count)
    st.metric("Shared assistants", snapshot.shared_count)
    st.metric("Revoked links", snapshot.revoked_count)
    st.write(f"Assistant service: {snapshot.provider_status}")
    st.write(f"Configured assistant model: {snapshot.configured_model}")
    st.write(f"Recent service failures: {snapshot.recent_provider_failures}")
    st.write(f"Last successful service call: {snapshot.last_successful_call}")
