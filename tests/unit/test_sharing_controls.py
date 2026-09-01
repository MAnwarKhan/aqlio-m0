from types import SimpleNamespace

from app.ui import home


def test_share_controls_use_full_url_without_rendering_raw_token(monkeypatch):
    links = []
    html = []
    monkeypatch.setattr(
        home.st,
        "context",
        SimpleNamespace(url="https://example.streamlit.app/?operations=1&share=old"),
    )
    monkeypatch.setattr(home.st, "link_button", lambda label, url: links.append((label, url)))
    monkeypatch.setattr(home.components, "html", lambda content, **_: html.append(content))
    home._render_share_controls("sample-token")
    assert links == [
        ("Open Shared Application", "https://example.streamlit.app/?share=sample-token")
    ]
    assert "Copy Link</button>" in html[0]
    assert "operations=1" not in html[0]
    assert "navigator.clipboard.writeText" in html[0]
    assert 'role="status"' in html[0]
