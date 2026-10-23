"""의존 방향 정책(AGENTS.md §10-2)을 import AST로 검사한다.

api -> world -> minds/agents -> memory·llm 순으로, 아래 층은 위 층을 import하지 않는다.
"""

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# 층 -> 그 층이 import하면 안 되는 최상위 패키지
FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "llm": frozenset({"agents", "minds", "world", "api"}),
    "agents": frozenset({"minds", "world", "api"}),
    "minds": frozenset({"api"}),
    "world": frozenset({"api"}),
}


def _imported_top_levels(path: Path, layer: str) -> set[str]:
    """파일이 import하는 최상위 패키지 이름들. 상대 import는 src 기준으로 풀어서 본다."""
    package_parts = path.relative_to(SRC_ROOT).parts[:-1]
    tops: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            tops.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    tops.add(node.module.split(".")[0])
                continue
            base = package_parts[: len(package_parts) - (node.level - 1)]
            resolved = [*base, *(node.module.split(".") if node.module else [])]
            tops.add(resolved[0] if resolved else layer)
        elif isinstance(node, ast.Call):
            tops.update(_dynamic_import_targets(node))
    return tops


def _dynamic_import_targets(node: ast.Call) -> set[str]:
    """`importlib.import_module("x.y")`, `import_module("x")`, `__import__("x")`의 문자열 리터럴."""
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name not in {"import_module", "__import__"} or not node.args:
        return set()
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return {first.value.split(".")[0]}
    return set()


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_layer_does_not_import_upper_layers(layer: str) -> None:
    forbidden = FORBIDDEN_IMPORTS[layer]
    violations: list[str] = []
    for path in sorted((SRC_ROOT / layer).rglob("*.py")):
        bad = _imported_top_levels(path, layer) & forbidden
        if bad:
            violations.append(f"{path.relative_to(SRC_ROOT)} -> {sorted(bad)}")
    assert not violations, "위 층 import 금지 위반:\n" + "\n".join(violations)


def test_dynamic_string_imports_are_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "bad.py"
    source.write_text(
        "import importlib\n"
        'importlib.import_module("agents.planning")\n'
        '__import__("minds")\n'
        "from importlib import import_module\n"
        'import_module("api.app")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(f"{__name__}.SRC_ROOT", tmp_path)

    assert {"agents", "minds", "api"} <= _imported_top_levels(source, "llm")
