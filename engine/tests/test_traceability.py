"""The traceability matrix covers every requirement and cites real tests."""

import ast
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "data"


def requirement_ids() -> set[str]:
    catalogue = yaml.safe_load((DATA / "requirements.yaml").read_text("utf-8"))
    return {item["id"] for section in catalogue.values() for item in section}


def matrix() -> dict[str, list[str]]:
    return yaml.safe_load((DATA / "traceability.yaml").read_text("utf-8"))


def test_every_requirement_is_verified() -> None:
    assert set(matrix()) == requirement_ids()
    assert all(refs for refs in matrix().values())


def test_engine_references_exist() -> None:
    for refs in matrix().values():
        for ref in refs:
            if not ref.startswith("engine:"):
                continue
            file, test = ref.removeprefix("engine:").split("::")
            tree = ast.parse((ROOT / "engine" / "tests" / file).read_text("utf-8"))
            names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
            assert test in names, ref


def test_ui_shell_and_plugin_references_exist() -> None:
    for refs in matrix().values():
        for ref in refs:
            if ref.startswith("ui:"):
                file, name = ref.removeprefix("ui:").split(" > ", 1)
                source = (ROOT / "desktop" / "src" / "lib" / file).read_text("utf-8")
                assert f'it("{name}"' in source, ref
            elif ref.startswith("shell:"):
                module, name = ref.removeprefix("shell:").split("::")
                source = (ROOT / "desktop" / "src-tauri" / "src" / f"{module}.rs").read_text(
                    "utf-8"
                )
                assert re.search(rf"fn {name}\(\)", source), ref
            elif ref.startswith("plugin:"):
                module, *_, name = ref.removeprefix("plugin:").split("::")
                source = (ROOT / "daw" / "vst3" / "src" / f"{module}.rs").read_text("utf-8")
                assert f"fn {name}()" in source, ref
            else:
                assert ref.startswith(("engine:", "manual: ")), ref
