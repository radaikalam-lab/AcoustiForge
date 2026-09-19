"""Dependency and scope isolation verification tests.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6C, 6D, 6F)
"""

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "acoustiforge"

FORBIDDEN_MODULES = {
    "cmsis",
    "cmsis_dsp",
    "cmsis_stream",
    "arm_dsp",
    "scipy",
    "pydantic",
    "sounddevice",
    "pyaudio",
    "serial",
    "bluetooth",
    "socket",
}

# stdlib modules permitted only in platform-specific binding modules
STDLIB_ALLOWED_MODULES = {
    "ctypes": {"alsa.py"},
}

OUT_OF_SCOPE_KEYWORDS = {
    "compressor",
    "limiter",
    "psychoacoustic",
    "bass_boost",
    "spatializer",
    "graphic_eq",
}


def test_no_forbidden_dependencies_imported() -> None:
    """Scan all Python source files in src/ to verify 100% dependency isolation."""
    python_files = list(SRC_ROOT.rglob("*.py"))
    assert len(python_files) > 0, "No source files found in src/acoustiforge"

    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0].lower()
                    _assert_not_forbidden(root_mod, alias.name, py_file)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0].lower()
                    _assert_not_forbidden(root_mod, node.module, py_file)


def _assert_not_forbidden(root_mod: str, full_name: str, py_file: Path) -> None:
    if root_mod in FORBIDDEN_MODULES:
        raise AssertionError(
            f"Forbidden import '{full_name}' detected in {py_file.name}"
        )
    allowed_files = STDLIB_ALLOWED_MODULES.get(root_mod)
    if allowed_files is not None and py_file.name not in allowed_files:
        raise AssertionError(
            f"Module '{root_mod}' is only allowed in {sorted(allowed_files)}, "
            f"but found in {py_file.name}"
        )


def test_scope_containment_no_out_of_scope_features() -> None:
    """Verify that zero out-of-scope functionality is present in src/acoustiforge."""
    python_files = list(SRC_ROOT.rglob("*.py"))

    for py_file in python_files:
        content = py_file.read_text(encoding="utf-8").lower()
        for kw in OUT_OF_SCOPE_KEYWORDS:
            assert kw not in content, (
                f"Out-of-scope keyword '{kw}' found in {py_file.name}"
            )
