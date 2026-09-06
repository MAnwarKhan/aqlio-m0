"""Guided idea-to-application participant journey."""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode, urlsplit, urlunsplit

import streamlit as st
import streamlit.components.v1 as components

from app.application import M0Service, OperationsService, build_runtime_foundation
from app.application.eligibility_advisor import PROGRAM_RULES, AdvisorInput, AdvisorResult
from app.application.errors import AqlioError, ShareAccessError
from app.application.journey import next_step, project_status
from app.application.m0_service import Answer
from app.config import Settings, SettingsError
from app.domain import (
    ApplicationSpecification,
    ApplicationType,
    AssetStatus,
    ProjectStatus,
    PublicationVisibility,
)
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
    st.caption("Architecture reference test")
    if st.button("Build Synthetic Eligibility Advisor"):
        project = service.create_advisor_project(
            name="Eligibility & Recommendation Advisor",
            problem="Applicants need a transparent check against synthetic program requirements.",
            users="People testing a fictional university-admission scenario.",
            outcome="A deterministic eligibility result, explanation, gaps, and next actions.",
        )
        service.build_advisor_working_version(project.id)
        st.session_state["project_id"] = project.id
        st.session_state["new_project"] = False
        _go(project.id, "test")
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
        if (
            project.metadata.get("template")
            == ApplicationType.ELIGIBILITY_RECOMMENDATION_ADVISOR.value
        ):
            _render_advisor(service, project_id)
            return
        st.header(project.name)
        st.caption(project_status(project))
        notice = st.session_state.pop(f"notice-{project_id}", None)
        if notice:
            st.warning(notice)
        step = st.session_state.get(f"step-{project_id}", next_step(project))
        if step in {"test", "improve", "run"} and not project.prepared_document_count:
            step = next_step(project)
        if step == "run" and not project.guided_test_count:
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


def _render_advisor(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    specification = service.get_application_specification(project_id)
    st.header(specification.name)
    st.caption("Synthetic reference application · Working Version")
    st.warning("This uses fictional program rules and does not predict real admission outcomes.")
    st.write(specification.description)
    _render_behavioral_evaluation(service, project_id, specification)
    courses = sorted({course for rule in PROGRAM_RULES for course in rule.prerequisite_courses})
    with st.form(f"advisor-test-{project.current_version_id}"):
        gpa = st.number_input("GPA", min_value=0.0, max_value=4.0, step=0.1)
        completed = st.multiselect("Completed prerequisite courses", courses)
        program = st.selectbox("Target program", [rule.program for rule in PROGRAM_RULES])
        tested = st.form_submit_button("Test Advisor", type="primary")
    result_key = f"advisor-result-{project.id}-{project.current_version_id}"
    if tested:
        st.session_state[result_key] = service.test_advisor(
            project.id, AdvisorInput(gpa, tuple(completed), program)
        )
        st.rerun()
    result = st.session_state.get(result_key)
    if isinstance(result, AdvisorResult):
        st.subheader(result.eligibility_status.replace("_", " ").title())
        st.write(result.explanation)
        st.markdown("**Satisfied requirements**")
        for item in result.satisfied_requirements:
            st.write(f"✓ {item}")
        st.markdown("**Unmet requirements**")
        for item in result.unmet_requirements:
            st.write(f"○ {item}")
        st.markdown("**Recommended next actions or alternatives**")
        for item in result.recommended_next_actions:
            st.write(f"- {item}")
        st.caption(result.disclaimer)
        if st.button("Yes, it worked"):
            service.confirm_advisor_test_success(project.id)
            st.rerun()
    project = service.get_my_project(project_id)
    with st.expander("Improve Working Version"):
        with st.form(f"advisor-improve-{project.current_version_id}"):
            request = st.text_area("What would you like to improve?", max_chars=2000)
            title = st.text_input("Application title", value=specification.name)
            style = st.selectbox("Recommendation style", ["direct", "supportive"])
            apply = st.form_submit_button("Apply Improvement")
        if apply:
            service.apply_advisor_improvement(
                project.id, request, title=title, recommendation_style=style
            )
            st.success("A new Working Version was created. Test and evaluate it again.")
            st.rerun()
    if (
        project.guided_test_count
        and specification.evaluation_report
        and st.button("Approve Working Version")
    ):
        service.approve_working_version(project.id)
        st.success("Approved Version created. It is immutable and includes evaluation evidence.")


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
    specification = service.get_application_specification(project_id)
    ui_config = dict(specification.ui_config)
    st.subheader("Working Version")
    st.caption("Improvements change this version only. Publish an update when ready.")
    st.markdown(f"### {specification.name}")
    instructions = specification.description or (
        "Use the application you built inside Aqlio."
        if running
        else "Ask a question your users might ask. Check the answer and its sources."
    )
    st.write(instructions)
    _render_behavioral_evaluation(service, project_id, specification)
    key = f"answer-{project_id}-{project.current_version_id}-{'run' if running else 'test'}"

    def render_question_box() -> None:
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
            st.rerun()

    if ui_config.get("question_position", "top") == "top":
        render_question_box()
    answer = st.session_state.get(key)
    if answer:
        _render_answer(answer, ui_config)
    if ui_config.get("question_position") == "bottom":
        render_question_box()
    project = service.get_my_project(project_id)
    pending = bool(
        answer is not None
        and project.metadata.get("pending_test_correlation_id") == answer.correlation_id
    )
    feedback_key = f"feedback-{project_id}-{project.current_version_id}"
    if answer is not None and pending and not running:
        st.write("Did your application answer this correctly?")
        if st.button("Yes, it worked", disabled=answer.abstained):
            service.confirm_test_success(project_id, answer.correlation_id)
            st.session_state.pop(feedback_key, None)
            st.rerun()
        if st.button("Needs Improvement"):
            st.session_state[feedback_key] = True
            st.rerun()
        if st.session_state.get(feedback_key):
            with st.form(f"test-feedback-{project_id}"):
                feedback = st.text_area("What was wrong with the answer?", max_chars=2000)
                submitted = st.form_submit_button("Continue to Improve", type="primary")
            if submitted:
                service.record_test_feedback(project_id, answer.correlation_id, feedback)
                st.session_state.pop(feedback_key, None)
                _go(project_id, "improve")
    elif answer and not answer.abstained and not running:
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
        _go(project_id, "improve")


def _render_answer(answer: Answer, ui_config: dict[str, str] | None = None) -> None:
    ui_config = ui_config or {}
    if answer.abstained:
        st.warning(
            "I couldn't find enough information in your documents to answer that confidently."
        )
    else:
        layout = ui_config.get("response_layout", "prose")
        if ui_config.get("display_density") == "detailed":
            st.caption("Answer from the Working Version, followed by its authorized sources.")
        if layout == "table":
            st.table({"Answer": [answer.text]})
        elif layout == "list":
            st.markdown(f"- {answer.text}")
        else:
            st.write(answer.text)
        st.markdown("**Sources**")
        if ui_config.get("citation_presentation") == "compact":
            st.caption(", ".join(dict.fromkeys(item.document_name for item in answer.citations)))
        else:
            for citation in answer.citations:
                st.text(f"{citation.document_name} — source passage")


def _render_behavioral_evaluation(
    service: M0Service, project_id: str, specification: ApplicationSpecification
) -> None:
    behavioral = specification.behavioral_specification
    report = specification.evaluation_report
    if behavioral is None:
        return
    st.markdown("**Behavioral evaluation**")
    st.caption(
        "Automated checks support your judgment. They do not decide whether the application "
        "meets your needs."
    )
    statuses = {item.requirement_id: item for item in report.results} if report else {}
    with st.expander("See requirements and acceptance checks"):
        for requirement in behavioral.requirements:
            result = statuses.get(requirement.id)
            label = result.status.value.replace("_", " ").title() if result else "Not Yet Tested"
            st.write(f"{requirement.id} — {label}: {requirement.description}")
            if result:
                st.caption(result.explanation)
    if st.button("Run Behavioral Evaluation"):
        service.evaluate_working_version(project_id)
        st.rerun()
    failures = [item for item in statuses.values() if item.status.value == "FAIL"]
    if failures and st.button("Improve Failed Requirements"):
        service.improve_failed_evaluation(project_id)
        _go(project_id, "improve")


def _render_improve(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    st.subheader("Improve Working Version")
    st.info(
        "Changes affect the Working Version. Your Published Version stays unchanged "
        "until you publish a new version."
    )
    st.write("Describe how answers should improve, then review the change before applying it.")
    proposal_key = f"improvement-proposal-{project_id}-{project.current_version_id}"
    applied_key = f"improvement-applied-{project_id}"
    current_version = service.repository.get_version(project.current_version_id or "")
    config = dict(current_version.assistant_config) if current_version else {}
    default_style = config.get("response_style", "balanced")
    feedback = project.metadata.get("improvement_feedback", "")
    with st.form(f"improve-{project_id}"):
        request = st.text_area("What would you like to improve?", value=feedback, max_chars=2000)
        styles = ["concise", "balanced", "detailed"]
        style = st.selectbox(
            "Response style",
            styles,
            index=styles.index(default_style) if default_style in styles else 1,
            format_func=str.title,
        )
        review = st.form_submit_button("Review Improvement", type="primary")
    if review:
        proposed_change = service.propose_improvement(project_id, request, response_style=style)
        st.session_state[proposal_key] = {
            "request": proposed_change.request,
            "response_style": proposed_change.response_style,
            "summary": proposed_change.summary,
            "supported": proposed_change.supported,
            "participant_message": proposed_change.participant_message,
        }
        st.session_state.pop(applied_key, None)
        st.rerun()
    saved_proposal = st.session_state.get(proposal_key)
    if saved_proposal:
        st.markdown("**Proposed change**")
        st.write(saved_proposal["summary"])
        if not saved_proposal["supported"]:
            st.info(saved_proposal["participant_message"])
        if st.button("Apply Improvement", type="primary", disabled=not saved_proposal["supported"]):
            version = service.apply_improvement(
                project_id,
                saved_proposal["request"],
                response_style=saved_proposal["response_style"],
            )
            st.session_state[applied_key] = version.id
            st.session_state.pop(proposal_key, None)
            st.rerun()
    project = service.get_my_project(project_id)
    if st.session_state.get(applied_key) == project.current_version_id:
        st.success("Improvement applied to the Working Version. Test it again before publishing.")
        if st.button("Test Again", type="primary"):
            st.session_state.pop(applied_key, None)
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
    st.divider()
    _render_ui_improve(service, project_id)


def _render_ui_improve(service: M0Service, project_id: str) -> None:
    specification = service.get_application_specification(project_id)
    config = dict(specification.ui_config)
    proposal_key = f"ui-improvement-proposal-{project_id}-{specification.project_version_id}"
    applied_key = f"ui-improvement-applied-{project_id}"
    st.subheader("Improve Look & Experience")
    st.write("Choose from the supported changes. Review them before updating your Working Version.")
    with st.form(f"ui-improve-{project_id}"):
        request = st.text_area("What would you like to improve about the screen?", max_chars=2000)
        title = st.text_input("Application title", value=specification.name, max_chars=120)
        instructions = st.text_area(
            "Instructions for users",
            value=specification.description or "Ask a question about the documents.",
            max_chars=500,
        )
        question_position = st.selectbox(
            "Question box position",
            ["top", "bottom"],
            index=0 if config.get("question_position", "top") == "top" else 1,
            format_func=str.title,
        )
        layouts = ["prose", "list", "table"]
        current_layout = config.get("response_layout", "prose")
        response_layout = st.selectbox(
            "Answer layout",
            layouts,
            index=layouts.index(current_layout) if current_layout in layouts else 0,
            format_func=str.title,
        )
        citation_options = ["expanded", "compact"]
        current_citations = config.get("citation_presentation", "expanded")
        citation_presentation = st.selectbox(
            "Source display",
            citation_options,
            index=(
                citation_options.index(current_citations)
                if current_citations in citation_options
                else 0
            ),
            format_func=str.title,
        )
        densities = ["concise", "balanced", "detailed"]
        current_density = config.get("display_density", "balanced")
        display_density = st.selectbox(
            "Display detail",
            densities,
            index=densities.index(current_density) if current_density in densities else 1,
            format_func=str.title,
        )
        review = st.form_submit_button("Review Look & Experience", type="primary")
    if review:
        proposal = service.propose_ui_improvement(
            project_id,
            request,
            title=title,
            instructions=instructions,
            question_position=question_position,
            response_layout=response_layout,
            citation_presentation=citation_presentation,
            display_density=display_density,
        )
        st.session_state[proposal_key] = {
            "request": proposal.request,
            "ui_config": proposal.ui_config,
            "summary": proposal.summary,
            "supported": proposal.supported,
            "participant_message": proposal.participant_message,
        }
        st.rerun()
    saved = st.session_state.get(proposal_key)
    if saved:
        st.markdown("**Proposed look and experience**")
        st.write(saved["summary"])
        if not saved["supported"]:
            st.info(saved["participant_message"])
        if st.button(
            "Apply Look & Experience",
            type="primary",
            disabled=not saved["supported"],
        ):
            version = service.apply_ui_improvement(
                project_id,
                saved["request"],
                **saved["ui_config"],
            )
            st.session_state[applied_key] = version.id
            st.session_state.pop(proposal_key, None)
            st.rerun()
    project = service.get_my_project(project_id)
    if st.session_state.get(applied_key) == project.current_version_id:
        st.success("Look and experience updated. See it now, then test the Working Version again.")
        if st.button("See and Test Updated Application", type="primary"):
            st.session_state.pop(applied_key, None)
            _go(project_id, "test")


def _render_readiness(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    if project.has_blocking_preparation_error:
        st.warning("Resolve document issues in Improve before publishing.")
        return
    _render_approval(service, project_id)
    if project.status != ProjectStatus.DEPLOYED:
        st.caption("Publish a private snapshot of this Working Version inside Aqlio.")
        if st.button("Publish Application"):
            service.publish_working_application(project_id)
            st.rerun()
    else:
        st.caption("This Working Version is already published.")


def _render_approval(service: M0Service, project_id: str) -> None:
    project = service.get_my_project(project_id)
    specification = service.get_application_specification(project_id)
    approved = service.latest_approved_version(project_id)
    current_is_approved = bool(
        approved and approved.specification.project_version_id == specification.project_version_id
    )
    st.subheader("Approve Working Version")
    st.write(
        "Approval means: This version works the way I want and can now be used as the basis "
        "for publishing or generating application source code."
    )
    with st.expander("Review this version before approval"):
        st.write(f"Application: {specification.name}")
        st.write(f"Definition: {project.metadata.get('idea', project.description or 'Not added')}")
        st.write("Supported functionality: grounded answers from authorized documents with sources")
        st.write(
            "Functional improvement: "
            + specification.behavior_config.get("improvement_request", "No applied change")
        )
        st.write(
            "Look and experience: "
            + ", ".join(
                f"{key.replace('_', ' ')}: {value}"
                for key, value in specification.ui_config.items()
                if key != "improvement_request"
            )
            if specification.ui_config
            else "Look and experience: Default"
        )
        documents = service.list_documents(project_id)
        st.write(
            "Sources: " + (", ".join(item.original_name for item in documents) or "No documents")
        )
        st.write(f"Current version: {specification.project_version_id}")
        report = specification.evaluation_report
        if report:
            passed = sum(item.status.value == "PASS" for item in report.results)
            failed = sum(item.status.value == "FAIL" for item in report.results)
            untested = len(report.results) - passed - failed
            st.write(
                f"Behavioral evaluation: {passed} passed, {failed} failed, "
                f"{untested} not yet tested"
            )
        else:
            st.write("Behavioral evaluation: Not yet tested")
    behavioral = specification.behavioral_specification
    required_ids = (
        {
            criterion_id
            for requirement in behavioral.requirements
            if requirement.required
            for criterion_id in requirement.acceptance_criterion_ids
        }
        if behavioral
        else set()
    )
    result_statuses = (
        {
            result.acceptance_criterion_id: result.status.value
            for result in specification.evaluation_report.results
        }
        if specification.evaluation_report
        else {}
    )
    evaluation_ready = bool(required_ids) and all(
        result_statuses.get(criterion_id) == "PASS" for criterion_id in required_ids
    )
    if not current_is_approved or approved is None:
        if st.button("Approve This Version", type="primary", disabled=not evaluation_ready):
            service.approve_working_version(project_id)
            st.rerun()
        return
    st.success(f"Approved Version: {approved.id}")
    st.write("Choose what you want to do next.")
    if st.button("Run in Aqlio"):
        _go(project_id, "run")
    if st.button("Publish in Aqlio"):
        service.publish_working_application(project_id)
        st.rerun()
    export_key = f"application-export-{approved.id}"
    if st.button("Get My Application Code"):
        package = service.generate_application_export(project_id)
        st.session_state[export_key] = package.id
        st.rerun()
    package_id = st.session_state.get(export_key)
    if package_id:
        download = service.download_application_export(package_id)
        st.success("Your application code is ready for independent deployment.")
        st.download_button(
            "Download Application Code",
            data=download.content,
            file_name=download.package.filename,
            mime="application/zip",
        )
        st.caption(
            "The package excludes private source documents. Add production documents after setup."
        )
    st.caption("Approval and code export do not publish or commercially deploy this application.")


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
