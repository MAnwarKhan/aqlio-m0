"""Guided idea-to-application participant journey."""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode, urlsplit, urlunsplit

import streamlit as st
import streamlit.components.v1 as components

from app.application import M0Service, OperationsService, build_runtime_foundation
from app.application.errors import AqlioError, ShareAccessError
from app.application.journey import next_step, project_status
from app.application.m0_service import Answer
from app.config import Settings, SettingsError
from app.domain import AssetStatus, ProjectStatus, PublicationVisibility
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
        workspace = service.resolve_workspace()
    except (AqlioError, AuthenticationRequired):
        st.error("Aqlio could not start safely. Please contact support.")
        return
    if st.query_params.get("operations") == "1":
        _render_operations(service)
        return
    st.title("Turn your idea into a working AI solution.")
    st.caption(workspace.name)
    st.write("Aqlio guides you from idea to a working AI application—one simple step at a time.")
    if service.settings.auth_mode == "development":
        st.warning("Shared demo workspace: use sample ideas and documents only.")
    if service.settings.persistence_mode == "in_memory":
        st.warning(
            "Temporary demo: progress is kept while this demo is running "
            "and may disappear when it restarts."
        )
    elif service.settings.storage_mode == "in_memory":
        st.warning("Project details are saved, but uploaded files may disappear on restart.")
    else:
        st.caption("Your project progress is saved automatically.")
    if service.settings.ai_mode == "fake":
        st.caption(
            "Demo answers and idea guidance are deterministic examples, not a live AI assessment."
        )
    if st.button("+ Start New Project"):
        st.session_state["project_id"] = None
        st.session_state["new_project"] = True
        st.rerun()
    if st.button("My Projects"):
        st.session_state["project_id"] = None
        st.session_state["new_project"] = False
        st.rerun()
    if st.session_state.get("new_project"):
        _render_create_project(service)
        return
    project_id = st.session_state.get("project_id")
    if project_id:
        _render_project(service, project_id)
        return
    st.header("My Projects")
    projects = service.list_my_projects()
    if not projects:
        _render_create_project(service)
    for project in projects:
        with st.container(border=True):
            st.subheader(project.name)
            st.caption(project_status(project))
            if st.button("Continue Building", key=f"continue-{project.id}"):
                st.session_state["project_id"] = project.id
                st.session_state[f"step-{project.id}"] = next_step(project)
                st.rerun()


def _go(project_id: str, step: str) -> None:
    st.session_state[f"step-{project_id}"] = step
    st.rerun()


def _render_create_project(service: M0Service) -> None:
    st.subheader("My Idea")
    st.write("Start with an idea. You can refine it as you go.")
    with st.form("create-project"):
        idea = st.text_area("What would you like to build or solve with AI?", max_chars=2000)
        evaluate = st.form_submit_button("Evaluate My Idea")
        submitted = st.form_submit_button("Continue", type="primary")
    if submitted or evaluate:
        try:
            project = service.create_idea(idea)
            st.session_state["project_id"] = project.id
            st.session_state["new_project"] = False
            if evaluate:
                try:
                    service.evaluate_idea(project.id)
                except (AqlioError, ProviderCallError) as exc:
                    st.session_state[f"notice-{project.id}"] = str(exc)
            _go(project.id, "define")
        except AqlioError as exc:
            st.error(str(exc))


def _render_project(service: M0Service, project_id: str) -> None:
    try:
        project = service.get_my_project(project_id)
        st.header(project.name)
        st.caption(project_status(project))
        notice = st.session_state.pop(f"notice-{project_id}", None)
        if notice:
            st.warning(notice)
        step = st.session_state.get(f"step-{project_id}", next_step(project))
        if step in {"test", "improve", "run"} and not project.prepared_document_count:
            step = next_step(project)
        if step in {"improve", "run"} and not project.guided_test_count:
            step = "test"
        if step == "define":
            _render_definition(service, project_id)
        elif step == "build":
            _render_documents(service, project_id)
        elif step == "improve":
            _render_improve(service, project_id)
        else:
            _render_testing(service, project_id, running=step == "run")
        publication = service.latest_publication(project_id)
        if publication:
            _render_publication(service, publication.id)
    except (AqlioError, ProviderCallError) as exc:
        st.error(str(exc))


_DEFINITION_FIELDS = {
    "idea": "My Idea",
    "problem": "What problem are you solving?",
    "users": "Who is this for?",
    "outcome": "What would a useful result look like?",
    "ai_role": "What should the AI help people do?",
    "information": "What information will it need?",
}


def _render_definition(service: M0Service, project_id: str) -> None:
    st.subheader("Define My Solution")
    st.write("Turn your idea into a small first version. Short answers are enough.")
    project = service.get_my_project(project_id)

    def save_field(field: str, key: str) -> None:
        try:
            service.update_definition(project_id, {field: st.session_state[key]})
        except AqlioError as exc:
            st.session_state[f"notice-{project_id}"] = str(exc)

    for field, label in _DEFINITION_FIELDS.items():
        key = f"definition-{project_id}-{field}"
        st.text_area(
            label,
            value=project.metadata.get(field, ""),
            key=key,
            max_chars=2000,
            on_change=save_field,
            args=(field, key),
        )
    if st.button("Evaluate My Idea"):
        service.evaluate_idea(project_id)
        st.rerun()
    evaluation = project.metadata.get("idea_evaluation")
    if evaluation:
        st.caption(
            "Optional guidance only. Improve My Idea by editing the fields above, or continue."
        )
        st.text(evaluation)
    if st.button("Start Building", type="primary"):
        service.define_solution(project_id)
        _go(project_id, "build")


def _render_documents(service: M0Service, project_id: str) -> None:
    st.subheader("Build")
    st.write("Build an AI Assistant using your documents—the first supported Aqlio solution.")
    st.caption(
        "Add documents your assistant should understand. "
        "Selection starts preparation automatically."
    )
    uploads = st.file_uploader(
        "Add PDF, DOCX, or TXT documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key=f"uploads-{project_id}",
    )
    attempts_key = f"upload-attempts-{project_id}"
    attempts = st.session_state.setdefault(attempts_key, {})
    prepared_now = False
    for upload in uploads or []:
        content = upload.getvalue()
        fingerprint = hashlib.sha256(upload.name.encode() + content).hexdigest()
        if fingerprint not in attempts:
            try:
                with st.spinner(f"Preparing {upload.name}…"):
                    service.add_and_prepare_document(project_id, upload.name, content)
                attempts[fingerprint] = ""
                prepared_now = True
            except (AqlioError, ProviderCallError) as exc:
                attempts[fingerprint] = str(exc)
        if attempts[fingerprint]:
            st.error(f"{upload.name}: {attempts[fingerprint]}")
            if st.button("Try Again", key=f"retry-upload-{project_id}-{fingerprint}"):
                del attempts[fingerprint]
                st.rerun()
    if prepared_now:
        st.rerun()
    for document in service.list_documents(project_id):
        ready = document.status == AssetStatus.READY
        st.write(
            f"{'✓' if ready else '○'} {document.original_name} — "
            f"{'Ready' if ready else 'Needs attention'}"
        )
        if not ready:
            st.warning(
                document.participant_message or "We couldn't finish preparing this document."
            )
            if st.button("Try Again", key=f"prepare-{document.id}"):
                service.prepare_document(project_id, document.id)
                st.session_state[attempts_key] = {}
                st.rerun()
    project = service.get_my_project(project_id)
    if project.prepared_document_count:
        st.success("Documents added ✓ · Documents prepared ✓")
        st.write("Your documents are ready. Next, try a question your users might ask.")
        if st.button("Test My Application", type="primary"):
            _go(project_id, "test")
    else:
        st.info("Next: select at least one document to build your assistant.")
    if st.button("Back to My Idea"):
        _go(project_id, "define")


def _render_testing(service: M0Service, project_id: str, *, running: bool = False) -> None:
    project = service.get_my_project(project_id)
    st.subheader("Working Version")
    st.caption("Improvements change this version only. Publish an update when ready.")
    st.write("Run Application" if running else "Test My Application")
    st.write(
        "Use the application you built inside Aqlio."
        if running
        else "Ask a question your users might ask. Check the answer and its sources."
    )
    key = f"answer-{project_id}-{project.current_version_id}-{'run' if running else 'test'}"
    with st.form(f"question-{project_id}-{'run' if running else 'test'}"):
        question = st.text_input("Ask a question")
        ask = st.form_submit_button("Ask" if running else "Test Your Assistant", type="primary")
    if ask:
        st.session_state.pop(key, None)
        st.session_state[key] = (
            service.run_application(project_id, question)
            if running
            else service.ask_question(project_id, question, guided=True)
        )
    answer = st.session_state.get(key)
    if answer:
        _render_answer(answer)
    project = service.get_my_project(project_id)
    if answer and not answer.abstained:
        st.success("Your application is working with this question")
    if project.guided_test_count:
        if st.button("Test Again"):
            st.session_state.pop(key, None)
            _go(project_id, "test")
        if st.button("Improve"):
            _go(project_id, "improve")
        if not running and st.button("Run Application"):
            _go(project_id, "run")
        _render_readiness(service, project_id)
    elif st.button("Improve"):
        _go(project_id, "build")


def _render_answer(answer: Answer) -> None:
    if answer.abstained:
        st.warning(
            "I couldn't find enough information in your documents to answer that confidently."
        )
    else:
        st.text(answer.text)
        st.markdown("**Sources**")
        for citation in answer.citations:
            st.text(f"{citation.document_name} — source passage")


def _render_improve(service: M0Service, project_id: str) -> None:
    st.subheader("Improve Working Version")
    st.info(
        "Changes affect the Working Version. Your Published Version stays unchanged "
        "until you publish a new version."
    )
    st.write(
        "For this first version, you can change answer length or add clearer source documents."
    )
    st.caption(
        "Only the selected answer length is applied. Summaries, comparisons, "
        "and other new behaviors are not built automatically."
    )
    with st.form(f"improve-{project_id}"):
        request = st.text_area("What would you like to improve?", max_chars=2000)
        length = st.selectbox(
            "Answer length",
            ["short", "standard"],
            format_func=lambda value: "Shorter answers" if value == "short" else "Standard answers",
        )
        apply = st.form_submit_button("Apply Answer Length")
    if apply:
        service.improve_application(project_id, request, answer_length=length)
        _go(project_id, "test")
    if st.button("Add Better Documents"):
        _go(project_id, "build")
    pdfs = [
        document
        for document in service.list_documents(project_id)
        if document.media_type == "application/pdf"
    ]
    if pdfs:
        st.caption(
            "Refresh existing PDFs to apply text-reading corrections to the Working Version."
        )
        if st.button("Refresh PDF Documents"):
            for document in pdfs:
                service.prepare_document(project_id, document.id, refresh=True)
            _go(project_id, "test")
    if st.button("Back to Testing"):
        _go(project_id, "test")


def _render_readiness(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    if project.has_blocking_preparation_error:
        st.warning("Resolve document issues in Improve before publishing.")
        return
    if project.status != ProjectStatus.DEPLOYED:
        st.caption("Publish a private snapshot of this Working Version inside Aqlio.")
        if st.button("Publish Application"):
            service.publish_working_application(project_id)
            st.rerun()
    else:
        st.caption("This Working Version is already published.")


def _render_publication(service: M0Service, publication_id: str) -> None:
    service.open_private(publication_id)
    st.subheader("Published Version")
    st.caption(
        "A stable snapshot inside Aqlio. Improve the Working Version, then publish an update. "
        "Existing shared links keep their original Published Version."
    )
    link = service.repository.get_share_link(publication_id)
    shared = link is not None and link.visibility == PublicationVisibility.LINK_ONLY
    st.write("Visibility: Anyone with the link" if shared else "Visibility: Only me")
    token_key = f"share-token-{publication_id}"
    if not shared:
        confirmed = st.checkbox(
            "Allow anyone with the link to ask questions using this version's documents",
            key=f"share-confirm-{publication_id}",
        )
        if st.button("Create Share Link", disabled=not confirmed, key=f"share-{publication_id}"):
            receipt = service.enable_link_sharing(publication_id)
            st.session_state[token_key] = receipt.token
            st.rerun()
    if shared:
        token = st.session_state.get(token_key)
        if token:
            _render_share_controls(token)
        else:
            st.caption(
                "The existing link remains active. Stop sharing before creating a replacement."
            )
        if st.button("Stop Sharing", key=f"revoke-{publication_id}"):
            service.revoke_sharing(publication_id)
            st.session_state.pop(token_key, None)
            st.rerun()


def _render_share_controls(token: str) -> None:
    # Bearer credentials belong in navigation URLs, not visible diagnostic text.
    current = urlsplit(st.context.url or "")
    if current.scheme not in {"http", "https"} or not current.netloc:
        st.info("Open this page through its application address to use sharing controls.")
        return
    url = urlunsplit(
        (current.scheme, current.netloc, current.path, urlencode({"share": token}), "")
    )
    st.link_button("Open Shared Application", url)
    encoded = json.dumps(url).replace("<", "\\u003c")
    components.html(
        """
        <button id="copy" style="padding:8px 14px;background:white;border:1px solid #ccc;
        border-radius:8px;cursor:pointer">Copy Link</button>
        <span id="status" role="status" style="font:14px sans-serif"></span>
        <script>
        const link = """
        + encoded
        + """;
        document.getElementById("copy").onclick = async () => {
          let copied = false;
          try { await navigator.clipboard.writeText(link); copied = true; }
          catch (_) {
            const input = document.createElement("textarea");
            input.value = link;
            input.style.position = "fixed"; input.style.opacity = "0";
            document.body.appendChild(input); input.select();
            try { copied = document.execCommand("copy"); } catch (_) {}
            input.remove();
          }
          document.getElementById("status").textContent = copied ? "Link copied" :
            "Copy unavailable here. Open Shared Application and copy its address.";
        };
        </script>
        """,
        height=48,
    )


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
