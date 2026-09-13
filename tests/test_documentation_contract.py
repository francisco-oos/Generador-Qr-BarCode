import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _start_line(node):
    decorators = getattr(node, "decorator_list", []) or []
    return min([node.lineno] + [d.lineno for d in decorators]) - 1


def test_python_symbols_have_why_comment_or_docstring():
    missing = []
    for path in (ROOT / "app").glob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(lines))

        def walk(nodes):
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    start = _start_line(node)
                    nearby = "\n".join(lines[max(0, start - 3):start])
                    if "# WHY:" not in nearby and not ast.get_docstring(node):
                        missing.append(f"{path.name}:{node.name}@{node.lineno}")
                    walk(node.body)

        walk(tree.body)
    assert not missing, f"Symbols without rationale: {missing}"


def test_named_javascript_functions_have_why_comment():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    lines = js.splitlines()
    missing = []
    for index, line in enumerate(lines):
        match = re.match(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", line)
        if not match:
            continue
        nearby = "\n".join(lines[max(0, index - 3):index])
        if "/** WHY:" not in nearby:
            missing.append(f"{match.group(1)}@{index + 1}")
    assert not missing, f"JS functions without rationale: {missing}"


def test_review_and_maintainer_docs_are_packaged_and_linked():
    required = [
        "docs/CODE_REVIEW_GUIDE.md",
        "docs/MAINTAINER_GUIDE.md",
        "docs/UX_AND_WORKFLOW.md",
        "docs/MANUAL_RAPIDO.md",
        "docs/ARCHITECTURE.md",
    ]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for relative in required:
        assert (ROOT / relative).exists(), relative
        assert relative in readme, f"README does not link {relative}"
