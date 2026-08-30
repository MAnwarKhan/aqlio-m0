from io import BytesIO

from docx import Document
from streamlit.testing.v1 import AppTest

from app.ui import home
from tests.helpers import build_service


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_idea_definition_autosave_and_multiple_project_navigation(monkeypatch):
    service = build_service()
    monkeypatch.setattr(home, "_service", lambda: service)
    app = AppTest.from_file("streamlit_app.py").run()
    assert any("may disappear" in item.value for item in app.warning)
    assert not any("saved automatically" in item.value for item in app.caption)
    app.text_area[0].input("Help people understand their handbook")
    button(app, "Continue").click().run()
    assert not app.exception
    project_id = service.list_my_projects()[0].id
    assert not any(item.label == "Deploy in Aqlio" for item in app.button)
    app.text_area[1].input("Finding policy answers takes too long").run()
    assert (
        service.get_my_project(project_id).metadata["problem"]
        == "Finding policy answers takes too long"
    )
    button(app, "My Projects").click().run()
    button(app, "Continue Building").click().run()
    assert app.text_area[1].value == "Finding policy answers takes too long"
    button(app, "+ Start New Project").click().run()
    app.text_area[0].input("A second idea")
    button(app, "Continue").click().run()
    assert len(service.list_my_projects()) == 2
    assert not app.exception


def test_docx_selection_prepares_once_and_unlocks_test_without_add_button(monkeypatch):
    service = build_service()
    project = service.create_project("Document demo")
    monkeypatch.setattr(home, "_service", lambda: service)
    document = Document()
    document.add_paragraph("Annual leave is available after approval by your manager.")
    upload = BytesIO()
    document.save(upload)
    upload.name = "handbook.docx"
    # AppTest does not expose file selection; substitute only the upload widget boundary.
    monkeypatch.setattr(home.st, "file_uploader", lambda *args, **kwargs: [upload])
    app = AppTest.from_file("streamlit_app.py")
    app.session_state["project_id"] = project.id
    app.session_state[f"step-{project.id}"] = "build"
    app.run()
    assert not app.exception
    prepared = service.get_my_project(project.id)
    assert prepared.valid_document_count == prepared.prepared_document_count == 1
    assert any("Documents added ✓" in item.value for item in app.success)
    assert not any(item.label == "Add Documents" for item in app.button)
    version_id = prepared.current_version_id
    app.run()
    assert service.get_my_project(project.id).current_version_id == version_id
    button(app, "Test My Application").click().run()
    app.text_input[0].input("When is annual leave available?")
    button(app, "Test Your Assistant").click().run()
    assert not app.exception
    assert service.get_my_project(project.id).guided_test_count == 1
    button(app, "Run My Application").click().run()
    assert not any(item.label == "Deploy in Aqlio" for item in app.button)
    app.text_input[0].input("When is annual leave available?")
    button(app, "Ask").click().run()
    button(app, "Deploy in Aqlio").click().run()
    assert service.get_my_project(project.id).metadata["publication_id"]
    assert not app.exception


def test_upload_failure_visible_and_not_retried_on_unrelated_rerun(monkeypatch):
    service = build_service()
    project = service.create_project("Recovery")
    monkeypatch.setattr(home, "_service", lambda: service)
    upload = BytesIO(b"not a docx")
    upload.name = "bad.docx"
    monkeypatch.setattr(home.st, "file_uploader", lambda *args, **kwargs: [upload])
    app = AppTest.from_file("streamlit_app.py")
    app.session_state["project_id"] = project.id
    app.session_state[f"step-{project.id}"] = "build"
    app.run()
    assert app.error and not app.exception
    events = len(service.repository.list_lifecycle_events())
    app.run()
    assert len(service.repository.list_lifecycle_events()) == events
    assert any(item.label == "Try Again" for item in app.button)
