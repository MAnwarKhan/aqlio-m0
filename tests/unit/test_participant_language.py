import ast
from pathlib import Path


def test_participant_ui_does_not_contain_prohibited_infrastructure_copy() -> None:
    ui_root = Path(__file__).parents[2] / "app" / "ui"
    prohibited = {
        "api key",
        "database",
        "embedding",
        "environment variable",
        "github",
        "object storage",
        "oidc",
        "postgresql",
        "provider",
        "railway",
        "repository",
        "vector database",
    }
    visible_strings: list[str] = []
    for path in ui_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "st":
                continue
            visible_strings.extend(
                arg.value.lower()
                for arg in node.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )

    assert all(term not in text for term in prohibited for text in visible_strings)
